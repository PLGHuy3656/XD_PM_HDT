import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../Environment/EnvironmentSelect'

import '../Environment/EnvironmentSelect.css'
import './DevicesPage.css'

const farms = [
  {
    id: 'farm-binh-chanh',
    name: 'Nhà yến Bình Chánh',
    zones: [
      { id: 'zone-a', name: 'Khu vực A' },
      { id: 'zone-b', name: 'Khu vực B' },
      { id: 'zone-c', name: 'Khu vực C' },
      { id: 'zone-d', name: 'Khu vực D' },
      { id: 'zone-e', name: 'Khu vực E' },
    ],
  },
]

const devices = [
  {
    id: 'ESP32-CTRL-01',
    name: 'Bộ điều khiển môi trường',
    type: 'CONTROLLER',
    typeLabel: 'ESP32 Controller',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-a',
    status: 'ONLINE',
    firmware: 'v1.4.2',
    signal: -51,
    lastSeen: 'Vừa xong',
    description: 'Điều khiển phun sương, thông gió và sưởi.',
  },
  {
    id: 'ENV-01',
    name: 'Cảm biến môi trường',
    type: 'SENSOR',
    typeLabel: 'Environment Sensor',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-a',
    status: 'ONLINE',
    firmware: 'v1.2.8',
    signal: -57,
    lastSeen: '4 giây trước',
    description: 'Theo dõi nhiệt độ, độ ẩm, CO₂ và ánh sáng.',
  },
  {
    id: 'CAM-01',
    name: 'Camera cửa ra vào',
    type: 'CAMERA',
    typeLabel: 'AI Camera Node',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-a',
    status: 'ONLINE',
    firmware: 'v2.1.0',
    signal: -62,
    lastSeen: '7 giây trước',
    description: 'Nguồn hình ảnh cho đếm chim và AI Detection.',
  },
  {
    id: 'ESP32-CTRL-02',
    name: 'Bộ điều khiển môi trường',
    type: 'CONTROLLER',
    typeLabel: 'ESP32 Controller',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-b',
    status: 'WARNING',
    firmware: 'v1.4.2',
    signal: -79,
    lastSeen: '18 giây trước',
    description: 'Tín hiệu Wi-Fi yếu, thiết bị vẫn đang hoạt động.',
  },
  {
    id: 'ENV-02',
    name: 'Cảm biến môi trường',
    type: 'SENSOR',
    typeLabel: 'Environment Sensor',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-b',
    status: 'ONLINE',
    firmware: 'v1.2.8',
    signal: -65,
    lastSeen: '10 giây trước',
    description: 'Theo dõi nhiệt độ, độ ẩm, CO₂ và ánh sáng.',
  },
  {
    id: 'AUDIO-01',
    name: 'Audio Monitoring Node',
    type: 'AUDIO',
    typeLabel: 'Audio Node',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-c',
    status: 'OFFLINE',
    firmware: 'v1.0.6',
    signal: null,
    lastSeen: '12 phút trước',
    description: 'Thu tín hiệu âm thanh phục vụ phát hiện bất thường.',
  },
  {
    id: 'CAM-02',
    name: 'Camera giám sát',
    type: 'CAMERA',
    typeLabel: 'AI Camera Node',
    farmId: 'farm-binh-chanh',
    zoneId: 'zone-d',
    status: 'ONLINE',
    firmware: 'v2.1.0',
    signal: -60,
    lastSeen: '6 giây trước',
    description: 'Giám sát hình ảnh và sự kiện AI trong nhà yến.',
  },
]

const statusMeta = {
  ONLINE: {
    label: 'Online',
    className: 'online',
  },
  WARNING: {
    label: 'Cần chú ý',
    className: 'warning',
  },
  OFFLINE: {
    label: 'Offline',
    className: 'offline',
  },
}

const typeFilters = [
  { value: 'ALL', label: 'Tất cả thiết bị' },
  { value: 'CONTROLLER', label: 'Controller' },
  { value: 'SENSOR', label: 'Sensor' },
  { value: 'CAMERA', label: 'Camera' },
  { value: 'AUDIO', label: 'Audio' },
]

const statusFilters = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'ONLINE', label: 'Online' },
  { value: 'WARNING', label: 'Cần chú ý' },
  { value: 'OFFLINE', label: 'Offline' },
]

function DeviceIcon({ type }) {
  if (type === 'CAMERA') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="6" width="18" height="13" rx="3" />
        <circle cx="12" cy="12.5" r="3.2" />
        <path d="M8 6 9.5 3.8h5L16 6" />
      </svg>
    )
  }

  if (type === 'AUDIO') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 10v4" />
        <path d="M9 7v10" />
        <path d="M13 4v16" />
        <path d="M17 7v10" />
        <path d="M21 10v4" />
      </svg>
    )
  }

  if (type === 'SENSOR') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M9 15.5V5a3 3 0 0 1 6 0v10.5" />
        <path d="M9 15.5a5 5 0 1 0 6 0" />
        <path d="M12 8v8" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="5" width="14" height="14" rx="3" />
      <path d="M9 2v3M15 2v3M9 19v3M15 19v3" />
      <path d="M2 9h3M2 15h3M19 9h3M19 15h3" />
      <path d="M9 9h6v6H9z" />
    </svg>
  )
}

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

function WifiIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 9a12 12 0 0 1 16 0" />
      <path d="M7 12a8 8 0 0 1 10 0" />
      <path d="M10 15a4 4 0 0 1 4 0" />
      <circle cx="12" cy="18" r="1" />
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

          {filteredDevices.length > 0 ? (
            <div className="device-table-card">
              <div className="device-table-head">
                <span>Thiết bị</span>
                <span>Khu vực</span>
                <span>Trạng thái</span>
                <span>Tín hiệu</span>
                <span>Hoạt động gần nhất</span>
                <span />
              </div>

              <div className="device-table-body">
                {filteredDevices.map((device) => {
                  const status =
                    statusMeta[device.status]

                  return (
                    <button
                      type="button"
                      key={device.id}
                      className={`device-row ${
                        selectedDeviceId === device.id
                          ? 'selected'
                          : ''
                      }`}
                      onClick={() =>
                        setSelectedDeviceId(device.id)
                      }
                    >
                      <span className="device-main-cell">
                        <span
                          className={`device-type-icon ${device.type.toLowerCase()}`}
                        >
                          <DeviceIcon type={device.type} />
                        </span>

                        <span>
                          <strong>{device.name}</strong>
                          <small>
                            {device.id} · {device.typeLabel}
                          </small>
                        </span>
                      </span>

                      <span className="device-zone-cell">
                        {getZoneName(device)}
                      </span>

                      <span>
                        <span
                          className={`device-status-badge ${status.className}`}
                        >
                          <i />
                          {status.label}
                        </span>
                      </span>

                      <span className="device-signal-cell">
                        <WifiIcon />

                        {device.signal !== null
                          ? `${device.signal} dBm`
                          : '--'}
                      </span>

                      <span className="device-last-seen">
                        {device.lastSeen}
                      </span>

                      <span className="device-row-arrow">
                        →
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="device-empty-state">
              <div className="device-empty-icon">
                <DeviceIcon type="CONTROLLER" />
              </div>

              <h3>Không tìm thấy thiết bị</h3>

              <p>
                Thử thay đổi khu vực, trạng thái hoặc từ khóa
                tìm kiếm.
              </p>
            </div>
          )}
        </section>

        {selectedDevice && (
          <section className="device-detail-panel">
            <div className="device-detail-heading">
              <div className="device-detail-title">
                <span
                  className={`device-type-icon large ${selectedDevice.type.toLowerCase()}`}
                >
                  <DeviceIcon type={selectedDevice.type} />
                </span>

                <div>
                  <span className="devices-section-label">
                    DEVICE DETAIL
                  </span>

                  <h2>{selectedDevice.name}</h2>

                  <p>{selectedDevice.id}</p>
                </div>
              </div>

              <button
                type="button"
                className="device-detail-close"
                onClick={() =>
                  setSelectedDeviceId(null)
                }
                aria-label="Đóng chi tiết thiết bị"
              >
                ×
              </button>
            </div>

            <div className="device-detail-grid">
              <div>
                <span>Loại thiết bị</span>
                <strong>
                  {selectedDevice.typeLabel}
                </strong>
              </div>

              <div>
                <span>Khu vực</span>
                <strong>
                  {getZoneName(selectedDevice)}
                </strong>
              </div>

              <div>
                <span>Firmware</span>
                <strong>
                  {selectedDevice.firmware}
                </strong>
              </div>

              <div>
                <span>Tín hiệu Wi-Fi</span>
                <strong>
                  {selectedDevice.signal !== null
                    ? `${selectedDevice.signal} dBm`
                    : 'Không có tín hiệu'}
                </strong>
              </div>

              <div>
                <span>Trạng thái</span>

                <strong
                  className={`device-detail-status ${statusMeta[
                    selectedDevice.status
                  ].className}`}
                >
                  {
                    statusMeta[selectedDevice.status]
                      .label
                  }
                </strong>
              </div>

              <div>
                <span>Hoạt động gần nhất</span>
                <strong>
                  {selectedDevice.lastSeen}
                </strong>
              </div>
            </div>

            <div className="device-detail-note">
              <strong>Vai trò thiết bị</strong>
              <p>{selectedDevice.description}</p>
            </div>
          </section>
        )}
      </div>
    </AppLayout>
  )
}

export default DevicesPage