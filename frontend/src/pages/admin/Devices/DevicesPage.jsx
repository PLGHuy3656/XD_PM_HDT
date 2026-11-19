import { useMemo, useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import Select from '../../../components/ui/Select'

import DeviceTable from '../../../components/features/admin/devices/DeviceTable'
import DeviceDetailPanel from '../../../components/features/admin/devices/DeviceDetailPanel'

import { useAdminData } from '../../../features/admin'

import './DevicesPage.css'

const statusFilterOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'ONLINE', label: 'Online' },
  { value: 'WARNING', label: 'Cần chú ý' },
  { value: 'OFFLINE', label: 'Offline' },
]

function DevicesPage() {
  const {
    devices,
    farms,
    createDevice: apiCreateDevice,
    updateDevice: apiUpdateDevice,
    deleteDevice: apiDeleteDevice,
    loading,
    error,
  } = useAdminData()

  const [createOpen, setCreateOpen] = useState(false)
  const [editingDevice, setEditingDevice] = useState(null)
  const [devForm, setDevForm] = useState({ node_id: '', farm_id: '', zone_id: '', name: '', device_type: 'CONTROLLER' })
  const [actionError, setActionError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const [searchTerm, setSearchTerm] = useState('')

  const [statusFilter, setStatusFilter] =
    useState('ALL')
  const [typeFilter, setTypeFilter] =
    useState('ALL')
  const [farmFilter, setFarmFilter] =
    useState('ALL')

  const [selectedDeviceId, setSelectedDeviceId] =
    useState(null)

  const selectedDevice = devices.find(
    (device) => device.id === selectedDeviceId,
  )

  const typeFilterOptions = useMemo(
    () => [
      { value: 'ALL', label: 'Tất cả loại' },
      ...[...new Set(devices.map((device) => device.type))].map(
        (type) => ({
          value: type,
          label: type,
        }),
      ),
    ],
    [devices],
  )

  const farmFilterOptions = useMemo(() => {
    const uniqueFarms = new Map()

    devices.forEach((device) => {
      uniqueFarms.set(
        device.farm.id,
        device.farm,
      )
    })

    return [
      { value: 'ALL', label: 'Tất cả nhà yến' },
      ...[...uniqueFarms.values()].map((farm) => ({
        value: farm.id,
        label: farm.name,
      })),
    ]
  }, [devices])

  const filteredDevices = useMemo(() => {
    const keyword =
      searchTerm.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesSearch =
        !keyword ||
        device.id.toLowerCase().includes(keyword) ||
        device.name.toLowerCase().includes(keyword) ||
        device.type.toLowerCase().includes(keyword) ||
        device.farm.name
          .toLowerCase()
          .includes(keyword) ||
        device.zone.name
          .toLowerCase()
          .includes(keyword)

      const matchesStatus =
        statusFilter === 'ALL' ||
        device.status === statusFilter

      const matchesType =
        typeFilter === 'ALL' ||
        device.type === typeFilter

      const matchesFarm =
        farmFilter === 'ALL' ||
        device.farm.id === farmFilter

      return (
        matchesSearch &&
        matchesStatus &&
        matchesType &&
        matchesFarm
      )
    })
  }, [
    devices,
    searchTerm,
    statusFilter,
    typeFilter,
    farmFilter,
  ])

  const onlineCount = devices.filter(
    (device) => device.status === 'ONLINE',
  ).length

  const warningCount = devices.filter(
    (device) => device.status === 'WARNING',
  ).length

  const offlineCount = devices.filter(
    (device) => device.status === 'OFFLINE',
  ).length

  const selectedFarmZones = useMemo(() => {
    const f = (farms || []).find((item) => item.id === devForm.farm_id)
    return f?.zones || []
  }, [farms, devForm.farm_id])

  async function handleSaveDevice(event) {
    event.preventDefault()
    setActionError('')
    if (!editingDevice && (!devForm.node_id.trim() || !devForm.farm_id)) {
      setActionError('Vui lòng nhập Node ID và chọn nhà yến.')
      return
    }
    setSubmitting(true)
    let res
    if (editingDevice) {
      const targetId = editingDevice.deviceId || editingDevice.deviceUuid || editingDevice.id
      res = await apiUpdateDevice(targetId, {
        name: devForm.name.trim() || null,
        zone_id: devForm.zone_id || null,
      })
    } else {
      const payload = {
        node_id: devForm.node_id.trim(),
        farm_id: devForm.farm_id,
        name: devForm.name.trim() || null,
        device_type: devForm.device_type || 'CONTROLLER',
      }
      if (devForm.zone_id) payload.zone_id = devForm.zone_id
      res = await apiCreateDevice(payload)
    }
    setSubmitting(false)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể lưu thiết bị.')
      return
    }
    setDevForm({ node_id: '', farm_id: '', zone_id: '', name: '', device_type: 'CONTROLLER' })
    setEditingDevice(null)
    setCreateOpen(false)
  }

  async function handleDeleteDevice(device) {
    if (!window.confirm(`Xác nhận xóa thiết bị "${device.name || device.id}"?`)) return
    setActionError('')
    const res = await apiDeleteDevice(device.deviceId || device.deviceUuid || device.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể xóa thiết bị.')
      return
    }
    setSelectedDeviceId(null)
  }

  return (
    <AppLayout>
      <div className="admin-devices-page">
        <section className="admin-devices-hero">
          <div>
            <span>SYSTEM DEVICE OVERVIEW</span>

            <h1>Quản lý thiết bị</h1>

            <p>
              Giám sát trạng thái, vị trí triển khai và
              provisioning của thiết bị trên toàn hệ thống.
            </p>
          </div>

          <div className="admin-devices-readonly">
            <i />
            Quản lý &amp; Đăng ký
          </div>
        </section>

        <section className="admin-devices-stats">
          <article>
            <span>Tổng thiết bị</span>
            <strong>{devices.length}</strong>
            <small>Toàn hệ thống</small>
          </article>

          <article>
            <span>Online</span>
            <strong>{onlineCount}</strong>
            <small>Hoạt động bình thường</small>
          </article>

          <article>
            <span>Cần chú ý</span>
            <strong>{warningCount}</strong>
            <small>Cần Technician kiểm tra</small>
          </article>

          <article>
            <span>Offline</span>
            <strong>{offlineCount}</strong>
            <small>Mất kết nối</small>
          </article>
        </section>

        <section className="admin-devices-content">
          {(error || actionError) && (
            <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fef2f2', color: '#b91c1c' }}>
              {actionError || error}
            </div>
          )}
          <div className="admin-devices-content__heading">
            <div>
              <span>DEVICE DIRECTORY</span>
              <h2>Danh sách thiết bị</h2>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <p>
                {loading ? 'Đang tải...' : `${filteredDevices.length} / ${devices.length} thiết bị`}
              </p>
              <button
                type="button"
                className="admin-farm-edit-button"
                onClick={() => {
                  setActionError('')
                  setCreateOpen(true)
                }}
              >
                + Đăng ký thiết bị
              </button>
            </div>
          </div>

          <div className="admin-devices-toolbar">
            <input
              type="search"
              value={searchTerm}
              onChange={(event) =>
                setSearchTerm(event.target.value)
              }
              placeholder="Tìm Device ID, tên, Farm, Zone..."
            />

            <Select
              value={statusFilter}
              options={statusFilterOptions}
              onChange={setStatusFilter}
            />

            <Select
              value={typeFilter}
              options={typeFilterOptions}
              onChange={setTypeFilter}
            />

            <Select
              value={farmFilter}
              options={farmFilterOptions}
              onChange={setFarmFilter}
            />
          </div>

          <DeviceTable
            devices={filteredDevices}
            onViewDevice={(device) =>
              setSelectedDeviceId(device.id)
            }
          />
        </section>

        <DeviceDetailPanel
          device={selectedDevice}
          onClose={() =>
            setSelectedDeviceId(null)
          }
          onEdit={(device) => {
            setActionError('')
            setEditingDevice(device)
            setDevForm({
              node_id: device.nodeId || device.id,
              farm_id: device.farm?.id || '',
              zone_id: device.zone?.id && /^[0-9a-f]{8}-/i.test(device.zone.id) ? device.zone.id : '',
              name: device.name || '',
              device_type: device.rawType || 'ENVIRONMENT_MONITOR',
            })
            setCreateOpen(true)
          }}
          onDelete={handleDeleteDevice}
        />

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
              <h3>{editingDevice ? 'Chỉnh sửa thiết bị' : 'Đăng ký thiết bị mới'}</h3>
              {!editingDevice && (
                <>
                  <label>
                    Node ID *
                    <input
                      value={devForm.node_id}
                      onChange={(e) => setDevForm((c) => ({ ...c, node_id: e.target.value }))}
                      placeholder="VD: SWC-NODE-003"
                    />
                  </label>
                  <label>
                    Loại thiết bị *
                    <select
                      value={devForm.device_type}
                      onChange={(e) => setDevForm((c) => ({ ...c, device_type: e.target.value }))}
                    >
                      <option value="ENVIRONMENT_MONITOR">Cảm biến môi trường (ENVIRONMENT_MONITOR)</option>
                      <option value="CAMERA">Camera AI (CAMERA)</option>
                      <option value="ACTUATOR">Thiết bị điều khiển (ACTUATOR)</option>
                      <option value="AUDIO_MONITOR">Cảm biến âm thanh (AUDIO_MONITOR)</option>
                    </select>
                  </label>
                  <label>
                    Nhà yến *
                    <select
                      value={devForm.farm_id}
                      onChange={(e) => setDevForm((c) => ({ ...c, farm_id: e.target.value, zone_id: '' }))}
                    >
                      <option value="">-- Chọn nhà yến --</option>
                      {(farms || []).map((f) => (
                        <option key={f.id} value={f.id}>{f.name} ({f.code})</option>
                      ))}
                    </select>
                  </label>
                </>
              )}
              <label>
                Tên thiết bị
                <input
                  value={devForm.name}
                  onChange={(e) => setDevForm((c) => ({ ...c, name: e.target.value }))}
                  placeholder="VD: Cảm biến tầng 1"
                />
              </label>
              {selectedFarmZones.length > 0 && (
                <label>
                  Khu vực (tùy chọn)
                  <select
                    value={devForm.zone_id}
                    onChange={(e) => setDevForm((c) => ({ ...c, zone_id: e.target.value }))}
                  >
                    <option value="">-- Chưa gán khu vực --</option>
                    {selectedFarmZones.map((z) => (
                      <option key={z.id} value={z.id}>{z.name}</option>
                    ))}
                  </select>
                </label>
              )}
              <div className="admin-farm-modal__actions">
                <button type="button" className="admin-farm-modal__cancel" onClick={() => setCreateOpen(false)}>Hủy</button>
                <button type="submit" className="admin-farm-modal__save" disabled={submitting}>{submitting ? 'Đang lưu...' : 'Đăng ký'}</button>
              </div>
            </form>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default DevicesPage
