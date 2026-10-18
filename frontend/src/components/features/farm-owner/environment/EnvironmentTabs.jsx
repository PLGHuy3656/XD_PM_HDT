import { NavLink } from 'react-router-dom'

function EnvironmentTabs() {
  return (
    <nav className="environment-subnav" aria-label="Điều hướng môi trường">
      <NavLink
        to="/owner/environment"
        end
        className={({ isActive }) =>
          `environment-subnav__tab ${isActive ? 'active' : ''}`
        }
      >
        <span className="environment-subnav__icon">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 19V10" />
            <path d="M10 19V5" />
            <path d="M16 19v-7" />
            <path d="M22 19V8" />
          </svg>
        </span>

        <span>
          <strong>Giám sát</strong>
          <small>Dữ liệu & xu hướng</small>
        </span>
      </NavLink>

      <NavLink
        to="/owner/environment/control"
        className={({ isActive }) =>
          `environment-subnav__tab ${isActive ? 'active' : ''}`
        }
      >
        <span className="environment-subnav__icon">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h10" />
            <path d="M18 7h2" />
            <circle cx="16" cy="7" r="2" />

            <path d="M4 17h2" />
            <path d="M10 17h10" />
            <circle cx="8" cy="17" r="2" />
          </svg>
        </span>

        <span>
          <strong>Điều khiển</strong>
          <small>AUTO / MANUAL</small>
        </span>
      </NavLink>
    </nav>
  )
}

export default EnvironmentTabs