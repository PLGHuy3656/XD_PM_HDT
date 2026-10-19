export const systemStats = [
  {
    id: 'nodes',
    label: 'Device Nodes',
    value: '8 / 8',
    description: 'T?t c? node ?ang ph?n h?i',
    status: 'healthy',
    statusLabel: 'Ho?t ??ng t?t',
    icon: '?',
  },
  {
    id: 'sensors',
    label: 'Sensors',
    value: '24 / 26',
    description: '2 sensor c?n ki?m tra',
    status: 'warning',
    statusLabel: 'C?n ch? ?',
    icon: '?',
  },
  {
    id: 'actuators',
    label: 'Actuators',
    value: '6 / 6',
    description: 'S?n s?ng ho?t ??ng',
    status: 'healthy',
    statusLabel: 'S?n s?ng',
    icon: '?',
  },
  {
    id: 'mqtt',
    label: 'MQTT',
    value: 'Connected',
    description: 'Latency 28 ms',
    status: 'healthy',
    statusLabel: '?? k?t n?i',
    icon: '?',
  },
]

export const devices = [
  {
    id: 'ESP32-01',
    zone: 'T?ng 1 ? Khu A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '12 gi?y tr??c',
  },
  {
    id: 'ESP32-02',
    zone: 'T?ng 2 ? Khu A',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '18 gi?y tr??c',
  },
  {
    id: 'ESP32-03',
    zone: 'T?ng 1 ? Khu B',
    status: 'warning',
    sensors: '3 / 4',
    lastSeen: '1 ph?t tr??c',
  },
  {
    id: 'ESP32-04',
    zone: 'T?ng 2 ? Khu B',
    status: 'online',
    sensors: '4 / 4',
    lastSeen: '22 gi?y tr??c',
  },
  {
    id: 'ESP32-05',
    zone: 'Ph?ng k? thu?t',
    status: 'offline',
    sensors: '0 / 4',
    lastSeen: '12 ph?t tr??c',
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
    title: 'ESP32-05 m?t k?t n?i',
    description: 'Kh?ng nh?n telemetry trong 12 ph?t',
    time: '12 ph?t tr??c',
  },
  {
    id: 2,
    level: 'warning',
    title: 'SHT31-03 ph?n h?i kh?ng ?n ??nh',
    description: 'ESP32-03 ? T?ng 1 ? Khu B',
    time: '28 ph?t tr??c',
  },
  {
    id: 3,
    level: 'info',
    title: 'MQTT ?? k?t n?i l?i',
    description: 'ESP32-02 ho?t ??ng b?nh th??ng',
    time: '1 gi? tr??c',
  },
]
