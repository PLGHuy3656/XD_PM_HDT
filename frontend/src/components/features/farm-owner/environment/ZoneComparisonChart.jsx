import { comparisonColors } from './environmentMockData'

function ZoneComparisonChart({
  zones,
  metricKey,
}) {
  const width = 900
  const height = 230
  const padding = 20

  const metrics = (zones || [])
    .map((zone) => zone?.metrics?.[metricKey])
    .filter(Boolean)

  const hasChartSeries =
    metrics.length > 0 &&
    metrics.some((m) => Array.isArray(m.values) && m.values.length >= 2)

  if (!hasChartSeries) {
    return (
      <div
        className="comparison-chart"
        style={{
          padding: '2rem 1rem',
          textAlign: 'center',
          color: '#64748b',
          fontSize: '0.9rem',
        }}
      >
        Chưa có dữ liệu so sánh giữa các khu vực từ IoT Service.
      </div>
    )
  }

  const min = Math.min(
    ...metrics.map((metric) => metric.min ?? 0)
  )

  const max = Math.max(
    ...metrics.map((metric) => metric.max ?? 100)
  )
  const range = (max - min) || 1

  const getPoints = (metric) => {
    const vals = Array.isArray(metric?.values) ? metric.values : []
    if (vals.length < 2) return ''
    return vals
      .map((value, index) => {
        const x =
          padding +
          (index / (vals.length - 1)) *
            (width - padding * 2)

        const y =
          padding +
          (1 - (value - min) / range) *
            (height - padding * 2)

        return `${x},${y}`
      })
      .join(' ')
  }

  return (
    <div className="comparison-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        {[0, 1, 2, 3, 4].map((line) => {
          const y =
            padding +
            (line / 4) *
              (height - padding * 2)

          return (
            <line
              key={line}
              x1={padding}
              x2={width - padding}
              y1={y}
              y2={y}
              className="comparison-grid-line"
            />
          )
        })}

        {metrics.map((metric, index) => (
          <polyline
            key={zones[index].id}
            points={getPoints(metric)}
            className="comparison-line"
            style={{
              stroke:
                comparisonColors[index],
            }}
          />
        ))}
      </svg>
    </div>
  )
}

export default ZoneComparisonChart