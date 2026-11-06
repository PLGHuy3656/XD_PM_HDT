const statusLabels = {
  HEALTHY: 'Ổn định',
  WARNING: 'Cảnh báo',
  OFFLINE: 'Offline',
}

function DiagnosticNodeList({
  nodes,
  selectedNodeId,
  onSelect,
}) {
  return (
    <section className="diagnostic-node-section">
      <div className="diagnostic-section-heading">
        <div>
          <span className="diagnostic-eyebrow">DEVICE HEALTH</span>
          <h2>Thiết bị cần chẩn đoán</h2>
        </div>

        <span className="diagnostic-count">
          {nodes.length} thiết bị
        </span>
      </div>

      <div className="diagnostic-node-list">
        {nodes.map((node) => (
          <button
            type="button"
            key={node.id}
            className={`diagnostic-node-row ${
              selectedNodeId === node.id ? 'active' : ''
            }`}
            onClick={() => onSelect(node)}
          >
            <div className="diagnostic-node-main">
              <span
                className={`diagnostic-status-dot ${node.status.toLowerCase()}`}
              />

              <div>
                <strong>{node.name}</strong>
                <span>{node.id} · {node.type}</span>
              </div>
            </div>

            <div className="diagnostic-node-location">
              <strong>{node.zone}</strong>
              <span>{node.farm}</span>
            </div>

            <div className="diagnostic-node-signal">
              <strong>
                {node.connectivity.rssi === null
                  ? '--'
                  : `${node.connectivity.rssi} dBm`}
              </strong>
              <span>RSSI</span>
            </div>

            <div className="diagnostic-node-heartbeat">
              <strong>{node.lastSeen}</strong>
              <span>Heartbeat</span>
            </div>

            <span
              className={`diagnostic-status-badge ${node.status.toLowerCase()}`}
            >
              {statusLabels[node.status]}
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default DiagnosticNodeList