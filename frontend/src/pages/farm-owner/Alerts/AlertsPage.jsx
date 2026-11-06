import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import AlertFilters from '../../../components/features/farm-owner/alerts/AlertFilters'
import AlertList from '../../../components/features/farm-owner/alerts/AlertList'
import AlertDetailPanel from '../../../components/features/farm-owner/alerts/AlertDetailPanel'

import {
  alertFarms,
  alerts as initialAlerts,
  alertStatusOptions,
  alertSeverityOptions,
} from '../../../components/features/farm-owner/alerts/alertsMockData'

import './AlertsPage.css'

function AlertsPage() {
  const [farmId, setFarmId] = useState(alertFarms[0].id)
  const [zoneId, setZoneId] = useState('all')

  const [statusFilter, setStatusFilter] =
    useState('ALL')

  const [severityFilter, setSeverityFilter] =
    useState('ALL')

  const [alerts, setAlerts] = useState(initialAlerts)
  const [selectedAlertId, setSelectedAlertId] =
    useState(null)

  const selectedFarm =
    alertFarms.find((farm) => farm.id === farmId) ??
    alertFarms[0]

  const selectedAlert =
    alerts.find(
      (alert) => alert.id === selectedAlertId,
    ) ?? null

  const filteredAlerts = useMemo(() => {
    return alerts.filter((alert) => {
      const matchesFarm = alert.farmId === farmId

      const matchesZone =
        zoneId === 'all' || alert.zoneId === zoneId

      const matchesStatus =
        statusFilter === 'ALL' ||
        alert.status === statusFilter

      const matchesSeverity =
        severityFilter === 'ALL' ||
        alert.severity === severityFilter

      return (
        matchesFarm &&
        matchesZone &&
        matchesStatus &&
        matchesSeverity
      )
    })
  }, [
    alerts,
    farmId,
    zoneId,
    statusFilter,
    severityFilter,
  ])

  function handleFarmChange(nextFarmId) {
    const nextFarm =
      alertFarms.find(
        (farm) => farm.id === nextFarmId,
      ) ?? alertFarms[0]

    setFarmId(nextFarm.id)
    setZoneId('all')
  }

  function handleAcknowledge(alertId) {
    setAlerts((currentAlerts) =>
      currentAlerts.map((alert) =>
        alert.id === alertId
          ? {
              ...alert,
              status: 'ACKNOWLEDGED',
            }
          : alert,
      ),
    )
  }

  function handleResolve(alertId) {
    setAlerts((currentAlerts) =>
      currentAlerts.map((alert) =>
        alert.id === alertId
          ? {
              ...alert,
              status: 'RESOLVED',
            }
          : alert,
      ),
    )
  }

  return (
    <AppLayout>
      <div className="alerts-page">
        <header className="alerts-page-heading">
          <div>
            <span className="alerts-eyebrow">
              MONITORING & ALERTS
            </span>

            <h1>Cảnh báo</h1>

            <p>
              Theo dõi và xử lý các bất thường về môi
              trường, thiết bị và AI tại nhà yến.
            </p>
          </div>

          <div className="alerts-context-selectors">
            <label>
              <span>Nhà yến</span>

              <EnvironmentSelect
                value={farmId}
                onChange={handleFarmChange}
                options={alertFarms.map((farm) => ({
                  value: farm.id,
                  label: farm.name,
                }))}
              />
            </label>

            <label>
              <span>Khu vực</span>

              <EnvironmentSelect
                value={zoneId}
                onChange={setZoneId}
                options={selectedFarm.zones.map(
                  (zone) => ({
                    value: zone.id,
                    label: zone.name,
                  }),
                )}
              />
            </label>
          </div>
        </header>

        <AlertFilters
          status={statusFilter}
          severity={severityFilter}
          statusOptions={alertStatusOptions}
          severityOptions={alertSeverityOptions}
          onStatusChange={setStatusFilter}
          onSeverityChange={setSeverityFilter}
        />

        <section className="alerts-results">
          <div className="alerts-results-heading">
            <div>
              <strong>Cảnh báo gần đây</strong>

              <span>
                {filteredAlerts.length} cảnh báo phù hợp
              </span>
            </div>

            <small>
              Dữ liệu hiện tại là mock frontend
            </small>
          </div>

          <AlertList
            alerts={filteredAlerts}
            onViewDetail={(alert) =>
              setSelectedAlertId(alert.id)
            }
          />
        </section>

        <AlertDetailPanel
          alert={selectedAlert}
          onClose={() => setSelectedAlertId(null)}
          onAcknowledge={handleAcknowledge}
          onResolve={handleResolve}
        />
      </div>
    </AppLayout>
  )
}

export default AlertsPage