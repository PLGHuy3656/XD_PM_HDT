function StatusDot({ status }) {
  return <span className={`technician-status-dot ${status}`} />
}

function ConnectivityPanel() {
  return (
    <section className="technician-card technician-connectivity-panel">
      <div className="technician-card-heading">
        <div>
          <span>CONNECTIVITY</span>
          <h3>Kết nối hệ thống</h3>
          <p>Trạng thái giao tiếp giữa thiết bị và hệ thống</p>
        </div>
      </div>

      <div className="technician-connectivity-list">
        <div>
          <span>
            <StatusDot status="healthy" />
            MQTT Broker
          </span>
          <strong>Connected</strong>
        </div>

        <div>
          <span>
            <StatusDot status="healthy" />
            Internet
          </span>
          <strong>Online</strong>
        </div>

        <div>
          <span>
            <StatusDot status="healthy" />
            Edge Gateway
          </span>
          <strong>Online</strong>
        </div>

        <div>
          <span>Latency</span>
          <strong>28 ms</strong>
        </div>

        <div>
          <span>Last Sync</span>
          <strong>14:32:08</strong>
        </div>
      </div>
    </section>
  )
}

export default ConnectivityPanel