import { useNavigate } from 'react-router-dom'
import AppLayout from '../../../components/layout/AppLayout'

import ManagementCard from '../../../components/features/admin/dashboard/ManagementCard'
import UserAccessPanel from '../../../components/features/admin/dashboard/UserAccessPanel'
import SystemHealthPanel from '../../../components/features/admin/dashboard/SystemHealthPanel'
import { managementItems as defaultManagementItems } from '../../../components/features/admin/dashboard/dashboardMockData'
import { useAdminData } from '../../../features/admin'
import { USE_MOCK } from '../../../api/config.js'

import './DashboardPage.css'

function StatusDot({ status = 'healthy' }) {
  return <span className={`admin-status-dot ${status}`} />
}

function DashboardPage() {
  const navigate = useNavigate()
  const { dashboardStats, loading, error } = useAdminData()

  const items = dashboardStats?.managementItems || (USE_MOCK ? defaultManagementItems : [])
  const roles = dashboardStats?.roles
  const recentAccounts = dashboardStats?.recentAccounts
  const services = dashboardStats?.services
  const hasServiceData = Array.isArray(services) && services.length > 0

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
            <StatusDot status={error ? 'attention' : (loading || !hasServiceData ? 'attention' : 'healthy')} />

            <div>
              <span>PLATFORM STATUS</span>
              <strong>
                {error
                  ? 'Cần kiểm tra API'
                  : loading
                    ? 'Đang kiểm tra...'
                    : hasServiceData
                      ? 'Hoạt động ổn định'
                      : 'Chế độ quản trị'}
              </strong>
            </div>
          </div>
        </section>

        {error && (
          <div className="admin-dashboard-error" style={{ padding: '1rem', margin: '1rem 0', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', borderRadius: '8px', color: '#ef4444' }}>
            <span>⚠️ {error}</span>
          </div>
        )}

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
            {items.map((item) => (
              <ManagementCard
                key={item.id}
                item={item}
                onOpen={navigate}
              />
            ))}
          </div>
        </section>

        <section className="admin-dashboard-section">
          <UserAccessPanel
            onOpen={navigate}
            roles={roles}
            recentAccounts={recentAccounts}
          />
        </section>

        <section className="admin-dashboard-section">
          <SystemHealthPanel
            onOpen={navigate}
            services={services}
          />
        </section>
      </div>
    </AppLayout>
  )
}


export default DashboardPage