const metricNames = {
  temperature: 'Nhiệt độ',
  humidity: 'Độ ẩm',
  co2: 'CO₂',
  light: 'Ánh sáng',
}

function EnvironmentDetailPanel({ zone, onClose }) {
  if (!zone) {
    return null
  }

  return (
    <div
      className="tech-env-overlay"
      role="presentation"
      onMouseDown={onClose}
    >
      <aside
        className="tech-env-detail"
        role="dialog"
        aria-modal="true"
        aria-label={`Chi tiết ${zone.name}`}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="tech-env-detail-header">
          <div>
            <span>ENVIRONMENT DIAGNOSTICS</span>
            <h2>{zone.name}</h2>
            <p>{zone.farm} · {zone.controller}</p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng"
          >
            ×
          </button>
        </header>

        <div className="tech-env-detail-body">
          <section>
            <div className="tech-env-detail-title">
              <strong>Telemetry hiện tại</strong>
              <span>Cập nhật {zone.updatedAt}</span>
            </div>

            <div className="tech-env-metric-grid">
              {Object.entries(zone.metrics).map(([key, metric]) => (
                <article key={key}>
                  <span>{metricNames[key]}</span>

                  <strong
                    className={metric.status.toLowerCase()}
                  >
                    {metric.value === null
                      ? '--'
                      : `${metric.value}${metric.unit}`}
                  </strong>

                  <small>
                    {metric.status === 'NORMAL'
                      ? 'Bình thường'
                      : metric.status === 'WARNING'
                        ? 'Cần kiểm tra'
                        : 'Không có dữ liệu'}
                  </small>
                </article>
              ))}
            </div>
          </section>

          <section>
            <div className="tech-env-detail-title">
              <strong>Thông tin kỹ thuật</strong>
              <span>Technical context</span>
            </div>

            <div className="tech-env-tech-info">
              <div>
                <span>Controller / Node</span>
                <strong>{zone.controller}</strong>
              </div>

              <div>
                <span>Trạng thái khu vực</span>
                <strong>
                  {zone.status === 'NORMAL'
                    ? 'Ổn định'
                    : 'Cần kiểm tra'}
                </strong>
              </div>
            </div>
          </section>

          <section>
            <div className="tech-env-detail-title">
              <strong>Nhận định kỹ thuật</strong>
              <span>Diagnostic note</span>
            </div>

            <div
              className={`tech-env-note ${zone.status.toLowerCase()}`}
            >
              {zone.technicalNote}
            </div>
          </section>

          <div className="tech-env-scope-note">
            <strong>Phạm vi Technician</strong>
            <p>
              Trang này cung cấp dữ liệu môi trường để hỗ trợ chẩn đoán
              Sensor, Node và Actuator. Điều khiển môi trường tự động hoặc
              Manual Override thuộc luồng Farm Owner và quyền Backend.
            </p>
          </div>
        </div>
      </aside>
    </div>
  )
}

export default EnvironmentDetailPanel