export const environmentSummary = {
  totalZones: 5,
  normalZones: 3,
  warningZones: 2,
  sensorIssues: 1,
}

export const environmentZones = [
  {
    id: 'ZONE-A',
    name: 'Khu vực A',
    farm: 'Nhà yến Bình An',
    status: 'NORMAL',
    updatedAt: '8 giây trước',
    controller: 'ESP32-CTRL-01',
    metrics: {
      temperature: { value: 28.4, unit: '°C', status: 'NORMAL' },
      humidity: { value: 82, unit: '%', status: 'NORMAL' },
      co2: { value: 612, unit: 'ppm', status: 'NORMAL' },
      light: { value: 4.2, unit: 'lux', status: 'NORMAL' },
    },
    technicalNote: 'Sensor hoạt động ổn định, dữ liệu cập nhật bình thường.',
  },
  {
    id: 'ZONE-B',
    name: 'Khu vực B',
    farm: 'Nhà yến Bình An',
    status: 'WARNING',
    updatedAt: '18 giây trước',
    controller: 'ESP32-CTRL-02',
    metrics: {
      temperature: { value: 30.1, unit: '°C', status: 'NORMAL' },
      humidity: { value: 74, unit: '%', status: 'WARNING' },
      co2: { value: 690, unit: 'ppm', status: 'NORMAL' },
      light: { value: 3.8, unit: 'lux', status: 'NORMAL' },
    },
    technicalNote:
      'Độ ẩm thấp. Cần đối chiếu Sensor và trạng thái máy phun sương.',
  },
  {
    id: 'ZONE-C',
    name: 'Khu vực C',
    farm: 'Nhà yến Bình An',
    status: 'NORMAL',
    updatedAt: '21 giây trước',
    controller: 'AUDIO-01',
    metrics: {
      temperature: { value: 28.8, unit: '°C', status: 'NORMAL' },
      humidity: { value: 80, unit: '%', status: 'NORMAL' },
      co2: { value: 640, unit: 'ppm', status: 'NORMAL' },
      light: { value: 4.0, unit: 'lux', status: 'NORMAL' },
    },
    technicalNote: 'Telemetry ổn định.',
  },
  {
    id: 'ZONE-PA-A',
    name: 'Khu vực A',
    farm: 'Nhà yến Phú An',
    status: 'NORMAL',
    updatedAt: '12 giây trước',
    controller: 'ESP32-CTRL-03',
    metrics: {
      temperature: { value: 27.9, unit: '°C', status: 'NORMAL' },
      humidity: { value: 84, unit: '%', status: 'NORMAL' },
      co2: { value: 580, unit: 'ppm', status: 'NORMAL' },
      light: { value: 4.6, unit: 'lux', status: 'NORMAL' },
    },
    technicalNote: 'Không phát hiện bất thường kỹ thuật.',
  },
  {
    id: 'ZONE-D',
    name: 'Khu vực D',
    farm: 'Nhà yến Phú An',
    status: 'WARNING',
    updatedAt: '16 giây trước',
    controller: 'ESP32-CTRL-04',
    metrics: {
      temperature: { value: 30.6, unit: '°C', status: 'NORMAL' },
      humidity: { value: 74, unit: '%', status: 'WARNING' },
      co2: { value: 820, unit: 'ppm', status: 'NORMAL' },
      light: { value: 135, unit: 'lux', status: 'NORMAL' },
    },
    technicalNote:
      'Độ ẩm dưới ngưỡng cài đặt. Node ESP32-CTRL-04 cần theo dõi kết nối.',
  },
]
