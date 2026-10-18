function YieldTrendChart({ data }) {
  const maxValue = Math.max(
    ...data.map((item) => item.value),
  )

  return (
    <section className="analytics-card yield-trend-card">
      <header className="analytics-card-heading">
        <div>
          <span className="analytics-card-eyebrow">
            YIELD HISTORY
          </span>

          <h2>Xu hướng sản lượng</h2>

          <p>
            Sản lượng tổ yến ghi nhận theo từng tháng.
          </p>
        </div>

        <span className="analytics-period-badge">
          6 tháng
        </span>
      </header>

      <div className="yield-chart">
        {data.map((item) => (
          <article key={item.label}>
            <strong>{item.value} kg</strong>

            <div className="yield-chart-track">
              <span
                style={{
                  height: `${Math.max(
                    (item.value / maxValue) * 100,
                    8,
                  )}%`,
                }}
              />
            </div>

            <small>{item.label}</small>
          </article>
        ))}
      </div>
    </section>
  )
}

export default YieldTrendChart