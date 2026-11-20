import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'

import '../TechnicianWorkspace.css'

import {
  REGISTERABLE_DEVICE_TYPES,
  DEFAULT_REGISTER_TYPE,
  registrationTypeMeta,
  validateRegistration,
  registeredNotice,
  registrationErrorText,
} from '../../../features/devices/deviceRegistration.js'

// INT02-F04: only types with a real backend/hardware contract (shared with the Owner form)
const DEVICE_TYPE_OPTIONS = REGISTERABLE_DEVICE_TYPES.map((t) => ({ value: t.value, label: t.label }))

const EMPTY_REGISTER_FORM = {
  node_id: '',
  name: '',
  device_type: DEFAULT_REGISTER_TYPE,
  zone_id: '',
}

function InstallationPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    devices,
    telemetryError,
    loading,
    error,
    refetch,
    createDevice,
    updateDeviceZone,
  } = useTechnicianData()

  const [draftZones, setDraftZones] = useState({})
  const [savingId, setSavingId] = useState(null)
  const [notice, setNotice] = useState('')
  const [actionError, setActionError] = useState('')

  const [registerOpen, setRegisterOpen] = useState(false)
  const [registerForm, setRegisterForm] = useState(EMPTY_REGISTER_FORM)
  const [registerError, setRegisterError] = useState('')
  const [registerSubmitting, setRegisterSubmitting] = useState(false)

  const zoneOptions = [
    { value: '', label: 'Chưa phân bổ Zone' },
    ...zones.map((z) => ({
      value: z.id,
      label: `${z.code && z.code !== '--' ? `${z.code} · ` : ''}${z.name}`,
    })),
  ]

  const sortedDevices = useMemo(
    () =>
      [...devices].sort((a, b) => {
        if (!a.isZoneAssigned && b.isZoneAssigned) return -1
        if (a.isZoneAssigned && !b.isZoneAssigned) return 1
        return String(a.nodeId || a.name).localeCompare(String(b.nodeId || b.name))
      }),
    [devices],
  )

  const unassignedCount = devices.filter((d) => !d.isZoneAssigned).length

  const handleOpenRegister = () => {
    setRegisterForm(EMPTY_REGISTER_FORM)
    setRegisterError('')
    setRegisterOpen(true)
  }

  const handleRegisterSubmit = async (event) => {
    event.preventDefault()
    if (!selectedFarmId) return
    setRegisterError('')
    setNotice('')

    const cleanNodeId = registerForm.node_id.trim()
    const cleanName = registerForm.name.trim()
    const invalid = validateRegistration(registerForm, { requireName: true })
    if (invalid) {
      setRegisterError(invalid)
      return
    }

    setRegisterSubmitting(true)
    const res = await createDevice({
      node_id: cleanNodeId,
      name: cleanName,
      device_type: registerForm.device_type,
      farm_id: selectedFarmId,
      zone_id: registerForm.zone_id || null,
    })
    setRegisterSubmitting(false)

    if (!res?.success) {
      setRegisterError(registrationErrorText(res?.error))
      return
    }

    const assignedZone = zones.find((z) => z.id === registerForm.zone_id)
    setNotice(
      `Đã đăng ký thiết bị "${cleanName}" (${cleanNodeId}) tại ${selectedFarm?.name || 'nhà yến'} — ${assignedZone ? `Zone: ${assignedZone.name}` : 'Chưa phân bổ Zone'}. ${registeredNotice(registerForm.device_type)}`,
    )
    setRegisterOpen(false)
    setRegisterForm(EMPTY_REGISTER_FORM)
  }

  const handleSaveZone = async (device) => {
    const nextZoneId =
      draftZones[device.id] !== undefined ? draftZones[device.id] : device.zoneId || ''
    setSavingId(device.id)
    setActionError('')
    setNotice('')
    const res = await updateDeviceZone(device.id, nextZoneId || null)
    setSavingId(null)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể cập nhật phân bổ khu vực cho thiết bị.')
      return
    }
    const targetZone = zones.find((z) => z.id === nextZoneId)
    setNotice(
      `Đã lưu phân bổ khu vực cho ${device.name} (${device.nodeId}) → ${targetZone ? targetZone.name : 'Chưa phân bổ Zone'}.`,
    )
  }

  return (
    <AppLayout>
      <div className="tech-ws">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN INSTALLATION & MAPPING</span>
            <h1>Lắp đặt & Đăng ký thiết bị</h1>
            <p>
              Đăng ký thiết bị phần cứng mới vào nhà yến được phân công và quản lý phân bổ khu vực (Zone).
            </p>
          </div>

          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách</span>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  onChange={(nextId) => {
                    setSelectedFarmId(nextId)
                    setDraftZones({})
                    setNotice('')
                    setActionError('')
                  }}
                  options={farms.map((farm) => ({
                    value: farm.id,
                    label: formatFarmOptionLabel(farm),
                  }))}
                />
              </div>
            )}

            {selectedFarmId && (
              <button
                type="button"
                className="tech-ws-btn tech-ws-btn--primary"
                style={{ height: '42px' }}
                onClick={handleOpenRegister}
              >
                + Đăng ký thiết bị
              </button>
            )}
          </div>
        </header>

        {notice && <div className="tech-ws-notice">{notice}</div>}

        {(error || actionError) && (
          <ErrorMessage
            title="Lỗi thao tác lắp đặt"
            message={actionError || error}
            onRetry={refetch}
          />
        )}

        {telemetryError && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ IoT"
            message="Đăng ký thiết bị lưu thông tin vào hệ thống quản lý và chỉ chuyển trạng thái trực tuyến khi nhận heartbeat MQTT thực tế từ IoT Service."
            onRetry={refetch}
          />
        )}

        {loading && farms.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải dữ liệu lắp đặt..." />
          </div>
        ) : farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến được phân công"
            description="Admin cần phân công bạn vào một nhà yến đã được phê duyệt để đăng ký và phân bổ thiết bị."
          />
        ) : (
          <>
            <section className="tech-ws-kpi-grid">
              <article className="tech-ws-kpi-card">
                <span>Nhà yến đang chọn</span>
                <strong style={{ fontSize: '16px' }}>{selectedFarm?.name || '--'}</strong>
                <small>{selectedFarm?.code || '---'}</small>
              </article>
              <article className="tech-ws-kpi-card">
                <span>Khu vực khả dụng</span>
                <strong>{zones.length}</strong>
                <small>Zones thuộc nhà yến</small>
              </article>
              <article className="tech-ws-kpi-card">
                <span>Thiết bị đã đăng ký</span>
                <strong>{devices.length}</strong>
                <small>Trong hệ thống quản lý</small>
              </article>
              <article className="tech-ws-kpi-card">
                <span>Chưa phân bổ Zone</span>
                <strong style={{ color: unassignedCount > 0 ? '#b45309' : '#059669' }}>
                  {unassignedCount}
                </strong>
                <small>Ưu tiên gán khu vực</small>
              </article>
            </section>

            <section className="tech-ws-card" style={{ marginBottom: '16px' }}>
              <div className="tech-ws-card__head" style={{ marginBottom: 0 }}>
                <div>
                  <span className="tech-ws-eyebrow">01 · DEVICE REGISTRATION</span>
                  <h2>Đăng ký thiết bị phần cứng mới</h2>
                  <p style={{ margin: '4px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Nhập Hardware Node ID thực tế trên thiết bị ESP32/Camera để gắn vào nhà yến {selectedFarm ? formatFarmOptionLabel(selectedFarm) : ''}. Có thể gán Zone ngay hoặc để Chưa phân bổ.
                  </p>
                </div>
                <button
                  type="button"
                  className="tech-ws-btn tech-ws-btn--primary"
                  onClick={handleOpenRegister}
                >
                  + Đăng ký thiết bị
                </button>
              </div>
            </section>

            {sortedDevices.length === 0 ? (
              <EmptyState
                title="Chưa có thiết bị nào trong nhà yến này"
                description="Bấm '+ Đăng ký thiết bị' ở trên để đăng ký thiết bị phần cứng đầu tiên vào nhà yến."
              />
            ) : (
              <section className="tech-ws-card">
                <div className="tech-ws-card__head">
                  <div>
                    <span className="tech-ws-eyebrow">02 · DEVICE–ZONE ASSIGNMENT</span>
                    <h2>Phân bổ & thay đổi khu vực lắp đặt</h2>
                  </div>
                </div>
                <div className="tech-ws-table-wrap">
                  <table className="tech-ws-table">
                    <thead>
                      <tr>
                        <th>Thiết bị & Node ID</th>
                        <th>Loại</th>
                        <th>Trạng thái Zone</th>
                        <th style={{ minWidth: '220px' }}>Chọn khu vực (Zone)</th>
                        <th>Thao tác</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sortedDevices.map((device) => {
                        const currentDraft =
                          draftZones[device.id] !== undefined
                            ? draftZones[device.id]
                            : device.zoneId || ''
                        const isDirty = currentDraft !== (device.zoneId || '')
                        return (
                          <tr key={device.id}>
                            <td>
                              <strong style={{ display: 'block', color: '#102d3f' }}>
                                {device.nodeId || device.id}
                              </strong>
                              <small style={{ color: '#64748b', display: 'block' }}>{device.name}</small>
                              <small className="tech-ws-truncate" title={device.deviceId} style={{ color: '#94a3b8', fontSize: '11px' }}>
                                UUID: {device.deviceId}
                              </small>
                            </td>
                            <td>{device.typeLabel}</td>
                            <td>
                              <span
                                className={`tech-badge ${
                                  device.isZoneAssigned ? 'tech-badge--online' : 'tech-badge--warning'
                                }`}
                              >
                                {device.isZoneAssigned ? device.zoneName : 'Chưa phân bổ Zone'}
                              </span>
                            </td>
                            <td>
                              <EnvironmentSelect
                                value={currentDraft}
                                options={zoneOptions}
                                onChange={(val) =>
                                  setDraftZones((prev) => ({ ...prev, [device.id]: val }))
                                }
                              />
                            </td>
                            <td>
                              <button
                                type="button"
                                className="tech-ws-btn tech-ws-btn--primary"
                                disabled={!isDirty || savingId === device.id}
                                onClick={() => handleSaveZone(device)}
                              >
                                {savingId === device.id ? 'Đang lưu...' : 'Lưu Zone'}
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        )}

        {registerOpen && (
          <div
            className="tech-ws-modal-backdrop"
            role="presentation"
            onMouseDown={() => !registerSubmitting && setRegisterOpen(false)}
          >
            <div
              className="tech-ws-modal"
              role="dialog"
              aria-modal="true"
              aria-label="Đăng ký thiết bị mới"
              onMouseDown={(e) => e.stopPropagation()}
            >
              <div className="tech-ws-modal__head">
                <div>
                  <span className="tech-ws-eyebrow">DEVICE REGISTRATION</span>
                  <h2>Đăng ký thiết bị mới</h2>
                </div>
                <button
                  type="button"
                  className="tech-ws-modal__close"
                  onClick={() => setRegisterOpen(false)}
                  disabled={registerSubmitting}
                  aria-label="Đóng"
                >
                  ×
                </button>
              </div>

              <form className="tech-ws-form" onSubmit={handleRegisterSubmit}>
                <div className="tech-ws-form__field">
                  <label>Nhà yến được phân công</label>
                  <input
                    className="tech-ws-form__input"
                    value={selectedFarm ? formatFarmOptionLabel(selectedFarm) : ''}
                    disabled
                  />
                </div>

                <div className="tech-ws-form__field">
                  <label htmlFor="tech-reg-node-id">{registrationTypeMeta(registerForm.device_type).nodeLabel} *</label>
                  <input
                    id="tech-reg-node-id"
                    className="tech-ws-form__input"
                    value={registerForm.node_id}
                    onChange={(e) => setRegisterForm((f) => ({ ...f, node_id: e.target.value }))}
                    placeholder={registrationTypeMeta(registerForm.device_type).placeholder}
                    disabled={registerSubmitting}
                  />
                  <span className="tech-ws-form__hint">
                    Duy nhất toàn hệ thống; chữ, số, - _ . (3–64 ký tự).
                  </span>
                </div>

                <div className="tech-ws-form__field">
                  <label htmlFor="tech-reg-name">Tên thiết bị *</label>
                  <input
                    id="tech-reg-name"
                    className="tech-ws-form__input"
                    value={registerForm.name}
                    onChange={(e) => setRegisterForm((f) => ({ ...f, name: e.target.value }))}
                    placeholder="Ví dụ: Cảm biến môi trường Tầng 1"
                    disabled={registerSubmitting}
                  />
                </div>

                <div className="tech-ws-form__field">
                  <label>Loại thiết bị *</label>
                  <EnvironmentSelect
                    value={registerForm.device_type}
                    options={DEVICE_TYPE_OPTIONS}
                    onChange={(val) => setRegisterForm((f) => ({ ...f, device_type: val }))}
                  />
                  <span className="tech-ws-form__hint" data-testid="tech-register-type-help">
                    {registrationTypeMeta(registerForm.device_type).help}
                  </span>
                </div>

                <div className="tech-ws-form__field">
                  <label>Khu vực lắp đặt (Zone)</label>
                  <EnvironmentSelect
                    value={registerForm.zone_id}
                    options={zoneOptions}
                    onChange={(val) => setRegisterForm((f) => ({ ...f, zone_id: val }))}
                  />
                  <span className="tech-ws-form__hint">
                    Có thể để &quot;Chưa phân bổ Zone&quot; và gán sau khi lắp đặt thực tế.
                  </span>
                </div>

                {registerError && (
                  <div style={{ padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#b91c1c', fontSize: '12px', fontWeight: 600 }}>
                    {registerError}
                  </div>
                )}

                <div className="tech-ws-modal__actions">
                  <button
                    type="button"
                    className="tech-ws-btn"
                    onClick={() => setRegisterOpen(false)}
                    disabled={registerSubmitting}
                  >
                    Hủy
                  </button>
                  <button
                    type="submit"
                    className="tech-ws-btn tech-ws-btn--primary"
                    disabled={registerSubmitting}
                  >
                    {registerSubmitting ? 'Đang đăng ký...' : 'Xác nhận đăng ký'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default InstallationPage
