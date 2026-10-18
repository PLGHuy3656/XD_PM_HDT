import { comparisonColors } from './environmentMockData'

function ZoneComparisonChart({
  zones,
  metricKey,
}) {
  const width = 900
  const height = 230
  const padding = 20

  const metrics = zones.map(
    (zone) => zone.metrics[metricKey]
  )

  const min = Math.min(
    ...metrics.map((metric) => metric.min)
  )

  const max = Math.max(
    ...metrics.map((metric) => metric.max)
  )

  const getPoints = (metric) =>
    metric.values
      .map((value, index) => {
        const x =
          padding +
          (index /
            (metric.values.length - 1)) *
            (width - padding * 2)

        const y =
          padding +
          (1 -
            (value - min) / (max - min)) *
            (height - padding * 2)

        return `${x},${y}`
      })
      .join(' ')

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