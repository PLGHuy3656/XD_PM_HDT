import { useMemo } from 'react'

function EnvironmentChart({ metric }) {
  const width = 900
  const height = 220
  const padding = 18

  const usableWidth = width - padding * 2
  const usableHeight = height - padding * 2

  const points = useMemo(
    () =>
      metric.values.map((value, index) => {
        const x =
          padding +
          (index / (metric.values.length - 1)) *
            usableWidth

        const y =
          padding +
          (1 -
            (value - metric.min) /
              (metric.max - metric.min)) *
            usableHeight

        return { x, y }
      }),
    [metric, usableHeight, usableWidth]
  )

  const polyline = points
    .map((point) => `${point.x},${point.y}`)
    .join(' ')

  const areaPath = [
    `M ${points[0].x} ${height - padding}`,
    ...points.map(
      (point) => `L ${point.x} ${point.y}`
    ),
    `L ${points[points.length - 1].x} ${height - padding}`,
    'Z',
  ].join(' ')

  const safeTop =
    padding +
    (1 -
      (metric.safeMax - metric.min) /
        (metric.max - metric.min)) *
      usableHeight

  const safeBottom =
    padding +
    (1 -
      (metric.safeMin - metric.min) /
        (metric.max - metric.min)) *
      usableHeight

  return (
    <div className="environment-chart">
      <div className="chart-canvas">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient
              id="environmentArea"
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stopColor="currentColor"
                stopOpacity="0.18"
              />
              <stop
                offset="100%"
                stopColor="currentColor"
                stopOpacity="0.01"
              />
            </linearGradient>
          </defs>

          {[0, 1, 2, 3, 4].map((line) => {
            const y =
              padding +
              (line / 4) * usableHeight

            return (
              <line
                key={line}
                x1={padding}
                x2={width - padding}
                y1={y}
                y2={y}
                className="chart-grid-line"
              />
            )
          })}

          <rect
            x={padding}
            y={safeTop}
            width={usableWidth}
            height={safeBottom - safeTop}
            className="chart-safe-zone"
          />

          <path
            d={areaPath}
            className="chart-area"
          />

          <polyline
            points={polyline}
            className="chart-line"
          />

          {points.map((point, index) => (
            <circle
              key={index}
              cx={point.x}
              cy={point.y}
              r={
                index === points.length - 1
                  ? 5
                  : 2.8
              }
              className={
                index === points.length - 1
                  ? 'chart-point current'
                  : 'chart-point'
              }
            />
          ))}
        </svg>
      </div>

      <div className="chart-time-axis">
        <span>00:00</span>
        <span>04:00</span>
        <span>08:00</span>
        <span>12:00</span>
        <span>16:00</span>
        <span>20:00</span>
        <span>Hiện tại</span>
      </div>
    </div>
  )
}

export default EnvironmentChart