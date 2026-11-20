const healthLabels = {
  HEALTHY: 'Ổn định',
  WARNING: 'Cảnh báo',
  UNAVAILABLE: 'Không khả dụng',
  // INT01-R1: honest states when no self-test / feedback sensor exists
  REPORTING: 'Đang gửi dữ liệu',
  UNSUPPORTED: 'Chưa được hỗ trợ',
  UNVERIFIED: 'Chưa xác minh',
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

  const connectivity = node.connectivity || {}
  const sensors = Array.isArray(node.sensors) ? node.sensors : []
  const actuators = Array.isArray(node.actuators) ? node.actuators : []
  const issues = Array.isArray(node.issues) ? node.issues : []

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
                <strong>{connectivity.mqtt || 'Chưa kết nối IoT'}</strong>
              </div>

              <div>
                <span>Wi-Fi</span>
                <strong>{connectivity.wifi || '--'}</strong>
              </div>

              <div>
                <span>RSSI</span>
                <strong>
                  {connectivity.rssi == null
                    ? '--'
                    : `${connectivity.rssi} dBm${connectivity.rssiSource ? ` (${connectivity.rssiSource})` : ''}`}
                </strong>
              </div>

              <div>
                <span>IP Address</span>
                <strong>{connectivity.ip || '--'}</strong>
              </div>
            </div>
          </section>

          <section>
            <div className="diagnostic-detail-title">
              <span>Sensor Health</span>
              <small>Tình trạng cảm biến</small>
            </div>

            <div className="diagnostic-health-list">
              {sensors.length > 0 ? (
                sensors.map((sensor) => (
                  <HealthItem
                    key={sensor.name}
                    item={sensor}
                    showValue
                  />
                ))
              ) : (
                <p className="diagnostic-empty">
                  {node.loading ? 'Đang tải dữ liệu IoT…' : 'Chưa có dữ liệu cảm biến từ IoT Service.'}
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
              {actuators.length > 0 ? (
                actuators.map((actuator) => (
                  <HealthItem
                    key={actuator.name}
                    item={actuator}
                    showValue={actuator.value !== undefined}
                  />
                ))
              ) : (
                <p className="diagnostic-empty">
                  Chưa có dữ liệu actuator từ IoT Service.
                </p>
              )}
            </div>
          </section>

          <section>
            <div className="diagnostic-detail-title">
              <span>Technical Issues</span>
              <small>Lỗi kỹ thuật phát hiện được</small>
            </div>

            {issues.length > 0 ? (
              <div className="diagnostic-issue-list">
                {issues.map((issue) => (
                  <div className="diagnostic-issue" key={issue}>
                    <span>!</span>
                    <p>{issue}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="diagnostic-no-issue">
                Chưa ghi nhận sự cố kỹ thuật nào trên thiết bị này.
              </div>
            )}
          </section>

          <div className="diagnostic-permission-note">
            <strong>Phạm vi quyền Technician</strong>
            <p>
              Kỹ thuật viên chỉ xem và phân bổ khu vực cho các thiết bị thuộc nhà yến được Admin phân công. Dữ liệu heartbeat/sensor thời gian thực sẽ cập nhật khi IoT Service khả dụng.
            </p>
          </div>
        </div>
      </aside>
    </div>
  )
}

export default DiagnosticDetailPanel