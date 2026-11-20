import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import EnvironmentSelect from '../../../components/ui/Select'
import AppLayout from '../../../components/layout/AppLayout'
import SectionCard from '../../../components/features/farm-owner/dashboard/SectionCard'
import StatusBadge from '../../../components/features/farm-owner/dashboard/StatusBadge'
import DeviceQuickCard from '../../../components/features/farm-owner/dashboard/DeviceQuickCard'
import AlertItem from '../../../components/features/farm-owner/dashboard/AlertItem'
import { LoadingSpinner } from '../../../components/common/feedback/index.js'

import DashboardAiCamera from '../../../components/features/farm-owner/dashboard/DashboardAiCamera'
import {
  environmentMetrics as defaultMetrics,
  mockDevices,
  mockAlerts,
} from '../../../components/features/farm-owner/dashboard/dashboardMockData'

import { useAuth } from '../../../context/AuthContext'
import { useFarms } from '../../../features/farms/hooks/useFarms'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { useDevices } from '../../../features/devices/hooks/useDevices'
import { useAlerts } from '../../../features/alerts/hooks/useAlerts'
import { useTelemetry } from '../../../features/telemetry/hooks/useTelemetry'
import { metricSource, sourceLabel, overallSource, formatRelativeTime } from '../../../features/telemetry/provenance.js'
import { deviceStatusMeta, resolveIotState } from '../../../features/devices/deviceStatus.js'
import { useCameras } from '../../../features/cameras/hooks/useCameras'
import { USE_MOCK } from '../../../api/config.js'

import '../../../components/features/farm-owner/dashboard/DashboardComponents.css'
import './DashboardPage.css'

function EnvironmentPanel({ telemetry }) {
  const [selectedMetric, setSelectedMetric] = useState('temperature')
  const [hoveredPoint, setHoveredPoint] = useState(null)

  if (!USE_MOCK && !telemetry) {
    return (
      <div style={{ padding: '1.25rem', color: '#64748b', fontSize: '0.9rem' }}>
        Chưa có dữ liệu telemetry từ cảm biến IoT cho nhà yến này.
      </div>
    )
  }

  const effectiveMetrics = { ...defaultMetrics }
  if (!USE_MOCK) {
    // INT01-R1: real mode keeps only labels/ranges from the template — never its numbers or series
    Object.keys(effectiveMetrics).forEach((k) => {
      effectiveMetrics[k] = {
        ...effectiveMetrics[k],
        value: null,
        displayValue: '--',
        values: [],
        source: metricSource(telemetry, k),
      }
    })
  }
  if (telemetry) {
    if (telemetry.temperature != null) {
      effectiveMetrics.temperature = {
        ...effectiveMetrics.temperature,
        value: telemetry.temperature,
        displayValue: `${telemetry.temperature.toFixed(1)}°C`,
      }
    }
    if (telemetry.humidity != null) {
      effectiveMetrics.humidity = {
        ...effectiveMetrics.humidity,
        value: telemetry.humidity,
        displayValue: `${Math.round(telemetry.humidity)}%`,
      }
    }
    if (telemetry.co2 != null) {
      effectiveMetrics.co2 = {
        ...effectiveMetrics.co2,
        value: telemetry.co2,
        displayValue: `${Math.round(telemetry.co2)} ppm`,
      }
    }
    if (telemetry.light != null) {
      effectiveMetrics.light = {
        ...effectiveMetrics.light,
        value: telemetry.light,
        displayValue: `${Math.round(telemetry.light)} lux`,
      }
    }
  }

  const metric = effectiveMetrics[selectedMetric]
  const width = 460
  const height = 110
  const paddingX = 14
  const paddingY = 16

  const points = (metric.values || []).map((value, index) => {
    const x =
      paddingX +
      (index / ((metric.values || []).length - 1 || 1)) * (width - paddingX * 2)
    const ratio = (value - metric.min) / (metric.max - metric.min || 1)
    const y = height - paddingY - ratio * (height - paddingY * 2)
    return {
      x,
      y,
      value,
      time: `${String(index * 2).padStart(2, '0')}:00`,
    }
  })

  const polyline = points.map((p) => `${p.x},${p.y}`).join(' ')

  const safeMinPercent =
    ((metric.safeMin - metric.min) / (metric.max - metric.min || 1)) * 100
  const safeMaxPercent =
    ((metric.safeMax - metric.min) / (metric.max - metric.min || 1)) * 100
  const hasValue = metric.value != null && Number.isFinite(Number(metric.value))
  const inRange = hasValue && metric.value >= metric.safeMin && metric.value <= metric.safeMax
  const currentPercent = !hasValue ? null : Math.min(
    100,
    Math.max(
      0,
      ((metric.value - metric.min) / (metric.max - metric.min || 1)) * 100,
    ),
  )

  return (
    <div className="environment-card">
      <div className="environment-tab-list">
        {Object.entries(effectiveMetrics).map(([key, item]) => (
          <button
            key={key}
            type="button"
            className={
              selectedMetric === key
                ? 'environment-tab active'
                : 'environment-tab'
            }
            onClick={() => {
              setSelectedMetric(key)
              setHoveredPoint(null)
            }}
          >
            <span>{item.label}</span>
            <strong>{item.displayValue}</strong>
          </button>
        ))}
      </div>

      <div className="environment-summary">
        <div>
          <span>Hiện tại</span>
          <strong>{metric.displayValue}</strong>
          {metric.source && metric.source !== 'PHYSICAL' && (
            <small data-testid="dashboard-metric-source">{sourceLabel(metric.source)}</small>
          )}
        </div>
        {!hasValue ? (
          <StatusBadge status="offline">Chưa có dữ liệu</StatusBadge>
        ) : inRange ? (
          <StatusBadge status="normal">Trong ngưỡng</StatusBadge>
        ) : (
          <StatusBadge status="warning">Ngoài ngưỡng</StatusBadge>
        )}
      </div>

      <div className="environment-range">
        <div className="range-information">
          <span>
            {metric.min}
            {metric.unit}
          </span>
          <strong>
            Ngưỡng khuyến nghị: {metric.safeMin}–{metric.safeMax}
            {metric.unit}
          </strong>
          <span>
            {metric.max}
            {metric.unit}
          </span>
        </div>

        <div className="range-track">
          <div
            className="range-safe-zone"
            style={{
              left: `${safeMinPercent}%`,
              width: `${safeMaxPercent - safeMinPercent}%`,
            }}
          />
          {currentPercent != null && (
            <div
              className="range-current-marker"
              style={{
                left: `${currentPercent}%`,
              }}
            >
              <span />
            </div>
          )}
        </div>
      </div>

      <div
        className="compact-chart"
        onMouseLeave={() => setHoveredPoint(null)}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
        >
          <line x1="0" y1="35" x2={width} y2="35" className="chart-grid-line" />
          <line x1="0" y1="70" x2={width} y2="70" className="chart-grid-line" />
          <polyline
            points={polyline}
            className="environment-line"
            vectorEffect="non-scaling-stroke"
          />
          {points.map((point, index) => (
            <circle
              key={index}
              cx={point.x}
              cy={point.y}
              r="3.5"
              className="chart-point"
              onMouseEnter={() => setHoveredPoint(point)}
            />
          ))}
          {points.length > 0 && (
            <circle
              cx={points.at(-1).x}
              cy={points.at(-1).y}
              r="4"
              className="current-chart-point"
            />
          )}
        </svg>

        {hoveredPoint && (
          <div className="chart-tooltip">
            <span>{metric.label}</span>
            <strong>
              {hoveredPoint.value}
              {metric.unit}
            </strong>
            <small>{hoveredPoint.time}</small>
          </div>
        )}
      </div>

      <div className="chart-times">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>24:00</span>
      </div>
    </div>
  )
}

const IOT_STATE_META = {
  ONLINE: { label: 'IoT trực tuyến', badge: 'normal' },
  OFFLINE: { label: 'IoT ngoại tuyến', badge: 'danger' },
  UNKNOWN: { label: 'IoT chưa có heartbeat', badge: 'warning' },
  UNAVAILABLE: { label: 'IoT không khả dụng', badge: 'offline' },
  NONE: { label: 'Chưa có thiết bị IoT', badge: 'offline' },
}

function IotStatusStrip({ telemetry, devices, pollStatus, isStale }) {
  const state = USE_MOCK ? 'ONLINE' : resolveIotState(devices, pollStatus)
  const meta = IOT_STATE_META[state]
  const source = telemetry ? overallSource(telemetry) : null
  return (
    <div className="dashboard-iot-strip" data-testid="dashboard-iot-status" data-iot-state={state}>
      <StatusBadge status={meta.badge}>{meta.label}</StatusBadge>
      {source && source !== 'UNAVAILABLE' && (
        <span className={`dashboard-iot-source source-${source.toLowerCase()}`} data-testid="dashboard-iot-source">
          {source}
        </span>
      )}
      <small>
        Cập nhật: {telemetry?.timestamp ? formatRelativeTime(telemetry.timestamp) : '--'}
        {isStale ? ' · dữ liệu cũ' : ''}
      </small>
    </div>
  )
}

function OperationsOverview({ telemetry, devices = [], alerts = [], alertsError = null, pollStatus = 'idle', isStale = false }) {
  const navigate = useNavigate()

  // Cameras have their own AI block above; quick devices list IoT nodes with the INT01-R1 status vocabulary
  const iotDevices = devices.filter((d) => d.type !== 'CAMERA')
  const quickDevices =
    iotDevices.length > 0
      ? iotDevices.slice(0, 4).map((d) => ({
          id: d.id,
          name: d.name,
          // DeviceQuickCard reads `description` / `connected`: presence must come from IoT, never default to online
          description: `${d.zoneName || d.zoneId || '--'} · ${deviceStatusMeta(d.status).label}`,
          connected: d.status === 'ONLINE' || d.status === 'WARNING',
        }))
      : (USE_MOCK ? mockDevices : [])

  const recentAlerts =
    alerts.length > 0 ? alerts.slice(0, 4) : (USE_MOCK ? mockAlerts : [])

  return (
    <div className="operations-grid">
      <section className="operations-environment">
        <div className="operations-section-title">
          <div>
            <h3>Môi trường</h3>
            <p>Chỉ số hiện tại và ngưỡng vận hành</p>
          </div>
        </div>
        <IotStatusStrip telemetry={telemetry} devices={devices} pollStatus={pollStatus} isStale={isStale} />
        <EnvironmentPanel telemetry={telemetry} />
      </section>

      <section className="operations-devices">
        <div className="operations-section-title">
          <div>
            <h3>Thiết bị nhanh</h3>
            <p>Thiết bị điều khiển chính</p>
          </div>
        </div>

        <div className="quick-device-list">
          {quickDevices.length === 0 ? (
            <div style={{ padding: '0.75rem', color: '#64748b', fontSize: '0.88rem' }}>
              Chưa có thiết bị IoT nào trong nhà yến này.
            </div>
          ) : (
            quickDevices.map((device) => (
              <DeviceQuickCard key={device.id} {...device} />
            ))
          )}
        </div>
      </section>

      <section className="operations-alerts">
        <div className="operations-section-title">
          <div>
            <h3>Cảnh báo gần đây</h3>
            <p>Sự kiện cần chú ý</p>
          </div>

          <button
            type="button"
            className="dashboard-text-button"
            onClick={() => navigate('/owner/alerts')}
          >
            Xem tất cả
          </button>
        </div>

        <div className="alert-list">
          {!USE_MOCK && alertsError ? (
            <div style={{ padding: '0.75rem', color: '#64748b', fontSize: '0.88rem' }}>
              Chưa kết nối dịch vụ Cảnh báo.
            </div>
          ) : recentAlerts.length === 0 ? (
            <div style={{ padding: '0.75rem', color: '#64748b', fontSize: '0.88rem' }}>
              Chưa có cảnh báo nào.
            </div>
          ) : (
            recentAlerts.map((alert) => (
              <AlertItem key={alert.id} {...alert} />
            ))
          )}
        </div>
      </section>
    </div>
  )
}

function DashboardPage() {
  const { user } = useAuth()
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    loading: farmsLoading,
  } = useFarms()

  const { devices } = useDevices(selectedFarmId, { requireFarmId: true })
  const { alerts, error: alertsError } = useAlerts(selectedFarmId)
  const { telemetry, pollStatus, isStale } = useTelemetry(selectedFarmId)
  const { cameras } = useCameras(selectedFarmId, null, { requireFarmId: true })

  const ownerName = user?.fullName || user?.name || 'Farm Owner'
  const hasLiveSignal = Boolean(telemetry) || devices.some((d) => d.status === 'ONLINE')

  return (
    <AppLayout>
      <div className="owner-dashboard">
        <section className="dashboard-welcome">
          <div className="dashboard-welcome-main">
            <div className="dashboard-welcome-copy">
              <span className="dashboard-eyebrow">NESTMATE OVERVIEW</span>

              <h1>
                Chào buổi sáng,
                <strong> {ownerName}</strong>
              </h1>

              <p>
                {hasLiveSignal || USE_MOCK
                  ? 'Mọi thứ trong nhà yến đang được theo dõi. Các chỉ số môi trường hiện ở trạng thái ổn định.'
                  : 'Hệ thống đang sẵn sàng. Chọn nhà yến và kết nối thiết bị IoT/AI để nhận dữ liệu thời gian thực.'}
              </p>
            </div>

            <div className="dashboard-system-status">
              <span>Tình trạng hệ thống</span>
              <StatusBadge status={hasLiveSignal || USE_MOCK ? 'normal' : 'warning'}>
                {hasLiveSignal || USE_MOCK ? 'Hoạt động ổn định' : 'Chưa có dữ liệu telemetry'}
              </StatusBadge>
            </div>
          </div>

          <div className="dashboard-farm">
            <span className="dashboard-farm-label">Nhà yến đang theo dõi</span>

            {farmsLoading && !selectedFarm ? (
              <div style={{ padding: '0.5rem 0' }}>
                <LoadingSpinner size="sm" text="Đang tải..." />
              </div>
            ) : (
              <div style={{ marginTop: '0.25rem' }}>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  onChange={setSelectedFarmId}
                  options={farms.map((f) => ({
                    value: f.id,
                    label: formatFarmOptionLabel(f),
                  }))}
                />
              </div>
            )}

            <p className="farm-last-update">
              Cập nhật dữ liệu gần nhất:
              <strong> {USE_MOCK ? 'vài giây trước' : telemetry?.timestamp ? formatRelativeTime(telemetry.timestamp) : '--'}</strong>
            </p>
          </div>
        </section>

        <SectionCard
          title="Camera AI"
          subtitle="Trạng thái AI runtime, phát hiện và đếm chim — cùng nguồn với trang Giám sát chim yến"
          className="live-camera-card"
        >
          <DashboardAiCamera key={selectedFarmId || 'none'} cameras={cameras} farmId={selectedFarmId} />
        </SectionCard>

        <SectionCard
          title="Tổng quan vận hành"
          subtitle="Môi trường, thiết bị và cảnh báo của nhà yến"
          className="operations-card"
        >
          <OperationsOverview
            telemetry={telemetry}
            devices={devices}
            alerts={alerts}
            alertsError={alertsError}
            pollStatus={pollStatus}
            isStale={isStale}
          />
        </SectionCard>
      </div>
    </AppLayout>
  )
}

export default DashboardPage
