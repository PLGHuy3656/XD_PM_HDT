import YieldSummary from './YieldSummary'
import YieldTrendChart from './YieldTrendChart'
import ZoneYieldPanel from './ZoneYieldPanel'
import HarvestHistory from './HarvestHistory'

function AnalyticsYield({
  summary,
  trend,
  zones,
  history,
}) {
  return (
    <div className="analytics-yield">
      <YieldSummary data={summary} />

      <div className="analytics-yield-grid">
        <YieldTrendChart data={trend} />

        <ZoneYieldPanel data={zones} />
      </div>

      <HarvestHistory data={history} />
    </div>
  )
}

export default AnalyticsYield