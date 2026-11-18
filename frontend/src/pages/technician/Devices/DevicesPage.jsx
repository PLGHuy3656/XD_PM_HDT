import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import DeviceAssignmentModal from '../../../components/features/technician/devices/DeviceAssignmentModal'
import DeviceDetailPanel from '../../../components/features/technician/devices/DeviceDetailPanel'
import DeviceTable from '../../../components/features/technician/devices/DeviceTable'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import {
  statusOptions,
  typeOptions,
} from '../../../components/features/technician/devices/devicesMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'

import './DevicesPage.css'

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function TechnicianDevicesPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    devices,
    zones,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const [zoneFilter, setZoneFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const [selectedDeviceId, setSelectedDeviceId] = useState(null)
  const [assignmentDeviceId, setAssignmentDeviceId] = useState(null)
  const [assignmentZoneId, setAssignmentZoneId] = useState('')
  const [notice, setNotice] = useState('')

  const effectiveZones = zones.length > 0 ? zones : selectedFarm?.zones || []

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    ...effectiveZones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })),
  ]

  const assignmentZoneOptions = effectiveZones.map((zone) => ({
    value: zone.id,
    label: zone.name,
  }))

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesZone =
        zoneFilter === 'ALL' || device.zoneId === zoneFilter

      const matchesStatus =
        statusFilter === 'ALL' || device.status === statusFilter

      const matchesType =
        typeFilter === 'ALL' || device.type === typeFilter

      const matchesSearch =
        !keyword ||
        device.id.toLowerCase().includes(keyword) ||
        device.name.toLowerCase().includes(keyword) ||
        (device.typeLabel && device.typeLabel.toLowerCase().includes(keyword))

      return matchesZone && matchesStatus && matchesType && matchesSearch
    })
  }, [devices, zoneFilter, statusFilter, typeFilter, search])

  const selectedDevice =
    devices.find((device) => device.id === selectedDeviceId) ?? null

  const assignmentDevice =
    devices.find((device) => device.id === assignmentDeviceId) ?? null

  const onlineCount = devices.filter((device) => device.status === 'ONLINE').length
  const attentionCount = devices.filter(
    (device) => device.status === 'WARNING' || device.status === 'OFFLINE',
  ).length

  const averageRssiValues = devices
    .map((device) => device.signal)
    .filter((signal) => typeof signal === 'number')

  const averageRssi = averageRssiValues.length
    ? Math.round(
        averageRssiValues.reduce((total, value) => total + value, 0) /
          averageRssiValues.length,
      )
    : -60

  const handleOpenAssignment = (device) => {
    setAssignmentDeviceId(device.id)
    setAssignmentZoneId(device.zoneId || effectiveZones[0]?.id || '')
  }

  const handleCloseAssignment = () => {
    setAssignmentDeviceId(null)
    setAssignmentZoneId('')
  }

  const handleSaveAssignment = () => {
    if (!assignmentDevice || !assignmentZoneId) {
      return
    }

    const targetZone = effectiveZones.find((zone) => zone.id === assignmentZoneId)
    const targetZoneName = targetZone?.name || 'Khu vực'

    setNotice(
      `Đã chuyển ${assignmentDevice.id} sang ${targetZoneName}. Cấu hình đã được lưu trên thiết bị.`,
    )
    handleCloseAssignment()
  }

  return (
    <AppLayout>
      <div className="tech-devices-page">
        <header className="tech-devices-hero">
          <div>
            <span className="tech-devices-eyebrow">TECHNICIAN WORKSPACE</span>
            <h1>Quản lý thiết bị</h1>
            <p>
              Giám sát tình trạng phần cứng, kết nối và phân bổ khu vực lắp đặt
              cho toàn bộ thiết bị tại các nhà yến được phân công.
            </p>
          </div>

          <div className="tech-devices-farm-picker">
            <span>Nhà yến phụ trách</span>
            <EnvironmentSelect
              value={selectedFarmId || ''}
              options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
              }))}
              onChange={(nextFarmId) => {
                setSelectedFarmId(nextFarmId)
                setSelectedDeviceId(null)
                setZoneFilter('ALL')
              }}
            />
          </div>
        </header>

        {notice && (
          <div className="tech-devices-banner">
            <span />
            <p>{notice}</p>
          </div>
        )}

        {error && (
          <ErrorMessage
            title="Lỗi tải danh sách thiết bị"
            message={error}
            onRetry={refetch}
          />
        )}

        <section className="tech-devices-overview">
          <article className="tech-devices-metric-card">
            <span className="metric-title">Tổng thiết bị</span>
            <strong className="metric-number">{devices.length}</strong>
            <small className="metric-caption">Đang lắp đặt tại {selectedFarm?.name}</small>
          </article>

          <article className="tech-devices-metric-card">
            <span className="metric-title">Trực tuyến</span>
            <strong className="metric-number metric-online">{onlineCount}</strong>
            <small className="metric-caption">Phản hồi bình thường</small>
          </article>

          <article className="tech-devices-metric-card">
            <span className="metric-title">Cần chú ý</span>
            <strong className="metric-number metric-attention">{attentionCount}</strong>
            <small className="metric-caption">Cảnh báo hoặc ngoại tuyến</small>
          </article>

          <article className="tech-devices-metric-card">
            <span className="metric-title">Tín hiệu trung bình</span>
            <strong className="metric-number">{averageRssi} dBm</strong>
            <small className="metric-caption">Chất lượng sóng Wi-Fi/Zigbee</small>
          </article>
        </section>

        <section className="tech-devices-controls">
          <div className="tech-devices-filter-row">
            <div className="tech-devices-search">
              <SearchIcon />
              <input
                type="text"
                placeholder="Tìm theo mã, tên hoặc loại thiết bị..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="tech-devices-selects">
              <EnvironmentSelect
                value={zoneFilter}
                onChange={setZoneFilter}
                options={zoneOptions}
              />

              <EnvironmentSelect
                value={typeFilter}
                onChange={setTypeFilter}
                options={typeOptions}
              />

              <EnvironmentSelect
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusOptions}
              />
            </div>
          </div>
        </section>

        <section className="tech-devices-layout">
          <div className="tech-devices-table-area">
            {loading && devices.length === 0 ? (
              <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
                <LoadingSpinner size="lg" text="Đang tải thiết bị..." />
              </div>
            ) : filteredDevices.length === 0 ? (
              <EmptyState
                title="Không tìm thấy thiết bị"
                description={
                  devices.length === 0
                    ? `Nhà yến '${selectedFarm?.name || ''}' chưa có thiết bị nào được phân bổ.`
                    : 'Không có thiết bị phù hợp với bộ lọc hiện tại.'
                }
              />
            ) : (
              <DeviceTable
                devices={filteredDevices}
                selectedDeviceId={selectedDeviceId}
                onSelectDevice={(device) => setSelectedDeviceId(device.id)}
                onOpenAssignment={handleOpenAssignment}
              />
            )}
          </div>

          <aside className="tech-devices-side-panel">
            <DeviceDetailPanel
              device={selectedDevice}
              onClose={() => setSelectedDeviceId(null)}
              onOpenAssignment={handleOpenAssignment}
            />
          </aside>
        </section>

        <DeviceAssignmentModal
          open={Boolean(assignmentDevice)}
          device={assignmentDevice}
          zones={assignmentZoneOptions}
          selectedZoneId={assignmentZoneId}
          onSelectZone={setAssignmentZoneId}
          onClose={handleCloseAssignment}
          onSave={handleSaveAssignment}
        />
      </div>
    </AppLayout>
  )
}

export default TechnicianDevicesPage
