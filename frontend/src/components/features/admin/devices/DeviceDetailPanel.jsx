import {
  deviceStatusLabels,
  provisioningLabels,
} from './adminDevicesData'

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  )
}

function DeviceDetailPanel({ device, onClose, onEdit, onDelete }) {
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
            className="admin-device-detail__close"
            onClick={onClose}
            aria-label="Đóng"
          >
            <CloseIcon />
          </button>
        </header>

        {(onEdit || onDelete) && (
          <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
            {onEdit && (
              <button
                type="button"
                className="admin-farm-edit-button"
                onClick={() => onEdit(device)}
              >
                Chỉnh sửa thiết bị
              </button>
            )}
            {onDelete && (
              <button
                type="button"
                className="admin-farm-edit-button"
                style={{ borderColor: '#dc2626', color: '#dc2626' }}
                onClick={() => onDelete(device)}
              >
                Xóa thiết bị
              </button>
            )}
          </div>
        )}

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
              <span>Node ID</span>
              <strong>{device.nodeId || device.id}</strong>
            </div>

            <div>
              <span>Device UUID</span>
              <strong style={{ fontSize: '0.78rem', wordBreak: 'break-all' }}>{device.deviceId || '--'}</strong>
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
              <span>Khu vực (Zone)</span>
              <strong style={!device.isZoneAssigned ? { color: '#b45309' } : undefined}>
                {device.zone.name}
              </strong>
              <small>{device.isZoneAssigned ? device.zone.floor : 'Chưa gán khu vực'}</small>
            </div>

            <div>
              <span>Technician phụ trách Farm</span>
              <strong>{device.farmTechnician?.name || 'Chưa phân công'}</strong>
              <small>{device.farmTechnician?.email || '--'}</small>
            </div>
          </div>
        </section>

        <section className="admin-device-detail__section">
          <span className="admin-device-detail__label">
            QUẢN TRỊ THIẾT BỊ
          </span>

          <div className="admin-device-readonly-note">
            <strong>Đăng ký &amp; phân bổ</strong>

            <p>
              Administrator quản lý đăng ký thiết bị, cập nhật
              thông tin và theo dõi phân bổ Farm/Zone. Việc có
              Zone chưa đồng nghĩa thiết bị đã lắp đặt hoặc Online;
              lắp đặt và chẩn đoán thực tế thuộc quy trình Technician.
            </p>
          </div>
        </section>
      </aside>
    </div>
  )
}

export default DeviceDetailPanel
