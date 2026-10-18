import { statusMeta } from './devicesMockData'
import { DeviceIcon } from './DeviceTable'

function DeviceDetailPanel({
  device,
  zoneName,
  onClose,
}) {
  return (
    <section className="device-detail-panel">
      <div className="device-detail-heading">
        <div className="device-detail-title">
          <span
            className={`device-type-icon large ${device.type.toLowerCase()}`}
          >
            <DeviceIcon type={device.type} />
          </span>

          <div>
            <span className="devices-section-label">
              DEVICE DETAIL
            </span>

            <h2>{device.name}</h2>
            <p>{device.id}</p>
          </div>
        </div>

        <button
          type="button"
          className="device-detail-close"
          onClick={onClose}
          aria-label="Đóng chi tiết thiết bị"
        >
          ×
        </button>
      </div>

      <div className="device-detail-grid">
        <div>
          <span>Loại thiết bị</span>
          <strong>{device.typeLabel}</strong>
        </div>

        <div>
          <span>Khu vực</span>
          <strong>{zoneName}</strong>
        </div>

        <div>
          <span>Firmware</span>
          <strong>{device.firmware}</strong>
        </div>

        <div>
          <span>Tín hiệu Wi-Fi</span>
          <strong>
            {device.signal !== null
              ? `${device.signal} dBm`
              : 'Không có tín hiệu'}
          </strong>
        </div>

        <div>
          <span>Trạng thái</span>
          <strong
            className={`device-detail-status ${
              statusMeta[device.status].className
            }`}
          >
            {statusMeta[device.status].label}
          </strong>
        </div>

        <div>
          <span>Hoạt động gần nhất</span>
          <strong>{device.lastSeen}</strong>
        </div>
      </div>

      <div className="device-detail-note">
        <strong>Vai trò thiết bị</strong>
        <p>{device.description}</p>
      </div>
    </section>
  )
}

export default DeviceDetailPanel