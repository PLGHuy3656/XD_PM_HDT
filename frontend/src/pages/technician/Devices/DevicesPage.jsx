import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

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
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'

import '../TechnicianWorkspace.css'
import './DevicesPage.css'

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function TechnicianDevicesPage() {
  const navigate = useNavigate()
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    devices,
    zones,
    telemetryError,
    loading,
    error,
    refetch,
    updateDeviceZone,
  } = useTechnicianData()

  const [zoneFilter, setZoneFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const [selectedDeviceId, setSelectedDeviceId] = useState(null)
  const [assignmentDeviceId, setAssignmentDeviceId] = useState(null)
  const [assignmentZoneId, setAssignmentZoneId] = useState('')
  const [assignmentSaving, setAssignmentSaving] = useState(false)
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')

  const effectiveZones = zones.length > 0 ? zones : selectedFarm?.zones || []

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    { value: 'UNASSIGNED', label: 'Chưa phân bổ Zone' },
    ...effectiveZones.map((zone) => ({
      value: zone.id,
      label: `${zone.code && zone.code !== '--' ? `${zone.code} · ` : ''}${zone.name}`,
    })),
  ]

  const assignmentZoneOptions = [
    { value: '', label: 'Chưa phân bổ Zone (Gỡ khỏi Zone)' },
    ...effectiveZones.map((zone) => ({
      value: zone.id,
      label: `${zone.code && zone.code !== '--' ? `${zone.code} · ` : ''}${zone.name}`,
    })),
  ]

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesZone =
        zoneFilter === 'ALL' ||
        (zoneFilter === 'UNASSIGNED' ? !device.isZoneAssigned : device.zoneId === zoneFilter)

      const matchesStatus =
        statusFilter === 'ALL' || device.status === statusFilter

      const matchesType =
        typeFilter === 'ALL' || device.type === typeFilter

      const matchesSearch =
        !keyword ||
        device.id.toLowerCase().includes(keyword) ||
        (device.nodeId && device.nodeId.toLowerCase().includes(keyword)) ||
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
  const unassignedCount = devices.filter((device) => !device.isZoneAssigned).length
  const attentionCount = devices.filter(
    (device) => device.status === 'WARNING' || device.status === 'OFFLINE',
  ).length

  const averageRssiValues = devices
    .map((device) => device.signal)
    .filter((signal) => typeof signal === 'number')

  const averageRssi = averageRssiValues.length
    ? `${Math.round(
        averageRssiValues.reduce((total, value) => total + value, 0) /
          averageRssiValues.length,
      )} dBm`
    : 'Chưa có'

  const handleOpenAssignment = (deviceOrId) => {
    const target =
      typeof deviceOrId === 'string'
        ? devices.find((d) => d.id === deviceOrId)
        : deviceOrId
    if (!target) return
    setActionError('')
    setAssignmentDeviceId(target.id)
    setAssignmentZoneId(target.zoneId || '')
  }

  const handleCloseAssignment = () => {
    setAssignmentDeviceId(null)
    setAssignmentZoneId('')
    setActionError('')
  }

  const handleSaveAssignment = async () => {
    if (!assignmentDevice) {
      return
    }
    setActionError('')
    setNotice('')
    setAssignmentSaving(true)
    const res = await updateDeviceZone(assignmentDevice.id, assignmentZoneId || null)
    setAssignmentSaving(false)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể cập nhật phân bổ khu vực cho thiết bị.')
      return
    }
    const targetZone = effectiveZones.find((zone) => zone.id === assignmentZoneId)
    const targetZoneName = targetZone?.name || 'Chưa phân bổ Zone'
    setNotice(
      `Đã cập nhật phân bổ khu vực cho ${assignmentDevice.name} (${assignmentDevice.nodeId}) → ${targetZoneName}.`,
    )
    handleCloseAssignment()
  }

  return (
    <AppLayout>
      <div className="tech-ws tech-devices-page">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN DEVICES</span>
            <h1>Quản lý thiết bị</h1>
            <p>
              Giám sát thiết bị đã đăng ký, trạng thái kết nối IoT và phân bổ khu vực tại nhà yến được phân công.
            </p>
          </div>

          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách</span>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  options={farms.map((farm) => ({
                    value: farm.id,
                    label: formatFarmOptionLabel(farm),
                  }))}
                  onChange={(nextFarmId) => {
                    setSelectedFarmId(nextFarmId)
                    setSelectedDeviceId(null)
                    setZoneFilter('ALL')
                    setNotice('')
                    setActionError('')
                  }}
                />
              </div>
            )}
            <button
              type="button"
              className="tech-ws-btn tech-ws-btn--primary"
              style={{ height: '42px' }}
              onClick={() => navigate('/technician/installation')}
            >
              + Lắp đặt / Đăng ký mới
            </button>
          </div>
        </header>

        {notice && <div className="tech-ws-notice">{notice}</div>}

        {(error || actionError) && (
          <ErrorMessage
            title="Lỗi thao tác thiết bị"
            message={actionError || error}
            onRetry={refetch}
          />
        )}

        <section className="tech-ws-kpi-grid">
          <article className="tech-ws-kpi-card">
            <span>Tổng thiết bị</span>
            <strong>{devices.length}</strong>
            <small>{selectedFarm ? `Tại ${selectedFarm.name}` : 'Chưa chọn nhà yến'}</small>
          </article>

          <article className="tech-ws-kpi-card">
            <span>Trực tuyến</span>
            <strong>{telemetryError ? '—' : onlineCount}</strong>
            <small>{telemetryError ? 'Chưa kết nối dịch vụ IoT' : 'Phản hồi bình thường'}</small>
          </article>

          <article className="tech-ws-kpi-card">
            <span>Chưa phân bổ Zone</span>
            <strong style={{ color: unassignedCount > 0 ? '#b45309' : '#059669' }}>
              {unassignedCount}
            </strong>
            <small>{attentionCount > 0 ? `${attentionCount} thiết bị cần chú ý` : 'Cần gán khu vực lắp đặt'}</small>
          </article>

          <article className="tech-ws-kpi-card">
            <span>Tín hiệu trung bình</span>
            <strong>{averageRssi}</strong>
            <small>{telemetryError ? 'Chưa kết nối dịch vụ IoT' : 'Chất lượng sóng Wi-Fi/Zigbee'}</small>
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
                farmName={selectedFarm?.name || ''}
                selectedDeviceId={selectedDeviceId}
                onOpenDetail={(id) => setSelectedDeviceId(id)}
                onSelectDevice={(device) => setSelectedDeviceId(device.id)}
                onOpenAssignment={handleOpenAssignment}
              />
            )}
          </div>

          <aside className="tech-devices-side-panel">
            <DeviceDetailPanel
              device={selectedDevice}
              zoneName={
                selectedDevice?.isZoneAssigned
                  ? selectedDevice.zoneName
                  : 'Chưa phân bổ Zone'
              }
              onClose={() => setSelectedDeviceId(null)}
              onAssign={handleOpenAssignment}
            />
          </aside>
        </section>

        <DeviceAssignmentModal
          device={assignmentDevice}
          currentZoneName={
            assignmentDevice?.isZoneAssigned
              ? assignmentDevice.zoneName
              : 'Chưa phân bổ Zone'
          }
          farmName={selectedFarm ? formatFarmOptionLabel(selectedFarm) : ''}
          zoneId={assignmentZoneId}
          zoneOptions={assignmentZoneOptions}
          saving={assignmentSaving}
          error={actionError}
          onZoneChange={setAssignmentZoneId}
          onClose={handleCloseAssignment}
          onConfirm={handleSaveAssignment}
        />
      </div>
    </AppLayout>
  )
}

export default TechnicianDevicesPage
