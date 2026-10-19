const healthLabels = {
  HEALTHY: 'Ổn định',
  WARNING: 'Cảnh báo',
  UNAVAILABLE: 'Không khả dụng',
}

function HealthItem({ item, showValue = false }) {
  return (
    <div className="diagnostic-health-item">
      <div>
        <span
          className={`diagnostic-status-dot ${item.status.toLowerCase()}`}
        />
        <strong>{item.name}</strong>
      </div>

      <span className={`diagnostic-health-state ${item.status.toLowerCase()}`}>
        {showValue && item.value !== undefined
          ? item.value
          : healthLabels[item.status]}
      </span>
    </div>
  )
}

function DiagnosticDetailPanel({ node, onClose }) {
  if (!node) {
    return null
  }

  return (
    <div
      className="diagnostic-overlay"
      role="presentation"
      onMouseDown={onClose}
    >
      <aside
        className="diagnostic-detail-panel"
        role="dialog"
        aria-modal="true"
        aria-label={`Chẩn đoán ${node.name}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="diagnostic-detail-header">
          <div>
            <span>TECHNICAL DIAGNOSTICS</span>
            <h2>{node.name}</h2>
            <p>{node.id} · {node.farm} · {node.zone}</p>
          </div>

          <button
            type="button"
            className="diagnostic-close"
            onClick={onClose}
            aria-label="Đóng"
          >
            ×
          </button>
        </header>

        <div className="diagnostic-detail-body">
          <section>
            <div className="diagnostic-detail-title">
              <span>Kết nối</span>
              <small>Connectivity / MQTT</small>
            </div>

            <div className="diagnostic-connectivity-grid">
              <div>
                <span>MQTT</span>
                <strong>{node.connectivity.mqtt}</strong>
              </div>

              <div>
                <span>Wi-Fi</span>
                <strong>{node.connectivity.wifi}</strong>
              </div>

              <div>
                <span>RSSI</span>
                <strong>
                  {node.connectivity.rssi === null
                    ? '--'
                    : `${node.connectivity.rssi} dBm`}
                </strong>
              </div>

              <div>
                <span>IP Address</span>
                <strong>{node.connectivity.ip}</strong>
              </div>
            </div>
          </section>

          <section>
            <div className="diagnostic-detail-title">
              <span>Sensor Health</span>
              <small>Tình trạng cảm biến</small>
            </div>

            <div className="diagnostic-health-list">
              {node.sensors.length > 0 ? (
                node.sensors.map((sensor) => (
                  <HealthItem
                    key={sensor.name}
                    item={sensor}
                    showValue
                  />
                ))
              ) : (
                <p className="diagnostic-empty">
                  Thiết bị này không có Sensor.
                </p>
              )}
            </div>
          </section>

          <section>
            <div className="diagnostic-detail-title">
              <span>Actuator Health</span>
              <small>Tình trạng cơ cấu chấp hành</small>
            </div>

            <div className="diagnostic-health-list">
              {node.actuators.length > 0 ? (
                node.actuators.map((actuator) => (
                  <HealthItem
                    key={actuator.name}
                    item={actuator}
                  />
                ))
              ) : (
                <p className="diagnostic-empty">
                  Thiết bị này không quản lý Actuator.
                </p>
              )}
            </div>
          </section>

          <section>
            <div className="diagnostic-detail-title">
              <span>Technical Issues</span>
              <small>Lỗi kỹ thuật phát hiện được</small>
            </div>

            {node.issues.length > 0 ? (
              <div className="diagnostic-issue-list">
                {node.issues.map((issue) => (
                  <div className="diagnostic-issue" key={issue}>
                    <span>!</span>
                    <p>{issue}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="diagnostic-no-issue">
                Không phát hiện lỗi kỹ thuật trên thiết bị này.
              </div>
            )}
          </section>

          <div className="diagnostic-permission-note">
            <strong>Giới hạn quyền Technician</strong>
            <p>
              Chẩn đoán và thao tác kiểm tra thủ công chỉ được thực hiện
              trong phạm vi quyền do Backend cấp. Giao diện hiện tại sử
              dụng dữ liệu mock và chưa gửi lệnh trực tiếp đến ESP32.
            </p>
          </div>
        </div>
      </aside>
    </div>
  )
}

export default DiagnosticDetailPanel