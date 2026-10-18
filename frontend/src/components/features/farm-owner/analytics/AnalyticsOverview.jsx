import BirdActivityChart from './BirdActivityChart'
import ZoneDensityPanel from './ZoneDensityPanel'
import MicroClimateScore from './MicroClimateScore'
import AlertDistribution from './AlertDistribution'

function PerformanceCard({
  label,
  value,
  suffix,
  description,
  highlight = false,
}) {
  return (
    <article
      className={`analytics-performance-item ${
        highlight ? 'highlight' : ''
      }`}
    >
      <span>{label}</span>

      <strong>
        {value}
        {suffix && <small>{suffix}</small>}
      </strong>

      <p>{description}</p>
    </article>
  )
}

function AnalyticsOverview({
  performance,
  birdActivity,
  density,
  climate,
  alerts,
}) {
  return (
    <div className="analytics-overview">
      <section className="analytics-performance">
        <header>
          <div>
            <span className="analytics-card-eyebrow">
              BIRD PERFORMANCE
            </span>

            <h2>Hiệu suất đàn chim</h2>
          </div>

          <span className="analytics-performance-change">
            +{performance.change}% so với kỳ trước
          </span>
        </header>

        <div className="analytics-performance-grid">
          <PerformanceCard
            label="Chim vào"
            value={performance.entries}
            description="Lượt ghi nhận hôm nay"
          />

          <PerformanceCard
            label="Chim ra"
            value={performance.exits}
            description="Lượt ghi nhận hôm nay"
          />

          <PerformanceCard
            label="Tỷ lệ quay về"
            value={performance.returnRate}
            suffix="%"
            description="Theo dữ liệu Entry / Exit"
            highlight
          />

          <PerformanceCard
            label="Chênh lệch"
            value={`+${performance.difference}`}
            description="Ước tính hiện diện"
          />
        </div>
      </section>

      <div className="analytics-overview-primary-grid">
        <BirdActivityChart data={birdActivity} />

        <ZoneDensityPanel zones={density} />
      </div>

      <div className="analytics-overview-secondary-grid">
        <MicroClimateScore zones={climate} />

        <AlertDistribution data={alerts} />
      </div>
    </div>
  )
}

export default AnalyticsOverview