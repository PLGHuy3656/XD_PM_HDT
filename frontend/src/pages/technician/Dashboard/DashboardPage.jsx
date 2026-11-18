import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'

import DeviceStatusPanel from '../../../components/features/technician/dashboard/DeviceStatusPanel'
import SensorHealthPanel from '../../../components/features/technician/dashboard/SensorHealthPanel'
import ConnectivityPanel from '../../../components/features/technician/dashboard/ConnectivityPanel'
import AlertsPanel from '../../../components/features/technician/dashboard/AlertsPanel'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'
import EnvironmentSelect from '../../../components/ui/Select'

import { useAuth } from '../../../context/AuthContext'
import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'

import './DashboardPage.css'

function StatusDot({ status }) {
  return <span className={`technician-status-dot ${status}`} />
}

function CollapseButton({ collapsed, onClick, label }) {
  return (
    <button
      className="technician-collapse-button"
      type="button"
      onClick={onClick}
      aria-label={`${collapsed ? 'Mở rộng' : 'Thu gọn'} ${label}`}
      aria-expanded={!collapsed}
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path
          d={collapsed ? 'M6 9l6 6 6-6' : 'M6 15l6-6 6 6'}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </button>
  )
}

function SectionTitle({
  eyebrow,
  title,
  description,
  collapsed,
  onToggle,
}) {
  return (
    <div
      className={`technician-section-title ${
        collapsed ? 'technician-section-title--collapsed' : ''
      }`}
    >
      <div className="technician-section-title__content">
        <span>{eyebrow}</span>

        <div className="technician-section-title__text">
          <h2>{title}</h2>

          {!collapsed && description && (
            <p>{description}</p>
          )}
        </div>
      </div>

      <CollapseButton
        collapsed={collapsed}
        onClick={onToggle}
        label={title}
      />
    </div>
  )
}

function SystemStatCard({ item }) {
  return (
    <article className="technician-stat-card">
      <div className="technician-stat-card__top">
        <span className="technician-stat-card__icon">
          {item.icon}
        </span>

        <span
          className={`technician-stat-card__status technician-stat-card__status--${item.status}`}
        >
          <StatusDot status={item.status} />
          {item.statusLabel}
        </span>
      </div>

      <div className="technician-stat-card__body">
        <span>{item.label}</span>
        <strong>{item.value}</strong>
        <p>{item.description}</p>
      </div>
    </article>
  )
}

function DashboardPage() {
  const { user } = useAuth()
  const {
    systemStats,
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    devices,
    alerts,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const [collapsedSections, setCollapsedSections] = useState({
    system: false,
    devices: false,
    alerts: false,
  })

  const toggleSection = (section) => {
    setCollapsedSections((current) => ({
      ...current,
      [section]: !current[section],
    }))
  }

  const techName = user?.fullName || user?.name || 'Kỹ thuật viên'

  return (
    <AppLayout>
      <div className="technician-dashboard">
        <section className="technician-welcome">
          <div className="technician-welcome__content">
            <span className="technician-welcome__eyebrow">
              NESTMATE TECHNICAL OVERVIEW
            </span>

            <h1>
              Chào buổi sáng, <strong>{techName}</strong>
            </h1>

            <p>
              Theo dõi trạng thái thiết bị, kết nối và sức khỏe hạ tầng nhà yến
              được phân công.
            </p>

            <div className="technician-welcome__system">
              <span>Tình trạng hệ thống</span>

              <strong>
                <StatusDot status="healthy" />
                Hoạt động ổn định
              </strong>
            </div>
          </div>

          <div className="technician-welcome__farm">
            <span>NHÀ YẾN ĐANG GIÁM SÁT</span>

            {farms.length > 1 ? (
              <div style={{ marginTop: '0.25rem' }}>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  onChange={setSelectedFarmId}
                  options={farms.map((f) => ({
                    value: f.id,
                    label: f.name,
                  }))}
                />
              </div>
            ) : (
              <button type="button">
                <div>
                  <StatusDot status="healthy" />
                  <strong>{selectedFarm?.name || 'Chưa phân công'}</strong>
                </div>
                <span>›</span>
              </button>
            )}

            <p>
              Mã trại: <strong>{selectedFarm?.code || '---'}</strong> · Cập nhật vừa xong
            </p>
          </div>
        </section>

        {error && (
          <ErrorMessage
            title="Lỗi tải dữ liệu kỹ thuật viên"
            message={error}
            onRetry={refetch}
          />
        )}

        {loading && !selectedFarm ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải dữ liệu kỹ thuật..." />
          </div>
        ) : (
          <>
            <section className="technician-dashboard-section">
              <SectionTitle
                eyebrow="SYSTEM HEALTH"
                title="Tình trạng hệ thống"
                description="Tổng quan nhanh trạng thái hạ tầng kỹ thuật"
                collapsed={collapsedSections.system}
                onToggle={() => toggleSection('system')}
              />

              {!collapsedSections.system && (
                <div className="technician-stats-grid">
                  {systemStats.map((item) => (
                    <SystemStatCard key={item.id} item={item} />
                  ))}
                </div>
              )}
            </section>

            <section className="technician-dashboard-section">
              <SectionTitle
                eyebrow="DEVICE & DIAGNOSTICS"
                title="Thiết bị & trạng thái"
                description="Theo dõi node, sensor và kết nối hệ thống"
                collapsed={collapsedSections.devices}
                onToggle={() => toggleSection('devices')}
              />

              {!collapsedSections.devices && (
                <div className="technician-main-grid">
                  <DeviceStatusPanel devices={devices} />

                  <div className="technician-side-column">
                    <SensorHealthPanel />
                    <ConnectivityPanel />
                  </div>
                </div>
              )}
            </section>

            <section className="technician-dashboard-section">
              <SectionTitle
                eyebrow="TECHNICAL ALERTS"
                title="Cảnh báo gần đây"
                description="Các sự kiện kỹ thuật cần Technician chú ý"
                collapsed={collapsedSections.alerts}
                onToggle={() => toggleSection('alerts')}
              />

              {!collapsedSections.alerts && (
                <section className="technician-card technician-alerts-panel">
                  <AlertsPanel alerts={alerts} />
                </section>
              )}
            </section>
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default DashboardPage
