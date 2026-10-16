import { useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import SectionCard from '../../../components/features/farm-owner/dashboard/SectionCard'
import StatusBadge from '../../../components/features/farm-owner/dashboard/StatusBadge'
import DeviceQuickCard from '../../../components/features/farm-owner/dashboard/DeviceQuickCard'
import AlertItem from '../../../components/features/farm-owner/dashboard/AlertItem'

import '../../../components/features/farm-owner/dashboard/DashboardComponents.css'
import './DashboardPage.css'

import {
  environmentMetrics,
  mockDevices,
  mockAlerts,
} from '../../../components/features/farm-owner/dashboard/dashboardMockData'

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

function LiveCamera() {
  return (
    <div className="live-camera-layout">
      <div className="camera-preview">
        <div className="camera-toolbar">
          <div>
            <span className="camera-live-dot" />
            LIVE
          </div>

          <span>CAM-01 · Lối vào chính</span>
        </div>

        <div className="camera-placeholder">
          <CameraIcon />

          <strong>Camera trực tiếp</strong>

          <span>
            Luồng camera sẽ được kết nối từ Camera Node
          </span>
        </div>

        <div className="mock-detection detection-one">
          <span>Swiftlet · 96%</span>
        </div>

        <div className="mock-detection detection-two">
          <span>Swiftlet · 93%</span>
        </div>
      </div>

      <aside className="camera-information">
        <div className="camera-online">
          <span className="camera-online-dot" />

          <div>
            <strong>Camera đang trực tuyến</strong>
            <small>CAM-01 · AI đang hoạt động</small>
          </div>
        </div>

        <div className="camera-stat-grid">
          <article>
            <span>Chim vào</span>
            <strong>128</strong>
            <small>Hôm nay</small>
          </article>

          <article>
            <span>Chim ra</span>
            <strong>96</strong>
            <small>Hôm nay</small>
          </article>

          <article>
            <span>Chênh lệch</span>
            <strong>+32</strong>
            <small>Ước tính hiện diện</small>
          </article>

          <article>
            <span>Sự kiện AI</span>
            <strong>03</strong>
            <small>Cần kiểm tra</small>
          </article>
        </div>

        <button
          type="button"
          className="open-camera-button"
        >
          Xem camera
          <span>→</span>
        </button>
      </aside>
    </div>
  )
}

function EnvironmentPanel() {
  const [selectedMetric, setSelectedMetric] =
    useState('temperature')

  const [hoveredPoint, setHoveredPoint] =
    useState(null)

  const metric = environmentMetrics[selectedMetric]

  const width = 700
  const height = 105

  const points = metric.values.map((value, index) => {
    const x =
      (index / (metric.values.length - 1)) *
      width

    const y =
      height -
      ((value - metric.min) /
        (metric.max - metric.min)) *
        height

    const hour = Math.round(
      (index / (metric.values.length - 1)) * 24
    )

    return {
      x,
      y,
      value,
      time: `${String(hour).padStart(2, '0')}:00`,
    }
  })

  const polyline = points
    .map((point) => `${point.x},${point.y}`)
    .join(' ')

  const currentPercent =
    ((metric.value - metric.min) /
      (metric.max - metric.min)) *
    100

  const safeMinPercent =
    ((metric.safeMin - metric.min) /
      (metric.max - metric.min)) *
    100

  const safeMaxPercent =
    ((metric.safeMax - metric.min) /
      (metric.max - metric.min)) *
    100

  return (
    <div className="environment-panel">
      <div className="environment-tabs">
        {Object.entries(environmentMetrics).map(
          ([key, item]) => (
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
          )
        )}
      </div>

      <div className="environment-summary">
        <div>
          <span>Hiện tại</span>
          <strong>{metric.displayValue}</strong>
        </div>

        <StatusBadge status="normal">
          Trong ngưỡng
        </StatusBadge>
      </div>

      <div className="environment-range">
        <div className="range-information">
          <span>
            {metric.min}{metric.unit}
          </span>

          <strong>
            Ngưỡng khuyến nghị:
            {' '}
            {metric.safeMin}–{metric.safeMax}
            {metric.unit}
          </strong>

          <span>
            {metric.max}{metric.unit}
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
          <line
            x1="0"
            y1="35"
            x2={width}
            y2="35"
            className="chart-grid-line"
          />

          <line
            x1="0"
            y1="70"
            x2={width}
            y2="70"
            className="chart-grid-line"
          />

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
              r="9"
              className="chart-hover-target"
              onMouseEnter={() =>
                setHoveredPoint(point)
              }
            />
          ))}

          <circle
            cx={points.at(-1).x}
            cy={points.at(-1).y}
            r="4"
            className="current-chart-point"
          />
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

function OperationsOverview() {
  return (
    <div className="operations-grid">
      <section className="operations-environment">
        <div className="operations-section-title">
          <div>
            <h3>Môi trường</h3>
            <p>
              Chỉ số hiện tại và ngưỡng vận hành
            </p>
          </div>
        </div>

        <EnvironmentPanel />
      </section>

      <section className="operations-devices">
        <div className="operations-section-title">
          <div>
            <h3>Thiết bị nhanh</h3>
            <p>Thiết bị điều khiển chính</p>
          </div>
        </div>

        <div className="quick-device-list">
          {mockDevices.map((device) => (
            <DeviceQuickCard
              key={device.id}
              {...device}
            />
          ))}
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
          >
            Xem tất cả
          </button>
        </div>

        <div className="alert-list">
          {mockAlerts.map((alert) => (
            <AlertItem
              key={alert.id}
              {...alert}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

function DashboardPage() {
  return (
    <AppLayout>
      <div className="owner-dashboard">
      <section className="dashboard-welcome">
        <div className="dashboard-welcome-left">
          <div className="dashboard-welcome-copy">
            <span className="dashboard-eyebrow">
              NESTMATE OVERVIEW
            </span>

            <h1>
              Chào buổi sáng,
              <strong> Farm Owner</strong>
            </h1>

            <p>
              Mọi thứ trong nhà yến đang được theo dõi.
              Các chỉ số môi trường hiện ở trạng thái ổn định.
            </p>
          </div>

          <div className="dashboard-system-status">
            <span>Tình trạng hệ thống</span>

            <StatusBadge status="normal">
              Hoạt động ổn định
            </StatusBadge>
          </div>
        </div>

        <div className="dashboard-farm">
          <span className="dashboard-farm-label">
            Nhà yến đang theo dõi
          </span>

          <button
            type="button"
            className="dashboard-farm-selector"
          >
            <span className="farm-status-dot" />

            <span className="farm-selector-copy">
              <strong>Trại Bình Chánh</strong>
              <small>Hoạt động bình thường</small>
            </span>

            <svg
              className="farm-chevron"
              viewBox="0 0 24 24"
              aria-hidden="true"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m8 10 4 4 4-4" />
            </svg>
          </button>

          <p className="farm-last-update">
            Cập nhật dữ liệu gần nhất:
            <strong> vài giây trước</strong>
          </p>
        </div>
      </section>

        <SectionCard
          title="Live Camera"
          subtitle="Giám sát lối vào và phân tích AI theo thời gian thực"
          className="live-camera-card"
        >
          <LiveCamera />
        </SectionCard>

        <SectionCard
          title="Tổng quan vận hành"
          subtitle="Môi trường, thiết bị và cảnh báo của nhà yến"
          className="operations-card"
        >
          <OperationsOverview />
        </SectionCard>
      </div>
    </AppLayout>
  )
}

export default DashboardPage