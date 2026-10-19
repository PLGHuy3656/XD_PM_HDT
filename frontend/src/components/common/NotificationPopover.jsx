import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import './NotificationPopover.css'

const initialNotifications = [
  {
    id: 1,
    type: 'danger',
    title: 'Nhiệt độ vượt ngưỡng',
    message: 'Khu vực A đang ghi nhận 31.8°C.',
    time: '5 phút trước',
    unread: true,
  },
  {
    id: 2,
    type: 'warning',
    title: 'Phát hiện bất thường AI',
    message: 'Camera lối vào phát hiện chuyển động bất thường.',
    time: '18 phút trước',
    unread: true,
  },
  {
    id: 3,
    type: 'info',
    title: 'Thiết bị đã kết nối lại',
    message: 'ESP32-Z02 đã khôi phục kết nối.',
    time: '1 giờ trước',
    unread: false,
  },
]

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
      <path d="M5 12h14" />
      <path d="m14 7 5 5-5 5" />
    </svg>
  )
}

function NotificationPopover() {
  const navigate = useNavigate()
  const containerRef = useRef(null)

  const [open, setOpen] = useState(false)
  const [notifications, setNotifications] =
    useState(initialNotifications)

  const unreadCount = useMemo(
    () =>
      notifications.filter(
        (notification) => notification.unread,
      ).length,
    [notifications],
  )

  useEffect(() => {
    if (!open) return undefined

    const handleOutsideClick = (event) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target)
      ) {
        setOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener(
        'mousedown',
        handleOutsideClick,
      )
      document.removeEventListener('keydown', handleEscape)
    }
  }, [open])

  const handleNotificationClick = (id) => {
    setNotifications((current) =>
      current.map((notification) =>
        notification.id === id
          ? { ...notification, unread: false }
          : notification,
      ),
    )
  }

  const handleMarkAllRead = () => {
    setNotifications((current) =>
      current.map((notification) => ({
        ...notification,
        unread: false,
      })),
    )
  }

  const handleViewAll = () => {
    setOpen(false)
    navigate('/owner/alerts')
  }

  return (
    <div
      className="notification-popover"
      ref={containerRef}
    >
      <button
        type="button"
        className={`notification-button ${
          open ? 'notification-button--active' : ''
        }`}
        aria-label={
          unreadCount > 0
            ? `${unreadCount} thông báo chưa đọc`
            : 'Thông báo'
        }
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <BellIcon />

        {unreadCount > 0 && (
          <span className="notification-badge">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="notification-panel">
          <div className="notification-panel__header">
            <div>
              <span className="notification-panel__eyebrow">
                Trung tâm cảnh báo
              </span>

              <h3>Thông báo</h3>
            </div>

            {unreadCount > 0 && (
              <span className="notification-panel__count">
                {unreadCount} mới
              </span>
            )}
          </div>

          <div className="notification-panel__toolbar">
            <span>Cập nhật gần đây</span>

            <button
              type="button"
              onClick={handleMarkAllRead}
              disabled={unreadCount === 0}
            >
              Đánh dấu đã đọc
            </button>
          </div>

          <div className="notification-list">
            {notifications.map((notification) => (
              <button
                type="button"
                key={notification.id}
                className={`notification-item ${
                  notification.unread
                    ? 'notification-item--unread'
                    : ''
                }`}
                onClick={() =>
                  handleNotificationClick(notification.id)
                }
              >
                <span
                  className={`notification-item__status notification-item__status--${notification.type}`}
                />

                <span className="notification-item__content">
                  <span className="notification-item__title-row">
                    <strong>{notification.title}</strong>

                    {notification.unread && (
                      <span className="notification-item__unread" />
                    )}
                  </span>

                  <span className="notification-item__message">
                    {notification.message}
                  </span>

                  <span className="notification-item__time">
                    {notification.time}
                  </span>
                </span>
              </button>
            ))}
          </div>

          <button
            type="button"
            className="notification-panel__footer"
            onClick={handleViewAll}
          >
            <span>Xem tất cả cảnh báo</span>
            <ArrowIcon />
          </button>
        </div>
      )}
    </div>
  )
}

export default NotificationPopover