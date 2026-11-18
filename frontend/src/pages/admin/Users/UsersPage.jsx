import { useEffect, useMemo, useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import Select from '../../../components/ui/Select'
import UserTable from '../../../components/features/admin/users/UserTable'
import UserDetailPanel from '../../../components/features/admin/users/UserDetailPanel'
import UserEditModal from '../../../components/features/admin/users/UserEditModal'
import UserStatusModal from '../../../components/features/admin/users/UserStatusModal'
import UserCreateModal from '../../../components/features/admin/users/UserCreateModal'
import {
  initialAdminUsers,
  userRoleLabels,
} from '../../../components/features/admin/users/usersMockData'
import { usersApi } from '../../../api'
import { USE_MOCK } from '../../../api/config'
import { useAdminData } from '../../../features/admin'

import './UsersPage.css'

const roleFilterOptions = [
  { value: 'ALL', label: 'Tất cả vai trò' },
  ...Object.entries(userRoleLabels).map(([value, label]) => ({
    value,
    label,
  })),
]

const statusFilterOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'ACTIVE', label: 'Đang hoạt động' },
  { value: 'LOCKED', label: 'Đã khóa' },
]

function SearchIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function AddIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

function getToday() {
  return new Intl.DateTimeFormat('vi-VN').format(new Date())
}

function UsersPage() {
  const { users: realUsers, loading, error } = useAdminData()
  const [users, setUsers] = useState(() => (USE_MOCK ? initialAdminUsers : []))

  // Sync real users from authoritative APIs (Management Service GET /api/users)
  useEffect(() => {
    if (realUsers && realUsers.length > 0) {
      setUsers(realUsers)
    }
  }, [realUsers])

  const [searchTerm, setSearchTerm] = useState('')
  const [roleFilter, setRoleFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')


  const [selectedUserId, setSelectedUserId] =
    useState(null)

  const [editingUserId, setEditingUserId] =
    useState(null)

  const [statusUserId, setStatusUserId] =
    useState(null)

  const [createOpen, setCreateOpen] = useState(false)
  const [createError, setCreateError] = useState('')

  const selectedUser = users.find(
    (user) => user.id === selectedUserId,
  )

  const editingUser = users.find(
    (user) => user.id === editingUserId,
  )

  const statusUser = users.find(
    (user) => user.id === statusUserId,
  )

  const filteredUsers = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase()

    return users.filter((user) => {
      const matchesSearch =
        !keyword ||
        user.name.toLowerCase().includes(keyword) ||
        user.email.toLowerCase().includes(keyword) ||
        user.phone.toLowerCase().includes(keyword) ||
        user.id.toLowerCase().includes(keyword)

      const matchesRole =
        roleFilter === 'ALL' || user.role === roleFilter

      const matchesStatus =
        statusFilter === 'ALL' ||
        user.status === statusFilter

      return matchesSearch && matchesRole && matchesStatus
    })
  }, [users, searchTerm, roleFilter, statusFilter])

  const activeUsers = users.filter(
    (user) => user.status === 'ACTIVE',
  ).length

  const technicianUsers = users.filter(
    (user) => user.role === 'TECHNICIAN',
  ).length

  const ownerUsers = users.filter(
    (user) => user.role === 'FARM_OWNER',
  ).length

  async function handleCreateUser(data) {
    if (USE_MOCK) {
      const emailExists = users.some(
        (user) =>
          user.email.toLowerCase() ===
          data.email.toLowerCase(),
      )

      if (emailExists) {
        setCreateError(
          'Email này đã được sử dụng bởi một tài khoản khác.',
        )
        return
      }

      const highestId = users.reduce((highest, user) => {
        const number = Number(user.id.replace('USR-', ''))

        return Number.isNaN(number)
          ? highest
          : Math.max(highest, number)
      }, 0)

      const newUser = {
        id: `USR-${String(highestId + 1).padStart(3, '0')}`,
        ...data,
        status: 'ACTIVE',
        joinedAt: getToday(),
        lastActive: 'Chưa đăng nhập',
      }

      setUsers((current) => [...current, newUser])

      setCreateOpen(false)
      setCreateError('')
      setSelectedUserId(newUser.id)
      return
    }

    // Real API Gateway Call (FR-UAM-05)
    try {
      const created = await usersApi.createUser({
        email: data.email,
        password: data.password || 'swiftlet_demo_pass_2026',
        full_name: data.name,
        phone: data.phone || null,
        role: data.role || 'FARM_OWNER',
        status: 'ACTIVE',
      })

      const mapped = {
        id: created.id,
        name: created.full_name,
        email: created.email,
        phone: created.phone || '--',
        role: (created.roles && created.roles[0]) || data.role,
        roles: created.roles || [data.role],
        status: created.status,
        joinedAt: getToday(),
        lastActive: 'Chưa đăng nhập',
      }

      setUsers((current) => [mapped, ...current])
      setCreateOpen(false)
      setCreateError('')
      setSelectedUserId(mapped.id)
    } catch (err) {
      setCreateError(err.message || 'Không thể tạo người dùng.')
    }
  }

  async function handleSaveUser(updatedUser) {
    if (USE_MOCK) {
      const duplicateEmail = users.some(
        (user) =>
          user.id !== updatedUser.id &&
          user.email.toLowerCase() ===
            updatedUser.email.toLowerCase(),
      )

      if (duplicateEmail) {
        return
      }

      setUsers((current) =>
        current.map((user) =>
          user.id === updatedUser.id ? updatedUser : user,
        ),
      )

      setEditingUserId(null)
      setSelectedUserId(updatedUser.id)
      return
    }

    // Real API Gateway Call (FR-UAM-05)
    try {
      await usersApi.updateUser(updatedUser.id, {
        full_name: updatedUser.name,
        phone: updatedUser.phone,
        role: updatedUser.role,
      })
      setUsers((current) =>
        current.map((user) =>
          user.id === updatedUser.id ? updatedUser : user,
        ),
      )
      setEditingUserId(null)
      setSelectedUserId(updatedUser.id)
    } catch (err) {
      console.error('Update user failed:', err)
    }
  }

  async function handleConfirmStatus(user) {
    const nextStatus = user.status === 'ACTIVE' ? 'LOCKED' : 'ACTIVE'

    if (USE_MOCK) {
      setUsers((current) =>
        current.map((item) =>
          item.id === user.id
            ? {
                ...item,
                status: nextStatus,
              }
            : item,
        ),
      )
      setStatusUserId(null)
      return
    }

    // Real API Gateway Call (FR-UAM-05)
    try {
      await usersApi.updateUserStatus(user.id, nextStatus)
      setUsers((current) =>
        current.map((item) =>
          item.id === user.id
            ? {
                ...item,
                status: nextStatus,
                lastActive: nextStatus === 'ACTIVE' ? 'Đang hoạt động' : 'Đã khóa',
              }
            : item,
        ),
      )
      setStatusUserId(null)
    } catch (err) {
      console.error('Update status failed:', err)
    }
  }

  return (
    <AppLayout>
      <div className="admin-users-page">
        <section className="admin-users-hero">
          <div>
            <span className="admin-users-eyebrow">
              USER &amp; ACCESS MANAGEMENT
            </span>

            <h1>Quản lý người dùng</h1>

            <p>
              Quản lý tài khoản và quyền truy cập của Farm Owner,
              Technician và Administrator.
            </p>
          </div>

          <button
            type="button"
            className="admin-users-create"
            onClick={() => {
              setCreateError('')
              setCreateOpen(true)
            }}
          >
            <AddIcon />
            <span>Thêm người dùng</span>
          </button>
        </section>

        <section className="admin-users-stats">
          <article>
            <span>Tổng tài khoản</span>
            <strong>{users.length}</strong>
            <small>Toàn hệ thống</small>
          </article>

          <article>
            <span>Đang hoạt động</span>
            <strong>{activeUsers}</strong>
            <small>Tài khoản khả dụng</small>
          </article>

          <article>
            <span>Farm Owner</span>
            <strong>{ownerUsers}</strong>
            <small>Chủ nhà yến</small>
          </article>

          <article>
            <span>Technician</span>
            <strong>{technicianUsers}</strong>
            <small>Kỹ thuật viên</small>
          </article>
        </section>

        <section className="admin-users-content">
          <div className="admin-users-content__heading">
            <div>
              <span>ACCESS DIRECTORY</span>
              <h2>Danh sách tài khoản</h2>
              <p>
                {filteredUsers.length} / {users.length} tài khoản
              </p>
            </div>
          </div>

          <div className="admin-users-toolbar">
            <label className="admin-users-search">
              <SearchIcon />

              <input
                type="search"
                value={searchTerm}
                onChange={(event) =>
                  setSearchTerm(event.target.value)
                }
                placeholder="Tìm theo tên, email, số điện thoại..."
              />
            </label>

            <div className="admin-users-filters">
              <div className="admin-users-filter-item">
                <span>Vai trò</span>

                <Select
                  value={roleFilter}
                  options={roleFilterOptions}
                  onChange={setRoleFilter}
                />
              </div>

              <div className="admin-users-filter-item">
                <span>Trạng thái</span>

                <Select
                  value={statusFilter}
                  options={statusFilterOptions}
                  onChange={setStatusFilter}
                />
              </div>
            </div>
          </div>

          <UserTable
            users={filteredUsers}
            onViewUser={(user) =>
              setSelectedUserId(user.id)
            }
          />
        </section>

        <UserDetailPanel
          user={selectedUser}
          onClose={() => setSelectedUserId(null)}
          onEdit={(user) =>
            setEditingUserId(user.id)
          }
          onChangeStatus={(user) =>
            setStatusUserId(user.id)
          }
        />

        <UserEditModal
          user={editingUser}
          onClose={() => setEditingUserId(null)}
          onSave={handleSaveUser}
        />

        <UserStatusModal
          user={statusUser}
          onClose={() => setStatusUserId(null)}
          onConfirm={handleConfirmStatus}
        />

        <UserCreateModal
          open={createOpen}
          onClose={() => {
            setCreateOpen(false)
            setCreateError('')
          }}
          onCreate={handleCreateUser}
        />

        {createError && createOpen && (
          <div className="admin-user-create-error">
            {createError}
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default UsersPage
