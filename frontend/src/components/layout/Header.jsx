import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NotificationPopover from '../common/NotificationPopover'
import { useAuth } from '../../context/AuthContext'
import { formatHeaderEnvironment } from '../../features/telemetry/adapters/telemetryAdapter'
import { useFarmTelemetry } from '../../features/telemetry/farmTelemetryPoller'
import { isSimulatedTelemetry, formatRelativeTime } from '../../features/telemetry/provenance'
import { clearActiveFarm, useActiveFarm } from '../../features/farms/activeFarmStore'
import { USE_MOCK } from '../../api/config'
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

const roleSearchTargets = {
  ADMIN: [
    { label: 'Tổng quan quản trị', path: '/admin/dashboard', keywords: 'dashboard tong quan quan tri' },
    { label: 'Quản lý người dùng', path: '/admin/users', keywords: 'users nguoi dung tai khoan' },
    { label: 'Quản lý nhà yến', path: '/admin/farms', keywords: 'farms nha yen phan cong' },
    { label: 'Quản lý thiết bị', path: '/admin/devices', keywords: 'devices thiet bi node' },
    { label: 'Thông báo', path: '/notifications', keywords: 'notifications thong bao canh bao' },
    { label: 'Hệ thống & Hạ tầng', path: '/admin/system', keywords: 'system he thong ha tang' },
    { label: 'Cài đặt tài khoản', path: '/settings', keywords: 'settings cai dat' },
  ],
  FARM_OWNER: [
    { label: 'Tổng quan nhà yến', path: '/owner/dashboard', keywords: 'dashboard tong quan' },
    { label: 'Quản lý nhà yến & Khu vực', path: '/owner/farms', keywords: 'farms zones nha yen khu vuc' },
    { label: 'Môi trường nhà yến', path: '/owner/environment', keywords: 'environment moi truong nhiet do am' },
    { label: 'Điều khiển môi trường', path: '/owner/environment/control', keywords: 'control dieu khien' },
    { label: 'Thiết bị', path: '/owner/devices', keywords: 'devices thiet bi' },
    { label: 'Giám sát chim yến', path: '/owner/swiftlets', keywords: 'swiftlets chim yen camera ai' },
    { label: 'Cảnh báo', path: '/owner/alerts', keywords: 'alerts canh bao' },
    { label: 'Phân tích', path: '/owner/analytics', keywords: 'analytics phan tich' },
    { label: 'Cài đặt tài khoản', path: '/settings', keywords: 'settings cai dat' },
  ],
  TECHNICIAN: [
    { label: 'Tổng quan kỹ thuật', path: '/technician/dashboard', keywords: 'dashboard tong quan' },
    { label: 'Môi trường phụ trách', path: '/technician/environment', keywords: 'environment moi truong' },
    { label: 'Thiết bị phụ trách', path: '/technician/devices', keywords: 'devices thiet bi' },
    { label: 'Lắp đặt thiết bị', path: '/technician/installation', keywords: 'installation lap dat' },
    { label: 'Chẩn đoán thiết bị', path: '/technician/diagnostics', keywords: 'diagnostics chan doan' },
    { label: 'Cảnh báo & Yêu cầu', path: '/technician/alerts', keywords: 'alerts canh bao yeu cau' },
    { label: 'Cài đặt tài khoản', path: '/settings', keywords: 'settings cai dat' },
  ],
}

function Header() {
  const navigate = useNavigate()
  const { user, logout, isMockMode } = useAuth()
  // INT01-R1: Header telemetry follows the farm the user selected on a page (never "first farm")
  const activeFarm = useActiveFarm(user?.id)
  const farmTelemetry = useFarmTelemetry(USE_MOCK ? null : activeFarm?.farmId || null)
  const headerState = USE_MOCK
    ? { kind: 'mock', label: 'Dữ liệu minh họa (Mock)' }
    : !activeFarm
      ? { kind: 'none', label: 'Chưa chọn nhà yến' }
      : farmTelemetry.status === 'forbidden'
        ? { kind: 'error', label: 'Không có quyền xem nhà yến này' }
        : farmTelemetry.status === 'unavailable'
          ? { kind: 'error', label: 'Mất kết nối dịch vụ IoT' }
          : farmTelemetry.status === 'error'
            ? { kind: 'error', label: 'Lỗi tải số liệu' }
            : farmTelemetry.status === 'empty'
              ? { kind: 'empty', label: 'Chưa có dữ liệu cảm biến' }
              : farmTelemetry.status === 'loading'
                ? { kind: 'loading', label: 'Đang tải…' }
                : farmTelemetry.status === 'stale'
                  ? { kind: 'stale', label: `Dữ liệu cũ · ${formatRelativeTime(farmTelemetry.telemetry?.timestamp)}` }
                  : isSimulatedTelemetry(farmTelemetry.telemetry)
                    ? { kind: 'simulated', label: 'Mô phỏng · ESP32 Simulator' }
                    : { kind: 'live', label: 'Trực tiếp' }
  const showValues = USE_MOCK || ['ok', 'stale'].includes(farmTelemetry.status)

  const [profileOpen, setProfileOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchFocused, setSearchFocused] = useState(false)

  const profileRef = useRef(null)
  const searchRef = useRef(null)

  const displayName = user?.name || 'NestMate User'
  const roleLabel = roleLabels[user?.role] || 'Người dùng'
  const displayEnvironment = formatHeaderEnvironment(
    USE_MOCK ? null : showValues ? farmTelemetry.telemetry : null,
    isMockMode,
  )

  useEffect(() => {
    // A farm the Gateway refuses (e.g. reassigned) must not stay selected in the Header
    if (!USE_MOCK && farmTelemetry.status === 'forbidden') clearActiveFarm()
  }, [farmTelemetry.status])

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
      <div className="header-search" ref={searchRef} style={{ position: 'relative' }}>
        <SearchIcon />

        <input
          type="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onFocus={() => setSearchFocused(true)}
          onBlur={() => setTimeout(() => setSearchFocused(false), 150)}
          onKeyDown={(e) => {
            const targets = roleSearchTargets[user?.role] || []
            const q = searchQuery.trim().toLowerCase()
            const matched = q
              ? targets.filter(
                  (t) => t.label.toLowerCase().includes(q) || t.keywords.includes(q),
                )
              : []
            if (e.key === 'Enter' && matched.length > 0) {
              setSearchQuery('')
              setSearchFocused(false)
              navigate(matched[0].path)
            } else if (e.key === 'Escape') {
              setSearchFocused(false)
            }
          }}
          placeholder="Đi nhanh tới trang..."
          aria-label="Tìm kiếm trang theo vai trò"
        />

        {searchFocused && searchQuery.trim() && (
          <div
            style={{
              position: 'absolute',
              top: 'calc(100% + 6px)',
              left: 0,
              right: 0,
              background: '#fffdf9',
              border: '1px solid #e2dbcf',
              borderRadius: '12px',
              boxShadow: '0 12px 30px rgba(15, 29, 47, 0.14)',
              zIndex: 120,
              overflow: 'hidden',
            }}
          >
            {(roleSearchTargets[user?.role] || [])
              .filter((t) => {
                const q = searchQuery.trim().toLowerCase()
                return t.label.toLowerCase().includes(q) || t.keywords.includes(q)
              })
              .map((item) => (
                <button
                  key={item.path}
                  type="button"
                  onMouseDown={() => {
                    setSearchQuery('')
                    setSearchFocused(false)
                    navigate(item.path)
                  }}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '10px 14px',
                    border: 0,
                    background: 'transparent',
                    color: '#172b46',
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  {item.label}
                </button>
              ))}
          </div>
        )}
      </div>

      <div
        className={`header-environment header-environment--${headerState.kind}`}
        data-testid="header-telemetry"
        data-telemetry-state={headerState.kind}
        title={activeFarm?.farmName ? `Số liệu của: ${activeFarm.farmName}` : headerState.label}
      >
        <div className="header-environment-context">
          <span>{activeFarm?.farmName || (USE_MOCK ? 'Mock' : 'Nhà yến')}</span>
          <strong>{headerState.label}</strong>
        </div>
        {displayEnvironment.map((item) => (
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