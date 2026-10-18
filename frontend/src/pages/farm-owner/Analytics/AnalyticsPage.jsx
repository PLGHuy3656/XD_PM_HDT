import { useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import AnalyticsTabs from '../../../components/features/farm-owner/analytics/AnalyticsTabs'
import AnalyticsOverview from '../../../components/features/farm-owner/analytics/AnalyticsOverview'
import AnalyticsDetail from '../../../components/features/farm-owner/analytics/AnalyticsDetail'
import AnalyticsYield from '../../../components/features/farm-owner/analytics/AnalyticsYield'

import {
  analyticsFarms,
  birdPerformance,
  hourlyBirdActivity,
  zoneDensity,
  microClimateScores,
  alertDistribution,
  environmentMetrics,
  analyticsPeriods,
  environmentComparison,
  birdTrendAnalytics,
  returnRateCorrelation,
  alertTrend,
  yieldSummary,
  yieldTrend,
  zoneYield,
  harvestHistory,
} from '../../../components/features/farm-owner/analytics/analyticsMockData'

import './AnalyticsPage.css'

function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState('overview')
  const [farmId, setFarmId] = useState(
    analyticsFarms[0].id,
  )

  const selectedFarm =
    analyticsFarms.find(
      (farm) => farm.id === farmId,
    ) ?? analyticsFarms[0]

  return (
    <AppLayout>
      <main className="analytics-page">
        <header className="analytics-page-heading">
          <div>
            <span className="analytics-eyebrow">
              INSIGHTS & PERFORMANCE
            </span>

            <h1>Phân tích</h1>

            <p>
              Phân tích môi trường, hoạt động đàn chim,
              cảnh báo và hiệu quả vận hành nhà yến.
            </p>
          </div>

          <label className="analytics-farm-selector">
            <span>Nhà yến</span>

            <EnvironmentSelect
              value={farmId}
              onChange={setFarmId}
              options={analyticsFarms.map((farm) => ({
                value: farm.id,
                label: farm.name,
              }))}
            />
          </label>
        </header>

        <AnalyticsTabs
          activeTab={activeTab}
          onChange={setActiveTab}
        />

        {activeTab === 'overview' && (
          <AnalyticsOverview
            performance={birdPerformance}
            birdActivity={hourlyBirdActivity}
            density={zoneDensity}
            climate={microClimateScores}
            alerts={alertDistribution}
          />
        )}

        {activeTab === 'detail' && (
          <AnalyticsDetail
            metrics={environmentMetrics}
            periods={analyticsPeriods}
            comparison={environmentComparison}
            birdTrend={birdTrendAnalytics}
            correlation={returnRateCorrelation}
            alerts={alertTrend}
          />
        )}

        {activeTab === 'yield' && (
          <AnalyticsYield
            summary={yieldSummary}
            trend={yieldTrend}
            zones={zoneYield}
            history={harvestHistory}
          />
        )}

        <span className="analytics-selected-farm">
          Dữ liệu minh họa · {selectedFarm.name}
        </span>
      </main>
    </AppLayout>
  )
}

export default AnalyticsPage