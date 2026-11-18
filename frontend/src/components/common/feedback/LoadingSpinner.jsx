import './LoadingSpinner.css'

export function LoadingSpinner({
  size = 'md',
  message = '',
  className = '',
}) {
  return (
    <div className={`loading-spinner-wrapper ${className}`} role="status">
      <div className={`loading-spinner loading-spinner--${size}`} />
      {message && <span className="loading-spinner-message">{message}</span>}
      <span className="sr-only">Đang tải...</span>
    </div>
  )
}

export default LoadingSpinner
