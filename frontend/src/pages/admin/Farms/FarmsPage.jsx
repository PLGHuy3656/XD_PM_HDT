import { useMemo, useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import Select from '../../../components/ui/Select'
import FarmTable from '../../../components/features/admin/farms/FarmTable'
import FarmDetailPanel from '../../../components/features/admin/farms/FarmDetailPanel'
import FarmEditModal from '../../../components/features/admin/farms/FarmEditModal'
import TechnicianAssignmentModal from '../../../components/features/admin/farms/TechnicianAssignmentModal'

import {
  adminFarms,
  getFarmDeviceCount,
} from '../../../components/features/admin/farms/adminFarmsMockData'

import {
  initialAdminUsers,
} from '../../../components/features/admin/users/usersMockData'

import './FarmsPage.css'

const healthFilterOptions = [
  { value: 'ALL', label: 'Tất cả tình trạng' },
  { value: 'GOOD', label: 'Ổn định' },
  { value: 'ATTENTION', label: 'Cần theo dõi' },
]

function FarmsPage() {
  const [farms, setFarms] = useState(adminFarms)

  const [searchTerm, setSearchTerm] = useState('')
  const [healthFilter, setHealthFilter] =
    useState('ALL')

  const [selectedFarmId, setSelectedFarmId] =
    useState(null)

  const [editingFarmId, setEditingFarmId] =
    useState(null)

  const [assignmentFarmId, setAssignmentFarmId] =
    useState(null)

  const technicians = initialAdminUsers.filter(
    (user) =>
      user.role === 'TECHNICIAN' &&
      user.status === 'ACTIVE',
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
        farm.owner.name
          .toLowerCase()
          .includes(keyword) ||
        technicianName.includes(keyword)

      const matchesHealth =
        healthFilter === 'ALL' ||
        farm.health === healthFilter

      return matchesSearch && matchesHealth
    })
  }, [farms, searchTerm, healthFilter])

  const totalZones = farms.reduce(
    (total, farm) =>
      total + farm.zones.length,
    0,
  )

  const totalDevices = farms.reduce(
    (total, farm) =>
      total + getFarmDeviceCount(farm),
    0,
  )

  const attentionFarms = farms.filter(
    (farm) => farm.health === 'ATTENTION',
  ).length

  function handleSaveFarm(updatedFarm) {
    setFarms((current) =>
      current.map((farm) =>
        farm.id === updatedFarm.id
          ? updatedFarm
          : farm,
      ),
    )

    setEditingFarmId(null)
    setSelectedFarmId(updatedFarm.id)
  }

  function handleAssignTechnician(
    farm,
    technician,
  ) {
    const technicianSnapshot = {
      id: technician.id,
      name: technician.name,
      email: technician.email,
      phone: technician.phone,
      status: 'ASSIGNED',
    }

    setFarms((current) =>
      current.map((item) =>
        item.id === farm.id
          ? {
              ...item,
              technician: technicianSnapshot,
            }
          : item,
      ),
    )

    setAssignmentFarmId(null)
    setSelectedFarmId(farm.id)
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
          <div className="admin-farms-content__heading">
            <div>
              <span>FARM DIRECTORY</span>
              <h2>Danh sách nhà yến</h2>
              <p>
                {filteredFarms.length} /{' '}
                {farms.length} nhà yến
              </p>
            </div>
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
          onAssignTechnician={(farm) =>
            setAssignmentFarmId(farm.id)
          }
        />

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
