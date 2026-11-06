export const installationFarms = [
  {
    id: 'farm-binh-an',
    name: 'Nhà yến Bình An',
    location: 'Thủ Đức, TP. Hồ Chí Minh',
    zones: [
      { id: 'zone-a', name: 'Khu vực A' },
      { id: 'zone-b', name: 'Khu vực B' },
      { id: 'zone-c', name: 'Khu vực C' },
    ],
  },
  {
    id: 'farm-phu-an',
    name: 'Nhà yến Phú An',
    location: 'Dĩ An, Bình Dương',
    zones: [
      { id: 'zone-a', name: 'Khu vực A' },
      { id: 'zone-d', name: 'Khu vực D' },
    ],
  },
]

export const deviceTypes = [
  {
    id: 'controller',
    label: 'ESP32 Controller',
  },
  {
    id: 'sensor-node',
    label: 'Sensor Node',
  },
  {
    id: 'actuator-node',
    label: 'Actuator Node',
  },
]

export const initialInstallation = {
  farmId: 'farm-binh-an',
  zoneId: 'zone-a',
  deviceId: 'ESP32-CTRL-01',
  deviceType: 'controller',
  serialNumber: 'NM-ESP32-2026-001',
  firmware: 'v1.4.2',
  mqttTopic: 'nestmate/binh-an/zone-a/controller-01',
  samplingInterval: '30',
}

export const verificationItems = [
  {
    id: 'power',
    label: 'Nguồn thiết bị',
    description:
      'Thiết bị đã khởi động và hoạt động ổn định.',
  },
  {
    id: 'network',
    label: 'Kết nối mạng',
    description:
      'Node có kết nối Wi-Fi và địa chỉ IP hợp lệ.',
  },
  {
    id: 'mqtt',
    label: 'MQTT Broker',
    description:
      'Thiết bị kết nối và gửi heartbeat đến broker.',
  },
  {
    id: 'sensor',
    label: 'Sensor telemetry',
    description:
      'Dữ liệu cảm biến được ghi nhận bình thường.',
  },
  {
    id: 'actuator',
    label: 'Actuator',
    description:
      'Thiết bị chấp hành phản hồi trạng thái.',
  },
]
