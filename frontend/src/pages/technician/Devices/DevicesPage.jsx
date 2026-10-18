import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import DeviceAssignmentModal from '../../../components/features/technician/devices/DeviceAssignmentModal'
import DeviceDetailPanel from '../../../components/features/technician/devices/DeviceDetailPanel'
import DeviceTable from '../../../components/features/technician/devices/DeviceTable'

import {
  farms,
  initialDevices,
  statusOptions,
  typeOptions,
} from '../../../components/features/technician/devices/devicesMockData'

import './DevicesPage.css'

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </svg>
  )
}

function TechnicianDevicesPage() {
  const [devices, setDevices] = useState(initialDevices)
  const [farmId, setFarmId] = useState(farms[0].id)
  const [zoneFilter, setZoneFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const [selectedDeviceId, setSelectedDeviceId] =
    useState(null)

  const [assignmentDeviceId, setAssignmentDeviceId] =
    useState(null)

  const [assignmentZoneId, setAssignmentZoneId] =
    useState('')

  const [notice, setNotice] = useState('')

  const selectedFarm =
    farms.find((farm) => farm.id === farmId) ?? farms[0]

  const zoneOptions = [
    { value: 'ALL', label: 'Tất cả khu vực' },
    ...selectedFarm.zones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })),
  ]

  const assignmentZoneOptions = selectedFarm.zones.map(
    (zone) => ({
      value: zone.id,
      label: zone.name,
    })
  )

  const filteredDevices = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return devices.filter((device) => {
      const matchesZone =
        zoneFilter === 'ALL' ||
        device.zoneId === zoneFilter

      const matchesStatus =
        statusFilter === 'ALL' ||
        device.status === statusFilter

      const matchesType =
        typeFilter === 'ALL' ||
        device.type === typeFilter

      const matchesSearch =
        !keyword ||
        device.id.toLowerCase().includes(keyword) ||
        device.name.toLowerCase().includes(keyword) ||
        device.typeLabel.toLowerCase().includes(keyword)

      return (
        matchesZone &&
        matchesStatus &&
        matchesType &&
        matchesSearch
      )
    })
  }, [
    devices,
    zoneFilter,
    statusFilter,
    typeFilter,
    search,
  ])

  const selectedDevice =
    devices.find(
      (device) => device.id === selectedDeviceId
    ) ?? null

  const assignmentDevice =
    devices.find(
      (device) => device.id === assignmentDeviceId
    ) ?? null

  const onlineCount = devices.filter(
    (device) => device.status === 'ONLINE'
  ).length

  const attentionCount = devices.filter(
    (device) =>
      device.status === 'WARNING' ||
      device.status === 'OFFLINE'
  ).length

  const averageRssiValues = devices
    .filter((device) => device.rssi !== null)
    .map((device) => device.rssi)

  const averageRssi =
    averageRssiValues.length > 0
      ? Math.round(
          averageRssiValues.reduce(
            (sum, value) => sum + value,
            0
          ) / averageRssiValues.length
        )
      : null

  const getZoneName = (zoneId) =>
    selectedFarm.zones.find(
      (zone) => zone.id === zoneId
    )?.name ?? 'Chưa gán'

  const openAssignment = (device) => {
    setAssignmentDeviceId(device.id)
    setAssignmentZoneId(device.zoneId)
    setNotice('')
  }

  const closeAssignment = () => {
    setAssignmentDeviceId(null)
    setAssignmentZoneId('')
  }

  const handleAssignment = () => {
    if (!assignmentDevice || !assignmentZoneId) return

    const previousZoneId = assignmentDevice.zoneId

    if (previousZoneId === assignmentZoneId) {
      setNotice('Thiết bị đang thuộc khu vực này.')
      return
    }

    setDevices((currentDevices) =>
      currentDevices.map((device) =>
        device.id === assignmentDevice.id
          ? {
              ...device,
              zoneId: assignmentZoneId,
            }
          : device
      )
    )

    setNotice(
      `${assignmentDevice.id} đã được chuyển từ ${getZoneName(
        previousZoneId
      )} sang ${getZoneName(assignmentZoneId)}.`
    )

    setAssignmentDeviceId(null)
    setAssignmentZoneId('')
  }

  return (
    <AppLayout>
      <div className="tech-devices-page">
        <header className="tech-devices-hero">
          <div>
            <span className="tech-devices-kicker">
              DEVICE OPERATIONS
            </span>

            <h1>Quản lý thiết bị</h1>

            <p>
              Theo dõi node kỹ thuật, kết nối và phân bổ
              thiết bị theo từng khu vực nhà yến.
            </p>
          </div>

          <div className="tech-devices-system-chip">
            <span className="tech-system-pulse" />

            <div>
              <strong>Device Network Active</strong>
              <span>
                {onlineCount}/{devices.length} nodes online
              </span>
            </div>
          </div>
        </header>

        <section className="tech-device-metrics">
          <article>
            <span>TOTAL NODES</span>
            <strong>{devices.length}</strong>
            <small>Registered devices</small>
          </article>

          <article className="healthy">
            <span>ONLINE</span>
            <strong>{onlineCount}</strong>
            <small>Responding normally</small>
          </article>

          <article className="attention">
            <span>NEEDS ATTENTION</span>
            <strong>{attentionCount}</strong>
            <small>Warning or offline</small>
          </article>

          <article>
            <span>AVG. SIGNAL</span>
            <strong>
              {averageRssi !== null
                ? `${averageRssi} dBm`
                : '--'}
            </strong>
            <small>Connected nodes</small>
          </article>
        </section>

        <section className="tech-device-workspace">
          <div className="tech-workspace-heading">
            <div>
              <span className="tech-section-code">
                DEVICE REGISTRY
              </span>

              <h2>Node & Connectivity</h2>

              <p>
                Kiểm tra nhanh trạng thái kết nối, heartbeat
                và vị trí được gán của từng node.
              </p>
            </div>

            <div className="tech-farm-field">
              <EnvironmentSelect
                label="Nhà yến"
                value={farmId}
                options={farms.map((farm) => ({
                  value: farm.id,
                  label: farm.name,
                }))}
                onChange={(nextFarmId) => {
                  setFarmId(nextFarmId)
                  setZoneFilter('ALL')
                }}
              />
            </div>
          </div>

          <div className="tech-device-toolbar">
            <label className="tech-device-search">
              <SearchIcon />

              <input
                value={search}
                onChange={(event) =>
                  setSearch(event.target.value)
                }
                placeholder="Tìm Device ID, tên node..."
              />
            </label>

            <EnvironmentSelect
              label="Khu vực"
              value={zoneFilter}
              options={zoneOptions}
              onChange={setZoneFilter}
            />

            <EnvironmentSelect
              label="Trạng thái"
              value={statusFilter}
              options={statusOptions}
              onChange={setStatusFilter}
            />

            <EnvironmentSelect
              label="Loại node"
              value={typeFilter}
              options={typeOptions}
              onChange={setTypeFilter}
            />
          </div>

          {notice && (
            <div className="tech-device-notice">
              <span>✓</span>
              {notice}
            </div>
          )}

          <DeviceTable
            devices={filteredDevices}
            farmName={selectedFarm.name}
            getZoneName={getZoneName}
            onOpenDetail={setSelectedDeviceId}
            onOpenAssignment={openAssignment}
          />
        </section>

        {selectedDevice && (
          <DeviceDetailPanel
            device={selectedDevice}
            zoneName={getZoneName(selectedDevice.zoneId)}
            onClose={() => setSelectedDeviceId(null)}
            onAssign={() => {
              setSelectedDeviceId(null)
              openAssignment(selectedDevice)
            }}
          />
        )}

        {assignmentDevice && (
          <DeviceAssignmentModal
            device={assignmentDevice}
            currentZoneName={getZoneName(
              assignmentDevice.zoneId
            )}
            farmName={selectedFarm.name}
            zoneId={assignmentZoneId}
            zoneOptions={assignmentZoneOptions}
            onZoneChange={setAssignmentZoneId}
            onClose={closeAssignment}
            onConfirm={handleAssignment}
          />
        )}
      </div>
    </AppLayout>
  )
}

export default TechnicianDevicesPage