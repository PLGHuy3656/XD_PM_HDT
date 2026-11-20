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

  // INT01-R1: only services deployed in this environment count towards availability
  const deployedServices = (systemHealth || []).filter((s) => s.status !== 'NOT_DEPLOYED' && s.tier !== 'PLANNED')
  const activeCount = deployedServices.filter(
    (s) => s.status === 'HEALTHY' || s.status === 'healthy',
  ).length
  const totalCount = deployedServices.length

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
            {error
              ? 'Degraded'
              : loading
                ? 'Checking...'
                : totalCount > 0
                  ? `${activeCount}/${totalCount} Active`
                  : 'Operational'}
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