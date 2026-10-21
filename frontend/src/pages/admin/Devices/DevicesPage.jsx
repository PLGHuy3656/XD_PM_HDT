import { useMemo, useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'

import DeviceTable from '../../../components/features/admin/devices/DeviceTable'
import DeviceDetailPanel from '../../../components/features/admin/devices/DeviceDetailPanel'

import {
  getAdminDevices,
} from '../../../components/features/admin/devices/adminDevicesData'

import './DevicesPage.css'

function DevicesPage() {
  const devices = useMemo(
    () => getAdminDevices(),
    [],
  )

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

  const deviceTypes = useMemo(
    () => [...new Set(devices.map((device) => device.type))],
    [devices],
  )

  const farms = useMemo(() => {
    const uniqueFarms = new Map()

    devices.forEach((device) => {
      uniqueFarms.set(
        device.farm.id,
        device.farm,
      )
    })

    return [...uniqueFarms.values()]
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
            Admin · Read only
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
          <div className="admin-devices-content__heading">
            <div>
              <span>DEVICE DIRECTORY</span>
              <h2>Danh sách thiết bị</h2>
            </div>

            <p>
              {filteredDevices.length} / {devices.length}{' '}
              thiết bị
            </p>
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

            <select
              value={statusFilter}
              onChange={(event) =>
                setStatusFilter(event.target.value)
              }
            >
              <option value="ALL">
                Tất cả trạng thái
              </option>
              <option value="ONLINE">Online</option>
              <option value="WARNING">
                Cần chú ý
              </option>
              <option value="OFFLINE">Offline</option>
            </select>

            <select
              value={typeFilter}
              onChange={(event) =>
                setTypeFilter(event.target.value)
              }
            >
              <option value="ALL">
                Tất cả loại
              </option>

              {deviceTypes.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>

            <select
              value={farmFilter}
              onChange={(event) =>
                setFarmFilter(event.target.value)
              }
            >
              <option value="ALL">
                Tất cả nhà yến
              </option>

              {farms.map((farm) => (
                <option
                  key={farm.id}
                  value={farm.id}
                >
                  {farm.name}
                </option>
              ))}
            </select>
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
        />
      </div>
    </AppLayout>
  )
}

export default DevicesPage