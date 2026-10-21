export const adminFarms = [
  {
    id: 'farm-binh-an',
    code: 'NM-BA-01',
    name: 'Nhà yến Bình An',
    address: 'Thủ Đức, TP. Hồ Chí Minh',
    status: 'ACTIVE',
    health: 'GOOD',
    owner: {
      id: 'USR-001',
      name: 'Nguyễn Văn Minh',
      email: 'minh.owner@nestmate.vn',
      phone: '090 123 4567',
    },
    technician: {
      id: 'USR-003',
      name: 'Nguyễn Minh Khang',
      email: 'tech@swiftletcare.dev',
      phone: '090 345 6789',
      status: 'ASSIGNED',
    },
    zones: [
      {
        id: 'zone-a',
        name: 'Khu vực A',
        floor: 'Tầng 1',
        status: 'STABLE',
        devices: [
          {
            id: 'ESP32-CTRL-01',
            name: 'Bộ điều khiển môi trường',
            type: 'ESP32 Controller',
            status: 'ONLINE',
          },
          {
            id: 'ENV-01',
            name: 'Cảm biến môi trường',
            type: 'Environment Sensor',
            status: 'ONLINE',
          },
          {
            id: 'CAM-01',
            name: 'Camera cửa ra vào',
            type: 'AI Camera Node',
            status: 'ONLINE',
          },
        ],
      },
      {
        id: 'zone-b',
        name: 'Khu vực B',
        floor: 'Tầng 2',
        status: 'STABLE',
        devices: [
          {
            id: 'ESP32-CTRL-02',
            name: 'Bộ điều khiển môi trường',
            type: 'ESP32 Controller',
            status: 'WARNING',
          },
          {
            id: 'ENV-02',
            name: 'Cảm biến môi trường',
            type: 'Environment Sensor',
            status: 'ONLINE',
          },
        ],
      },
      {
        id: 'zone-c',
        name: 'Khu vực C',
        floor: 'Tầng 3',
        status: 'ATTENTION',
        devices: [
          {
            id: 'AUDIO-01',
            name: 'Audio Monitoring Node',
            type: 'Audio Node',
            status: 'OFFLINE',
          },
        ],
      },
    ],
  },

  {
    id: 'farm-phu-an',
    code: 'NM-PA-02',
    name: 'Nhà yến Phú An',
    address: 'Dĩ An, Bình Dương',
    status: 'ACTIVE',
    health: 'ATTENTION',
    owner: {
      id: 'USR-002',
      name: 'Trần Hoàng Nam',
      email: 'nam.owner@nestmate.vn',
      phone: '091 245 7812',
    },
    technician: {
      id: 'USR-004',
      name: 'Trần Quốc Huy',
      email: 'huy.technician@swiftletcare.dev',
      phone: '091 456 7820',
      status: 'ASSIGNED',
    },
    zones: [
      {
        id: 'zone-a',
        name: 'Khu vực A',
        floor: 'Tầng 1',
        status: 'STABLE',
        devices: [
          {
            id: 'ESP32-CTRL-03',
            name: 'Bộ điều khiển môi trường',
            type: 'ESP32 Controller',
            status: 'ONLINE',
          },
          {
            id: 'ENV-03',
            name: 'Cảm biến môi trường',
            type: 'Environment Sensor',
            status: 'ONLINE',
          },
        ],
      },
      {
        id: 'zone-d',
        name: 'Khu vực D',
        floor: 'Tầng 2',
        status: 'ATTENTION',
        devices: [
          {
            id: 'ESP32-CTRL-04',
            name: 'Bộ điều khiển môi trường',
            type: 'ESP32 Controller',
            status: 'WARNING',
          },
          {
            id: 'CAM-02',
            name: 'Camera giám sát',
            type: 'AI Camera Node',
            status: 'ONLINE',
          },
        ],
      },
    ],
  },
]

export const farmStatusLabels = {
  ACTIVE: 'Đang hoạt động',
  INACTIVE: 'Ngừng hoạt động',
}

export const farmHealthLabels = {
  GOOD: 'Ổn định',
  ATTENTION: 'Cần theo dõi',
}

export function getFarmDeviceCount(farm) {
  return farm.zones.reduce(
    (total, zone) => total + zone.devices.length,
    0,
  )
}

export function getFarmOnlineDeviceCount(farm) {
  return farm.zones.reduce(
    (total, zone) =>
      total +
      zone.devices.filter(
        (device) => device.status === 'ONLINE',
      ).length,
    0,
  )
}
