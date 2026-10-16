import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../farm-owner/Environment/EnvironmentSelect'

import '../../farm-owner/Environment/EnvironmentSelect.css'
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

const initialDevices = [
  {
    id: 'ESP32-CTRL-01',
    name: 'Environmental Controller',
    type: 'CONTROLLER',
    typeLabel: 'ESP32 Controller',
    zoneId: 'zone-a',
    status: 'ONLINE',
    firmware: 'v1.4.2',
    rssi: -51,
    lastSeen: 'Vừa xong',
    ip: '192.168.1.21',
  },
  {
    id: 'ENV-01',
    name: 'Environment Sensor Node',
    type: 'SENSOR',
    typeLabel: 'SHT31 · CO₂ · Light',
    zoneId: 'zone-a',
    status: 'ONLINE',
    firmware: 'v1.2.8',
    rssi: -57,
    lastSeen: '4 giây trước',
    ip: '192.168.1.22',
  },
  {
    id: 'CAM-01',
    name: 'Entry Camera Node',
    type: 'CAMERA',
    typeLabel: 'AI Camera',
    zoneId: 'zone-a',
    status: 'ONLINE',
    firmware: 'v2.1.0',
    rssi: -62,
    lastSeen: '7 giây trước',
    ip: '192.168.1.31',
  },
  {
    id: 'ESP32-CTRL-02',
    name: 'Environmental Controller',
    type: 'CONTROLLER',
    typeLabel: 'ESP32 Controller',
    zoneId: 'zone-b',
    status: 'WARNING',
    firmware: 'v1.4.2',
    rssi: -79,
    lastSeen: '18 giây trước',
    ip: '192.168.1.24',
  },
  {
    id: 'ENV-02',
    name: 'Environment Sensor Node',
    type: 'SENSOR',
    typeLabel: 'SHT31 · CO₂ · Light',
    zoneId: 'zone-b',
    status: 'ONLINE',
    firmware: 'v1.2.8',
    rssi: -65,
    lastSeen: '10 giây trước',
    ip: '192.168.1.25',
  },
  {
    id: 'AUDIO-01',
    name: 'Audio Monitoring Node',
    type: 'AUDIO',
    typeLabel: 'Audio Edge Node',
    zoneId: 'zone-c',
    status: 'OFFLINE',
    firmware: 'v1.0.6',
    rssi: null,
    lastSeen: '12 phút trước',
    ip: '--',
  },
  {
    id: 'CAM-02',
    name: 'Monitoring Camera',
    type: 'CAMERA',
    typeLabel: 'AI Camera',
    zoneId: 'zone-d',
    status: 'ONLINE',
    firmware: 'v2.1.0',
    rssi: -60,
    lastSeen: '6 giây trước',
    ip: '192.168.1.33',
  },
]

const statusMeta = {
  ONLINE: {
    label: 'Online',
    className: 'online',
  },
  WARNING: {
    label: 'Warning',
    className: 'warning',
  },
  OFFLINE: {
    label: 'Offline',
    className: 'offline',
  },
}

const statusOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'ONLINE', label: 'Online' },
  { value: 'WARNING', label: 'Warning' },
  { value: 'OFFLINE', label: 'Offline' },
]

const typeOptions = [
  { value: 'ALL', label: 'Tất cả thiết bị' },
  { value: 'CONTROLLER', label: 'Controller' },
  { value: 'SENSOR', label: 'Sensor' },
  { value: 'CAMERA', label: 'Camera' },
  { value: 'AUDIO', label: 'Audio' },
]

function DeviceIcon({ type }) {
  if (type === 'CAMERA') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="6" width="18" height="13" rx="3" />
        <circle cx="12" cy="12.5" r="3.2" />
        <path d="M8 6 9.5 4h5L16 6" />
      </svg>
    )
  }

  if (type === 'AUDIO') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M5 10v4M9 7v10M13 4v16M17 7v10M21 10v4" />
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

function SignalIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 9a12 12 0 0 1 16 0" />
      <path d="M7 12a8 8 0 0 1 10 0" />
      <path d="M10 15a4 4 0 0 1 4 0" />
      <circle cx="12" cy="18" r="1" />
    </svg>
  )
}

function TechnicianDevicesPage() {
  const [devices, setDevices] = useState(initialDevices)
  const [farmId, setFarmId] = useState(farms[0].id)
  const [zoneFilter, setZoneFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const [selectedDeviceId, setSelectedDeviceId] =
    useState(null)

  const [assignmentDeviceId, setAssignmentDeviceId] =
    useState(null)

  const [assignmentZoneId, setAssignmentZoneId] =
    useState('')

  const [notice, setNotice] = useState('')

  const selectedFarm =
    farms.find((farm) => farm.id === farmId) ?? farms[0]

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    ...selectedFarm.zones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })),
  ]

  const assignmentZoneOptions = selectedFarm.zones.map(
    (zone) => ({
      value: zone.id,
      label: zone.name,
    })
  )

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesZone =
        zoneFilter === 'ALL' ||
        device.zoneId === zoneFilter

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
        matchesZone &&
        matchesStatus &&
        matchesType &&
        matchesSearch
      )
    })
  }, [
    devices,
    zoneFilter,
    statusFilter,
    typeFilter,
    search,
  ])

  const selectedDevice =
    devices.find(
      (device) => device.id === selectedDeviceId
    ) ?? null

  const assignmentDevice =
    devices.find(
      (device) => device.id === assignmentDeviceId
    ) ?? null

  const onlineCount = devices.filter(
    (device) => device.status === 'ONLINE'
  ).length

  const attentionCount = devices.filter(
    (device) =>
      device.status === 'WARNING' ||
      device.status === 'OFFLINE'
  ).length

  const averageRssiValues = devices
    .filter((device) => device.rssi !== null)
    .map((device) => device.rssi)

  const averageRssi = Math.round(
    averageRssiValues.reduce(
      (sum, value) => sum + value,
      0
    ) / averageRssiValues.length
  )

  const getZoneName = (zoneId) =>
    selectedFarm.zones.find(
      (zone) => zone.id === zoneId
    )?.name ?? 'Chưa gán'

  const openAssignment = (device) => {
    setAssignmentDeviceId(device.id)
    setAssignmentZoneId(device.zoneId)
    setNotice('')
  }

  const closeAssignment = () => {
    setAssignmentDeviceId(null)
    setAssignmentZoneId('')
  }

  const handleAssignment = () => {
    if (!assignmentDevice || !assignmentZoneId) return

    const previousZoneId = assignmentDevice.zoneId

    if (previousZoneId === assignmentZoneId) {
      setNotice('Thiết bị đang thuộc khu vực này.')
      return
    }

    setDevices((currentDevices) =>
      currentDevices.map((device) =>
        device.id === assignmentDevice.id
          ? {
              ...device,
              zoneId: assignmentZoneId,
            }
          : device
      )
    )

    setNotice(
      `${assignmentDevice.id} đã được chuyển từ ${getZoneName(
        previousZoneId
      )} sang ${getZoneName(assignmentZoneId)}.`
    )

    setAssignmentDeviceId(null)
    setAssignmentZoneId('')
  }

  return (
    <AppLayout>
      <div className="tech-devices-page">
        <header className="tech-devices-hero">
          <div>
            <span className="tech-devices-kicker">
              DEVICE OPERATIONS
            </span>

            <h1>Quản lý thiết bị</h1>

            <p>
              Theo dõi node kỹ thuật, kết nối và phân bổ
              thiết bị theo từng khu vực nhà yến.
            </p>
          </div>

          <div className="tech-devices-system-chip">
            <span className="tech-system-pulse" />

            <div>
              <strong>Device Network Active</strong>
              <span>
                {onlineCount}/{devices.length} nodes online
              </span>
            </div>
          </div>
        </header>

        <section className="tech-device-metrics">
          <article>
            <span>TOTAL NODES</span>
            <strong>{devices.length}</strong>
            <small>Registered devices</small>
          </article>

          <article className="healthy">
            <span>ONLINE</span>
            <strong>{onlineCount}</strong>
            <small>Responding normally</small>
          </article>

          <article className="attention">
            <span>NEEDS ATTENTION</span>
            <strong>{attentionCount}</strong>
            <small>Warning or offline</small>
          </article>

          <article>
            <span>AVG. SIGNAL</span>
            <strong>{averageRssi} dBm</strong>
            <small>Connected nodes</small>
          </article>
        </section>

        <section className="tech-device-workspace">
          <div className="tech-workspace-heading">
            <div>
              <span className="tech-section-code">
                DEVICE REGISTRY
              </span>

              <h2>Node & Connectivity</h2>

              <p>
                Kiểm tra nhanh trạng thái kết nối và vị trí
                được gán của từng node.
              </p>
            </div>

            <div className="tech-farm-field">
              <EnvironmentSelect
                label="Nhà yến"
                value={farmId}
                options={farms.map((farm) => ({
                  value: farm.id,
                  label: farm.name,
                }))}
                onChange={(nextFarmId) => {
                  setFarmId(nextFarmId)
                  setZoneFilter('ALL')
                }}
              />
            </div>
          </div>

          <div className="tech-device-toolbar">
            <label className="tech-device-search">
              <SearchIcon />

              <input
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Search Device ID, node name..."
              />
            </label>

            <EnvironmentSelect
              label="Khu vực"
              value={zoneFilter}
              options={zoneOptions}
              onChange={setZoneFilter}
            />

            <EnvironmentSelect
              label="Trạng thái"
              value={statusFilter}
              options={statusOptions}
              onChange={setStatusFilter}
            />

            <EnvironmentSelect
              label="Loại node"
              value={typeFilter}
              options={typeOptions}
              onChange={setTypeFilter}
            />
          </div>

          {notice && (
            <div className="tech-device-notice">
              <span>✓</span>
              {notice}
            </div>
          )}

          <div className="tech-device-table">
            <div className="tech-device-table-head">
              <span>Node</span>
              <span>Assignment</span>
              <span>Status</span>
              <span>Network</span>
              <span>Firmware</span>
              <span>Action</span>
            </div>

            {filteredDevices.length > 0 ? (
              <div className="tech-device-table-body">
                {filteredDevices.map((device) => {
                  const status =
                    statusMeta[device.status]

                  return (
                    <div
                      className="tech-device-row"
                      key={device.id}
                    >
                      <button
                        type="button"
                        className="tech-device-identity"
                        onClick={() =>
                          setSelectedDeviceId(device.id)
                        }
                      >
                        <span
                          className={`tech-device-icon ${device.type.toLowerCase()}`}
                        >
                          <DeviceIcon type={device.type} />
                        </span>

                        <span>
                          <strong>{device.id}</strong>
                          <small>
                            {device.name} · {device.typeLabel}
                          </small>
                        </span>
                      </button>

                      <div className="tech-assignment-cell">
                        <span>
                          {getZoneName(device.zoneId)}
                        </span>

                        <small>
                          {selectedFarm.name}
                        </small>
                      </div>

                      <div>
                        <span
                          className={`tech-status ${status.className}`}
                        >
                          <i />
                          {status.label}
                        </span>
                      </div>

                      <div className="tech-network-cell">
                        <span>
                          <SignalIcon />
                          {device.rssi !== null
                            ? `${device.rssi} dBm`
                            : 'No signal'}
                        </span>

                        <small>{device.ip}</small>
                      </div>

                      <div className="tech-firmware-cell">
                        <strong>{device.firmware}</strong>
                        <small>{device.lastSeen}</small>
                      </div>

                      <div className="tech-device-actions">
                        <button
                          type="button"
                          className="tech-action-secondary"
                          onClick={() =>
                            setSelectedDeviceId(device.id)
                          }
                        >
                          Chi tiết
                        </button>

                        <button
                          type="button"
                          className="tech-action-primary"
                          onClick={() =>
                            openAssignment(device)
                          }
                        >
                          Chuyển Zone
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="tech-device-empty">
                Không có node phù hợp với bộ lọc hiện tại.
              </div>
            )}
          </div>
        </section>

        {selectedDevice && (
          <div
            className="tech-modal-backdrop"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                setSelectedDeviceId(null)
              }
            }}
          >
            <section className="tech-device-modal">
              <div className="tech-modal-header">
                <div>
                  <span>NODE INSPECTION</span>
                  <h2>{selectedDevice.id}</h2>
                  <p>{selectedDevice.name}</p>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    setSelectedDeviceId(null)
                  }
                >
                  ×
                </button>
              </div>

              <div className="tech-modal-grid">
                <div>
                  <span>DEVICE TYPE</span>
                  <strong>
                    {selectedDevice.typeLabel}
                  </strong>
                </div>

                <div>
                  <span>ASSIGNED ZONE</span>
                  <strong>
                    {getZoneName(selectedDevice.zoneId)}
                  </strong>
                </div>

                <div>
                  <span>STATUS</span>
                  <strong
                    className={`tech-detail-${selectedDevice.status.toLowerCase()}`}
                  >
                    {
                      statusMeta[selectedDevice.status]
                        .label
                    }
                  </strong>
                </div>

                <div>
                  <span>RSSI</span>
                  <strong>
                    {selectedDevice.rssi !== null
                      ? `${selectedDevice.rssi} dBm`
                      : 'No signal'}
                  </strong>
                </div>

                <div>
                  <span>IP ADDRESS</span>
                  <strong>{selectedDevice.ip}</strong>
                </div>

                <div>
                  <span>FIRMWARE</span>
                  <strong>
                    {selectedDevice.firmware}
                  </strong>
                </div>

                <div>
                  <span>LAST SEEN</span>
                  <strong>
                    {selectedDevice.lastSeen}
                  </strong>
                </div>
              </div>

              <div className="tech-modal-info">
                Chẩn đoán Sensor / Camera / Actuator / MQTT
                sẽ được thực hiện tại module Chẩn đoán thiết
                bị. Trang này chỉ quản lý registry, trạng thái
                kết nối và assignment.
              </div>

              <div className="tech-modal-footer">
                <button
                  type="button"
                  className="tech-action-secondary"
                  onClick={() =>
                    setSelectedDeviceId(null)
                  }
                >
                  Đóng
                </button>

                <button
                  type="button"
                  className="tech-action-primary"
                  onClick={() => {
                    setSelectedDeviceId(null)
                    openAssignment(selectedDevice)
                  }}
                >
                  Chuyển Zone
                </button>
              </div>
            </section>
          </div>
        )}

        {assignmentDevice && (
          <div
            className="tech-modal-backdrop"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) {
                closeAssignment()
              }
            }}
          >
            <section className="tech-device-modal assignment">
              <div className="tech-modal-header">
                <div>
                  <span>ZONE ASSIGNMENT</span>
                  <h2>Chuyển thiết bị</h2>
                  <p>
                    {assignmentDevice.id} ·{' '}
                    {assignmentDevice.name}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={closeAssignment}
                >
                  ×
                </button>
              </div>

              <div className="tech-current-assignment">
                <span>VỊ TRÍ HIỆN TẠI</span>
                <strong>
                  {getZoneName(assignmentDevice.zoneId)}
                </strong>
                <small>{selectedFarm.name}</small>
              </div>

              <EnvironmentSelect
                label="Chuyển sang khu vực"
                value={assignmentZoneId}
                options={assignmentZoneOptions}
                onChange={setAssignmentZoneId}
              />

              <div className="tech-assignment-warning">
                <strong>Lưu ý</strong>
                <p>
                  Đây đang là thao tác mock phía Frontend.
                  Khi tích hợp Backend, quyền Technician và
                  việc gán Zone phải được kiểm tra lại tại API.
                </p>
              </div>

              <div className="tech-modal-footer">
                <button
                  type="button"
                  className="tech-action-secondary"
                  onClick={closeAssignment}
                >
                  Hủy
                </button>

                <button
                  type="button"
                  className="tech-action-primary"
                  onClick={handleAssignment}
                >
                  Xác nhận chuyển Zone
                </button>
              </div>
            </section>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default TechnicianDevicesPage