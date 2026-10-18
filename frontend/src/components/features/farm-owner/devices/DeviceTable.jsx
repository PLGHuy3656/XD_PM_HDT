import { statusMeta } from './devicesMockData'

function DeviceIcon({ type }) {
  if (type === 'CONTROLLER') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="4" y="5" width="16" height="14" rx="3" />
        <path d="M8 9h8M8 13h5" />
        <circle cx="16.5" cy="13.5" r="1" />
      </svg>
    )
  }

  if (type === 'SENSOR') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3v10" />
        <circle cx="12" cy="16" r="4" />
        <path d="M9 6h6" />
      </svg>
    )
  }

  if (type === 'CAMERA') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="3" y="6" width="14" height="12" rx="3" />
        <path d="m17 10 4-2v8l-4-2" />
        <circle cx="10" cy="12" r="2.5" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 9v6M9 6v12M13 4v16M17 7v10M21 10v4" />
    </svg>
  )
}

function WifiIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 9.5a11 11 0 0 1 14 0" />
      <path d="M8 13a6.5 6.5 0 0 1 8 0" />
      <path d="M11 16.5a2 2 0 0 1 2 0" />
    </svg>
  )
}

function DeviceTable({
  devices,
  selectedDeviceId,
  getZoneName,
  onSelectDevice,
}) {
  if (devices.length === 0) {
    return (
      <div className="device-empty-state">
        <div className="device-empty-icon">
          <DeviceIcon type="CONTROLLER" />
        </div>

        <h3>Không tìm thấy thiết bị</h3>

        <p>
          Thử thay đổi khu vực, trạng thái hoặc từ khóa tìm kiếm.
        </p>
      </div>
    )
  }

  return (
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
        {devices.map((device) => {
          const status = statusMeta[device.status]

          return (
            <button
              type="button"
              key={device.id}
              className={`device-row ${
                selectedDeviceId === device.id
                  ? 'selected'
                  : ''
              }`}
              onClick={() => onSelectDevice(device.id)}
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

              <span className="device-row-arrow">→</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export { DeviceIcon }
export default DeviceTable