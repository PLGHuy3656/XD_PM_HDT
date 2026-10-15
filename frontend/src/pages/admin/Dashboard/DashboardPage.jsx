import { useNavigate } from 'react-router-dom'
import AppLayout from '../../../components/layout/AppLayout'
import './DashboardPage.css'

const managementItems = [
  {
    id: 'users',
    eyebrow: 'USER & ACCESS',
    value: '24',
    title: 'Users & Roles',
    description: '22 tài khoản đang hoạt động',
    icon: '◎',
    path: '/admin/users',
  },
  {
    id: 'farms',
    eyebrow: 'FARM MANAGEMENT',
    value: '6',
    title: 'Nhà yến',
    description: '6 nhà yến đang hoạt động',
    icon: '⌂',
    path: '/admin/farms',
  },
  {
    id: 'devices',
    eyebrow: 'DEVICE REGISTRY',
    value: '38',
    title: 'Thiết bị',
    description: '35 thiết bị đang online',
    icon: '▣',
    path: '/admin/devices',
  },
]

const roles = [
  {
    id: 'owner',
    label: 'Farm Owner',
    description: 'Quản lý và vận hành nhà yến',
    value: 18,
    icon: 'FO',
  },
  {
    id: 'technician',
    label: 'Technician',
    description: 'Thiết bị và hỗ trợ kỹ thuật',
    value: 4,
    icon: 'TE',
  },
  {
    id: 'admin',
    label: 'Administrator',
    description: 'Quản trị nền tảng',
    value: 2,
    icon: 'AD',
  },
]

const recentAccounts = [
  {
    id: 1,
    name: 'Nguyễn Minh Anh',
    email: 'minhanh@nestmate.dev',
    role: 'Farm Owner',
    time: 'Hôm nay',
  },
  {
    id: 2,
    name: 'Trần Quốc Bảo',
    email: 'quocbao@nestmate.dev',
    role: 'Technician',
    time: 'Hôm qua',
  },
  {
    id: 3,
    name: 'Lê Hoàng Nam',
    email: 'hoangnam@nestmate.dev',
    role: 'Farm Owner',
    time: '12/10/2026',
  },
]

const services = [
  { id: 'api', name: 'Backend API', status: 'healthy' },
  { id: 'database', name: 'Database', status: 'healthy' },
  { id: 'mqtt', name: 'MQTT Broker', status: 'healthy' },
  { id: 'redis', name: 'Redis', status: 'healthy' },
  {
    id: 'notification',
    name: 'Notification',
    status: 'healthy',
  },
]

function StatusDot({ status = 'healthy' }) {
  return <span className={`admin-status-dot ${status}`} />
}

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

function ManagementCard({ item, onOpen }) {
  return (
    <button
      type="button"
      className="admin-management-card"
      onClick={() => onOpen(item.path)}
    >
      <div className="admin-management-card__top">
        <span className="admin-management-card__icon">
          {item.icon}
        </span>

        <span className="admin-management-card__arrow">
          <ArrowIcon />
        </span>
      </div>

      <span className="admin-management-card__eyebrow">
        {item.eyebrow}
      </span>

      <h3>{item.title}</h3>

      <div className="admin-management-card__stats">
        <strong>{item.value}</strong>

        <span>{item.description}</span>
      </div>
    </button>
  )
}

function UserAccessPanel({ onOpen }) {
  return (
    <section className="admin-panel">
      <div className="admin-panel-heading">
        <div>
          <span>USER & ACCESS</span>
          <h2>Người dùng & phân quyền</h2>
          <p>
            Phân bổ vai trò và các tài khoản gần đây
          </p>
        </div>

        <button
          type="button"
          className="admin-heading-action"
          onClick={() => onOpen('/admin/users')}
          aria-label="Mở quản lý người dùng"
        >
          <span>Xem tất cả</span>
          <ArrowIcon />
        </button>
      </div>

      <div className="admin-role-grid">
        {roles.map((role) => (
          <article
            className="admin-role-card"
            key={role.id}
          >
            <span className="admin-role-card__icon">
              {role.icon}
            </span>

            <div className="admin-role-card__content">
              <strong>{role.label}</strong>
              <p>{role.description}</p>
            </div>

            <strong className="admin-role-card__value">
              {role.value}
            </strong>
          </article>
        ))}
      </div>

      <div className="admin-recent">
        <div className="admin-recent__heading">
          <div>
            <span>RECENT ACCOUNTS</span>
            <strong>Tài khoản gần đây</strong>
          </div>

          <span>3 tài khoản mới nhất</span>
        </div>

        <div className="admin-account-list">
          {recentAccounts.map((account) => (
            <article
              className="admin-account-row"
              key={account.id}
            >
              <span className="admin-account-avatar">
                {account.name
                  .split(' ')
                  .slice(-2)
                  .map((word) => word[0])
                  .join('')}
              </span>

              <div className="admin-account-identity">
                <strong>{account.name}</strong>
                <span>{account.email}</span>
              </div>

              <span className="admin-account-role">
                {account.role}
              </span>

              <time>{account.time}</time>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

function SystemHealthPanel({ onOpen }) {
  return (
    <button
      type="button"
      className="admin-health-strip"
      onClick={() => onOpen('/admin/system')}
    >
      <div className="admin-health-strip__title">
        <span>SYSTEM HEALTH</span>
        <strong>Hạ tầng hệ thống</strong>
      </div>

      <div className="admin-health-strip__services">
        {services.map((service) => (
          <div
            className="admin-service"
            key={service.id}
          >
            <StatusDot status={service.status} />
            <span>{service.name}</span>
          </div>
        ))}
      </div>

      <div className="admin-health-strip__end">
        <div>
          <StatusDot />
          <strong>5 / 5</strong>
          <span>Operational</span>
        </div>

        <span className="admin-health-strip__arrow">
          <ArrowIcon />
        </span>
      </div>
    </button>
  )
}

function DashboardPage() {
  const navigate = useNavigate()

  return (
    <AppLayout>
      <div className="admin-dashboard">
        <section className="admin-hero">
          <div>
            <span className="admin-hero__eyebrow">
              NESTMATE ADMINISTRATION
            </span>

            <h1>Quản trị hệ thống</h1>

            <p>
              Quản lý người dùng, nhà yến, thiết bị và
              hạ tầng NestMate.
            </p>
          </div>

          <div className="admin-hero__status">
            <StatusDot />

            <div>
              <span>PLATFORM STATUS</span>
              <strong>Hoạt động ổn định</strong>
            </div>
          </div>
        </section>

        <section className="admin-dashboard-section">
          <div className="admin-section-heading">
            <div>
              <span>ADMINISTRATION</span>
              <h2>Quản lý hệ thống</h2>
              <p>
                Các khu vực quản trị chính của NestMate
              </p>
            </div>
          </div>

          <div className="admin-management-grid">
            {managementItems.map((item) => (
              <ManagementCard
                key={item.id}
                item={item}
                onOpen={navigate}
              />
            ))}
          </div>
        </section>

        <section className="admin-dashboard-section">
          <UserAccessPanel onOpen={navigate} />
        </section>

        <section className="admin-dashboard-section">
          <SystemHealthPanel onOpen={navigate} />
        </section>
      </div>
    </AppLayout>
  )
}

export default DashboardPage