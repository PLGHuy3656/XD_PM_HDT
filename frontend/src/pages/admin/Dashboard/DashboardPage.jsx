import { useNavigate } from 'react-router-dom'
import AppLayout from '../../../components/layout/AppLayout'

import ManagementCard from '../../../components/features/admin/dashboard/ManagementCard'
import UserAccessPanel from '../../../components/features/admin/dashboard/UserAccessPanel'
import SystemHealthPanel from '../../../components/features/admin/dashboard/SystemHealthPanel'
import { managementItems } from '../../../components/features/admin/dashboard/dashboardMockData'

import './DashboardPage.css'

function StatusDot({ status = 'healthy' }) {
  return <span className={`admin-status-dot ${status}`} />
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