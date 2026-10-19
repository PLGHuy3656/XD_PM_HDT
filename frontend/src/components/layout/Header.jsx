import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NotificationPopover from '../common/NotificationPopover'
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
  const navigate = useNavigate()
  const { user, logout } = useAuth()

  const [profileOpen, setProfileOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)

  const profileRef = useRef(null)

  const displayName = user?.name || 'NestMate User'
  const roleLabel = roleLabels[user?.role] || 'Người dùng'

  const initials = displayName
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (
        profileRef.current &&
        !profileRef.current.contains(event.target)
      ) {
        setProfileOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)

    return () => {
      document.removeEventListener(
        'mousedown',
        handleOutsideClick,
      )
    }
  }, [])

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 8)
    }

    handleScroll()

    window.addEventListener('scroll', handleScroll, {
      passive: true,
    })

    return () => {
      window.removeEventListener('scroll', handleScroll)
    }
  }, [])

  const handleSettings = () => {
    setProfileOpen(false)
    navigate('/settings')
  }

  const handleLogout = () => {
    setProfileOpen(false)
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <header
      className={`app-header ${
        scrolled ? 'app-header--scrolled' : ''
      }`}
    >
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
        <NotificationPopover />

        <div className="header-divider" />

        <div
          className="header-profile-menu"
          ref={profileRef}
        >
          <button
            type="button"
            className={`header-profile ${
              profileOpen ? 'header-profile--active' : ''
            }`}
            onClick={() =>
              setProfileOpen((current) => !current)
            }
            aria-expanded={profileOpen}
          >
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
          </button>

          {profileOpen && (
            <div className="profile-dropdown">
              <div className="profile-dropdown__identity">
                <strong>{displayName}</strong>
                <span>{user?.email}</span>
              </div>

              <div className="profile-dropdown__divider" />

              <button
                type="button"
                onClick={handleSettings}
              >
                <span>Cài đặt tài khoản</span>
                <small>Thông tin & thông báo</small>
              </button>

              <div className="profile-dropdown__divider" />

              <button
                type="button"
                className="profile-dropdown__logout"
                onClick={handleLogout}
              >
                Đăng xuất
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Header