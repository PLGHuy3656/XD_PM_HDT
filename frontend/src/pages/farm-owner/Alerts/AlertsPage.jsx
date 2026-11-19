import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import AlertFilters from '../../../components/features/farm-owner/alerts/AlertFilters'
import AlertList from '../../../components/features/farm-owner/alerts/AlertList'
import AlertDetailPanel from '../../../components/features/farm-owner/alerts/AlertDetailPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import {
  alertStatusOptions,
  alertSeverityOptions,
} from '../../../components/features/farm-owner/alerts/alertsMockData'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { useAlerts } from '../../../features/alerts/hooks/useAlerts'
import { USE_MOCK } from '../../../api/config.js'

import './AlertsPage.css'

function AlertsPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    error: farmsError,
  } = useFarms()

  const [zoneId, setZoneId] = useState('all')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [severityFilter, setSeverityFilter] = useState('ALL')
  const [selectedAlertId, setSelectedAlertId] = useState(null)

  const {
    alerts,
    loading: alertsLoading,
    error: alertsError,
    refetch: refetchAlerts,
    acknowledgeAlert,
    resolveAlert,
  } = useAlerts(selectedFarmId)

  const effectiveZones = zones.length > 0 ? zones : selectedFarm?.zones || []

  const selectedAlert =
    alerts.find((alert) => alert.id === selectedAlertId) ?? null

  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      const matchesZone = zoneId === 'all' || alert.zoneId === zoneId

      const matchesStatus =
        statusFilter === 'ALL' || alert.status === statusFilter

      const matchesSeverity =
        severityFilter === 'ALL' || alert.severity === severityFilter

      return matchesZone && matchesStatus && matchesSeverity
    })
  }, [alerts, zoneId, statusFilter, severityFilter])

  function handleFarmChange(nextFarmId) {
    setSelectedFarmId(nextFarmId)
    setZoneId('all')
    setSelectedAlertId(null)
  }

  function handleAcknowledge(alertId) {
    acknowledgeAlert(alertId, 'Farm owner acknowledged')
  }

  function handleResolve(alertId) {
    resolveAlert(alertId, 'Farm owner resolved')
  }

  return (
    <AppLayout>
      <div className="alerts-page">
        <header className="alerts-page-heading">
          <div>
            <span className="alerts-eyebrow">MONITORING & ALERTS</span>

            <h1>Cảnh báo</h1>

            <p>
              Theo dõi và xử lý các bất thường về môi trường, thiết bị và AI tại
              nhà yến.
            </p>
          </div>

          <div className="alerts-context-selectors">
            <label>
              <span>Nhà yến</span>

              <EnvironmentSelect
                value={selectedFarmId || ''}
                onChange={handleFarmChange}
                options={farms.map((farm) => ({
                  value: farm.id,
                  label: formatFarmOptionLabel(farm),
                }))}
              />
            </label>

            <label>
              <span>Khu vực</span>

              <EnvironmentSelect
                value={zoneId}
                onChange={setZoneId}
                options={[
                  { value: 'all', label: 'Tất cả khu vực' },
                  ...effectiveZones.map((zone) => ({
                    value: zone.id,
                    label: zone.name,
                  })),
                ]}
              />
            </label>
          </div>
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {alertsError && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ Cảnh báo"
            message={
              /upstream|503|unreachable|network/i.test(String(alertsError))
                ? 'Chưa kết nối dịch vụ Cảnh báo (Notification Service). Vui lòng thử lại sau.'
                : alertsError
            }
            onRetry={refetchAlerts}
          />
        )}

        <AlertFilters
          statusOptions={alertStatusOptions}
          severityOptions={alertSeverityOptions}
          activeStatus={statusFilter}
          activeSeverity={severityFilter}
          onStatusChange={setStatusFilter}
          onSeverityChange={setSeverityFilter}
        />

        <div className="alerts-content-grid">
          <section className="alerts-stream-section">
            <div className="alerts-stream-header">
              <h2>
                Danh sách cảnh báo
                <span>({filteredAlerts.length})</span>
              </h2>

              <span className="alerts-status-indicator">
                {alertsLoading
                  ? 'Đang cập nhật...'
                  : !USE_MOCK && alertsError
                    ? 'Notification Service chưa khả dụng'
                    : 'Hệ thống đang giám sát'}
              </span>
            </div>

            {alertsLoading && alerts.length === 0 ? (
              <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
                <LoadingSpinner size="lg" text="Đang tải cảnh báo..." />
              </div>
            ) : !USE_MOCK && alertsError && filteredAlerts.length === 0 ? (
              <EmptyState
                title="Chưa kết nối dịch vụ Cảnh báo (Notification Service)"
                description="Không thể tải danh sách cảnh báo do dịch vụ thông báo hiện chưa khả dụng."
              />
            ) : filteredAlerts.length === 0 ? (
              <EmptyState
                title="Không có cảnh báo nào"
                description={
                  alerts.length === 0
                    ? 'Hiện tại không có sự kiện bất thường nào trong nhà yến.'
                    : 'Không tìm thấy cảnh báo phù hợp với bộ lọc đã chọn.'
                }
              />
            ) : (
              <AlertList
                alerts={filteredAlerts}
                selectedAlertId={selectedAlertId}
                onSelectAlert={(alert) => setSelectedAlertId(alert.id)}
                onAcknowledge={handleAcknowledge}
                onResolve={handleResolve}
              />
            )}
          </section>

          <aside className="alerts-sidebar-panel">
            <AlertDetailPanel
              alert={selectedAlert}
              onClose={() => setSelectedAlertId(null)}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
            />
          </aside>
        </div>
      </div>
    </AppLayout>
  )
}

export default AlertsPage
