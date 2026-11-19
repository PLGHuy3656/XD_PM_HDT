import {
  systemAuditLogs,
  systemServices,
  systemStatusLabels,
} from './systemMockData'
import { USE_MOCK } from '../../../../api/config.js'

function SystemOverview({ services: propServices }) {
  const currentServices = propServices && propServices.length > 0 ? propServices : (USE_MOCK ? systemServices : [])
  const auditLogs = USE_MOCK ? systemAuditLogs : []

  const operationalServices = currentServices.filter(
    (service) => service.tier === 'CURRENT' || !service.tier,
  )

  const plannedServices = currentServices.filter(
    (service) => service.tier === 'PLANNED',
  )

  const healthyCount = operationalServices.filter(
    (service) => service.status === 'HEALTHY' || service.status === 'healthy',
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
          <strong>{auditLogs.length}</strong>
          <small>{USE_MOCK ? 'Dữ liệu minh họa (Mock)' : 'Chưa tích hợp API nhật ký'}</small>
        </article>
      </section>

      <section className="admin-system-card">
        <div className="admin-system-card__heading">
          <div>
            <span>{USE_MOCK ? 'SYSTEM HEALTH · MOCK DEMO' : 'SYSTEM HEALTH'}</span>
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
          {currentServices.map((service) => (
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
                    ? 'Độ trễ'
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
                {systemStatusLabels[service.status] || service.status}
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
          {auditLogs.length === 0 ? (
            <div style={{ padding: '1rem 0', color: '#64748b', fontSize: '0.9rem' }}>
              Chưa có dữ liệu nhật ký hoạt động.
            </div>
          ) : (
            auditLogs.slice(0, 4).map((log) => (
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
            ))
          )}
        </div>
      </section>
    </div>
  )
}

export default SystemOverview
