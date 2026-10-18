export const managementItems = [
  {
    id: 'users',
    eyebrow: 'USER & ACCESS',
    value: '24',
    title: 'Users & Roles',
    description: '22 tài khoản đang hoạt động',
    icon: '◎',
    path: '/admin/users',
  },
  {
    id: 'farms',
    eyebrow: 'FARM MANAGEMENT',
    value: '6',
    title: 'Nhà yến',
    description: '6 nhà yến đang hoạt động',
    icon: '⌂',
    path: '/admin/farms',
  },
  {
    id: 'devices',
    eyebrow: 'DEVICE REGISTRY',
    value: '38',
    title: 'Thiết bị',
    description: '35 thiết bị đang online',
    icon: '▣',
    path: '/admin/devices',
  },
]

export const roles = [
  {
    id: 'owner',
    label: 'Farm Owner',
    description: 'Quản lý và vận hành nhà yến',
    value: 18,
    icon: 'FO',
  },
  {
    id: 'technician',
    label: 'Technician',
    description: 'Thiết bị và hỗ trợ kỹ thuật',
    value: 4,
    icon: 'TE',
  },
  {
    id: 'admin',
    label: 'Administrator',
    description: 'Quản trị nền tảng',
    value: 2,
    icon: 'AD',
  },
]

export const recentAccounts = [
  {
    id: 1,
    name: 'Nguyễn Minh Anh',
    email: 'minhanh@nestmate.dev',
    role: 'Farm Owner',
    time: 'Hôm nay',
  },
  {
    id: 2,
    name: 'Trần Quốc Bảo',
    email: 'quocbao@nestmate.dev',
    role: 'Technician',
    time: 'Hôm qua',
  },
  {
    id: 3,
    name: 'Lê Hoàng Nam',
    email: 'hoangnam@nestmate.dev',
    role: 'Farm Owner',
    time: '12/10/2026',
  },
]

export const services = [
  { id: 'api', name: 'Backend API', status: 'healthy' },
  { id: 'database', name: 'Database', status: 'healthy' },
  { id: 'mqtt', name: 'MQTT Broker', status: 'healthy' },
  { id: 'redis', name: 'Redis', status: 'healthy' },
  {
    id: 'notification',
    name: 'Notification',
    status: 'healthy',
  },
]
