import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import {
  typeFilters,
  statusFilters,
} from '../../../components/features/farm-owner/devices/devicesMockData'
import {
  REGISTERABLE_DEVICE_TYPES,
  DEFAULT_REGISTER_TYPE,
  registrationTypeMeta,
  validateRegistration,
  registeredNotice,
  registrationErrorText,
} from '../../../features/devices/deviceRegistration.js'

import DeviceDetailPanel from '../../../components/features/farm-owner/devices/DeviceDetailPanel'
import DeviceTable from '../../../components/features/farm-owner/devices/DeviceTable'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { useDevices } from '../../../features/devices/hooks/useDevices'

import './DevicesPage.css'

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M20 7v5h-5" />
      <path d="M19 12a7 7 0 1 0-2 5" />
    </svg>
  )
}

function DevicesPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    error: farmsError,
  } = useFarms()

  const {
    devices,
    loading: devicesLoading,
    error: devicesError,
    createDevice,
    updateDevice,
    deleteDevice,
    refetch: refetchDevices,
  } = useDevices(selectedFarmId, { requireFarmId: true })

  const [zoneId, setZoneId] = useState('ALL')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [selectedDeviceId, setSelectedDeviceId] = useState(null)
  const [refreshLabel, setRefreshLabel] = useState('Làm mới')
  const [createOpen, setCreateOpen] = useState(false)
  const [editingDevice, setEditingDevice] = useState(null)
  const [devForm, setDevForm] = useState({ node_id: '', name: '', zone_id: '', device_type: DEFAULT_REGISTER_TYPE })
  const [formError, setFormError] = useState('')
  const [registerNotice, setRegisterNotice] = useState('')
  const [actionError, setActionError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const effectiveZones = zones.length > 0 ? zones : selectedFarm?.zones || []

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    ...effectiveZones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })),
  ]

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesZone = zoneId === 'ALL' || device.zoneId === zoneId

      const matchesStatus =
        statusFilter === 'ALL' || device.status === statusFilter

      const matchesType =
        typeFilter === 'ALL' || device.type === typeFilter

      const matchesSearch =
        !keyword ||
        device.id.toLowerCase().includes(keyword) ||
        device.name.toLowerCase().includes(keyword) ||
        (device.typeLabel && device.typeLabel.toLowerCase().includes(keyword))

      return matchesZone && matchesStatus && matchesType && matchesSearch
    })
  }, [devices, zoneId, search, statusFilter, typeFilter])

  const selectedDevice =
    devices.find((device) => device.id === selectedDeviceId) ?? null

  const onlineCount = devices.filter((device) => device.status === 'ONLINE').length
  const warningCount = devices.filter((device) => ['WARNING', 'UNKNOWN', 'UNAVAILABLE'].includes(device.status)).length
  const offlineCount = devices.filter((device) => device.status === 'OFFLINE').length
  const farmDeviceCount = devices.length

  const getZoneName = (device) => {
    return (
      effectiveZones.find((zone) => zone.id === device.zoneId)?.name ?? 'Chưa gán'
    )
  }

  const handleRefresh = async () => {
    setRefreshLabel('Đang làm mới...')
    await refetchDevices()
    setRefreshLabel(`Cập nhật ${new Date().toLocaleTimeString('vi-VN')}`)
  }

  const handleSaveDevice = async (event) => {
    event.preventDefault()
    if (!selectedFarmId) return
    setActionError('')
    setFormError('')
    setRegisterNotice('')
    if (!editingDevice) {
      const invalid = validateRegistration(devForm, { requireName: true })
      if (invalid) {
        setFormError(invalid)
        return
      }
    }
    setSubmitting(true)
    let res
    if (editingDevice) {
      const targetId = editingDevice.deviceId || editingDevice.deviceUuid || editingDevice.id
      res = await updateDevice(targetId, {
        name: devForm.name.trim() || null,
        zone_id: devForm.zone_id || null,
      })
    } else {
      const payload = {
        node_id: devForm.node_id.trim(),
        farm_id: selectedFarmId,
        name: devForm.name.trim() || null,
        device_type: devForm.device_type,
      }
      if (devForm.zone_id) payload.zone_id = devForm.zone_id
      res = await createDevice(payload)
    }
    setSubmitting(false)
    if (!res?.success) {
      if (editingDevice) setActionError(res?.error || 'Không thể lưu thiết bị.')
      else setFormError(registrationErrorText(res?.error))
      return
    }
    if (!editingDevice) {
      setRegisterNotice(`Đã đăng ký "${devForm.name.trim()}" (${devForm.node_id.trim()}). ${registeredNotice(devForm.device_type)}`)
    }
    setDevForm({ node_id: '', name: '', zone_id: '', device_type: DEFAULT_REGISTER_TYPE })
    setEditingDevice(null)
    setCreateOpen(false)
  }

  const handleDeleteDevice = async (device) => {
    if (!window.confirm(`Xác nhận xóa thiết bị "${device.name || device.id}"?`)) return
    setActionError('')
    const res = await deleteDevice(device.deviceId || device.deviceUuid || device.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể xóa thiết bị.')
      return
    }
    setSelectedDeviceId(null)
  }

  return (
    <AppLayout>
      <div className="devices-page">
        <header className="devices-hero">
          <div>
            <span className="devices-eyebrow">DEVICE MANAGEMENT</span>

            <h1>Thiết bị</h1>

            <p>
              Giám sát tình trạng kết nối, phiên bản firmware và vị trí lắp đặt
              của toàn bộ thiết bị theo từng nhà yến.
            </p>
          </div>

          <div className="devices-farm-picker" style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div>
              <span>Nhà yến</span>

              <EnvironmentSelect
                value={selectedFarmId || ''}
                onChange={(nextId) => {
                  setSelectedFarmId(nextId)
                  setSelectedDeviceId(null)
                  setZoneId('ALL')
                }}
                options={farms.map((farm) => ({
                  value: farm.id,
                  label: formatFarmOptionLabel(farm),
                }))}
              />
            </div>
            {selectedFarmId && (selectedFarm?.approvalStatus || 'APPROVED') === 'APPROVED' && (
              <button
                type="button"
                className="farm-button farm-button--primary"
                onClick={() => {
                  setActionError('')
                  setFormError('')
                  setCreateOpen(true)
                }}
                data-testid="owner-register-device"
              >
                + Thêm thiết bị
              </button>
            )}
          </div>
        </header>

        {selectedFarm && (selectedFarm.approvalStatus || 'APPROVED') !== 'APPROVED' && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fffbeb', color: '#92400e', border: '1px solid #fcd34d' }}>
            {selectedFarm.approvalStatus === 'REJECTED'
              ? `Nhà yến "${selectedFarm.name}" đã bị từ chối${selectedFarm.rejectionReason ? `: ${selectedFarm.rejectionReason}` : ''}. Không thể đăng ký thiết bị mới.`
              : `Nhà yến "${selectedFarm.name}" đang chờ Admin phê duyệt. Chức năng đăng ký thiết bị sẽ mở khóa sau khi được duyệt.`}
          </div>
        )}

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {registerNotice && (
          <p className="device-register-notice" data-testid="owner-register-notice">{registerNotice}</p>
        )}
        {(devicesError || actionError) && (
          <ErrorMessage
            title="Lỗi thao tác thiết bị"
            message={actionError || devicesError}
            onRetry={refetchDevices}
          />
        )}

        <section className="device-summary-grid">
          <article className="device-summary-card">
            <span className="device-summary-label">Tổng thiết bị</span>
            <strong>{farmDeviceCount}</strong>
            <small>Được định danh trong nhà yến</small>
          </article>

          <article className="device-summary-card">
            <span className="device-summary-label">Trực tuyến</span>
            <strong>{onlineCount}</strong>
            <small>Đang kết nối bình thường</small>
          </article>

          <article className="device-summary-card">
            <span className="device-summary-label">Cần kiểm tra</span>
            <strong>{warningCount}</strong>
            <small>Cảnh báo / chưa có heartbeat / IoT không xác định</small>
          </article>

          <article className="device-summary-card">
            <span className="device-summary-label">Ngoại tuyến</span>
            <strong>{offlineCount}</strong>
            <small>Đã xác nhận mất tín hiệu</small>
          </article>
        </section>

        <section className="device-list-section">
          <div className="device-toolbar">
            <div className="device-search">
              <SearchIcon />
              <input
                type="text"
                placeholder="Tìm theo mã, tên hoặc loại thiết bị..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>

            <div className="devices-selects" style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
              <EnvironmentSelect
                value={zoneId}
                onChange={setZoneId}
                options={zoneOptions}
              />

              <EnvironmentSelect
                value={typeFilter}
                onChange={setTypeFilter}
                options={typeFilters}
              />

              <EnvironmentSelect
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusFilters}
              />

              <button
                type="button"
                className="device-refresh-button"
                onClick={handleRefresh}
              >
                <RefreshIcon />
                {refreshLabel}
              </button>
            </div>
          </div>
        </section>

        <section className="devices-layout">
          <div className="devices-table-area">
            {devicesLoading && devices.length === 0 ? (
              <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
                <LoadingSpinner size="lg" text="Đang tải thiết bị..." />
              </div>
            ) : filteredDevices.length === 0 ? (
              <EmptyState
                title="Không tìm thấy thiết bị"
                description={
                  farmDeviceCount === 0
                    ? 'Nhà yến này chưa có thiết bị nào được cấu hình.'
                    : 'Không có thiết bị phù hợp với bộ lọc hiện tại.'
                }
              />
            ) : (
              <DeviceTable
                devices={filteredDevices}
                selectedDeviceId={selectedDeviceId}
                // INT01-R1: DeviceTable passes the device id (string); previously `.id` of a string -> panel never opened
                onSelectDevice={(deviceOrId) => setSelectedDeviceId(typeof deviceOrId === 'string' ? deviceOrId : deviceOrId?.id ?? null)}
                getZoneName={getZoneName}
              />
            )}
          </div>

          <aside className="devices-side-panel">
            <DeviceDetailPanel
              device={selectedDevice}
              zoneName={selectedDevice ? getZoneName(selectedDevice) : ''}
              farmName={selectedFarm?.name || ''}
              onClose={() => setSelectedDeviceId(null)}
            />
            {selectedDevice && (
              <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
                <button
                  type="button"
                  className="farm-button"
                  onClick={() => {
                    setActionError('')
                    setEditingDevice(selectedDevice)
                    setDevForm({
                      node_id: selectedDevice.nodeId || selectedDevice.id,
                      name: selectedDevice.name || '',
                      zone_id: selectedDevice.zoneId && /^[0-9a-f]{8}-/i.test(selectedDevice.zoneId) ? selectedDevice.zoneId : '',
                      device_type: selectedDevice.type || 'CONTROLLER',
                    })
                    setCreateOpen(true)
                  }}
                >
                  Chỉnh sửa thiết bị
                </button>
                <button
                  type="button"
                  className="farm-button"
                  style={{ borderColor: '#dc2626', color: '#dc2626' }}
                  onClick={() => handleDeleteDevice(selectedDevice)}
                >
                  Xóa thiết bị
                </button>
              </div>
            )}
          </aside>
        </section>

        {createOpen && (
          <div
            className="admin-farm-modal-backdrop"
            onMouseDown={() => {
              setCreateOpen(false)
              setEditingDevice(null)
            }}
          >
            <form
              className="admin-farm-modal admin-farm-form"
              onSubmit={handleSaveDevice}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <h3>{editingDevice ? 'Chỉnh sửa thiết bị' : 'Thêm thiết bị cho nhà yến'}</h3>
              {!editingDevice && (
                <>
                  <label>
                    Nhà yến
                    <input value={selectedFarm ? formatFarmOptionLabel(selectedFarm) : ''} disabled />
                  </label>
                  <label>
                    Loại thiết bị *
                    <select
                      value={devForm.device_type}
                      onChange={(e) => setDevForm((c) => ({ ...c, device_type: e.target.value }))}
                      data-testid="owner-register-type"
                    >
                      {REGISTERABLE_DEVICE_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </label>
                  <small className="device-register-help">{registrationTypeMeta(devForm.device_type).help}</small>
                  <label>
                    {registrationTypeMeta(devForm.device_type).nodeLabel} *
                    <input
                      value={devForm.node_id}
                      onChange={(e) => setDevForm((c) => ({ ...c, node_id: e.target.value }))}
                      placeholder={registrationTypeMeta(devForm.device_type).placeholder}
                      data-testid="owner-register-node"
                    />
                  </label>
                </>
              )}
              <label>
                Tên thiết bị{editingDevice ? '' : ' *'}
                <input
                  value={devForm.name}
                  onChange={(e) => setDevForm((c) => ({ ...c, name: e.target.value }))}
                  placeholder="Tên thiết bị"
                />
              </label>
              {effectiveZones.length > 0 && (
                <label>
                  Khu vực (tùy chọn)
                  <select
                    value={devForm.zone_id}
                    onChange={(e) => setDevForm((c) => ({ ...c, zone_id: e.target.value }))}
                  >
                    <option value="">-- Chưa gán khu vực --</option>
                    {effectiveZones.map((z) => (
                      <option key={z.id} value={z.id}>{z.name}</option>
                    ))}
                  </select>
                </label>
              )}
              {formError && <p className="device-register-error" data-testid="owner-register-error">{formError}</p>}
              <div className="admin-farm-modal__actions">
                <button type="button" className="admin-farm-modal__cancel" onClick={() => setCreateOpen(false)}>Hủy</button>
                <button type="submit" className="admin-farm-modal__save" disabled={submitting}>{submitting ? 'Đang lưu...' : 'Thêm thiết bị'}</button>
              </div>
            </form>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default DevicesPage
