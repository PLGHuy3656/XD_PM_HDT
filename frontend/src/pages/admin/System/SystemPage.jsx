import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import SystemOverview from '../../../components/features/admin/system/SystemOverview'
import SystemSettings from '../../../components/features/admin/system/SystemSettings'
import SystemAuditLog from '../../../components/features/admin/system/SystemAuditLog'
import { useAdminData } from '../../../features/admin'
import './SystemPage.css'

const tabs = [
  {
    id: 'overview',
    label: 'Tổng quan',
  },
  {
    id: 'settings',
    label: 'Cấu hình',
  },
  {
    id: 'audit',
    label: 'Nhật ký hoạt động',
  },
]

function SystemPage() {
  const [activeTab, setActiveTab] =
    useState('overview')
  const { systemHealth, alerts, loading, error } = useAdminData()

  return (
    <AppLayout>
      <div className="admin-system-page">
        <section className="admin-system-hero">
          <div>
            <span>SYSTEM ADMINISTRATION</span>
            <h1>Hệ thống</h1>

            <p>
              Giám sát sức khỏe dịch vụ, cấu hình mặc định
              và nhật ký hoạt động của NestMate.
            </p>
          </div>

          <span className="admin-system-overall-status">
            <i />
            {error ? 'Degraded' : 'Operational'}
          </span>
        </section>

        <nav className="admin-system-tabs">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={
                activeTab === tab.id
                  ? 'active'
                  : ''
              }
              onClick={() =>
                setActiveTab(tab.id)
              }
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {activeTab === 'overview' && (
          <SystemOverview services={systemHealth} alerts={alerts} />
        )}

        {activeTab === 'settings' && (
          <SystemSettings />
        )}

        {activeTab === 'audit' && (
          <SystemAuditLog />
        )}
      </div>
    </AppLayout>
  )
}


export default SystemPage