import { useNavigate } from 'react-router-dom'
import { EmptyState } from '../../../common/feedback/index.js'

const STATUS_DISPLAY = {
  ONLINE: { label: 'Trực tuyến', badgeClass: 'tech-badge--online' },
  WARNING: { label: 'Cảnh báo', badgeClass: 'tech-badge--warning' },
  OFFLINE: { label: 'Ngoại tuyến', badgeClass: 'tech-badge--offline' },
  UNKNOWN: { label: 'Chưa có heartbeat', badgeClass: 'tech-badge--unknown' },
  UNAVAILABLE: { label: 'Không xác định (IoT)', badgeClass: 'tech-badge--unknown' },
}

function DeviceStatusPanel({ devices = [] }) {
  const navigate = useNavigate()
  const displayDevices = Array.isArray(devices) ? devices : []

  return (
    <section className="tech-ws-card">
      <div className="tech-ws-card__head">
        <div>
          <span className="tech-ws-eyebrow">DEVICE REGISTRY</span>
          <h3>Thiết bị tại nhà yến</h3>
        </div>

        <button
          type="button"
          className="tech-ws-btn"
          onClick={() => navigate('/technician/devices')}
        >
          Xem tất cả ({displayDevices.length}) ›
        </button>
      </div>

      {displayDevices.length === 0 ? (
        <EmptyState
          title="Chưa có thiết bị nào"
          description="Nhà yến đang chọn chưa có thiết bị được đăng ký."
        />
      ) : (
        <div className="tech-ws-table-wrap">
          <table className="tech-ws-table">
            <thead>
              <tr>
                <th>Thiết bị & Node ID</th>
                <th>Loại</th>
                <th>Khu vực (Zone)</th>
                <th>Trạng thái IoT</th>
              </tr>
            </thead>
            <tbody>
              {displayDevices.map((device) => {
                const statusKey = String(device.status || 'UNKNOWN').toUpperCase()
                const statusInfo = STATUS_DISPLAY[statusKey] || STATUS_DISPLAY.UNKNOWN
                return (
                  <tr key={device.id}>
                    <td>
                      <strong style={{ display: 'block', color: '#102d3f' }}>
                        {device.nodeId || device.id}
                      </strong>
                      <small className="tech-ws-truncate" title={device.name} style={{ color: '#64748b' }}>
                        {device.name}
                      </small>
                    </td>
                    <td>{device.typeLabel || device.type}</td>
                    <td>
                      <span
                        className={`tech-badge ${
                          device.isZoneAssigned ? 'tech-badge--online' : 'tech-badge--warning'
                        }`}
                      >
                        {device.isZoneAssigned ? device.zoneName : 'Chưa phân bổ Zone'}
                      </span>
                    </td>
                    <td>
                      <span className={`tech-badge ${statusInfo.badgeClass}`}>
                        {statusInfo.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}

export default DeviceStatusPanel
