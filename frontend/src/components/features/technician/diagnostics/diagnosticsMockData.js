export const diagnosticSummary = {
  totalNodes: 8,
  healthyNodes: 5,
  warningNodes: 2,
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
    id: 'SENSOR-ENV-03',
    name: 'Cụm cảm biến Zone C',
    type: 'Sensor Node',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực C',
    status: 'HEALTHY',
    lastSeen: '18 giây trước',

    connectivity: {
      mqtt: 'CONNECTED',
      wifi: 'CONNECTED',
      rssi: -56,
      ip: '192.168.2.31',
    },

    sensors: [
      { name: 'Nhiệt độ', status: 'HEALTHY', value: '27.9°C' },
      { name: 'Độ ẩm', status: 'HEALTHY', value: '84%' },
      { name: 'CO₂', status: 'HEALTHY', value: '580 ppm' },
    ],

    actuators: [],

    issues: [],
  },

  {
    id: 'ESP32-CTRL-04',
    name: 'Bộ điều khiển Zone D',
    type: 'ESP32 Controller',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    status: 'OFFLINE',
    lastSeen: '12 phút trước',

    connectivity: {
      mqtt: 'DISCONNECTED',
      wifi: 'DISCONNECTED',
      rssi: null,
      ip: '192.168.2.24',
    },

    sensors: [
      { name: 'Nhiệt độ', status: 'UNAVAILABLE', value: '--' },
      { name: 'Độ ẩm', status: 'UNAVAILABLE', value: '--' },
    ],

    actuators: [
      { name: 'Quạt thông gió', status: 'UNAVAILABLE' },
      { name: 'Máy phun sương', status: 'UNAVAILABLE' },
    ],

    issues: [
      'Node không gửi heartbeat.',
      'MQTT đã mất kết nối.',
      'Không thể xác nhận trạng thái Sensor và Actuator.',
    ],
  },

  {
    id: 'CAM-AI-01',
    name: 'Camera AI cửa vào',
    type: 'AI Camera',
    farm: 'Nhà yến Bình An',
    zone: 'Lối vào',
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
]