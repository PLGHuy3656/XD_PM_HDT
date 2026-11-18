import { useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import AnalyticsTabs from '../../../components/features/farm-owner/analytics/AnalyticsTabs'
import AnalyticsOverview from '../../../components/features/farm-owner/analytics/AnalyticsOverview'
import AnalyticsDetail from '../../../components/features/farm-owner/analytics/AnalyticsDetail'
import AnalyticsYield from '../../../components/features/farm-owner/analytics/AnalyticsYield'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { useAnalytics } from '../../../features/analytics/hooks/useAnalytics'

import './AnalyticsPage.css'

function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState('overview')

  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    error: farmsError,
  } = useFarms()

  const {
    analyticsData,
    loading: analyticsLoading,
    error: analyticsError,
    refetch: refetchAnalytics,
  } = useAnalytics(selectedFarmId)

  return (
    <AppLayout>
      <div className="analytics-page">
        <header className="analytics-page-heading">
          <div>
            <span className="analytics-eyebrow">INSIGHTS & PERFORMANCE</span>

            <h1>Phân tích</h1>

            <p>
              Phân tích môi trường, hoạt động đàn chim, cảnh báo và hiệu quả vận
              hành nhà yến.
            </p>
          </div>

          <div className="analytics-farm-selector">
            <span>Nhà yến</span>

            <EnvironmentSelect
              value={selectedFarmId || ''}
              onChange={setSelectedFarmId}
              options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
              }))}
            />
          </div>
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {analyticsError && (
          <ErrorMessage
            title="Lỗi tải số liệu phân tích"
            message={analyticsError}
            onRetry={refetchAnalytics}
          />
        )}

        <AnalyticsTabs activeTab={activeTab} onChange={setActiveTab} />

        {analyticsLoading && !analyticsData ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang xử lý phân tích dữ liệu..." />
          </div>
        ) : (
          <>
            {activeTab === 'overview' && (
              <AnalyticsOverview
                performance={analyticsData.birdPerformance}
                birdActivity={analyticsData.hourlyBirdActivity}
                density={analyticsData.zoneDensity}
                climate={analyticsData.microClimateScores}
                alerts={analyticsData.alertDistribution}
              />
            )}

            {activeTab === 'detail' && (
              <AnalyticsDetail
                metrics={analyticsData.environmentMetrics}
                periods={analyticsData.analyticsPeriods}
                comparison={analyticsData.environmentComparison}
                birdTrend={analyticsData.birdTrendAnalytics}
                correlation={analyticsData.returnRateCorrelation}
                alerts={analyticsData.alertTrend}
              />
            )}

            {activeTab === 'yield' && (
              <AnalyticsYield
                summary={analyticsData.yieldSummary}
                trend={analyticsData.yieldTrend}
                zones={analyticsData.zoneYield}
                history={analyticsData.harvestHistory}
              />
            )}
          </>
        )}

        <span className="analytics-selected-farm">
          {analyticsData.hasDataGaps
            ? 'Dữ liệu thời gian thực (đang đồng bộ ETL NiFi)'
            : 'Dữ liệu phân tích trực tiếp'}{' '}
          · {selectedFarm?.name || 'Nhà yến'}
        </span>
      </div>
    </AppLayout>
  )
}

export default AnalyticsPage
