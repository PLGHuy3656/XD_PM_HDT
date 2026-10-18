function AlertTrendPanel({ data }) {
  const maxValue = Math.max(
    ...data.map(
      (item) =>
        item.critical +
        item.high +
        item.medium +
        item.low,
    ),
  )

  return (
    <section className="analytics-card alert-trend-panel">
      <header className="analytics-card-heading">
        <div>
          <span className="analytics-card-eyebrow">
            ALERT HISTORY
          </span>

          <h2>Xu hướng cảnh báo</h2>

          <p>
            Tổng số cảnh báo phát sinh theo ngày.
          </p>
        </div>

        <span className="analytics-period-badge">
          7 ngày
        </span>
      </header>

      <div className="alert-trend-chart">
        {data.map((item) => {
          const total =
            item.critical +
            item.high +
            item.medium +
            item.low

          return (
            <article key={item.label}>
              <strong>{total}</strong>

              <div className="alert-trend-track">
                <span
                  style={{
                    height: `${Math.max(
                      (total / maxValue) * 100,
                      8,
                    )}%`,
                  }}
                />
              </div>

              <small>{item.label}</small>
            </article>
          )
        })}
      </div>

      <div className="alert-trend-summary">
        <span>
          <i className="critical" />
          Critical
        </span>

        <span>
          <i className="high" />
          High
        </span>

        <span>
          <i className="medium" />
          Medium
        </span>

        <span>
          <i className="low" />
          Low
        </span>
      </div>
    </section>
  )
}

export default AlertTrendPanel