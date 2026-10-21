export const alertFarms = [
  {
    id: 'farm-binh-an',
    name: 'Nh� y?n B�nh An',
    zones: [
      {
        id: 'all',
        name: 'T?t c? khu v?c',
      },
      {
        id: 'zone-a',
        name: 'Khu v?c A � C?a ch�nh',
      },
      {
        id: 'zone-b',
        name: 'Khu v?c B � T?ng 2',
      },
      {
        id: 'zone-c',
        name: 'Khu v?c C � T?ng 3',
      },
    ],
  },
  {
    id: 'farm-phu-an',
    name: 'Nh� y?n Ph� An',
    zones: [
      {
        id: 'all',
        name: 'T?t c? khu v?c',
      },
      {
        id: 'zone-a',
        name: 'Khu v?c A � T?ng 1',
      },
      {
        id: 'zone-d',
        name: 'Khu v?c D � T?ng 2',
      },
    ],
  },
]

export const alerts = [
  {
    id: 'ALT-1042',
    severity: 'CRITICAL',
    status: 'OPEN',
    source: 'AI Vision',
    type: 'PREDATOR',
    title: 'Phát hiện cú gần cửa vào',
    description:
      'Camera AI phát hiện đối tượng có đặc trưng của cú xuất hiện gần lối vào nhà yến.',
    farmId: 'farm-binh-an',
    zoneId: 'zone-b',
    zoneName: 'Khu vực B · Tầng 2',
    device: 'CAM-02',
    time: '23:14 hôm qua',
    confidence: 88.5,
    value: null,
    threshold: null,
  },
  {
    id: 'ALT-1041',
    severity: 'HIGH',
    status: 'OPEN',
    source: 'Môi trường',
    type: 'TEMPERATURE',
    title: 'Nhiệt độ vượt ngưỡng',
    description:
      'Nhiệt độ tại khu vực A vượt ngưỡng vận hành được cấu hình.',
    farmId: 'farm-binh-an',
    zoneId: 'zone-a',
    zoneName: 'Khu vực A · Cửa chính',
    device: 'SHT31-01',
    time: '14:32 hôm nay',
    confidence: null,
    value: '32.4°C',
    threshold: 'Tối đa 31°C',
  },
  {
    id: 'ALT-1040',
    severity: 'HIGH',
    status: 'ACKNOWLEDGED',
    source: 'Thiết bị',
    type: 'DEVICE',
    title: 'Camera Node mất kết nối',
    description:
      'Hệ thống không nhận được heartbeat từ Camera Node trong khoảng thời gian cho phép.',
    farmId: 'farm-binh-an',
    zoneId: 'zone-b',
    zoneName: 'Khu vực B · Tầng 2',
    device: 'EDGE-03',
    time: '10:18 hôm nay',
    confidence: null,
    value: 'Offline',
    threshold: null,
  },
  {
    id: 'ALT-1039',
    severity: 'MEDIUM',
    status: 'ACKNOWLEDGED',
    source: 'Audio AI',
    type: 'AUDIO',
    title: 'Âm thanh bất thường',
    description:
      'Edge AI phát hiện mẫu âm thanh khác biệt so với trạng thái hoạt động bình thường.',
    farmId: 'farm-binh-an',
    zoneId: 'zone-a',
    zoneName: 'Khu vực A · Cửa chính',
    device: 'MIC-01',
    time: '21:36 hôm qua',
    confidence: 84.7,
    value: null,
    threshold: null,
  },
  {
    id: 'ALT-1038',
    severity: 'MEDIUM',
    status: 'RESOLVED',
    source: 'Môi trường',
    type: 'HUMIDITY',
    title: 'Độ ẩm xuống dưới ngưỡng',
    description:
      'Độ ẩm đã giảm xuống dưới ngưỡng vận hành và hiện đã trở lại mức bình thường.',
    farmId: 'farm-binh-an',
    zoneId: 'zone-a',
    zoneName: 'Khu vực A · Cửa chính',
    device: 'SHT31-01',
    time: '08:45 hôm qua',
    confidence: null,
    value: '72%',
    threshold: 'Tối thiểu 75%',
  },
  {
    id: 'ALT-1037',
    severity: 'LOW',
    status: 'RESOLVED',
    source: 'Thiết bị',
    type: 'DEVICE',
    title: 'Cảm biến mất kết nối tạm thời',
    description:
      'Cảm biến đã tự động kết nối lại sau một khoảng gián đoạn ngắn.',
    farmId: 'farm-binh-an',
    zoneId: 'zone-b',
    zoneName: 'Khu vực B · Tầng 2',
    device: 'SHT31-02',
    time: '17:20 · 14/10',
    confidence: null,
    value: 'Đã kết nối lại',
    threshold: null,
  },
]

export const alertStatusOptions = [
  {
    value: 'ALL',
    label: 'Tất cả',
  },
  {
    value: 'OPEN',
    label: 'Đang mở',
  },
  {
    value: 'ACKNOWLEDGED',
    label: 'Đã xác nhận',
  },
  {
    value: 'RESOLVED',
    label: 'Đã xử lý',
  },
]

export const alertSeverityOptions = [
  {
    value: 'ALL',
    label: 'Mọi mức',
  },
  {
    value: 'CRITICAL',
    label: 'CRITICAL',
  },
  {
    value: 'HIGH',
    label: 'HIGH',
  },
  {
    value: 'MEDIUM',
    label: 'MEDIUM',
  },
  {
    value: 'LOW',
    label: 'LOW',
  },
]
