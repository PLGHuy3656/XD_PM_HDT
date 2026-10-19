function AlertItem({
  title,
  description,
  time,
  level = 'warning',
}) {
  return (
    <article className="alert-item">
      <div className={`alert-indicator alert-${level}`}>
        <span>!</span>
      </div>

      <div className="alert-copy">
        <strong>{title}</strong>
        <span>{description}</span>
      </div>

      <time>{time}</time>
    </article>
  )
}

export default AlertItem