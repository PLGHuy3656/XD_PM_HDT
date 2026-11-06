import { adminFarms } from '../farms/adminFarmsMockData'

export const deviceStatusLabels = {
  ONLINE: 'Online',
  WARNING: 'Cần chú ý',
  OFFLINE: 'Offline',
}

export const provisioningLabels = {
  PROVISIONED: 'Đã kích hoạt',
  ATTENTION: 'Cần kiểm tra',
  DISCONNECTED: 'Mất kết nối',
}

export function getDeviceProvisioningStatus(device) {
  if (device.status === 'OFFLINE') {
    return 'DISCONNECTED'
  }

  if (device.status === 'WARNING') {
    return 'ATTENTION'
  }

  return 'PROVISIONED'
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