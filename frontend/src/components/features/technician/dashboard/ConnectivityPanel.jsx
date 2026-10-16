function StatusDot({ status }) {
  return <span className={`technician-status-dot ${status}`} />
}

function ConnectivityPanel() {
  return (
    <section className="technician-card technician-connectivity-panel">
      <div className="technician-card-heading">
        <div>
          <span>CONNECTIVITY</span>
          <h3>K?t n?i h? th?ng</h3>
          <p>Tr?ng th?i giao ti?p gi?a thi?t b? v? h? th?ng</p>
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
