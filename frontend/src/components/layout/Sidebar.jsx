import { NavLink } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import { navigationByRole } from '../../config/navigation'
import './Sidebar.css'

const icons = {
  home: (
    <>
      <path d="M3 11.5 12 4l9 7.5" />
      <path d="M5.5 10.5V20h13v-9.5" />
      <path d="M9.5 20v-6h5v6" />
    </>
  ),

  environment: (
    <>
      <path d="M7.5 14.5V6a2 2 0 0 1 4 0v8.5a4 4 0 1 1-4 0Z" />
      <path d="M9.5 16.5V9" />
      <path d="M17.5 5.5s-3 3.4-3 5.8a3 3 0 0 0 6 0c0-2.4-3-5.8-3-5.8Z" />
    </>
  ),

  device: (
    <>
      <path d="M5 6h14v12H5z" />
      <path d="M9 3h6v3" />
      <path d="M9 18v3" />
      <path d="M15 18v3" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),

  camera: (
    <>
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <circle cx="12" cy="12.5" r="3.5" />
      <path d="M8 6l1.5-2h5L16 6" />
    </>
  ),

  alert: (
    <>
      <path d="M12 3 3.5 19h17L12 3Z" />
      <path d="M12 9v4" />
      <path d="M12 16h.01" />
    </>
  ),

  analytics: (
    <>
      <path d="M4 20V10" />
      <path d="M10 20V4" />
      <path d="M16 20v-7" />
      <path d="M22 20H2" />
    </>
  ),

  diagnostics: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m16 16 5 5" />
      <path d="M8 11h6" />
      <path d="M11 8v6" />
    </>
  ),

  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <circle cx="17" cy="9" r="2.5" />
      <path d="M3 20c0-4 2.5-6 6-6s6 2 6 6" />
      <path d="M15 15c3.5 0 6 1.5 6 5" />
    </>
  ),

  farm: (
    <>
      <path d="M3 20V9l5-4 5 4v11" />
      <path d="M13 12l4-3 4 3v8" />
      <path d="M6 20v-5h4v5" />
      <path d="M16 20v-4h2v4" />
      <path d="M2 20h20" />
    </>
),

  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3" />
      <path d="M12 19v3" />
      <path d="M2 12h3" />
      <path d="M19 12h3" />
      <path d="m5 5 2 2" />
      <path d="m17 17 2 2" />
      <path d="m19 5-2 2" />
      <path d="m7 17-2 2" />
    </>
  ),
}

function MenuIcon({ name }) {
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
      {icons[name]}
    </svg>
  )
}

function Sidebar() {
  const { user } = useAuth()

  const menuItems = navigationByRole[user?.role] ?? []

  return (
    <aside className="sidebar">
      <div className="sidebar-logo-area">
        <img
          src="/Logo.png"
          alt="NestMate"
          className="sidebar-logo"
        />
      </div>

      <nav
        className="sidebar-nav"
        aria-label="Điều hướng chính"
      >
        {menuItems.map((item) => (
          <NavLink
            key={item.id}
            to={item.path}
            aria-label={item.label}
            className={({ isActive }) =>
              `sidebar-link${isActive ? ' active' : ''}`
            }
          >
            <MenuIcon name={item.icon} />

            <span
              className="sidebar-tooltip"
              role="tooltip"
            >
              {item.label}
            </span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}

export default Sidebar