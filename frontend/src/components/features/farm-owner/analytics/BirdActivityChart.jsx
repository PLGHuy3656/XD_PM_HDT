function BirdActivityChart({ data }) {
  const maxValue = Math.max(
    ...data.flatMap((item) => [
      item.entries,
      item.exits,
    ]),
  )

  return (
    <section className="analytics-card bird-activity-card">
      <header className="analytics-card-heading">
        <div>
          <span className="analytics-card-eyebrow">
            AI VISION
          </span>

          <h2>Hoạt động chim theo giờ</h2>

          <p>
            So sánh lưu lượng chim vào và ra trong ngày.
          </p>
        </div>

        <span className="analytics-period-badge">
          Hôm nay
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

      <div className="bird-bar-chart">
        {data.map((item) => (
          <div
            key={item.label}
            className="bird-bar-column"
          >
            <div className="bird-bar-track">
              <div
                className="bird-bar entries"
                style={{
                  height: `${Math.max(
                    (item.entries / maxValue) * 100,
                    4,
                  )}%`,
                }}
                title={`Chim vào: ${item.entries}`}
              />

              <div
                className="bird-bar exits"
                style={{
                  height: `${Math.max(
                    (item.exits / maxValue) * 100,
                    4,
                  )}%`,
                }}
                title={`Chim ra: ${item.exits}`}
              />
            </div>

            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  )
}

export default BirdActivityChart