import { statusMeta } from './devicesMockData'

function DeviceDetailPanel({
  device,
  zoneName,
  onClose,
  onAssign,
}) {
  const handleBackdropMouseDown = (event) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      className="tech-modal-backdrop"
      onMouseDown={handleBackdropMouseDown}
    >
      <section className="tech-device-modal">
        <div className="tech-modal-header">
          <div>
            <span>NODE INSPECTION</span>
            <h2>{device.id}</h2>
            <p>{device.name}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng chi tiết thiết bị"
          >
            ×
          </button>
        </div>

        <div className="tech-modal-grid">
          <div>
            <span>DEVICE TYPE</span>
            <strong>{device.typeLabel}</strong>
          </div>

          <div>
            <span>ASSIGNED ZONE</span>
            <strong>{zoneName}</strong>
          </div>

          <div>
            <span>STATUS</span>
            <strong
              className={`tech-detail-${device.status.toLowerCase()}`}
            >
              {statusMeta[device.status].label}
            </strong>
          </div>

          <div>
            <span>RSSI</span>
            <strong>
              {device.rssi !== null
                ? `${device.rssi} dBm`
                : 'No signal'}
            </strong>
          </div>

          <div>
            <span>MQTT</span>
            <strong>{device.mqttStatus}</strong>
          </div>

          <div>
            <span>IP ADDRESS</span>
            <strong>{device.ip}</strong>
          </div>

          <div>
            <span>FIRMWARE</span>
            <strong>{device.firmware}</strong>
          </div>

          <div>
            <span>LAST HEARTBEAT</span>
            <strong>{device.lastSeen}</strong>
          </div>

          <div>
            <span>TECHNICAL HEALTH</span>
            <strong>{device.technicalHealth}</strong>
          </div>

          <div>
            <span>SENSORS</span>
            <strong>{device.sensorHealth}</strong>
          </div>

          <div>
            <span>ACTUATORS</span>
            <strong>{device.actuatorHealth}</strong>
          </div>
        </div>

        <div className="tech-modal-info">
          Đây là trạng thái kỹ thuật tổng quan của node. Kiểm tra kết nối,
          Sensor, Actuator và MQTT chuyên sâu được thực hiện tại module
          Chẩn đoán thiết bị.
        </div>

        <div className="tech-modal-footer">
          <button
            type="button"
            className="tech-action-secondary"
            onClick={onClose}
          >
            Đóng
          </button>

          <button
            type="button"
            className="tech-action-primary"
            onClick={onAssign}
          >
            Chuyển Zone
          </button>
        </div>
      </section>
    </div>
  )
}

export default DeviceDetailPanel