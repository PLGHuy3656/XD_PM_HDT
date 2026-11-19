import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import {
  statusMeta,
  typeFilters,
  statusFilters,
} from '../../../components/features/farm-owner/devices/devicesMockData'

import DeviceDetailPanel from '../../../components/features/farm-owner/devices/DeviceDetailPanel'
import DeviceTable from '../../../components/features/farm-owner/devices/DeviceTable'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { useDevices } from '../../../features/devices/hooks/useDevices'

import './DevicesPage.css'

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 7v5h-5" />
      <path d="M19 12a7 7 0 1 0-2 5" />
    </svg>
  )
}

function DevicesPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    loading: farmsLoading,
    error: farmsError,
  } = useFarms()

  const {
    devices,
    loading: devicesLoading,
    error: devicesError,
    refetch: refetchDevices,
  } = useDevices(selectedFarmId)

  const [zoneId, setZoneId] = useState('ALL')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [selectedDeviceId, setSelectedDeviceId] = useState(null)
  const [refreshLabel, setRefreshLabel] = useState('Vừa xong')

  const effectiveZones = zones.length > 0 ? zones : selectedFarm?.zones || []

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    ...effectiveZones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })),
  ]

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesZone = zoneId === 'ALL' || device.zoneId === zoneId

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
  }, [devices, zoneId, search, statusFilter, typeFilter])

  const selectedDevice =
    devices.find((device) => device.id === selectedDeviceId) ?? null

  const onlineCount = devices.filter((device) => device.status === 'ONLINE').length
  const warningCount = devices.filter((device) => device.status === 'WARNING').length
  const offlineCount = devices.filter((device) => device.status === 'OFFLINE').length
  const farmDeviceCount = devices.length

  const getZoneName = (device) => {
    return (
      effectiveZones.find((zone) => zone.id === device.zoneId)?.name ?? 'Chưa gán'
    )
  }

  const handleRefresh = async () => {
    setRefreshLabel('Đang làm mới...')
    await refetchDevices()
    setRefreshLabel('Vừa xong')
  }

  return (
    <AppLayout>
      <div className="devices-page">
        <header className="devices-hero">
          <div>
            <span className="devices-eyebrow">DEVICE MANAGEMENT</span>

            <h1>Thiết bị</h1>

            <p>
              Giám sát tình trạng kết nối, phiên bản firmware và vị trí lắp đặt
              của toàn bộ thiết bị theo từng nhà yến.
            </p>
          </div>

          <div className="devices-farm-picker">
            <span>Nhà yến</span>

            <EnvironmentSelect
              value={selectedFarmId || ''}
              onChange={(nextId) => {
                setSelectedFarmId(nextId)
                setSelectedDeviceId(null)
                setZoneId('ALL')
              }}
              options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
              }))}
            />
          </div>
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {devicesError && (
          <ErrorMessage
            title="Lỗi tải thiết bị"
            message={devicesError}
            onRetry={refetchDevices}
          />
        )}

        <section className="devices-overview-grid">
          <article className="device-metric-card">
            <span className="metric-title">Tổng thiết bị</span>
            <strong className="metric-number">{farmDeviceCount}</strong>
            <small className="metric-caption">Được định danh trong nhà yến</small>
          </article>

          <article className="device-metric-card">
            <span className="metric-title">Trực tuyến</span>
            <strong className="metric-number metric-online">{onlineCount}</strong>
            <small className="metric-caption">Đang kết nối bình thường</small>
          </article>

          <article className="device-metric-card">
            <span className="metric-title">Cần kiểm tra</span>
            <strong className="metric-number metric-warning">{warningCount}</strong>
            <small className="metric-caption">Tín hiệu yếu hoặc chập chờn</small>
          </article>

          <article className="device-metric-card">
            <span className="metric-title">Ngoại tuyến</span>
            <strong className="metric-number metric-offline">{offlineCount}</strong>
            <small className="metric-caption">Mất tín hiệu trên 10 phút</small>
          </article>
        </section>

        <section className="devices-controls">
          <div className="devices-filter-row">
            <div className="devices-search">
              <SearchIcon />
              <input
                type="text"
                placeholder="Tìm theo mã, tên hoặc loại thiết bị..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="devices-selects">
              <EnvironmentSelect
                value={zoneId}
                onChange={setZoneId}
                options={zoneOptions}
              />

              <EnvironmentSelect
                value={typeFilter}
                onChange={setTypeFilter}
                options={typeFilters}
              />

              <EnvironmentSelect
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusFilters}
              />
            </div>

            <button
              type="button"
              className="devices-refresh-btn"
              onClick={handleRefresh}
            >
              <RefreshIcon />
              {refreshLabel}
            </button>
          </div>
        </section>

        <section className="devices-layout">
          <div className="devices-table-area">
            {devicesLoading && devices.length === 0 ? (
              <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
                <LoadingSpinner size="lg" text="Đang tải thiết bị..." />
              </div>
            ) : filteredDevices.length === 0 ? (
              <EmptyState
                title="Không tìm thấy thiết bị"
                description={
                  farmDeviceCount === 0
                    ? 'Nhà yến này chưa có thiết bị nào được cấu hình.'
                    : 'Không có thiết bị phù hợp với bộ lọc hiện tại.'
                }
              />
            ) : (
              <DeviceTable
                devices={filteredDevices}
                selectedDeviceId={selectedDeviceId}
                onSelectDevice={(device) => setSelectedDeviceId(device.id)}
                getZoneName={getZoneName}
              />
            )}
          </div>

          <aside className="devices-side-panel">
            <DeviceDetailPanel
              device={selectedDevice}
              getZoneName={getZoneName}
              onClose={() => setSelectedDeviceId(null)}
            />
          </aside>
        </section>
      </div>
    </AppLayout>
  )
}

export default DevicesPage
