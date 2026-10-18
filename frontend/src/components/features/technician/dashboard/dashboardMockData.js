export const systemStats = [
  {
    id: 'nodes',
    label: 'Device Nodes',
    value: '8 / 8',
    description: 'Tất cả node đang phản hồi',
    status: 'healthy',
    statusLabel: 'Hoạt động tốt',
    icon: 'N',
  },
  {
    id: 'sensors',
    label: 'Sensors',
    value: '24 / 26',
    description: '2 sensor cần kiểm tra',
    status: 'warning',
    statusLabel: 'Cần chú ý',
    icon: 'S',
  },
  {
    id: 'actuators',
    label: 'Actuators',
    value: '6 / 6',
    description: 'Sẵn sàng hoạt động',
    status: 'healthy',
    statusLabel: 'Sẵn sàng',
    icon: 'A',
  },
  {
    id: 'mqtt',
    label: 'MQTT',
    value: 'Connected',
    description: 'Latency 28 ms',
    status: 'healthy',
    statusLabel: 'Đã kết nối',
    icon: 'M',
  },
]

export const devices = [
  {
    id: 'ESP32-01',
    zone: 'Tầng 1 · Khu A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '12 giây trước',
  },
  {
    id: 'ESP32-02',
    zone: 'Tầng 2 · Khu A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '18 giây trước',
  },
  {
    id: 'ESP32-03',
    zone: 'Tầng 1 · Khu B',
    status: 'warning',
    sensors: '3 / 4',
    lastSeen: '1 phút trước',
  },
  {
    id: 'ESP32-04',
    zone: 'Tầng 2 · Khu B',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '22 giây trước',
  },
  {
    id: 'ESP32-05',
    zone: 'Phòng kỹ thuật',
    status: 'offline',
    sensors: '0 / 4',
    lastSeen: '12 phút trước',
  },
]

export const sensorHealth = [
  { label: 'Healthy', value: 24, status: 'healthy' },
  { label: 'Warning', value: 2, status: 'warning' },
  { label: 'Offline', value: 0, status: 'danger' },
]

export const alerts = [
  {
    id: 1,
    level: 'critical',
    title: 'ESP32-05 mất kết nối',
    description: 'Không nhận telemetry trong 12 phút',
    time: '12 phút trước',
  },
  {
    id: 2,
    level: 'warning',
    title: 'SHT31-03 phản hồi không ổn định',
    description: 'ESP32-03 · Tầng 1 · Khu B',
    time: '28 phút trước',
  },
  {
    id: 3,
    level: 'info',
    title: 'MQTT đã kết nối lại',
    description: 'ESP32-02 hoạt động bình thường',
    time: '1 giờ trước',
  },
]