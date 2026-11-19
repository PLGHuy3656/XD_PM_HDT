import { useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import AnalyticsTabs from '../../../components/features/farm-owner/analytics/AnalyticsTabs'
import AnalyticsOverview from '../../../components/features/farm-owner/analytics/AnalyticsOverview'
import AnalyticsDetail from '../../../components/features/farm-owner/analytics/AnalyticsDetail'
import AnalyticsYield from '../../../components/features/farm-owner/analytics/AnalyticsYield'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { useAnalytics } from '../../../features/analytics/hooks/useAnalytics'
import { USE_MOCK } from '../../../api/config.js'

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
    unavailable,
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
                label: formatFarmOptionLabel(farm),
              }))}
            />
          </div>
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {analyticsError && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ Phân tích"
            message={
              /upstream|503|unreachable|network/i.test(String(analyticsError))
                ? 'Chưa kết nối dịch vụ Phân tích (Analytics Service). Dữ liệu sẽ hiển thị khi dịch vụ hoạt động trở lại.'
                : analyticsError
            }
            onRetry={refetchAnalytics}
          />
        )}

        <AnalyticsTabs activeTab={activeTab} onChange={setActiveTab} />

        {!USE_MOCK && !analyticsLoading && (!selectedFarmId || unavailable) ? (
          <div style={{ padding: '2.5rem 1.5rem', textAlign: 'center', background: '#fffdf9', border: '1px solid #e6dfd3', borderRadius: '18px', color: '#64748b' }}>
            <strong style={{ display: 'block', color: '#172b46', marginBottom: '6px' }}>
              {!selectedFarmId ? 'Chưa có nhà yến được chọn' : 'Analytics Service chưa khả dụng'}
            </strong>
            <span style={{ fontSize: '0.9rem' }}>
              {!selectedFarmId
                ? 'Hãy tạo hoặc chọn một nhà yến để xem dữ liệu phân tích.'
                : 'Dữ liệu tổng hợp môi trường, chim yến và cảnh báo sẽ hiển thị khi Analytics Service & AI/IoT hoạt động.'}
            </span>
          </div>
        ) : analyticsLoading && !analyticsData ? (
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
