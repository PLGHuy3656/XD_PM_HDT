import {
  systemAuditLogs,
  systemServices,
  systemStatusLabels,
} from './systemMockData'

function SystemOverview() {
  const operationalServices = systemServices.filter(
    (service) => service.tier === 'CURRENT',
  )

  const plannedServices = systemServices.filter(
    (service) => service.tier === 'PLANNED',
  )

  const healthyCount = operationalServices.filter(
    (service) => service.status === 'HEALTHY',
  ).length

  return (
    <div className="admin-system-overview">
      <section className="admin-system-stats">
        <article>
          <span>Dịch vụ hiện hành</span>
          <strong>{operationalServices.length}</strong>
          <small>Đã triển khai trong repo</small>
        </article>

        <article>
          <span>Hoạt động tốt</span>
          <strong>{healthyCount}</strong>
          <small>
            {healthyCount}/{operationalServices.length} dịch vụ hiện hành
          </small>
        </article>

        <article>
          <span>Kiến trúc mục tiêu</span>
          <strong>{plannedServices.length}</strong>
          <small>Theo kế hoạch / Chưa tích hợp</small>
        </article>

        <article>
          <span>Audit gần đây</span>
          <strong>{systemAuditLogs.length}</strong>
          <small>Dữ liệu minh họa (Mock)</small>
        </article>
      </section>

      <section className="admin-system-card">
        <div className="admin-system-card__heading">
          <div>
            <span>SYSTEM HEALTH · MOCK DEMO</span>
            <h2>Trạng thái hạ tầng &amp; dịch vụ</h2>
            <p>
              Phân biệt các thành phần đã triển khai thực tế và các dịch vụ thuộc kiến trúc mục tiêu của học phần.
            </p>
          </div>

          <span className="admin-system-health-badge">
            <i />
            {healthyCount}/{operationalServices.length} Operational
          </span>
        </div>

        <div className="admin-system-services">
          {systemServices.map((service) => (
            <article
              key={service.id}
              className="admin-system-service"
            >
              <div className="admin-system-service__icon">
                {service.name.charAt(0)}
              </div>

              <div className="admin-system-service__info">
                <strong>{service.name}</strong>
                <span>{service.description}</span>
              </div>

              <div className="admin-system-service__latency">
                <span>
                  {service.latency
                    ? 'Latency (Mock)'
                    : 'Tích hợp'}
                </span>
                <strong>
                  {service.latency || 'Theo kế hoạch'}
                </strong>
              </div>

              <span
                className={`admin-system-service__status admin-system-service__status--${service.status.toLowerCase()}`}
              >
                <i />
                {systemStatusLabels[service.status]}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section className="admin-system-card">
        <div className="admin-system-card__heading">
          <div>
            <span>RECENT ACTIVITY</span>
            <h2>Hoạt động gần đây</h2>
          </div>
        </div>

        <div className="admin-system-recent">
          {systemAuditLogs.slice(0, 4).map((log) => (
            <div
              key={log.id}
              className="admin-system-recent__item"
            >
              <div>
                <strong>{log.description}</strong>
                <span>
                  {log.actor} · {log.target}
                </span>
              </div>

              <time>{log.time}</time>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default SystemOverview
