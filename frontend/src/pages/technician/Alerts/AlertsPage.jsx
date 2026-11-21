import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import AlertList from '../../../components/features/farm-owner/alerts/AlertList'
import AlertDetailPanel from '../../../components/features/farm-owner/alerts/AlertDetailPanel'
import InspectionRequestPanel from '../../../components/features/inspections/InspectionRequestPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'
import { useAlerts } from '../../../features/alerts/hooks/useAlerts'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { useAuth } from '../../../context/AuthContext'

import '../TechnicianWorkspace.css'
import './AlertsPage.css'
import '../../farm-owner/Alerts/AlertsPage.css'

const readOptions = [
  { value: 'ALL', label: 'Tất cả' },
  { value: 'UNREAD', label: 'Chưa đọc' },
  { value: 'READ', label: 'Đã đọc' },
]

/**
 * INT03-R1: Technician alerts = the caller's own operational notifications (Notification Service,
 * recipients = technicians actively assigned to the farm, resolved server-side) + Inspection
 * Requests (Management). The non-existent /api/v1/alerts endpoint is no longer called.
 */
function AlertsPage() {
  const { user } = useAuth()
  const [searchParams] = useSearchParams()
  const { farms, selectedFarmId, setSelectedFarmId, loading, error, refetch } = useTechnicianData()
  const [tab, setTab] = useState(searchParams.get('tab') === 'inspections' ? 'inspections' : 'alerts')
  const [readFilter, setReadFilter] = useState('ALL')
  const [search, setSearch] = useState('')
  const [selectedAlertId, setSelectedAlertId] = useState(null)

  const { alerts, loading: alertsLoading, error: alertsError, refetch: refetchAlerts, acknowledgeAlert } = useAlerts(selectedFarmId)
  const selectedFarm = farms.find((f) => f.id === selectedFarmId)

  const filtered = useMemo(() => {
    const kw = search.trim().toLowerCase()
    return alerts
      .map((a) => ({ ...a, farmName: a.farmName || selectedFarm?.name || '' }))
      .filter((a) => (readFilter === 'ALL' || a.status === readFilter) && (!kw || `${a.title} ${a.device} ${a.zoneName} ${a.description}`.toLowerCase().includes(kw)))
  }, [alerts, readFilter, search, selectedFarm])
  const selectedAlert = filtered.find((a) => a.id === selectedAlertId) || alerts.find((a) => a.id === selectedAlertId) || null
  const unreadCritical = alerts.filter((a) => a.status === 'UNREAD' && a.severity === 'CRITICAL').length

  return (
    <AppLayout>
      <div className="tech-ws">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN ALERTS</span>
            <h1>Cảnh báo &amp; Yêu cầu kiểm tra</h1>
            <p>Cảnh báo vận hành và yêu cầu kiểm tra của các nhà yến bạn đang được phân công.</p>
          </div>
          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách</span>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  options={farms.map((farm) => ({ value: farm.id, label: formatFarmOptionLabel(farm) }))}
                  onChange={(nextId) => {
                    setSelectedFarmId(nextId)
                    setSelectedAlertId(null)
                  }}
                />
              </div>
            )}
          </div>
        </header>

        {error && <ErrorMessage title="Lỗi tải dữ liệu kỹ thuật viên" message={error} onRetry={refetch} />}

        <nav className="tech-alerts-tabs" style={{ display: 'flex', gap: '8px', margin: '12px 0' }} role="tablist">
          <button type="button" role="tab" aria-selected={tab === 'alerts'} className={`ir-btn ${tab === 'alerts' ? 'ir-btn--primary' : 'ir-btn--ghost'}`} onClick={() => setTab('alerts')}>
            Cảnh báo kỹ thuật{unreadCritical > 0 ? ` (${unreadCritical} nghiêm trọng chưa đọc)` : ''}
          </button>
          <button type="button" role="tab" aria-selected={tab === 'inspections'} className={`ir-btn ${tab === 'inspections' ? 'ir-btn--primary' : 'ir-btn--ghost'}`} onClick={() => setTab('inspections')} data-testid="tech-tab-inspections">
            Yêu cầu kiểm tra
          </button>
        </nav>

        {tab === 'inspections' ? (
          <InspectionRequestPanel mode="technician" user={user} farmId={selectedFarmId} title="Yêu cầu kiểm tra được giao" />
        ) : loading && farms.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải cảnh báo..." />
          </div>
        ) : farms.length === 0 ? (
          <EmptyState title="Chưa có nhà yến được phân công" description="Liên hệ Admin để được phân công nhà yến trước khi theo dõi cảnh báo kỹ thuật." />
        ) : (
          <>
            {alertsError && (
              <ErrorMessage variant="warning" title="Notification Service chưa khả dụng" message="Không tải được cảnh báo. Danh sách sẽ tự cập nhật khi dịch vụ hoạt động trở lại." onRetry={refetchAlerts} />
            )}
            <section className="tech-alerts-tabs-nav">
              <div className="tech-alerts-tab-actions" style={{ width: '100%', justifyContent: 'space-between' }}>
                <div className="tech-alerts-search">
                  <input type="text" placeholder="Tìm theo tiêu đề, thiết bị, khu vực..." value={search} onChange={(e) => setSearch(e.target.value)} />
                </div>
                <div style={{ minWidth: '180px' }}>
                  <EnvironmentSelect value={readFilter} options={readOptions} onChange={setReadFilter} />
                </div>
              </div>
            </section>
            {alertsLoading && alerts.length === 0 ? (
              <div style={{ padding: '2rem', display: 'flex', justifyContent: 'center' }}>
                <LoadingSpinner size="md" text="Đang tải cảnh báo..." />
              </div>
            ) : filtered.length === 0 ? (
              <EmptyState
                title="Không có cảnh báo kỹ thuật"
                description={alerts.length === 0 ? 'Chưa có cảnh báo vận hành nào cho nhà yến này.' : 'Không có cảnh báo phù hợp bộ lọc.'}
              />
            ) : (
              <AlertList alerts={filtered} selectedAlertId={selectedAlertId} onViewDetail={(a) => setSelectedAlertId(a.id)} />
            )}
            <AlertDetailPanel
              alert={selectedAlert}
              onClose={() => setSelectedAlertId(null)}
              onAcknowledge={(id) => acknowledgeAlert(id)}
              onResolve={() => {}}
            />
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default AlertsPage
