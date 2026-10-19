function AlertDistribution({ data }) {
  const total = data.reduce(
    (sum, item) => sum + item.count,
    0,
  )

  return (
    <section className="analytics-card alert-distribution-card">
      <header className="analytics-card-heading compact">
        <div>
          <span className="analytics-card-eyebrow">
            ALERT HISTORY
          </span>

          <h2>Phân bố cảnh báo</h2>

          <p>
            Tổng hợp cảnh báo theo mức độ trong kỳ.
          </p>
        </div>

        <span className="analytics-period-badge">
          {total} cảnh báo
        </span>
      </header>

      <div className="alert-distribution-list">
        {data.map((item) => (
          <article key={item.severity}>
            <span
              className={`analytics-severity-dot ${item.severity.toLowerCase()}`}
            />

            <span>{item.severity}</span>

            <strong>{item.count}</strong>
          </article>
        ))}
      </div>
    </section>
  )
}

export default AlertDistribution