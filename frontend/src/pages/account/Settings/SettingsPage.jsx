import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import AppLayout from '../../../components/layout/AppLayout'
import { useAuth } from '../../../context/AuthContext'
import './SettingsPage.css'

const roleLabels = {
  FARM_OWNER: 'Chủ trại',
  TECHNICIAN: 'Kỹ thuật viên',
  ADMIN: 'Quản trị viên',
}

function SettingsPage() {
  const navigate = useNavigate()
  const { user, updateProfile, logout } = useAuth()

  const [profile, setProfile] = useState({
    name: user?.name ?? '',
    phone: user?.phone ?? '',
  })

  const [notifications, setNotifications] = useState({
    push: true,
    environment: true,
    aiThreat: true,
    quietHours: false,
  })

  const [saved, setSaved] = useState(false)

  const initials = (user?.name || 'NestMate User')
    .split(' ')
    .filter(Boolean)
    .map((part) => part[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  const handleProfileChange = (event) => {
    const { name, value } = event.target

    setProfile((current) => ({
      ...current,
      [name]: value,
    }))

    setSaved(false)
  }

  const toggleNotification = (key) => {
    setNotifications((current) => ({
      ...current,
      [key]: !current[key],
    }))

    setSaved(false)
  }

  const handleSave = (event) => {
    event.preventDefault()

    updateProfile(profile)

    localStorage.setItem(
      'nestmate_notification_settings',
      JSON.stringify(notifications),
    )

    setSaved(true)
  }

  const handleLogout = () => {
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <AppLayout>
      <main className="account-settings">
        <header className="account-settings__heading">
          <div>
            <span>ACCOUNT SETTINGS</span>
            <h1>Cài đặt tài khoản</h1>
            <p>
              Quản lý thông tin cá nhân, thông báo và bảo mật tài khoản
              NestMate.
            </p>
          </div>
        </header>

        <section className="account-profile-card">
          <div className="account-profile-card__identity">
            <div className="account-profile-avatar">
              {initials}
            </div>

            <div>
              <span className="account-profile-card__label">
                TÀI KHOẢN NESTMATE
              </span>

              <h2>{user?.name}</h2>

              <span className="account-role-badge">
                {roleLabels[user?.role] ?? 'Người dùng'}
              </span>
            </div>
          </div>

          <div className="account-profile-card__meta">
            <div>
              <span>Email</span>
              <strong>{user?.email}</strong>
            </div>

            <div>
              <span>Số điện thoại</span>
              <strong>{user?.phone || 'Chưa cập nhật'}</strong>
            </div>

            <button
              type="button"
              className="settings-logout-button"
              onClick={handleLogout}
            >
              Đăng xuất
            </button>
          </div>
        </section>

        <form
          className="settings-grid"
          onSubmit={handleSave}
        >
          <section className="settings-card settings-card--profile">
            <div className="settings-card__heading">
              <div className="settings-card__icon">
                U
              </div>

              <div>
                <h2>Thông tin cá nhân</h2>
                <p>Cập nhật thông tin hiển thị của tài khoản.</p>
              </div>
            </div>

            <div className="settings-fields">
              <label>
                <span>Họ và tên</span>

                <input
                  type="text"
                  name="name"
                  value={profile.name}
                  onChange={handleProfileChange}
                  placeholder="Nhập họ và tên"
                />
              </label>

              <label>
                <span>Email</span>

                <input
                  type="email"
                  value={user?.email ?? ''}
                  disabled
                />

                <small>
                  Email đăng nhập sẽ được quản lý bởi hệ thống.
                </small>
              </label>

              <label>
                <span>Số điện thoại</span>

                <input
                  type="tel"
                  name="phone"
                  value={profile.phone}
                  onChange={handleProfileChange}
                  placeholder="Thêm số điện thoại"
                />
              </label>
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card__heading">
              <div className="settings-card__icon">
                N
              </div>

              <div>
                <h2>Thông báo</h2>
                <p>Chọn những sự kiện bạn muốn nhận cảnh báo.</p>
              </div>
            </div>

            <div className="notification-settings">
              <NotificationRow
                title="Push Notification"
                description="Thông báo trên trình duyệt hoặc ứng dụng."
                enabled={notifications.push}
                onToggle={() => toggleNotification('push')}
              />

              <NotificationRow
                title="Cảnh báo môi trường"
                description="Nhiệt độ, độ ẩm và chất lượng không khí bất thường."
                enabled={notifications.environment}
                onToggle={() =>
                  toggleNotification('environment')
                }
              />

              <NotificationRow
                title="AI & Threat Alert"
                description="Phát hiện bất thường, động vật gây hại và sự kiện AI."
                enabled={notifications.aiThreat}
                onToggle={() =>
                  toggleNotification('aiThreat')
                }
              />

              <NotificationRow
                title="Giờ im lặng"
                description="Giảm thông báo thông thường, vẫn giữ cảnh báo nghiêm trọng."
                enabled={notifications.quietHours}
                onToggle={() =>
                  toggleNotification('quietHours')
                }
              />
            </div>
          </section>

          <section className="settings-card">
            <div className="settings-card__heading">
              <div className="settings-card__icon">
                S
              </div>

              <div>
                <h2>Bảo mật</h2>
                <p>Quản lý thông tin bảo mật của tài khoản.</p>
              </div>
            </div>

            <div className="security-panel">
              <div>
                <span>Mật khẩu</span>
                <strong>••••••••••••</strong>
                <p>
                  Thay đổi mật khẩu định kỳ để bảo vệ tài khoản.
                </p>
              </div>

              <button
                type="button"
                className="settings-secondary-button"
              >
                Đổi mật khẩu
              </button>
            </div>

            <div className="security-panel">
              <div>
                <span>Phiên đăng nhập</span>
                <strong>Thiết bị hiện tại</strong>
                <p>
                  Bạn đang đăng nhập với quyền{' '}
                  {roleLabels[user?.role] ?? 'Người dùng'}.
                </p>
              </div>

              <span className="session-status">
                Đang hoạt động
              </span>
            </div>
          </section>

          <div className="settings-save-bar">
            <div>
              {saved ? (
                <span className="settings-saved-message">
                  ✓ Đã lưu thay đổi
                </span>
              ) : (
                <span>
                  Các thay đổi chỉ áp dụng cho tài khoản hiện tại.
                </span>
              )}
            </div>

            <button
              type="submit"
              className="settings-save-button"
            >
              Lưu thay đổi
            </button>
          </div>
        </form>
      </main>
    </AppLayout>
  )
}

function NotificationRow({
  title,
  description,
  enabled,
  onToggle,
}) {
  return (
    <div className="notification-setting-row">
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>

      <button
        type="button"
        className={`settings-switch ${
          enabled ? 'settings-switch--active' : ''
        }`}
        onClick={onToggle}
        aria-pressed={enabled}
        aria-label={`${enabled ? 'Tắt' : 'Bật'} ${title}`}
      >
        <span />
      </button>
    </div>
  )
}

export default SettingsPage