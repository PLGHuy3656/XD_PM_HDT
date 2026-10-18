import { devices } from './dashboardMockData'

function StatusDot({ status }) {
  return <span className={`technician-status-dot ${status}`} />
}

function DeviceStatusPanel() {
  return (
    <section className="technician-card technician-device-panel">
      <div className="technician-card-heading">
        <div>
          <span>DEVICE MANAGEMENT</span>
          <h3>Trạng thái thiết bị</h3>
          <p>
            Theo dõi controller và sensor đang kết nối trong nhà yến
          </p>
        </div>

        <button type="button" className="technician-link-button">
          Xem tất cả
          <span aria-hidden="true">›</span>
        </button>
      </div>

      <div className="technician-device-list">
        <div className="technician-device-list__header">
          <span>Node</span>
          <span>Khu vực</span>
          <span>Sensor</span>
          <span>Trạng thái</span>
          <span>Cập nhật</span>
        </div>

        {devices.map((device) => (
          <article className="technician-device-row" key={device.id}>
            <div className="technician-device-row__node">
              <span
                className={`technician-device-icon technician-device-icon--${device.status}`}
                aria-hidden="true"
              >
                N
              </span>

              <strong>{device.id}</strong>
            </div>

            <span>{device.zone}</span>

            <strong className="technician-device-row__sensor">
              {device.sensors}
            </strong>

            <span
              className={`technician-device-state technician-device-state--${device.status}`}
            >
              <StatusDot
                status={
                  device.status === 'online'
                    ? 'healthy'
                    : device.status === 'warning'
                      ? 'warning'
                      : 'danger'
                }
              />

              {device.status === 'online'
                ? 'Online'
                : device.status === 'warning'
                  ? 'Warning'
                  : 'Offline'}
            </span>

            <span className="technician-device-row__time">
              {device.lastSeen}
            </span>
          </article>
        ))}
      </div>
    </section>
  )
}

export default DeviceStatusPanel