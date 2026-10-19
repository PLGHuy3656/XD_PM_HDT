export const systemStats = [
  {
    id: 'nodes',
    label: 'Device Nodes',
    value: '7 / 8',
    description: '1 node mất kết nối tại Khu vực D',
    status: 'warning',
    statusLabel: 'Cần chú ý',
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
    id: 'ESP32-CTRL-01',
    zone: 'Nhà yến Bình An · Khu vực A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '8 giây trước',
  },
  {
    id: 'ESP32-CTRL-02',
    zone: 'Nhà yến Bình An · Khu vực B',
    status: 'warning',
    sensors: '3 / 4',
    lastSeen: '18 giây trước',
  },
  {
    id: 'SENSOR-ENV-03',
    zone: 'Nhà yến Phú An · Khu vực C',
    status: 'online',
    sensors: '3 / 3',
    lastSeen: '12 giây trước',
  },
  {
    id: 'ESP32-CTRL-04',
    zone: 'Nhà yến Phú An · Khu vực D',
    status: 'offline',
    sensors: '0 / 4',
    lastSeen: '12 phút trước',
  },
  {
    id: 'ESP32-CTRL-05',
    zone: 'Nhà yến Bình An · Khu vực E',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '21 giây trước',
  },
]

export const sensorHealth = [
  { label: 'Healthy', value: 24, status: 'healthy' },
  { label: 'Warning', value: 2, status: 'warning' },
  { label: 'Offline', value: 0, status: 'danger' },
]

export const alerts = [
  {
    id: 'ALT-001',
    level: 'critical',
    title: 'ESP32-CTRL-04 mất kết nối',
    description: 'Nhà yến Phú An · Khu vực D · Không nhận telemetry',
    time: '12 phút trước',
  },
  {
    id: 'ALT-002',
    level: 'warning',
    title: 'SHT31-B02 độ ẩm dưới ngưỡng',
    description: 'ESP32-CTRL-02 · Nhà yến Bình An · Khu vực B',
    time: '28 phút trước',
  },
  {
    id: 'ALT-004',
    level: 'info',
    title: 'MQTT đã kết nối lại',
    description: 'ESP32-CTRL-01 · Nhà yến Bình An · Khu vực A',
    time: '1 giờ trước',
  },
]