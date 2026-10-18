function BirdTrendAnalytics({ data }) {
  const maxValue = Math.max(
    ...data.flatMap((item) => [
      item.entries,
      item.exits,
    ]),
  )

  return (
    <section className="analytics-card analytics-bird-trend">
      <header className="analytics-card-heading">
        <div>
          <span className="analytics-card-eyebrow">
            BIRD HISTORY
          </span>

          <h2>Xu hướng đàn chim</h2>

          <p>
            So sánh tổng lượt chim vào và ra theo ngày.
          </p>
        </div>

        <span className="analytics-period-badge">
          7 ngày
        </span>
      </header>

      <div className="bird-chart-legend">
        <span>
          <i className="entries" />
          Chim vào
        </span>

        <span>
          <i className="exits" />
          Chim ra
        </span>
      </div>

      <div className="analytics-trend-chart">
        {data.map((item) => (
          <div
            key={item.label}
            className="analytics-trend-column"
          >
            <div className="analytics-trend-bars">
              <span
                className="entries"
                style={{
                  height: `${Math.max(
                    (item.entries / maxValue) * 100,
                    5,
                  )}%`,
                }}
              />

              <span
                className="exits"
                style={{
                  height: `${Math.max(
                    (item.exits / maxValue) * 100,
                    5,
                  )}%`,
                }}
              />
            </div>

            <small>{item.label}</small>
          </div>
        ))}
      </div>
    </section>
  )
}

export default BirdTrendAnalytics