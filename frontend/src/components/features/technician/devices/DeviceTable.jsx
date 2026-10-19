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

function SignalIcon() {
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
  farmName,
  getZoneName,
  onOpenDetail,
  onOpenAssignment,
}) {
  return (
    <div className="tech-device-table">
      <div className="tech-device-table-head">
        <span>Node</span>
        <span>Assignment</span>
        <span>Status</span>
        <span>Network</span>
        <span>Firmware</span>
        <span>Action</span>
      </div>

      {devices.length > 0 ? (
        <div className="tech-device-table-body">
          {devices.map((device) => {
            const status = statusMeta[device.status]

            return (
              <div className="tech-device-row" key={device.id}>
                <button
                  type="button"
                  className="tech-device-identity"
                  onClick={() => onOpenDetail(device.id)}
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
                  <span>{getZoneName(device.zoneId)}</span>
                  <small>{farmName}</small>
                </div>

                <div>
                  <span className={`tech-status ${status.className}`}>
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
                  <small>
                    MQTT {device.mqttStatus} · {device.ip}
                  </small>
                </div>

                <div className="tech-firmware-cell">
                  <strong>{device.firmware}</strong>
                  <small>Heartbeat: {device.lastSeen}</small>
                </div>

                <div className="tech-device-actions">
                  <button
                    type="button"
                    className="tech-action-secondary"
                    onClick={() => onOpenDetail(device.id)}
                  >
                    Chi tiết
                  </button>

                  <button
                    type="button"
                    className="tech-action-primary"
                    onClick={() => onOpenAssignment(device)}
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
  )
}

export default DeviceTable