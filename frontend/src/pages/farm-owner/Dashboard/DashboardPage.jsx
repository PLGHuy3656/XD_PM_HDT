import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import EnvironmentSelect from '../../../components/ui/Select'
import AppLayout from '../../../components/layout/AppLayout'
import SectionCard from '../../../components/features/farm-owner/dashboard/SectionCard'
import StatusBadge from '../../../components/features/farm-owner/dashboard/StatusBadge'
import DeviceQuickCard from '../../../components/features/farm-owner/dashboard/DeviceQuickCard'
import AlertItem from '../../../components/features/farm-owner/dashboard/AlertItem'
import { LoadingSpinner } from '../../../components/common/feedback/index.js'

import { cameras as defaultMockCameras } from '../../../components/features/farm-owner/swiftlets/swiftletsMockData'
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
import { useCameras } from '../../../features/cameras/hooks/useCameras'
import { USE_MOCK } from '../../../api/config.js'

import '../../../components/features/farm-owner/dashboard/DashboardComponents.css'
import './DashboardPage.css'

function CameraIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="3" y="6" width="18" height="13" rx="2" />
      <circle cx="12" cy="12.5" r="3.5" />
      <path d="M8 6 9.5 4h5L16 6" />
    </svg>
  )
}

function LiveCamera({ cameras = [] }) {
  const effectiveCameras = cameras.length > 0 ? cameras : (USE_MOCK ? defaultMockCameras : [])
  const [selectedCameraId, setSelectedCameraId] = useState(effectiveCameras[0]?.id || 'CAM-01')

  if (effectiveCameras.length === 0) {
    return (
      <div style={{ padding: '1.5rem', color: '#64748b', textAlign: 'center' }}>
        Chưa có camera AI nào được cấu hình cho nhà yến này.
      </div>
    )
  }

  const selectedCamera =
    effectiveCameras.find((camera) => camera.id === selectedCameraId) ?? effectiveCameras[0]

  const currentIndex = effectiveCameras.findIndex(
    (camera) => camera.id === selectedCamera.id,
  )

  const isOnline = selectedCamera.status === 'ONLINE'

  function moveCamera(offset) {
    const nextIndex =
      (currentIndex + offset + effectiveCameras.length) % effectiveCameras.length
    setSelectedCameraId(effectiveCameras[nextIndex].id)
  }

  return (
    <div className="live-camera-layout">
      <div className={`camera-preview ${!isOnline ? 'camera-preview-offline' : ''}`}>
        <div className="camera-toolbar">
          <div>
            <span className={`camera-live-dot ${!isOnline ? 'offline' : ''}`} />
            {isOnline ? 'LIVE' : 'OFFLINE'}
          </div>
          <span>
            {selectedCamera.id} · {selectedCamera.name}
          </span>
        </div>

        {isOnline ? (
          <>
            <div className="camera-placeholder">
              <CameraIcon />
              <strong>Camera trực tiếp</strong>
              <span>Luồng camera đang được kết nối</span>
            </div>

            {(selectedCamera.detections || []).map((detection, index) => (
              <div
                key={detection.id || index}
                className={`mock-detection detection-${
                  index === 0 ? 'one' : index === 1 ? 'two' : 'three'
                }`}
              >
                <span>
                  {detection.label} · {detection.confidence}%
                </span>
              </div>
            ))}
          </>
        ) : (
          <div className="camera-placeholder camera-offline-placeholder">
            <CameraIcon />
            <strong>Camera ngoại tuyến</strong>
            <span>Không nhận được tín hiệu từ {selectedCamera.node || selectedCamera.id}</span>
          </div>
        )}
      </div>

      <aside className="camera-information">
        <div className="dashboard-camera-selector">
          <button
            type="button"
            onClick={() => moveCamera(-1)}
            aria-label="Camera trước"
          >
            ‹
          </button>

          <EnvironmentSelect
            value={selectedCamera.id}
            onChange={setSelectedCameraId}
            options={effectiveCameras.map((camera) => ({
              value: camera.id,
              label: `${camera.code || camera.id} · ${camera.name}${
                camera.status === 'OFFLINE' ? ' · Offline' : ''
              }`,
            }))}
          />

          <button
            type="button"
            onClick={() => moveCamera(1)}
            aria-label="Camera tiếp theo"
          >
            ›
          </button>
        </div>

        <div className={`camera-online ${!isOnline ? 'offline' : ''}`}>
          <span className="camera-online-dot" />
          <div>
            <strong>
              {isOnline ? 'Camera đang trực tuyến' : 'Camera ngoại tuyến'}
            </strong>
            <small>
              {selectedCamera.id} ·{' '}
              {isOnline ? 'AI đang hoạt động' : `Mất kết nối ${selectedCamera.node || ''}`}
            </small>
          </div>
        </div>

        <div className="camera-stat-grid">
          <article>
            <span>Chim vào</span>
            <strong>{isOnline ? (selectedCamera.entries ?? (USE_MOCK ? '128' : '—')) : '—'}</strong>
            <small>Hôm nay</small>
          </article>

          <article>
            <span>Chim ra</span>
            <strong>{isOnline ? (selectedCamera.exits ?? (USE_MOCK ? '94' : '—')) : '—'}</strong>
            <small>Hôm nay</small>
          </article>
        </div>
      </aside>
    </div>
  )
}

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
  const currentPercent = Math.min(
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
        </div>
        <StatusBadge status="normal">Trong ngưỡng</StatusBadge>
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
          <div
            className="range-current-marker"
            style={{
              left: `${currentPercent}%`,
            }}
          >
            <span />
          </div>
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

function OperationsOverview({ telemetry, devices = [], alerts = [], alertsError = null }) {
  const navigate = useNavigate()

  const quickDevices =
    devices.length > 0
      ? devices.slice(0, 4).map((d) => ({
          id: d.id,
          name: d.name,
          zone: d.zoneId || 'Tầng 1',
          state: d.status === 'ONLINE' ? 'Đang chạy' : 'Tắt',
          status: d.status === 'ONLINE' ? 'normal' : 'danger',
          value: d.firmware,
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
              Chưa có thiết bị nào trong nhà yến này.
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
  const { telemetry } = useTelemetry(selectedFarmId)
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
              <strong> {hasLiveSignal || USE_MOCK ? 'vài giây trước' : 'Chưa có dữ liệu'}</strong>
            </p>
          </div>
        </section>

        <SectionCard
          title="Live Camera"
          subtitle="Giám sát lối vào và phân tích AI theo thời gian thực"
          className="live-camera-card"
        >
          <LiveCamera cameras={cameras} />
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
          />
        </SectionCard>
      </div>
    </AppLayout>
  )
}

export default DashboardPage
