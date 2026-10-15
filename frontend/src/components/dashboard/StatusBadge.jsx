function StatusBadge({
  children,
  status = 'normal',
}) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-badge-dot" />
      {children}
    </span>
  )
}

export default StatusBadge