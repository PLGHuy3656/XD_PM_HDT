import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import TechnicalAlertsTab from '../../../components/features/technician/alerts/TechnicalAlertsTab'
import AlertDetailPanel from '../../../components/features/technician/alerts/AlertDetailPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import { technicalAlerts as mockTechnicalAlerts } from '../../../components/features/technician/alerts/alertsMockData'
import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { USE_MOCK } from '../../../api/config.js'

import '../TechnicianWorkspace.css'
import './AlertsPage.css'

const technicalStatusOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'OPEN', label: 'Chưa xử lý' },
  { value: 'INVESTIGATING', label: 'Đang kiểm tra' },
  { value: 'RESOLVED', label: 'Đã xử lý' },
]

function AlertsPage() {
  const {
    farms,
    selectedFarmId,
    setSelectedFarmId,
    alerts: apiAlerts,
    alertsError,
    loading,
    error,
    refetch,
    acknowledgeAlert,
    resolveAlert,
  } = useTechnicianData()

  const [statusFilter, setStatusFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [selectedAlert, setSelectedAlert] = useState(null)

  const effectiveAlerts = useMemo(
    () => (apiAlerts.length > 0 ? apiAlerts : (USE_MOCK ? mockTechnicalAlerts : [])),
    [apiAlerts],
  )

  const farmOptions = useMemo(
    () =>
      farms.map((farm) => ({
        value: farm.id,
        label: formatFarmOptionLabel(farm),
      })),
    [farms],
  )

  const filteredAlerts = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return effectiveAlerts.filter((item) => {
      const matchesStatus = statusFilter === 'ALL' || item.status === statusFilter
      const matchesSearch =
        !keyword ||
        (item.title && item.title.toLowerCase().includes(keyword)) ||
        (item.device && item.device.toLowerCase().includes(keyword)) ||
        (item.zone && item.zone.toLowerCase().includes(keyword))
      return matchesStatus && matchesSearch
    })
  }, [effectiveAlerts, statusFilter, search])

  const openCount = filteredAlerts.filter((item) => item.status !== 'RESOLVED').length
  const criticalCount = filteredAlerts.filter(
    (item) => item.level === 'critical' && item.status !== 'RESOLVED',
  ).length

  const isServiceUnavailable = !USE_MOCK && Boolean(alertsError)

  return (
    <AppLayout>
      <div className="tech-ws">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN ALERTS</span>
            <h1>Cảnh báo kỹ thuật</h1>
            <p>
              Theo dõi sự cố cảm biến, kết nối và cảnh báo kỹ thuật thuộc các nhà yến được phân công.
            </p>
          </div>

          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách</span>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  options={farmOptions}
                  onChange={(nextId) => {
                    setSelectedFarmId(nextId)
                    setSelectedAlert(null)
                  }}
                />
              </div>
            )}
          </div>
        </header>

        {error && (
          <ErrorMessage
            title="Lỗi tải dữ liệu kỹ thuật viên"
            message={error}
            onRetry={refetch}
          />
        )}

        {loading && farms.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải cảnh báo..." />
          </div>
        ) : farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến được phân công"
            description="Liên hệ Admin để được phân công nhà yến trước khi theo dõi cảnh báo kỹ thuật."
          />
        ) : isServiceUnavailable ? (
          <section className="tech-ws-card">
            <ErrorMessage
              variant="warning"
              title="Chưa kết nối dịch vụ Cảnh báo (Notification Service)"
              message="Dịch vụ Cảnh báo (Notification Service) hiện chưa khả dụng. Danh sách cảnh báo kỹ thuật và thao tác xác nhận/xử lý sẽ tự động khả dụng khi dịch vụ hoạt động trở lại."
              onRetry={refetch}
            />
          </section>
        ) : (
          <>
            <section className="tech-ws-kpi-grid" style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}>
              <article className="tech-ws-kpi-card">
                <span>Sự cố kỹ thuật đang mở</span>
                <strong>{openCount}</strong>
                <small>Cần kỹ thuật viên kiểm tra</small>
              </article>
              <article className="tech-ws-kpi-card">
                <span>Sự cố nghiêm trọng</span>
                <strong style={{ color: criticalCount > 0 ? '#b91c1c' : '#102d3f' }}>
                  {criticalCount}
                </strong>
                <small>Ảnh hưởng trực tiếp vận hành</small>
              </article>
            </section>

            <section className="tech-alerts-tabs-nav">
              <div className="tech-alerts-tab-actions" style={{ width: '100%', justifyContent: 'space-between' }}>
                <div className="tech-alerts-search">
                  <input
                    type="text"
                    placeholder="Tìm theo mã, thiết bị, khu vực..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>

                <div style={{ minWidth: '180px' }}>
                  <EnvironmentSelect
                    value={statusFilter}
                    options={technicalStatusOptions}
                    onChange={setStatusFilter}
                  />
                </div>
              </div>
            </section>

            <section className="tech-alerts-layout">
              <div className="tech-alerts-table-area">
                {filteredAlerts.length === 0 ? (
                  <EmptyState
                    title="Không có sự cố kỹ thuật nào"
                    description="Hiện tại không ghi nhận cảnh báo kỹ thuật mới cho nhà yến này."
                  />
                ) : (
                  <TechnicalAlertsTab
                    alerts={filteredAlerts}
                    selectedId={selectedAlert?.id}
                    onSelect={setSelectedAlert}
                  />
                )}
              </div>

              {selectedAlert && (
                <AlertDetailPanel
                  alert={selectedAlert}
                  onClose={() => setSelectedAlert(null)}
                  onAcknowledge={() => acknowledgeAlert(selectedAlert.id, 'Kỹ thuật viên đang kiểm tra')}
                  onResolve={() => resolveAlert(selectedAlert.id, 'Kỹ thuật viên đã xử lý sự cố')}
                />
              )}
            </section>
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default AlertsPage
