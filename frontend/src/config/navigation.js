export const navigationByRole = {
  FARM_OWNER: [
    {
      id: 'dashboard',
      label: 'Tổng quan',
      path: '/owner/dashboard',
      icon: 'home',
    },
    {
      id: 'farms',
      label: 'Nhà yến',
      path: '/owner/farms',
      icon: 'farm',
    },
    {
      id: 'environment',
      label: 'Môi trường',
      path: '/owner/environment',
      icon: 'environment',
    },
    {
      id: 'devices',
      label: 'Thiết bị',
      path: '/owner/devices',
      icon: 'device',
    },
    {
      id: 'swiftlets',
      label: 'Giám sát chim yến',
      path: '/owner/swiftlets',
      icon: 'camera',
    },
    {
      id: 'alerts',
      label: 'Cảnh báo',
      path: '/owner/alerts',
      icon: 'alert',
    },
    {
      id: 'analytics',
      label: 'Phân tích',
      path: '/owner/analytics',
      icon: 'analytics',
    },
  ],

  TECHNICIAN: [
    {
      id: 'dashboard',
      label: 'Tổng quan',
      path: '/technician/dashboard',
      icon: 'home',
    },
    {
      id: 'environment',
      label: 'Môi trường',
      path: '/technician/environment',
      icon: 'environment',
    },
    {
      id: 'devices',
      label: 'Thiết bị',
      path: '/technician/devices',
      icon: 'device',
    },
    {
      id: 'diagnostics',
      label: 'Chẩn đoán thiết bị',
      path: '/technician/diagnostics',
      icon: 'diagnostics',
    },
    {
      id: 'alerts',
      label: 'Cảnh báo',
      path: '/technician/alerts',
      icon: 'alert',
    },
  ],

  ADMIN: [
    {
      id: 'dashboard',
      label: 'Tổng quan',
      path: '/admin/dashboard',
      icon: 'home',
    },
    {
      id: 'users',
      label: 'Người dùng',
      path: '/admin/users',
      icon: 'users',
    },
    {
      id: 'farms',
      label: 'Nhà yến',
      path: '/admin/farms',
      icon: 'farm',
    },
    {
      id: 'devices',
      label: 'Thiết bị',
      path: '/admin/devices',
      icon: 'device',
    },
    {
      id: 'system',
      label: 'Hệ thống',
      path: '/admin/system',
      icon: 'settings',
    },
  ],
}