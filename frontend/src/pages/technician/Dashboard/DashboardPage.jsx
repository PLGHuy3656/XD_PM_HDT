import { useNavigate } from 'react-router-dom'
import AppLayout from '../../../components/layout/AppLayout'
import DeviceStatusPanel from '../../../components/features/technician/dashboard/DeviceStatusPanel'
import AlertsPanel from '../../../components/features/technician/dashboard/AlertsPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'
import EnvironmentSelect from '../../../components/ui/Select'

import { useAuth } from '../../../context/AuthContext'
import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { USE_MOCK } from '../../../api/config.js'

import '../TechnicianWorkspace.css'

function DashboardPage() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    devices,
    zones,
    alerts,
    alertsError,
    telemetryError,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const techName = user?.fullName || user?.name || 'Kỹ thuật viên'
  const unassignedCount = devices.filter((d) => !d.isZoneAssigned).length
  const onlineCount = devices.filter((d) => d.status === 'ONLINE').length

  return (
    <AppLayout>
      <div className="tech-ws">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN WORKSPACE</span>
            <h1>Tổng quan kỹ thuật — {techName}</h1>
            <p>
              Quản lý thiết bị, phân bổ khu vực lắp đặt và kiểm tra trạng thái kỹ thuật tại các nhà yến được Admin phân công.
            </p>

            <div className="tech-ws-quick-links">
              <button
                type="button"
                className="tech-ws-btn tech-ws-btn--primary"
                onClick={() => navigate('/technician/devices')}
              >
                Thiết bị ({devices.length})
              </button>
              <button
                type="button"
                className="tech-ws-btn"
                onClick={() => navigate('/technician/installation')}
              >
                Phân bổ Zone ({unassignedCount} chưa gán)
              </button>
              <button
                type="button"
                className="tech-ws-btn"
                onClick={() => navigate('/technician/diagnostics')}
              >
                Chẩn đoán
              </button>
            </div>
          </div>

          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách ({farms.length})</span>
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
          </div>
        </header>

        {error && (
          <ErrorMessage
            title="Lỗi tải dữ liệu kỹ thuật viên"
            message={error}
            onRetry={refetch}
          />
        )}

        {loading && farms.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải dữ liệu kỹ thuật..." />
          </div>
        ) : farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến được phân công"
            description="Liên hệ Quản trị viên (Admin) để được phân công phụ trách nhà yến."
          />
        ) : (
          <>
            <section className="tech-ws-kpi-grid">
              <article className="tech-ws-kpi-card">
                <span>Nhà yến phụ trách</span>
                <strong>{farms.length}</strong>
                <small>Đang được Admin phân công</small>
              </article>

              <article className="tech-ws-kpi-card">
                <span>Thiết bị đã đăng ký</span>
                <strong>{devices.length}</strong>
                <small>
                  {telemetryError ? 'IoT Service chưa kết nối' : `${onlineCount} trực tuyến`}
                </small>
              </article>

              <article className="tech-ws-kpi-card">
                <span>Chưa phân bổ Zone</span>
                <strong style={{ color: unassignedCount > 0 ? '#b45309' : '#059669' }}>
                  {unassignedCount}
                </strong>
                <small>Ưu tiên gán khu vực lắp đặt</small>
              </article>

              <article className="tech-ws-kpi-card">
                <span>Khu vực (Zones)</span>
                <strong>{zones.length}</strong>
                <small>{selectedFarm?.code || '---'}</small>
              </article>
            </section>

            <section className="tech-ws-grid-main">
              <DeviceStatusPanel devices={devices} />

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <section className="tech-ws-card">
                  <div className="tech-ws-card__head">
                    <h3>Nhà yến được phân công</h3>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {farms.map((farm) => (
                      <button
                        key={farm.id}
                        type="button"
                        onClick={() => setSelectedFarmId(farm.id)}
                        style={{
                          textAlign: 'left',
                          padding: '10px 12px',
                          borderRadius: '10px',
                          border: farm.id === selectedFarmId ? '1.5px solid #102d3f' : '1px solid #e2e8f0',
                          background: farm.id === selectedFarmId ? '#f8fafc' : '#fff',
                          cursor: 'pointer',
                        }}
                      >
                        <strong style={{ display: 'block', fontSize: '13px', color: '#102d3f' }}>
                          {formatFarmOptionLabel(farm)}
                        </strong>
                        <small style={{ color: '#64748b', fontSize: '11px' }}>
                          {farm.address} · {farm.zoneCount} khu vực · {farm.deviceCount} thiết bị
                        </small>
                      </button>
                    ))}
                  </div>
                </section>

                <section className="tech-ws-card">
                  <div className="tech-ws-card__head">
                    <h3>Trạng thái dịch vụ</h3>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Management Registry</span>
                      <span className="tech-badge tech-badge--online">Đã kết nối</span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>IoT Telemetry</span>
                      <span className={`tech-badge ${telemetryError ? 'tech-badge--unknown' : 'tech-badge--online'}`}>
                        {telemetryError ? 'Chưa kết nối' : 'Sẵn sàng'}
                      </span>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>Notification Alerts</span>
                      <span className={`tech-badge ${alertsError ? 'tech-badge--unknown' : 'tech-badge--online'}`}>
                        {alertsError ? 'Chưa kết nối' : 'Sẵn sàng'}
                      </span>
                    </div>
                  </div>
                </section>

                <section className="tech-ws-card">
                  <div className="tech-ws-card__head">
                    <h3>Cảnh báo kỹ thuật</h3>
                    <button
                      type="button"
                      className="tech-ws-btn"
                      onClick={() => navigate('/technician/alerts')}
                    >
                      Chi tiết ›
                    </button>
                  </div>
                  {!USE_MOCK && alertsError ? (
                    <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                      Dịch vụ Cảnh báo hiện chưa khả dụng. Cảnh báo kỹ thuật sẽ hiển thị khi dịch vụ hoạt động trở lại.
                    </p>
                  ) : (
                    <AlertsPanel alerts={alerts} />
                  )}
                </section>
              </div>
            </section>
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default DashboardPage
