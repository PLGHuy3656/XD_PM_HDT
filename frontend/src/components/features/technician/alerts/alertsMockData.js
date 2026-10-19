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
    title: 'Node điều khiển mất kết nối',
    type: 'NODE_DISCONNECTED',
    severity: 'CRITICAL',
    status: 'OPEN',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    device: 'ESP32-CTRL-04',
    occurredAt: '08:14 hôm nay',
    description:
      'Node không gửi heartbeat và telemetry trong hơn 10 phút.',
    diagnostic:
      'Không nhận được heartbeat. MQTT client hiện ở trạng thái disconnected.',
    recommendation:
      'Kiểm tra nguồn cấp, kết nối mạng và trạng thái MQTT của node.',
  },
  {
    id: 'ALT-002',
    title: 'Độ ẩm dưới ngưỡng vận hành',
    type: 'ABNORMAL_READING',
    severity: 'WARNING',
    status: 'OPEN',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực B',
    device: 'SHT31-B02',
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
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực C',
    device: 'CO2-C01',
    occurredAt: '07:22 hôm nay',
    description:
      'Không nhận được dữ liệu CO₂ từ sensor trong chu kỳ telemetry gần nhất.',
    diagnostic:
      'Node gateway vẫn online nhưng sensor CO₂ không trả về dữ liệu.',
    recommendation:
      'Kiểm tra dây kết nối, nguồn sensor và giao tiếp với node.',
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
    zone: 'Khu vực F',
    device: 'FAN-F01',
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
    sender: 'Nguyễn Minh Anh',
    priority: 'HIGH',
    status: 'NEW',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực B',
    createdAt: '08:05 hôm nay',
    content:
      'Độ ẩm khu vực B giảm liên tục từ sáng. Nhờ kỹ thuật viên kiểm tra sensor và hệ thống phun sương.',
    contact: '0901 234 567',
  },
  {
    id: 'REQ-002',
    title: 'Kiểm tra Node ESP32-CTRL-04',
    source: 'ADMIN',
    sender: 'System Administrator',
    priority: 'URGENT',
    status: 'IN_PROGRESS',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực D',
    createdAt: '07:35 hôm nay',
    content:
      'Node mất heartbeat. Kiểm tra connectivity và xác nhận tình trạng thiết bị.',
    contact: null,
  },
  {
    id: 'REQ-003',
    title: 'Camera cửa vào mất hình',
    source: 'FARM_OWNER',
    sender: 'Trần Quốc Nam',
    priority: 'NORMAL',
    status: 'NEW',
    farm: 'Nhà yến Bình An',
    zone: 'Khu vực A',
    createdAt: 'Hôm qua, 19:20',
    content:
      'Camera cửa vào không hiển thị hình ảnh. Nhờ kiểm tra nguồn và kết nối thiết bị.',
    contact: '0908 456 789',
  },
  {
    id: 'REQ-004',
    title: 'Xác nhận tình trạng Sensor CO₂',
    source: 'ADMIN',
    sender: 'System Administrator',
    priority: 'NORMAL',
    status: 'DONE',
    farm: 'Nhà yến Phú An',
    zone: 'Khu vực C',
    createdAt: 'Hôm qua, 14:10',
    content:
      'Kiểm tra sensor CO₂ sau khi hệ thống ghi nhận telemetry gián đoạn.',
    contact: null,
  },
]