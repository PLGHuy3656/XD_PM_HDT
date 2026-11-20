import { services } from './dashboardMockData'
import { USE_MOCK } from '../../../../api/config.js'

// INT01-R1: HEALTHY | DEGRADED | UNAVAILABLE | NOT_DEPLOYED
const DOT_CLASS = {
  healthy: 'healthy',
  degraded: 'warning',
  warning: 'warning',
  unavailable: 'danger',
  down: 'danger',
  not_deployed: 'planned',
  planned: 'planned',
}

function StatusDot({ status = 'healthy' }) {
  return <span className={`admin-status-dot ${DOT_CLASS[status] || 'danger'}`} />
}

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

function SystemHealthPanel({ onOpen, services: propServices }) {
  const currentServices = propServices && propServices.length > 0 ? propServices : (USE_MOCK ? services : [])
  const deployedServices = currentServices.filter(
    (service) => service.status !== 'NOT_DEPLOYED' && service.tier !== 'PLANNED',
  )
  const healthyCount = deployedServices.filter(
    (service) => service.status === 'healthy' || service.status === 'HEALTHY',
  ).length

  return (
    <button
      type="button"
      className="admin-health-strip"
      onClick={() => onOpen('/admin/system')}
    >
      <div className="admin-health-strip__title">
        <span>SYSTEM HEALTH</span>
        <strong>Hạ tầng hệ thống</strong>
      </div>

      <div className="admin-health-strip__services">
        {currentServices.map((service) => (
          <div className="admin-service" key={service.id}>
            <StatusDot status={service.status?.toLowerCase() || 'healthy'} />
            <span>{service.name}</span>
          </div>
        ))}
      </div>

      <div className="admin-health-strip__end">
        <div>
          <StatusDot />
          <strong>
            {healthyCount} / {deployedServices.length}
          </strong>
          <span>Operational</span>
        </div>

        <span className="admin-health-strip__arrow">
          <ArrowIcon />
        </span>
      </div>
    </button>
  )
}


export default SystemHealthPanel
