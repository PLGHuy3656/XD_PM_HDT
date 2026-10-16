import { services } from './dashboardMockData'

function StatusDot({ status = 'healthy' }) {
  return <span className={`admin-status-dot ${status}`} />
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

function SystemHealthPanel({ onOpen }) {
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
        {services.map((service) => (
          <div className="admin-service" key={service.id}>
            <StatusDot status={service.status} />
            <span>{service.name}</span>
          </div>
        ))}
      </div>

      <div className="admin-health-strip__end">
        <div>
          <StatusDot />
          <strong>5 / 5</strong>
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
