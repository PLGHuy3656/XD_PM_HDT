import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import TechnicalAlertsTab from '../../../components/features/technician/alerts/TechnicalAlertsTab'
import WorkRequestsTab from '../../../components/features/technician/alerts/WorkRequestsTab'
import AlertDetailPanel from '../../../components/features/technician/alerts/AlertDetailPanel'
import WorkRequestDetailPanel from '../../../components/features/technician/alerts/WorkRequestDetailPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import {
  technicalAlerts as mockTechnicalAlerts,
  workRequests as initialWorkRequests,
} from '../../../components/features/technician/alerts/alertsMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'

import './AlertsPage.css'

const technicalStatusOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'OPEN', label: 'Chưa xử lý' },
  { value: 'INVESTIGATING', label: 'Đang kiểm tra' },
  { value: 'RESOLVED', label: 'Đã xử lý' },
]

const workStatusOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'NEW', label: 'Mới' },
  { value: 'IN_PROGRESS', label: 'Đang xử lý' },
  { value: 'DONE', label: 'Hoàn thành' },
]

function AlertsPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    alerts: apiAlerts,
    loading,
    error,
    refetch,
    acknowledgeAlert,
    resolveAlert,
  } = useTechnicianData()

  const [activeTab, setActiveTab] = useState('technical')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const [selectedAlert, setSelectedAlert] = useState(null)
  const [selectedRequest, setSelectedRequest] = useState(null)

  const [workRequests, setWorkRequests] = useState(initialWorkRequests)

  const effectiveAlerts = apiAlerts.length > 0 ? apiAlerts : mockTechnicalAlerts

  const farmOptions = useMemo(() => {
    return [
      { value: 'ALL', label: 'Tất cả nhà yến phụ trách' },
      ...farms.map((farm) => ({
        value: farm.id,
        label: farm.name,
      })),
    ]
  }, [farms])

  const filteredAlerts = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return effectiveAlerts.filter((item) => {
      const matchesFarm =
        selectedFarmId === 'ALL' ||
        !item.farmId ||
        item.farmId === selectedFarmId

      const matchesStatus =
        statusFilter === 'ALL' || item.status === statusFilter

      const matchesSearch =
        !keyword ||
        (item.title && item.title.toLowerCase().includes(keyword)) ||
        (item.device && item.device.toLowerCase().includes(keyword)) ||
        (item.zone && item.zone.toLowerCase().includes(keyword))

      return matchesFarm && matchesStatus && matchesSearch
    })
  }, [effectiveAlerts, selectedFarmId, statusFilter, search])

  const filteredRequests = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return workRequests.filter((item) => {
      const matchesStatus =
        statusFilter === 'ALL' || item.status === statusFilter

      const matchesSearch =
        !keyword ||
        (item.title && item.title.toLowerCase().includes(keyword)) ||
        (item.sender && item.sender.toLowerCase().includes(keyword)) ||
        (item.zone && item.zone.toLowerCase().includes(keyword))

      return matchesStatus && matchesSearch
    })
  }, [workRequests, statusFilter, search])

  const openTechnical = filteredAlerts.filter(
    (item) => item.status !== 'RESOLVED',
  ).length

  const criticalTechnical = filteredAlerts.filter(
    (item) => item.level === 'critical' && item.status !== 'RESOLVED',
  ).length

  const newRequests = workRequests.filter(
    (item) => item.status === 'NEW',
  ).length

  const inProgressRequests = workRequests.filter(
    (item) => item.status === 'IN_PROGRESS',
  ).length

  const currentStatusOptions =
    activeTab === 'technical'
      ? technicalStatusOptions
      : workStatusOptions

  const handleTabChange = (tab) => {
    setActiveTab(tab)
    setStatusFilter('ALL')
    setSelectedAlert(null)
    setSelectedRequest(null)
  }

  const handleAcknowledgeAlert = async (alertId) => {
    await acknowledgeAlert(alertId, 'Kỹ thuật viên đang kiểm tra')
  }

  const handleResolveAlert = async (alertId) => {
    await resolveAlert(alertId, 'Kỹ thuật viên đã xử lý sự cố')
  }

  return (
    <AppLayout>
      <div className="tech-alerts-page">
        <header className="tech-alerts-hero">
          <div>
            <span className="tech-alerts-eyebrow">TECHNICIAN WORKSPACE</span>
            <h1>Cảnh báo & Yêu cầu</h1>
            <p>
              Theo dõi sự cố kỹ thuật và phiếu yêu cầu xử lý từ chủ nhà yến hoặc
              hệ thống tự động phát hiện.
            </p>
          </div>

          <div className="tech-alerts-farm-picker">
            <span>Nhà yến</span>
            <EnvironmentSelect
              value={selectedFarmId || 'ALL'}
              options={farmOptions}
              onChange={(nextId) => {
                setSelectedFarmId(nextId === 'ALL' ? farms[0]?.id : nextId)
                setSelectedAlert(null)
              }}
            />
          </div>
        </header>

        {error && (
          <ErrorMessage
            title="Lỗi tải danh sách cảnh báo"
            message={error}
            onRetry={refetch}
          />
        )}

        <section className="tech-alerts-overview">
          <article className="tech-alerts-metric-card">
            <span className="metric-title">Sự cố kỹ thuật mở</span>
            <strong className="metric-number metric-open">
              {openTechnical}
            </strong>
            <small className="metric-caption">Cần kỹ thuật viên xử lý</small>
          </article>

          <article className="tech-alerts-metric-card">
            <span className="metric-title">Sự cố nghiêm trọng</span>
            <strong className="metric-number metric-critical">
              {criticalTechnical}
            </strong>
            <small className="metric-caption">Ảnh hưởng trực tiếp vi khí hậu</small>
          </article>

          <article className="tech-alerts-metric-card">
            <span className="metric-title">Yêu cầu mới</span>
            <strong className="metric-number metric-new">
              {newRequests}
            </strong>
            <small className="metric-caption">Từ Farm Owner cần phản hồi</small>
          </article>

          <article className="tech-alerts-metric-card">
            <span className="metric-title">Đang xử lý</span>
            <strong className="metric-number metric-progress">
              {inProgressRequests}
            </strong>
            <small className="metric-caption">Phiếu công việc đang triển khai</small>
          </article>
        </section>

        <section className="tech-alerts-tabs-nav">
          <div className="tech-alerts-tab-buttons">
            <button
              type="button"
              className={activeTab === 'technical' ? 'active' : ''}
              onClick={() => handleTabChange('technical')}
            >
              <span>Sự cố kỹ thuật</span>
              <strong className="tab-badge">{openTechnical}</strong>
            </button>

            <button
              type="button"
              className={activeTab === 'requests' ? 'active' : ''}
              onClick={() => handleTabChange('requests')}
            >
              <span>Phiếu yêu cầu</span>
              <strong className="tab-badge">{newRequests}</strong>
            </button>
          </div>

          <div className="tech-alerts-tab-actions">
            <div className="tech-alerts-search">
              <input
                type="text"
                placeholder={
                  activeTab === 'technical'
                    ? 'Tìm theo mã, thiết bị, khu vực...'
                    : 'Tìm theo tiêu đề, người gửi...'
                }
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <EnvironmentSelect
              value={statusFilter}
              options={currentStatusOptions}
              onChange={setStatusFilter}
            />
          </div>
        </section>

        <section className="tech-alerts-layout">
          <div className="tech-alerts-table-area">
            {loading && effectiveAlerts.length === 0 ? (
              <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
                <LoadingSpinner size="lg" text="Đang tải cảnh báo..." />
              </div>
            ) : activeTab === 'technical' ? (
              filteredAlerts.length === 0 ? (
                <EmptyState
                  title="Không có sự cố kỹ thuật nào"
                  description="Hiện tại hạ tầng thiết bị và cảm biến đang hoạt động ổn định."
                />
              ) : (
                <TechnicalAlertsTab
                  alerts={filteredAlerts}
                  selectedAlertId={selectedAlert?.id}
                  onSelectAlert={setSelectedAlert}
                />
              )
            ) : filteredRequests.length === 0 ? (
              <EmptyState
                title="Không có phiếu yêu cầu nào"
                description="Không có yêu cầu bảo trì hoặc hỗ trợ mới từ chủ nhà yến."
              />
            ) : (
              <WorkRequestsTab
                requests={filteredRequests}
                selectedRequestId={selectedRequest?.id}
                onSelectRequest={setSelectedRequest}
              />
            )}
          </div>

          <aside className="tech-alerts-side-panel">
            {activeTab === 'technical' ? (
              <AlertDetailPanel
                alert={selectedAlert}
                onClose={() => setSelectedAlert(null)}
                onAcknowledge={handleAcknowledgeAlert}
                onResolve={handleResolveAlert}
              />
            ) : (
              <WorkRequestDetailPanel
                request={selectedRequest}
                onClose={() => setSelectedRequest(null)}
              />
            )}
          </aside>
        </section>
      </div>
    </AppLayout>
  )
}

export default AlertsPage
