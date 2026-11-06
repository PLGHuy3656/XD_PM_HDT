const metricValue = (metric) => {
  if (metric.value === null) {
    return '--'
  }

  return `${metric.value}${metric.unit}`
}

function EnvironmentZoneTable({ zones, onSelect }) {
  return (
    <section className="tech-env-table-card">
      <header className="tech-env-table-heading">
        <div>
          <span>ENVIRONMENT TELEMETRY</span>
          <h2>Thông số theo khu vực</h2>
          <p>
            Dữ liệu môi trường phục vụ kiểm tra Sensor và thiết bị kỹ thuật.
          </p>
        </div>

        <span className="tech-env-count">
          {zones.length} khu vực
        </span>
      </header>

      <div className="tech-env-table-wrap">
        <div className="tech-env-table-header">
          <span>Khu vực</span>
          <span>Nhiệt độ</span>
          <span>Độ ẩm</span>
          <span>CO₂</span>
          <span>Ánh sáng</span>
          <span>Cập nhật</span>
          <span>Trạng thái</span>
        </div>

        {zones.map((zone) => (
          <button
            type="button"
            className="tech-env-table-row"
            key={zone.id}
            onClick={() => onSelect(zone)}
          >
            <div className="tech-env-zone">
              <span
                className={`tech-env-dot ${zone.status.toLowerCase()}`}
              />
              <div>
                <strong>{zone.name}</strong>
                <small>{zone.farm}</small>
              </div>
            </div>

            {Object.values(zone.metrics).map((metric, index) => (
              <span
                key={index}
                className={`tech-env-metric ${metric.status.toLowerCase()}`}
              >
                {metricValue(metric)}
              </span>
            ))}

            <span className="tech-env-updated">
              {zone.updatedAt}
            </span>

            <span
              className={`tech-env-badge ${zone.status.toLowerCase()}`}
            >
              {zone.status === 'NORMAL' ? 'Ổn định' : 'Kiểm tra'}
            </span>
          </button>
        ))}
      </div>
    </section>
  )
}

export default EnvironmentZoneTable