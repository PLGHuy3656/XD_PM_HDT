import './EmptyState.css'

export function EmptyState({
  title = 'Không có dữ liệu',
  description = 'Hiện tại chưa có dữ liệu nào được ghi nhận.',
  icon = '📋',
  action = null,
  className = '',
}) {
  return (
    <div className={`empty-state ${className}`} role="status">
      <div className="empty-state-icon" aria-hidden="true">
        {icon}
      </div>
      <h3 className="empty-state-title">{title}</h3>
      {description && <p className="empty-state-description">{description}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  )
}

export default EmptyState
