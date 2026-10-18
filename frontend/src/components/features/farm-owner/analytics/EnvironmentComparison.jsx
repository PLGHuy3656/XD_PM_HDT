function buildPoints(data, key, width, height) {
  const values = data.map((item) => item[key])
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  return data
    .map((item, index) => {
      const x =
        data.length === 1
          ? width / 2
          : (index / (data.length - 1)) * width

      const y =
        height -
        ((item[key] - min) / range) * (height - 30) -
        15

      return `${x},${y}`
    })
    .join(' ')
}

function EnvironmentComparison({
  metric,
  periods,
  activePeriod,
  onPeriodChange,
  data,
}) {
  const width = 700
  const height = 220

  const zoneAPoints = buildPoints(
    data,
    'zoneA',
    width,
    height,
  )

  const zoneBPoints = buildPoints(
    data,
    'zoneB',
    width,
    height,
  )

  return (
    <section className="analytics-card environment-comparison">
      <header className="analytics-card-heading">
        <div>
          <span className="analytics-card-eyebrow">
            ENVIRONMENT HISTORY
          </span>

          <h2>
            So sánh {metric.label.toLowerCase()} giữa các khu vực
          </h2>

          <p>
            Theo dõi sự thay đổi giữa Khu vực A và Khu vực B.
          </p>
        </div>

        <div className="analytics-period-switcher">
          {periods.map((period) => (
            <button
              key={period.id}
              type="button"
              className={
                activePeriod === period.id
                  ? 'active'
                  : ''
              }
              onClick={() =>
                onPeriodChange(period.id)
              }
            >
              {period.label}
            </button>
          ))}
        </div>
      </header>

      <div className="analytics-line-legend">
        <span>
          <i className="zone-a" />
          Khu vực A
        </span>

        <span>
          <i className="zone-b" />
          Khu vực B
        </span>

        <strong>{metric.unit}</strong>
      </div>

      <div className="analytics-line-chart">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
          role="img"
          aria-label={`Biểu đồ ${metric.label}`}
        >
          <line
            x1="0"
            y1="55"
            x2={width}
            y2="55"
            className="analytics-grid-line"
          />

          <line
            x1="0"
            y1="110"
            x2={width}
            y2="110"
            className="analytics-grid-line"
          />

          <line
            x1="0"
            y1="165"
            x2={width}
            y2="165"
            className="analytics-grid-line"
          />

          <polyline
            points={zoneAPoints}
            className="analytics-line zone-a"
          />

          <polyline
            points={zoneBPoints}
            className="analytics-line zone-b"
          />
        </svg>

        <div className="analytics-line-labels">
          {data.map((item) => (
            <span key={item.label}>
              {item.label}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

export default EnvironmentComparison