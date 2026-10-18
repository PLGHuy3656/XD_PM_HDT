import { useState } from 'react'

const periods = [7, 14, 30]

function makePoints(values, width = 600, height = 180) {
  if (!values.length) return ''

  const max = Math.max(...values)
  const min = Math.min(...values)
  const range = max - min || 1

  return values
    .map((value, index) => {
      const x =
        values.length === 1
          ? width / 2
          : (index / (values.length - 1)) * width

      const y =
        height - ((value - min) / range) * (height - 36) - 18

      return `${x},${y}`
    })
    .join(' ')
}

function BirdTrendChart({ data }) {
  const [days, setDays] = useState(7)

  const records = data[days] ?? data[7] ?? []
  const entryPoints = makePoints(records.map((item) => item.entries))
  const exitPoints = makePoints(records.map((item) => item.exits))

  return (
    <section className="swiftlet-card swiftlet-trend-card">
      <div className="swiftlet-card-heading">
        <div>
          <h2>Xu hướng đếm chim</h2>
          <p>Số lượt vào tổ và xuất đàn theo ngày</p>
        </div>

        <div className="swiftlet-period-tabs">
          {periods.map((period) => (
            <button
              key={period}
              type="button"
              className={days === period ? 'active' : ''}
              onClick={() => setDays(period)}
            >
              {period} ngày
            </button>
          ))}
        </div>
      </div>

      <div className="swiftlet-chart-legend">
        <span className="entry">
          <i /> Vào tổ
        </span>

        <span className="exit">
          <i /> Xuất đàn
        </span>
      </div>

      <div className="swiftlet-chart">
        <svg viewBox="0 0 600 180" preserveAspectRatio="none">
          <line x1="0" y1="45" x2="600" y2="45" />
          <line x1="0" y1="90" x2="600" y2="90" />
          <line x1="0" y1="135" x2="600" y2="135" />

          <polyline
            className="entry-line"
            points={entryPoints}
          />

          <polyline
            className="exit-line"
            points={exitPoints}
          />
        </svg>

        <div className="swiftlet-chart-labels">
          {records.map((record) => (
            <span key={record.label}>{record.label}</span>
          ))}
        </div>

        {!data[days] && (
          <div className="swiftlet-chart-placeholder">
            Dữ liệu {days} ngày sẽ được cung cấp bởi Analytics API
          </div>
        )}
      </div>
    </section>
  )
}

export default BirdTrendChart