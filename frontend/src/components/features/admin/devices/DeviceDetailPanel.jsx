import {
  deviceStatusLabels,
  provisioningLabels,
} from './adminDevicesData'

function DeviceDetailPanel({ device, onClose }) {
  if (!device) return null

  return (
    <div
      className="admin-device-detail-backdrop"
      onMouseDown={onClose}
    >
      <aside
        className="admin-device-detail"
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        <header className="admin-device-detail__header">
          <div>
            <span>DEVICE OVERVIEW</span>
            <h2>{device.name}</h2>
            <p>{device.id}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
          >
            ×
          </button>
        </header>

        <section className="admin-device-detail__status">
          <div>
            <span>Trạng thái kết nối</span>

            <strong
              className={`admin-device-status admin-device-status--${device.status.toLowerCase()}`}
            >
              <i />
              {deviceStatusLabels[device.status]}
            </strong>
          </div>

          <div>
            <span>Provisioning</span>

            <strong>
              {
                provisioningLabels[
                  device.provisioning
                ]
              }
            </strong>
          </div>
        </section>

        <section className="admin-device-detail__section">
          <span className="admin-device-detail__label">
            THÔNG TIN THIẾT BỊ
          </span>

          <div className="admin-device-info-grid">
            <div>
              <span>Device ID</span>
              <strong>{device.id}</strong>
            </div>

            <div>
              <span>Loại thiết bị</span>
              <strong>{device.type}</strong>
            </div>

            <div>
              <span>Tên thiết bị</span>
              <strong>{device.name}</strong>
            </div>
          </div>
        </section>

        <section className="admin-device-detail__section">
          <span className="admin-device-detail__label">
            VỊ TRÍ TRIỂN KHAI
          </span>

          <div className="admin-device-location-card">
            <div>
              <span>Nhà yến</span>
              <strong>{device.farm.name}</strong>
              <small>{device.farm.code}</small>
            </div>

            <div>
              <span>Khu vực</span>
              <strong>{device.zone.name}</strong>
              <small>{device.zone.floor}</small>
            </div>
          </div>
        </section>

        <section className="admin-device-detail__section">
          <span className="admin-device-detail__label">
            QUYỀN QUẢN TRỊ
          </span>

          <div className="admin-device-readonly-note">
            <strong>Chế độ chỉ xem</strong>

            <p>
              Administrator giám sát trạng thái thiết bị
              toàn hệ thống. Cài đặt, cấu hình,
              diagnostics và thao tác kỹ thuật được thực
              hiện trong Technician workflow.
            </p>
          </div>
        </section>
      </aside>
    </div>
  )
}

export default DeviceDetailPanel