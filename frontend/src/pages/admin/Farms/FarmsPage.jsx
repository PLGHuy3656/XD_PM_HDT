import { useMemo, useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import Select from '../../../components/ui/Select'
import FarmTable from '../../../components/features/admin/farms/FarmTable'
import FarmDetailPanel from '../../../components/features/admin/farms/FarmDetailPanel'
import FarmEditModal from '../../../components/features/admin/farms/FarmEditModal'
import TechnicianAssignmentModal from '../../../components/features/admin/farms/TechnicianAssignmentModal'

import {
  getFarmDeviceCount,
} from '../../../components/features/admin/farms/adminFarmsMockData'

import { useAdminData } from '../../../features/admin'

import './FarmsPage.css'

const healthFilterOptions = [
  { value: 'ALL', label: 'Tất cả tình trạng' },
  { value: 'GOOD', label: 'Ổn định' },
  { value: 'ATTENTION', label: 'Cần theo dõi' },
]

const approvalFilterOptions = [
  { value: 'ALL', label: 'Tất cả phê duyệt' },
  { value: 'PENDING', label: 'Chờ duyệt' },
  { value: 'APPROVED', label: 'Đã duyệt' },
  { value: 'REJECTED', label: 'Từ chối' },
]

function FarmsPage() {
  const {
    farms,
    technicians,
    users,
    assignTechnician: apiAssignTechnician,
    unassignTechnician: apiUnassignTechnician,
    createFarm: apiCreateFarm,
    updateFarm: apiUpdateFarm,
    deleteFarm: apiDeleteFarm,
    approveFarm: apiApproveFarm,
    rejectFarm: apiRejectFarm,
    loading,
    error,
  } = useAdminData()

  const [searchTerm, setSearchTerm] = useState('')
  const [healthFilter, setHealthFilter] = useState('ALL')
  const [approvalFilter, setApprovalFilter] = useState('ALL')
  const [selectedFarmId, setSelectedFarmId] = useState(null)
  const [editingFarmId, setEditingFarmId] = useState(null)
  const [assignmentFarmId, setAssignmentFarmId] = useState(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({ farm_code: '', farm_name: '', address: '', owner_id: '' })
  const [actionError, setActionError] = useState('')
  const [actionNotice, setActionNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const owners = useMemo(
    () => (users || []).filter((u) => u.role === 'FARM_OWNER' && u.status === 'ACTIVE'),
    [users],
  )

  const selectedFarm = farms.find(
    (farm) => farm.id === selectedFarmId,
  )

  const editingFarm = farms.find(
    (farm) => farm.id === editingFarmId,
  )

  const assignmentFarm = farms.find(
    (farm) => farm.id === assignmentFarmId,
  )

  const filteredFarms = useMemo(() => {
    const keyword =
      searchTerm.trim().toLowerCase()

    return farms.filter((farm) => {
      const technicianName =
        farm.technician?.name?.toLowerCase() || ''

      const matchesSearch =
        !keyword ||
        farm.name.toLowerCase().includes(keyword) ||
        farm.code.toLowerCase().includes(keyword) ||
        farm.address
          .toLowerCase()
          .includes(keyword) ||
        (farm.owner?.name && farm.owner.name.toLowerCase().includes(keyword)) ||
        technicianName.includes(keyword)

      const matchesHealth =
        healthFilter === 'ALL' ||
        farm.health === healthFilter

      const matchesApproval =
        approvalFilter === 'ALL' ||
        (farm.approvalStatus || 'APPROVED') === approvalFilter

      return matchesSearch && matchesHealth && matchesApproval
    })
  }, [farms, searchTerm, healthFilter, approvalFilter])

  const totalZones = farms.reduce(
    (total, farm) =>
      total + (farm.zoneCount || farm.zones?.length || 0),
    0,
  )

  const totalDevices = farms.reduce(
    (total, farm) =>
      total + (farm.deviceCount !== undefined ? farm.deviceCount : (farm.zones ? getFarmDeviceCount(farm) : 0)),
    0,
  )

  const attentionFarms = farms.filter(
    (farm) => farm.health === 'ATTENTION',
  ).length

  async function handleSaveFarm(updatedFarm) {
    setActionError('')
    setSubmitting(true)
    const res = await apiUpdateFarm(updatedFarm.id, {
      farm_name: updatedFarm.name,
      address: updatedFarm.address,
      status: updatedFarm.status,
    })
    setSubmitting(false)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể cập nhật nhà yến.')
      return
    }
    setEditingFarmId(null)
    setSelectedFarmId(updatedFarm.id)
  }

  async function handleCreateFarm(event) {
    event.preventDefault()
    setActionError('')
    setActionNotice('')
    if (!createForm.farm_name.trim()) {
      setActionError('Vui lòng nhập tên nhà yến.')
      return
    }
    setSubmitting(true)
    const payload = {
      farm_name: createForm.farm_name.trim(),
      address: createForm.address.trim() || null,
      status: 'ACTIVE',
    }
    if (createForm.owner_id.trim()) {
      payload.owner_id = createForm.owner_id.trim()
    }
    const res = await apiCreateFarm(payload)
    setSubmitting(false)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể tạo nhà yến.')
      return
    }
    if (res?.data?.farm_code) {
      setActionNotice(`Đã tạo nhà yến "${res.data.farm_name}" — Mã nhà yến: ${res.data.farm_code}`)
    }
    setCreateForm({ farm_code: '', farm_name: '', address: '', owner_id: '' })
    setCreateOpen(false)
  }

  async function handleDeleteFarm(farm) {
    if (!window.confirm(`Xác nhận xóa nhà yến "${farm.name}" (${farm.code})?`)) return
    setActionError('')
    const res = await apiDeleteFarm(farm.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể xóa nhà yến.')
      return
    }
    setSelectedFarmId(null)
  }

  async function handleAssignTechnician(farm, technician) {
    setActionError('')
    const res = await apiAssignTechnician(farm.id, technician.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể phân công kỹ thuật viên.')
      return
    }
    setAssignmentFarmId(null)
    setSelectedFarmId(farm.id)
  }

  async function handleUnassignTechnician(farm) {
    if (!farm.technician?.id) return
    if (!window.confirm(`Hủy phân công kỹ thuật viên "${farm.technician.name}" khỏi "${farm.name}"?`)) return
    setActionError('')
    const res = await apiUnassignTechnician(farm.id, farm.technician.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể hủy phân công kỹ thuật viên.')
    }
  }

  async function handleApproveFarm(farm) {
    if (!window.confirm(`Xác nhận phê duyệt nhà yến "${farm.name}" (${farm.code})?`)) return
    setActionError('')
    setActionNotice('')
    const res = await apiApproveFarm(farm.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể phê duyệt nhà yến.')
      return
    }
    setActionNotice(`Đã phê duyệt nhà yến "${farm.name}".`)
  }

  async function handleRejectFarm(farm, reason) {
    setActionError('')
    setActionNotice('')
    const res = await apiRejectFarm(farm.id, reason)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể từ chối nhà yến.')
      return false
    }
    setActionNotice(`Đã từ chối nhà yến "${farm.name}".`)
    return true
  }


  return (
    <AppLayout>
      <div className="admin-farms-page">
        <section className="admin-farms-hero">
          <div>
            <span>FARM ADMINISTRATION</span>

            <h1>Quản lý nhà yến</h1>

            <p>
              Theo dõi Farm Owner, Technician phụ trách,
              khu vực và thiết bị của từng nhà yến.
            </p>
          </div>
        </section>

        <section className="admin-farms-stats">
          <article>
            <span>Tổng nhà yến</span>
            <strong>{farms.length}</strong>
            <small>Toàn hệ thống</small>
          </article>

          <article>
            <span>Tổng khu vực</span>
            <strong>{totalZones}</strong>
            <small>Đang được quản lý</small>
          </article>

          <article>
            <span>Tổng thiết bị</span>
            <strong>{totalDevices}</strong>
            <small>Đã gán vào nhà yến</small>
          </article>

          <article>
            <span>Cần theo dõi</span>
            <strong>{attentionFarms}</strong>
            <small>Nhà yến cần chú ý</small>
          </article>
        </section>

        <section className="admin-farms-content">
          {(error || actionError) && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fef2f2', color: '#b91c1c' }}>
              {actionError || error}
            </div>
          )}
          {actionNotice && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}>
              {actionNotice}
            </div>
          )}
          <div
            className="admin-farms-content__heading"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}
          >
            <div>
              <span>FARM DIRECTORY</span>
              <h2>Danh sách nhà yến</h2>
              <p>
                {loading ? 'Đang tải...' : `${filteredFarms.length} / ${farms.length} nhà yến`}
              </p>
            </div>
            <button
              type="button"
              className="admin-farm-edit-button"
              style={{ width: 'auto', minHeight: '40px', padding: '0 18px', marginTop: 0 }}
              onClick={() => {
                setActionError('')
                setCreateOpen(true)
              }}
            >
              + Thêm nhà yến
            </button>
          </div>

          <div className="admin-farms-toolbar">
            <input
              type="search"
              value={searchTerm}
              onChange={(event) =>
                setSearchTerm(event.target.value)
              }
              placeholder="Tìm nhà yến, Owner, Technician..."
            />

            <div className="admin-farms-toolbar__select">
              <Select
                value={healthFilter}
                options={healthFilterOptions}
                onChange={setHealthFilter}
              />
            </div>

            <div className="admin-farms-toolbar__select">
              <Select
                value={approvalFilter}
                options={approvalFilterOptions}
                onChange={setApprovalFilter}
              />
            </div>
          </div>

          <FarmTable
            farms={filteredFarms}
            onViewFarm={(farm) =>
              setSelectedFarmId(farm.id)
            }
          />
        </section>

        <FarmDetailPanel
          farm={selectedFarm}
          onClose={() =>
            setSelectedFarmId(null)
          }
          onEdit={(farm) =>
            setEditingFarmId(farm.id)
          }
          onDelete={handleDeleteFarm}
          onApprove={handleApproveFarm}
          onReject={handleRejectFarm}
          onAssignTechnician={(farm) =>
            setAssignmentFarmId(farm.id)
          }
          onUnassignTechnician={handleUnassignTechnician}
        />

        {createOpen && (
          <div className="admin-farm-modal-backdrop" onMouseDown={() => setCreateOpen(false)}>
            <form
              className="admin-farm-modal admin-farm-form"
              onSubmit={handleCreateFarm}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <h3>Thêm nhà yến mới</h3>
              <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                Mã nhà yến (Farm Code) sẽ được hệ thống tự động cấp duy nhất sau khi tạo.
              </p>
              <label>
                Tên nhà yến *
                <input
                  value={createForm.farm_name}
                  onChange={(e) => setCreateForm((c) => ({ ...c, farm_name: e.target.value }))}
                  placeholder="VD: Nhà yến Cần Giờ"
                />
              </label>
              <label>
                Địa chỉ
                <input
                  value={createForm.address}
                  onChange={(e) => setCreateForm((c) => ({ ...c, address: e.target.value }))}
                  placeholder="Địa chỉ nhà yến"
                />
              </label>
              {owners.length > 0 && (
                <label>
                  Chủ nhà yến (tùy chọn)
                  <select
                    value={createForm.owner_id}
                    onChange={(e) => setCreateForm((c) => ({ ...c, owner_id: e.target.value }))}
                  >
                    <option value="">-- Chưa gán Owner --</option>
                    {owners.map((o) => (
                      <option key={o.id} value={o.id}>{o.name} ({o.email})</option>
                    ))}
                  </select>
                </label>
              )}
              <div className="admin-farm-modal__actions">
                <button type="button" className="admin-farm-modal__cancel" onClick={() => setCreateOpen(false)}>Hủy</button>
                <button type="submit" className="admin-farm-modal__save" disabled={submitting}>{submitting ? 'Đang lưu...' : 'Tạo nhà yến'}</button>
              </div>
            </form>
          </div>
        )}

        <FarmEditModal
          farm={editingFarm}
          onClose={() =>
            setEditingFarmId(null)
          }
          onSave={handleSaveFarm}
        />

        <TechnicianAssignmentModal
          farm={assignmentFarm}
          technicians={technicians}
          farms={farms}
          onClose={() =>
            setAssignmentFarmId(null)
          }
          onConfirm={
            handleAssignTechnician
          }
        />
      </div>
    </AppLayout>
  )
}

export default FarmsPage
