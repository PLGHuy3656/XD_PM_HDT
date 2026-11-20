import { adminFarms } from '../farms/adminFarmsMockData'

export const deviceStatusLabels = {
  ONLINE: 'Online',
  WARNING: 'Cần chú ý',
  OFFLINE: 'Offline',
  UNKNOWN: 'Chưa có heartbeat',
  UNAVAILABLE: 'Không xác định (IoT)',
}

export const provisioningLabels = {
  PROVISIONED: 'Đã kích hoạt',
  ATTENTION: 'Cần kiểm tra',
  DISCONNECTED: 'Mất kết nối',
  UNKNOWN: 'Chưa xác nhận kết nối',
}

export function getDeviceProvisioningStatus(device) {
  if (device.status === 'OFFLINE') {
    return 'DISCONNECTED'
  }

  if (device.status === 'WARNING') {
    return 'ATTENTION'
  }

  // INT01-R1: never claim PROVISIONED without a heartbeat
  if (device.status === 'ONLINE') {
    return 'PROVISIONED'
  }

  return 'UNKNOWN'
}

export function getAdminDevices(farms = adminFarms) {
  return farms.flatMap((farm) =>
    farm.zones.flatMap((zone) =>
      zone.devices.map((device) => ({
        ...device,

        farm: {
          id: farm.id,
          code: farm.code,
          name: farm.name,
        },

        zone: {
          id: zone.id,
          name: zone.name,
          floor: zone.floor,
        },

        provisioning:
          getDeviceProvisioningStatus(device),
      })),
    ),
  )
}