import { useAuth } from '../../context/AuthContext'
import './Header.css'

function SearchIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
    >
      <circle cx="11" cy="11" r="6.5" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function BellIcon() {
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
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10 21h4" />
    </svg>
  )
}

const roleLabels = {
  FARM_OWNER: 'Chủ trại',
  TECHNICIAN: 'Kỹ thuật viên',
  ADMIN: 'Quản trị viên',
}

const environmentData = [
  {
    id: 'temperature',
    label: 'Nhiệt độ',
    value: '28.5°C',
  },
  {
    id: 'humidity',
    label: 'Độ ẩm',
    value: '78%',
  },
  {
    id: 'co2',
    label: 'CO₂',
    value: '620 ppm',
  },
  {
    id: 'light',
    label: 'Ánh sáng',
    value: '120 lux',
  },
]

function Header() {
  const { user } = useAuth()

  const displayName = user?.name || 'NestMate User'
  const roleLabel = roleLabels[user?.role] || 'Người dùng'

  const initials = displayName
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header className="app-header">
      <div className="header-search">
        <SearchIcon />

        <input
          type="search"
          placeholder="Tìm kiếm trong NestMate..."
          aria-label="Tìm kiếm"
        />
      </div>

      <div className="header-environment">
        {environmentData.map((item) => (
          <div
            className="header-environment-item"
            key={item.id}
          >
            <span>{item.label}</span>
            <strong>{item.value}</strong>
          </div>
        ))}
      </div>

      <div className="header-actions">
        <button
          type="button"
          className="notification-button"
          aria-label="Thông báo"
        >
          <BellIcon />
          <span className="notification-dot" />
        </button>

        <div className="header-divider" />

        <div className="header-profile">
          <div className="profile-copy">
            <strong>{displayName}</strong>
            <span>{roleLabel}</span>
          </div>

          <div
            className="profile-avatar"
            aria-label={displayName}
          >
            {initials}
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header