export const environmentMetrics = {
  temperature: {
    label: 'Nhiệt độ',
    value: 28.5,
    displayValue: '28.5°C',
    unit: '°C',
    min: 24,
    max: 34,
    safeMin: 27,
    safeMax: 31,
    values: [
      27.1, 27.4, 27.2, 27.8, 28.1,
      28.4, 28.8, 29.1, 28.9, 28.6, 28.5,
    ],
  },

  humidity: {
    label: 'Độ ẩm',
    value: 78,
    displayValue: '78%',
    unit: '%',
    min: 60,
    max: 100,
    safeMin: 75,
    safeMax: 90,
    values: [
      80, 79, 78, 77, 76,
      78, 81, 82, 80, 79, 78,
    ],
  },

  co2: {
    label: 'CO₂',
    value: 620,
    displayValue: '620 ppm',
    unit: ' ppm',
    min: 300,
    max: 1400,
    safeMin: 400,
    safeMax: 1000,
    values: [
      510, 530, 560, 590, 640,
      670, 710, 690, 660, 640, 620,
    ],
  },

  light: {
    label: 'Ánh sáng',
    value: 120,
    displayValue: '120 lux',
    unit: ' lux',
    min: 0,
    max: 300,
    safeMin: 50,
    safeMax: 180,
    values: [
      65, 72, 80, 95, 110,
      130, 145, 138, 132, 125, 120,
    ],
  },
}

export const mockDevices = [
  {
    id: 'misting',
    type: 'misting',
    name: 'Phun sương',
    description: 'Khu vực A',
    status: 'on',
    mode: 'AUTO',
  },
  {
    id: 'fan',
    type: 'fan',
    name: 'Quạt thông gió',
    description: 'Khu vực A',
    status: 'on',
    mode: 'AUTO',
  },
  {
    id: 'heater',
    type: 'heater',
    name: 'Máy sưởi',
    description: 'Khu vực B',
    status: 'off',
    mode: 'AUTO',
  },
]

export const mockAlerts = [
  {
    id: 1,
    title: 'Độ ẩm thấp',
    description: 'Khu vực B · 73%',
    time: '10 phút',
    level: 'warning',
  },
  {
    id: 2,
    title: 'Thiết bị mất kết nối',
    description: 'Sensor Node 04',
    time: '32 phút',
    level: 'danger',
  },
  {
    id: 3,
    title: 'Môi trường đã ổn định',
    description: 'Khu vực A',
    time: '1 giờ',
    level: 'normal',
  },
]
