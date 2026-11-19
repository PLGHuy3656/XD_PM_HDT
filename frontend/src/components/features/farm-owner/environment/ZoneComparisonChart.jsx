import { comparisonColors } from './environmentMockData'

function ZoneComparisonChart({
  zones = [],
  metricKey = 'temperature',
}) {
  const width = 900
  const height = 230
  const padding = 20

  if (!zones || zones.length === 0) {
    return (
      <div className="comparison-chart" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '180px', color: '#94a3b8' }}>
        <span>Vui lòng chọn ít nhất 1 khu vực để so sánh</span>
      </div>
    )
  }

  const validEntries = zones
    .map((zone, idx) => ({
      zone,
      idx,
      metric: zone?.metrics?.[metricKey],
    }))
    .filter((entry) => entry.metric && Array.isArray(entry.metric.values) && entry.metric.values.length > 0)

  if (validEntries.length === 0) {
    return (
      <div className="comparison-chart" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '180px', color: '#94a3b8' }}>
        <span>Chưa có đủ số liệu lịch sử để hiển thị biểu đồ so sánh</span>
      </div>
    )
  }

  const allValues = validEntries.flatMap((e) => e.metric.values)
  const minVal = Math.min(...allValues)
  const maxVal = Math.max(...allValues)
  const min = Math.min(minVal, ...validEntries.map((e) => e.metric.min ?? minVal))
  const max = Math.max(maxVal, ...validEntries.map((e) => e.metric.max ?? maxVal))
  const range = max === min ? 1 : max - min

  const getPoints = (metric) =>
    metric.values
      .map((value, index) => {
        const x =
          padding +
          (index / Math.max(1, metric.values.length - 1)) *
            (width - padding * 2)

        const y =
          padding +
          (1 - (value - min) / range) *
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

        {validEntries.map(({ zone, idx, metric }) => (
          <polyline
            key={zone.id || idx}
            points={getPoints(metric)}
            className="comparison-line"
            style={{
              stroke:
                comparisonColors[idx % comparisonColors.length],
            }}
          />
        ))}
      </svg>
    </div>
  )
}

export default ZoneComparisonChart
