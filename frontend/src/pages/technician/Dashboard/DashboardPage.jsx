import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import './DashboardPage.css'

const systemStats = [
  {
    id: 'nodes',
    label: 'Device Nodes',
    value: '8 / 8',
    description: 'Tất cả node đang phản hồi',
    status: 'healthy',
    statusLabel: 'Hoạt động tốt',
    icon: '▣',
  },
  {
    id: 'sensors',
    label: 'Sensors',
    value: '24 / 26',
    description: '2 sensor cần kiểm tra',
    status: 'warning',
    statusLabel: 'Cần chú ý',
    icon: '⌁',
  },
  {
    id: 'actuators',
    label: 'Actuators',
    value: '6 / 6',
    description: 'Sẵn sàng hoạt động',
    status: 'healthy',
    statusLabel: 'Sẵn sàng',
    icon: '⚙',
  },
  {
    id: 'mqtt',
    label: 'MQTT',
    value: 'Connected',
    description: 'Latency 28 ms',
    status: 'healthy',
    statusLabel: 'Đã kết nối',
    icon: '↯',
  },
]

const devices = [
  {
    id: 'ESP32-01',
    zone: 'Tầng 1 · Khu A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '12 giây trước',
  },
  {
    id: 'ESP32-02',
    zone: 'Tầng 2 · Khu A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '18 giây trước',
  },
  {
    id: 'ESP32-03',
    zone: 'Tầng 1 · Khu B',
    status: 'warning',
    sensors: '3 / 4',
    lastSeen: '1 phút trước',
  },
  {
    id: 'ESP32-04',
    zone: 'Tầng 2 · Khu B',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '22 giây trước',
  },
  {
    id: 'ESP32-05',
    zone: 'Phòng kỹ thuật',
    status: 'offline',
    sensors: '0 / 4',
    lastSeen: '12 phút trước',
  },
]

const sensorHealth = [
  { label: 'Healthy', value: 24, status: 'healthy' },
  { label: 'Warning', value: 2, status: 'warning' },
  { label: 'Offline', value: 0, status: 'danger' },
]

const alerts = [
  {
    id: 1,
    level: 'critical',
    title: 'ESP32-05 mất kết nối',
    description: 'Không nhận telemetry trong 12 phút',
    time: '12 phút trước',
  },
  {
    id: 2,
    level: 'warning',
    title: 'SHT31-03 phản hồi không ổn định',
    description: 'ESP32-03 · Tầng 1 · Khu B',
    time: '28 phút trước',
  },
  {
    id: 3,
    level: 'info',
    title: 'MQTT đã kết nối lại',
    description: 'ESP32-02 hoạt động bình thường',
    time: '1 giờ trước',
  },
]

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

function DeviceStatusPanel() {
  return (
    <section className="technician-card technician-device-panel">
      <div className="technician-card-heading">
        <div>
          <span>DEVICE MANAGEMENT</span>
          <h3>Trạng thái thiết bị</h3>
          <p>
            Theo dõi controller và sensor đang kết nối trong nhà yến
          </p>
        </div>

        <button type="button" className="technician-link-button">
          Xem tất cả
          <span>›</span>
        </button>
      </div>

      <div className="technician-device-list">
        <div className="technician-device-list__header">
          <span>Node</span>
          <span>Khu vực</span>
          <span>Sensor</span>
          <span>Trạng thái</span>
          <span>Cập nhật</span>
        </div>

        {devices.map((device) => (
          <article
            className="technician-device-row"
            key={device.id}
          >
            <div className="technician-device-row__node">
              <span
                className={`technician-device-icon technician-device-icon--${device.status}`}
              >
                ▣
              </span>

              <strong>{device.id}</strong>
            </div>

            <span>{device.zone}</span>

            <strong className="technician-device-row__sensor">
              {device.sensors}
            </strong>

            <span
              className={`technician-device-state technician-device-state--${device.status}`}
            >
              <StatusDot
                status={
                  device.status === 'online'
                    ? 'healthy'
                    : device.status === 'warning'
                      ? 'warning'
                      : 'danger'
                }
              />

              {device.status === 'online'
                ? 'Online'
                : device.status === 'warning'
                  ? 'Warning'
                  : 'Offline'}
            </span>

            <span className="technician-device-row__time">
              {device.lastSeen}
            </span>
          </article>
        ))}
      </div>
    </section>
  )
}

function SensorHealthPanel() {
  return (
    <section className="technician-card technician-health-panel">
      <div className="technician-card-heading">
        <div>
          <span>DIAGNOSTICS</span>
          <h3>Sensor Health</h3>
          <p>Tình trạng cảm biến đang được giám sát</p>
        </div>
      </div>

      <div className="technician-health-score">
        <div className="technician-health-ring">
          <div>
            <strong>92%</strong>
            <span>Healthy</span>
          </div>
        </div>

        <div className="technician-health-summary">
          {sensorHealth.map((item) => (
            <div
              className="technician-health-summary__item"
              key={item.label}
            >
              <span>
                <StatusDot status={item.status} />
                {item.label}
              </span>

              <strong>{item.value}</strong>
            </div>
          ))}
        </div>
      </div>

      <div className="technician-health-footer">
        <span>26 sensor được đăng ký</span>

        <button type="button">
          Chẩn đoán
          <span>›</span>
        </button>
      </div>
    </section>
  )
}

function ConnectivityPanel() {
  return (
    <section className="technician-card technician-connectivity-panel">
      <div className="technician-card-heading">
        <div>
          <span>CONNECTIVITY</span>
          <h3>Kết nối hệ thống</h3>
          <p>Trạng thái giao tiếp giữa thiết bị và hệ thống</p>
        </div>
      </div>

      <div className="technician-connectivity-list">
        <div>
          <span>
            <StatusDot status="healthy" />
            MQTT Broker
          </span>
          <strong>Connected</strong>
        </div>

        <div>
          <span>
            <StatusDot status="healthy" />
            Internet
          </span>
          <strong>Online</strong>
        </div>

        <div>
          <span>
            <StatusDot status="healthy" />
            Edge Gateway
          </span>
          <strong>Online</strong>
        </div>

        <div>
          <span>Latency</span>
          <strong>28 ms</strong>
        </div>

        <div>
          <span>Last Sync</span>
          <strong>14:32:08</strong>
        </div>
      </div>
    </section>
  )
}

function AlertsPanel() {
  return (
    <div className="technician-alert-list">
      {alerts.map((alert) => (
        <article
          className="technician-alert-item"
          key={alert.id}
        >
          <span
            className={`technician-alert-item__icon technician-alert-item__icon--${alert.level}`}
          >
            {alert.level === 'critical'
              ? '!'
              : alert.level === 'warning'
                ? '▲'
                : 'i'}
          </span>

          <div>
            <strong>{alert.title}</strong>
            <p>{alert.description}</p>
          </div>

          <time>{alert.time}</time>
        </article>
      ))}
    </div>
  )
}

function DashboardPage() {
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

  return (
    <AppLayout>
      <div className="technician-dashboard">
        <section className="technician-welcome">
          <div className="technician-welcome__content">
            <span className="technician-welcome__eyebrow">
              NESTMATE TECHNICAL OVERVIEW
            </span>

            <h1>Tổng quan kỹ thuật</h1>

            <p>
              Theo dõi trạng thái thiết bị, kết nối và sức khỏe
              hệ thống nhà yến.
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

            <button type="button">
              <div>
                <StatusDot status="healthy" />
                <strong>Trại Bình Chánh</strong>
              </div>

              <span>›</span>
            </button>

            <p>Cập nhật dữ liệu gần nhất: vài giây trước</p>
          </div>
        </section>

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
                <SystemStatCard
                  key={item.id}
                  item={item}
                />
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
              <DeviceStatusPanel />

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
              <AlertsPanel />
            </section>
          )}
        </section>
      </div>
    </AppLayout>
  )
}

export default DashboardPage