import './ErrorMessage.css'

function StatusIcon({ variant }) {
  if (variant === 'warning') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="error-message-svg">
        <path d="m10.29 3.86-8.6 14.9A1.5 1.5 0 0 0 3 21h18a1.5 1.5 0 0 0 1.31-2.24l-8.6-14.9a1.5 1.5 0 0 0-2.62 0Z" />
        <line x1="12" y1="9" x2="12" y2="13.5" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    )
  }

  if (variant === 'info') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true" className="error-message-svg">
        <circle cx="12" cy="12" r="9" />
        <line x1="12" y1="11" x2="12" y2="16" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true" className="error-message-svg">
      <circle cx="12" cy="12" r="9" />
      <line x1="12" y1="8" x2="12" y2="13" />
      <line x1="12" y1="16.5" x2="12.01" y2="16.5" />
    </svg>
  )
}

export function ErrorMessage({
  title = 'Đã xảy ra lỗi',
  message = 'Không thể tải dữ liệu từ máy chủ. Vui lòng thử lại.',
  onRetry = null,
  retryLabel = 'Thử lại',
  variant = 'danger',
  className = '',
}) {
  const safeVariant = ['danger', 'warning', 'info'].includes(variant) ? variant : 'danger'

  return (
    <div
      className={`error-message-panel error-message-panel--${safeVariant} ${className}`.trim()}
      role={safeVariant === 'info' ? 'status' : 'alert'}
    >
      <div className="error-message-content">
        <span className="error-message-icon" aria-hidden="true">
          <StatusIcon variant={safeVariant} />
        </span>
        <div className="error-message-texts">
          <strong className="error-message-title">{title}</strong>
          <p className="error-message-desc">{message}</p>
        </div>
      </div>
      {onRetry && (
        <button
          type="button"
          className="error-retry-btn"
          onClick={onRetry}
        >
          {retryLabel}
        </button>
      )}
    </div>
  )
}

export default ErrorMessage
