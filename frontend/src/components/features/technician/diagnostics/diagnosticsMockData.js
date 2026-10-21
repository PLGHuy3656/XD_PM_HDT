export const diagnosticSummary = {
  totalNodes: 6,
  healthyNodes: 4,
  warningNodes: 1,
  offlineNodes: 1,
}

export const diagnosticNodes = [
  {
    id: 'ESP32-CTRL-01',
    name: 'Bộ điều khiển Zone A',
    type: 'ESP32 Controller',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực A',
    status: 'HEALTHY',
    lastSeen: '10 giây trước',

    connectivity: {
      mqtt: 'CONNECTED',
      wifi: 'CONNECTED',
      rssi: -48,
      ip: '192.168.1.21',
    },

    sensors: [
      { name: 'Nhiệt độ', status: 'HEALTHY', value: '28.4°C' },
      { name: 'Độ ẩm', status: 'HEALTHY', value: '82%' },
      { name: 'CO₂', status: 'HEALTHY', value: '612 ppm' },
      { name: 'Ánh sáng', status: 'HEALTHY', value: '4.2 lux' },
    ],

    actuators: [
      { name: 'Quạt thông gió', status: 'HEALTHY' },
      { name: 'Máy phun sương', status: 'HEALTHY' },
    ],

    issues: [],
  },

  {
    id: 'ESP32-CTRL-02',
    name: 'Bộ điều khiển Zone B',
    type: 'ESP32 Controller',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực B',
    status: 'WARNING',
    lastSeen: '42 giây trước',

    connectivity: {
      mqtt: 'UNSTABLE',
      wifi: 'CONNECTED',
      rssi: -78,
      ip: '192.168.1.22',
    },

    sensors: [
      { name: 'Nhiệt độ', status: 'HEALTHY', value: '30.1°C' },
      { name: 'Độ ẩm', status: 'WARNING', value: '74%' },
      { name: 'CO₂', status: 'HEALTHY', value: '690 ppm' },
      { name: 'Ánh sáng', status: 'HEALTHY', value: '3.8 lux' },
    ],

    actuators: [
      { name: 'Quạt thông gió', status: 'HEALTHY' },
      { name: 'Máy phun sương', status: 'WARNING' },
    ],

    issues: [
      'Tín hiệu Wi-Fi yếu, kết nối MQTT không ổn định.',
      'Cảm biến độ ẩm ghi nhận giá trị thấp.',
      'Máy phun sương phản hồi chậm.',
    ],
  },

  {
    id: 'AUDIO-01',
    name: 'Node âm thanh Zone C',
    type: 'Audio Edge Node',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực C',
    status: 'OFFLINE',
    lastSeen: '12 phút trước',

    connectivity: {
      mqtt: 'DISCONNECTED',
      wifi: 'DISCONNECTED',
      rssi: null,
      ip: '192.168.1.35',
    },

    sensors: [
      { name: 'Microphone Array', status: 'UNAVAILABLE', value: '--' },
    ],

    actuators: [],

    issues: [
      'Node không gửi heartbeat.',
      'MQTT đã mất kết nối.',
    ],
  },

  {
    id: 'CAM-AI-01',
    name: 'Camera AI cửa vào',
    type: 'AI Camera',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực A',
    status: 'HEALTHY',
    lastSeen: '6 giây trước',

    connectivity: {
      mqtt: 'CONNECTED',
      wifi: 'CONNECTED',
      rssi: -52,
      ip: '192.168.1.41',
    },

    sensors: [
      { name: 'Camera', status: 'HEALTHY', value: 'Online' },
    ],

    actuators: [],

    issues: [],
  },

  {
    id: 'ESP32-CTRL-03',
    name: 'Bộ điều khiển Zone A',
    type: 'ESP32 Controller',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực A',
    status: 'HEALTHY',
    lastSeen: '5 giây trước',

    connectivity: {
      mqtt: 'CONNECTED',
      wifi: 'CONNECTED',
      rssi: -53,
      ip: '192.168.2.21',
    },

    sensors: [
      { name: 'Nhiệt độ', status: 'HEALTHY', value: '29.8°C' },
      { name: 'Độ ẩm', status: 'HEALTHY', value: '78%' },
      { name: 'CO₂', status: 'HEALTHY', value: '650 ppm' },
      { name: 'Ánh sáng', status: 'HEALTHY', value: '118 lux' },
    ],

    actuators: [
      { name: 'Quạt thông gió', status: 'HEALTHY' },
      { name: 'Máy phun sương', status: 'HEALTHY' },
    ],

    issues: [],
  },

  {
    id: 'ESP32-CTRL-04',
    name: 'Bộ điều khiển Zone D',
    type: 'ESP32 Controller',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    status: 'WARNING',
    lastSeen: '16 giây trước',

    connectivity: {
      mqtt: 'UNSTABLE',
      wifi: 'CONNECTED',
      rssi: -76,
      ip: '192.168.2.24',
    },

    sensors: [
      { name: 'Nhiệt độ', status: 'HEALTHY', value: '30.6°C' },
      { name: 'Độ ẩm', status: 'WARNING', value: '74%' },
      { name: 'CO₂', status: 'HEALTHY', value: '820 ppm' },
      { name: 'Ánh sáng', status: 'HEALTHY', value: '135 lux' },
    ],

    actuators: [
      { name: 'Quạt thông gió', status: 'HEALTHY' },
      { name: 'Máy phun sương', status: 'HEALTHY' },
    ],

    issues: [
      'Độ ẩm dưới ngưỡng vận hành tại Khu vực D.',
      'Tín hiệu Wi-Fi yếu (-76 dBm).',
    ],
  },
]
