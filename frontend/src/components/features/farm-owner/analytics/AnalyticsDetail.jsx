import { useState } from 'react'

import EnvironmentComparison from './EnvironmentComparison'
import BirdTrendAnalytics from './BirdTrendAnalytics'
import CorrelationPanel from './CorrelationPanel'
import AlertTrendPanel from './AlertTrendPanel'

function AnalyticsDetail({
  metrics,
  periods,
  comparison,
  birdTrend,
  correlation,
  alerts,
}) {
  const [metricId, setMetricId] =
    useState('temperature')

  const [periodId, setPeriodId] =
    useState('24h')

  const selectedMetric =
    metrics.find(
      (metric) => metric.id === metricId,
    ) ?? metrics[0]

  const comparisonData =
    comparison[selectedMetric.id] ?? []

  return (
    <div className="analytics-detail">
      <section className="analytics-detail-controls">
        <div>
          <span className="analytics-control-label">
            Chỉ số môi trường
          </span>

          <div className="analytics-metric-switcher">
            {metrics.map((metric) => (
              <button
                key={metric.id}
                type="button"
                className={
                  metricId === metric.id
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setMetricId(metric.id)
                }
              >
                {metric.label}
              </button>
            ))}
          </div>
        </div>

        <div className="analytics-detail-context">
          <span>
            So sánh
          </span>

          <strong>
            Khu vực A · Khu vực B
          </strong>
        </div>
      </section>

      <EnvironmentComparison
        metric={selectedMetric}
        periods={periods}
        activePeriod={periodId}
        onPeriodChange={setPeriodId}
        data={comparisonData}
      />

      <div className="analytics-detail-primary-grid">
        <BirdTrendAnalytics data={birdTrend} />

        <CorrelationPanel data={correlation} />
      </div>

      <AlertTrendPanel data={alerts} />
    </div>
  )
}

export default AnalyticsDetail