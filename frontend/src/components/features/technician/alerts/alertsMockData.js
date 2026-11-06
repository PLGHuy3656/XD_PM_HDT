export function severityLabel(severity) {
  return {
    CRITICAL: 'Nghiêm trọng',
    WARNING: 'Cảnh báo',
    INFO: 'Thông tin',
  }[severity]
}

export function technicalStatusLabel(status) {
  return {
    OPEN: 'Chưa xử lý',
    INVESTIGATING: 'Đang kiểm tra',
    RESOLVED: 'Đã xử lý',
  }[status]
}

export function workSourceLabel(source) {
  return source === 'ADMIN' ? 'Admin' : 'Farm Owner'
}

export function workPriorityLabel(priority) {
  return {
    URGENT: 'Khẩn cấp',
    HIGH: 'Cao',
    NORMAL: 'Bình thường',
  }[priority]
}

export function workStatusLabel(status) {
  return {
    NEW: 'Mới',
    IN_PROGRESS: 'Đang xử lý',
    DONE: 'Hoàn thành',
  }[status]
}

export const technicalAlerts = [
  {
    id: 'ALT-001',
    title: 'Độ ẩm dưới ngưỡng vận hành',
    type: 'ABNORMAL_READING',
    severity: 'WARNING',
    status: 'OPEN',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    device: 'ESP32-CTRL-04',
    occurredAt: '08:14 hôm nay',
    description:
      'Độ ẩm hiện tại 74%, thấp hơn ngưỡng môi trường được cấu hình.',
    diagnostic:
      'Node gửi telemetry với tín hiệu Wi-Fi yếu (-76 dBm).',
    recommendation:
      'Kiểm tra máy phun sương Khu vực D và độ ổn định kết nối Wi-Fi.',
  },
  {
    id: 'ALT-002',
    title: 'Độ ẩm dưới ngưỡng vận hành',
    type: 'ABNORMAL_READING',
    severity: 'WARNING',
    status: 'OPEN',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực B',
    device: 'ESP32-CTRL-02',
    occurredAt: '07:48 hôm nay',
    description:
      'Độ ẩm hiện tại 74%, thấp hơn ngưỡng môi trường được cấu hình.',
    diagnostic:
      'Sensor vẫn gửi dữ liệu ổn định. Chưa phát hiện lỗi kết nối.',
    recommendation:
      'Kiểm tra cảm biến độ ẩm và hệ thống phun sương của khu vực.',
  },
  {
    id: 'ALT-003',
    title: 'Sensor không phản hồi',
    type: 'SENSOR_TIMEOUT',
    severity: 'WARNING',
    status: 'INVESTIGATING',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực C',
    device: 'AUDIO-01',
    occurredAt: '07:22 hôm nay',
    description:
      'Không nhận được dữ liệu âm thanh từ node trong chu kỳ gần nhất.',
    diagnostic:
      'Audio node hiện ở trạng thái offline.',
    recommendation:
      'Kiểm tra nguồn cấp và kết nối mạng của node âm thanh.',
  },
  {
    id: 'ALT-004',
    title: 'MQTT reconnect bất thường',
    type: 'MQTT_CONNECTIVITY',
    severity: 'INFO',
    status: 'RESOLVED',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực A',
    device: 'ESP32-CTRL-01',
    occurredAt: '06:51 hôm nay',
    description:
      'Node thực hiện nhiều lần reconnect MQTT trong thời gian ngắn.',
    diagnostic:
      'Kết nối hiện đã ổn định và telemetry đã được khôi phục.',
    recommendation:
      'Theo dõi chất lượng mạng nếu hiện tượng tiếp tục xuất hiện.',
  },
  {
    id: 'ALT-005',
    title: 'Quạt thông gió không phản hồi',
    type: 'ACTUATOR_FAILURE',
    severity: 'CRITICAL',
    status: 'OPEN',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    device: 'ESP32-CTRL-04',
    occurredAt: 'Hôm qua, 22:36',
    description:
      'Actuator không xác nhận trạng thái sau lệnh điều khiển.',
    diagnostic:
      'Node vẫn online. Relay đã nhận lệnh nhưng không có phản hồi trạng thái từ quạt.',
    recommendation:
      'Kiểm tra relay, nguồn và kết nối vật lý của quạt.',
  },
]

export const workRequests = [
  {
    id: 'REQ-001',
    title: 'Kiểm tra độ ẩm Khu vực B',
    source: 'FARM_OWNER',
    sender: 'Nguyễn Văn Minh',
    priority: 'HIGH',
    status: 'NEW',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực B',
    createdAt: '08:05 hôm nay',
    content:
      'Độ ẩm khu vực B giảm liên tục từ sáng. Nhờ kỹ thuật viên kiểm tra sensor và hệ thống phun sương.',
    contact: '090 123 4567',
  },
  {
    id: 'REQ-002',
    title: 'Kiểm tra Node ESP32-CTRL-04',
    source: 'ADMIN',
    sender: 'Phạm Lê Gia Huy',
    priority: 'URGENT',
    status: 'IN_PROGRESS',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    createdAt: '07:35 hôm nay',
    content:
      'Node cảnh báo tín hiệu yếu và độ ẩm thấp tại Khu vực D. Kiểm tra connectivity và xác nhận tình trạng thiết bị.',
    contact: null,
  },
  {
    id: 'REQ-003',
    title: 'Camera cửa vào mất hình',
    source: 'FARM_OWNER',
    sender: 'Nguyễn Văn Minh',
    priority: 'NORMAL',
    status: 'NEW',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực A',
    createdAt: 'Hôm qua, 19:20',
    content:
      'Camera cửa vào không hiển thị hình ảnh. Nhờ kiểm tra nguồn và kết nối thiết bị.',
    contact: '090 123 4567',
  },
  {
    id: 'REQ-004',
    title: 'Xác nhận tình trạng Audio Node',
    source: 'ADMIN',
    sender: 'Phạm Lê Gia Huy',
    priority: 'NORMAL',
    status: 'DONE',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực C',
    createdAt: 'Hôm qua, 14:10',
    content:
      'Kiểm tra node âm thanh sau khi hệ thống ghi nhận mất kết nối.',
    contact: null,
  },
]
