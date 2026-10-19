import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import {
  farms,
  devices,
  statusMeta,
  typeFilters,
  statusFilters,
} from '../../../components/features/farm-owner/devices/devicesMockData'

import DeviceDetailPanel from '../../../components/features/farm-owner/devices/DeviceDetailPanel'
import DeviceTable from '../../../components/features/farm-owner/devices/DeviceTable'

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
  const [farmId, setFarmId] = useState(farms[0].id)
  const [zoneId, setZoneId] = useState('ALL')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [selectedDeviceId, setSelectedDeviceId] = useState(null)
  const [refreshLabel, setRefreshLabel] = useState('Vừa xong')

  const selectedFarm =
    farms.find((farm) => farm.id === farmId) ?? farms[0]

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    ...selectedFarm.zones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })),
  ]

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesFarm = device.farmId === farmId

      const matchesZone =
        zoneId === 'ALL' || device.zoneId === zoneId

      const matchesStatus =
        statusFilter === 'ALL' ||
        device.status === statusFilter

      const matchesType =
        typeFilter === 'ALL' ||
        device.type === typeFilter

      const matchesSearch =
        !keyword ||
        device.id.toLowerCase().includes(keyword) ||
        device.name.toLowerCase().includes(keyword) ||
        device.typeLabel.toLowerCase().includes(keyword)

      return (
        matchesFarm &&
        matchesZone &&
        matchesStatus &&
        matchesType &&
        matchesSearch
      )
    })
  }, [
    farmId,
    zoneId,
    search,
    statusFilter,
    typeFilter,
  ])

  const selectedDevice =
    devices.find(
      (device) => device.id === selectedDeviceId
    ) ?? null

  const onlineCount = devices.filter(
    (device) =>
      device.farmId === farmId &&
      device.status === 'ONLINE'
  ).length

  const warningCount = devices.filter(
    (device) =>
      device.farmId === farmId &&
      device.status === 'WARNING'
  ).length

  const offlineCount = devices.filter(
    (device) =>
      device.farmId === farmId &&
      device.status === 'OFFLINE'
  ).length

  const farmDeviceCount = devices.filter(
    (device) => device.farmId === farmId
  ).length

  const getZoneName = (device) => {
    return (
      selectedFarm.zones.find(
        (zone) => zone.id === device.zoneId
      )?.name ?? 'Chưa gán'
    )
  }

  const handleRefresh = () => {
    setRefreshLabel('Vừa xong')
  }

  return (
    <AppLayout>
      <div className="devices-page">
        <header className="devices-hero">
          <div>
            <span className="devices-eyebrow">
              DEVICE MANAGEMENT
            </span>

            <h1>Thiết bị nhà yến</h1>

            <p>
              Theo dõi trạng thái kết nối và sức khỏe các
              thiết bị đang hoạt động trong nhà yến.
            </p>
          </div>

          <div className="devices-live-status">
            <span className="devices-live-dot" />

            <div>
              <strong>Hệ thống thiết bị trực tuyến</strong>
              <span>Cập nhật {refreshLabel}</span>
            </div>
          </div>
        </header>

        <section className="device-summary-grid">
          <article className="device-summary-card">
            <span className="device-summary-label">
              Tổng thiết bị
            </span>

            <strong>{farmDeviceCount}</strong>

            <small>Trong nhà yến đang chọn</small>
          </article>

          <article className="device-summary-card positive">
            <span className="device-summary-label">
              Online
            </span>

            <strong>{onlineCount}</strong>

            <small>Hoạt động bình thường</small>
          </article>

          <article className="device-summary-card warning">
            <span className="device-summary-label">
              Cần chú ý
            </span>

            <strong>{warningCount}</strong>

            <small>Cần kiểm tra tín hiệu</small>
          </article>

          <article className="device-summary-card danger">
            <span className="device-summary-label">
              Offline
            </span>

            <strong>{offlineCount}</strong>

            <small>Mất kết nối</small>
          </article>
        </section>

        <section className="device-context-card">
          <div className="device-context-copy">
            <span className="devices-section-label">
              PHẠM VI THIẾT BỊ
            </span>

            <h2>Chọn khu vực theo dõi</h2>

            <p>
              Danh sách bên dưới được lọc theo nhà yến và
              khu vực đang chọn.
            </p>
          </div>

          <div className="device-context-fields">
            <EnvironmentSelect
              label="Nhà yến"
              value={farmId}
              options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
              }))}
              onChange={(nextFarmId) => {
                setFarmId(nextFarmId)
                setZoneId('ALL')
                setSelectedDeviceId(null)
              }}
            />

            <EnvironmentSelect
              label="Khu vực"
              value={zoneId}
              options={zoneOptions}
              onChange={(nextZoneId) => {
                setZoneId(nextZoneId)
                setSelectedDeviceId(null)
              }}
            />
          </div>
        </section>

        <section className="device-list-section">
          <div className="device-list-heading">
            <div>
              <span className="devices-section-index">
                01
              </span>

              <div>
                <h2>Danh sách thiết bị</h2>

                <p>
                  {filteredDevices.length} thiết bị phù hợp
                  với bộ lọc hiện tại
                </p>
              </div>
            </div>

            <button
              type="button"
              className="device-refresh-button"
              onClick={handleRefresh}
            >
              <RefreshIcon />
              Làm mới
            </button>
          </div>

          <div className="device-toolbar">
            <label className="device-search">
              <SearchIcon />

              <input
                type="text"
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Tìm theo tên hoặc Device ID..."
              />
            </label>

            <div className="device-filter-group">
              <EnvironmentSelect
                label="Trạng thái"
                value={statusFilter}
                options={statusFilters}
                onChange={setStatusFilter}
              />

              <EnvironmentSelect
                label="Loại thiết bị"
                value={typeFilter}
                options={typeFilters}
                onChange={setTypeFilter}
              />
            </div>
          </div>

          <DeviceTable
            devices={filteredDevices}
            selectedDeviceId={selectedDeviceId}
            getZoneName={getZoneName}
            onSelectDevice={setSelectedDeviceId}
          />
        </section>

        {selectedDevice && (
          <DeviceDetailPanel
            device={selectedDevice}
            zoneName={getZoneName(selectedDevice)}
            onClose={() => setSelectedDeviceId(null)}
          />
        )}
      </div>
    </AppLayout>
  )
}

export default DevicesPage