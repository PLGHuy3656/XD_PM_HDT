import './ErrorMessage.css'

export function ErrorMessage({
  title = 'Đã xảy ra lỗi',
  message = 'Không thể tải dữ liệu từ máy chủ. Vui lòng thử lại.',
  onRetry = null,
  retryLabel = 'Thử lại',
  className = '',
}) {
  return (
    <div className={`error-message-panel ${className}`} role="alert">
      <div className="error-message-content">
        <span className="error-message-icon" aria-hidden="true">⚠️</span>
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
