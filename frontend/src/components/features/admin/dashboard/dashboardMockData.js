import {
  adminFarms,
  getFarmDeviceCount,
  getFarmOnlineDeviceCount,
} from '../farms/adminFarmsMockData'
import {
  initialAdminUsers,
  userRoleLabels,
} from '../users/usersMockData'

const totalUsersCount = initialAdminUsers.length
const activeUsersCount = initialAdminUsers.filter(
  (user) => user.status === 'ACTIVE',
).length

const totalFarmsCount = adminFarms.length
const activeFarmsCount = adminFarms.filter(
  (farm) => farm.status === 'ACTIVE',
).length
const totalZonesCount = adminFarms.reduce(
  (total, farm) => total + farm.zones.length,
  0,
)

const totalDevicesCount = adminFarms.reduce(
  (total, farm) => total + getFarmDeviceCount(farm),
  0,
)
const onlineDevicesCount = adminFarms.reduce(
  (total, farm) => total + getFarmOnlineDeviceCount(farm),
  0,
)

export const managementItems = [
  {
    id: 'users',
    eyebrow: 'USER & ACCESS',
    value: String(totalUsersCount),
    title: 'Users & Roles',
    description: `${activeUsersCount} tài khoản đang hoạt động`,
    icon: '◎',
    path: '/admin/users',
  },
  {
    id: 'farms',
    eyebrow: 'FARM MANAGEMENT',
    value: String(totalFarmsCount),
    title: 'Nhà yến',
    description: `${activeFarmsCount} nhà yến · ${totalZonesCount} khu vực`,
    icon: '⌂',
    path: '/admin/farms',
  },
  {
    id: 'devices',
    eyebrow: 'DEVICE REGISTRY',
    value: String(totalDevicesCount),
    title: 'Thiết bị',
    description: `${onlineDevicesCount} thiết bị đang online`,
    icon: '▣',
    path: '/admin/devices',
  },
]

export const roles = [
  {
    id: 'owner',
    label: 'Farm Owner',
    description: 'Quản lý và vận hành nhà yến',
    value: initialAdminUsers.filter(
      (user) => user.role === 'FARM_OWNER',
    ).length,
    icon: 'FO',
  },
  {
    id: 'technician',
    label: 'Technician',
    description: 'Thiết bị và hỗ trợ kỹ thuật',
    value: initialAdminUsers.filter(
      (user) => user.role === 'TECHNICIAN',
    ).length,
    icon: 'TE',
  },
  {
    id: 'admin',
    label: 'Administrator',
    description: 'Quản trị nền tảng',
    value: initialAdminUsers.filter(
      (user) => user.role === 'ADMIN',
    ).length,
    icon: 'AD',
  },
]

export const recentAccounts = [...initialAdminUsers]
  .slice(0, 5)
  .reverse()
  .slice(0, 3)
  .map((user) => ({
    id: user.id,
    name: user.name,
    email: user.email,
    role: userRoleLabels[user.role],
    time: user.joinedAt,
  }))

export const services = [
  { id: 'fastapi', name: 'FastAPI Backend', status: 'healthy' },
  { id: 'postgresql', name: 'PostgreSQL', status: 'healthy' },
  { id: 'mqtt', name: 'MQTT Broker', status: 'healthy' },
  { id: 'ai-vision', name: 'AI Vision Pipeline', status: 'healthy' },
]
