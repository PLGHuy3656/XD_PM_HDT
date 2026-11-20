/**
 * INT02-F04: one registration contract for Owner and Technician forms.
 *
 * Only the device types the system actually uses are offered (Management stores device_type
 * as free text, so the UI must not invent types):
 *   ENVIRONMENT_MONITOR – ESP32 node: MQTT telemetry/heartbeat + relay commands (IoT Service)
 *   CAMERA              – AI camera in the Management Camera Registry (/api/cameras/{node_id});
 *                         its image source (synthetic test, browser webcam, uploaded video) is
 *                         chosen per session on the Swiftlets page, never stored on the device.
 * Speakers / LAN audio / other actuators are deferred (no backend or hardware contract yet).
 */
export const REGISTERABLE_DEVICE_TYPES = [
  {
    value: 'ENVIRONMENT_MONITOR',
    label: 'Nút IoT môi trường (ESP32)',
    nodeLabel: 'Hardware Node ID',
    placeholder: 'VD: SWC-DEMO-NODE-003',
    help: 'Nhập đúng ID cấu hình trong firmware ESP32 (MQTT). Sau khi đăng ký, thiết bị ở trạng thái "Đã đăng ký · chưa có heartbeat" và chỉ trực tuyến khi gửi heartbeat thật.',
  },
  {
    value: 'CAMERA',
    label: 'Camera AI',
    nodeLabel: 'Camera ID',
    placeholder: 'VD: CAM-03',
    help: 'Mã camera trong Camera Registry. Nguồn hình ảnh (video từ máy, webcam trình duyệt, video kiểm thử) được chọn khi bắt đầu phiên tại trang Giám sát chim yến — webcam trình duyệt không phải thiết bị MQTT.',
  },
]

export const DEFAULT_REGISTER_TYPE = 'ENVIRONMENT_MONITOR'

// Same character set the Gateway accepts for camera/device path segments
export const NODE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{2,63}$/

export function registrationTypeMeta(value) {
  return REGISTERABLE_DEVICE_TYPES.find((t) => t.value === value) || REGISTERABLE_DEVICE_TYPES[0]
}

/** Returns an error message or null. Uniqueness is enforced by Management (HTTP 409). */
export function validateRegistration({ node_id: nodeId, name, device_type: type } = {}, { requireName = true } = {}) {
  const id = String(nodeId || '').trim()
  if (!REGISTERABLE_DEVICE_TYPES.some((t) => t.value === type)) return 'Loại thiết bị không được hỗ trợ.'
  if (!id) return `Vui lòng nhập ${registrationTypeMeta(type).nodeLabel} thực tế của thiết bị.`
  if (!NODE_ID_PATTERN.test(id)) return 'ID chỉ gồm chữ, số, dấu gạch ngang/gạch dưới/chấm (3–64 ký tự, bắt đầu bằng chữ hoặc số).'
  if (requireName && !String(name || '').trim()) return 'Vui lòng nhập tên thiết bị.'
  return null
}

/** Human message after a successful registration — registration never means "online". */
export function registeredNotice(type) {
  return type === 'CAMERA'
    ? 'Camera đã có trong Camera Registry (REGISTERED). Bắt đầu phiên AI tại trang Giám sát chim yến.'
    : 'Thiết bị ở trạng thái Đã đăng ký · chưa có heartbeat — sẽ trực tuyến khi ESP32 gửi heartbeat MQTT.'
}

/** Map a backend error to a clear message (409 duplicate node_id, 403 farm/role, 400 zone). */
export function registrationErrorText(message = '') {
  const m = String(message)
  if (/already exists|409|duplicate|tồn tại/i.test(m)) return 'ID thiết bị đã tồn tại trong hệ thống — mỗi Node ID chỉ đăng ký một lần.'
  if (/approved/i.test(m)) return 'Nhà yến phải được Admin phê duyệt trước khi đăng ký thiết bị.'
  if (/zone/i.test(m)) return 'Khu vực không thuộc nhà yến đã chọn.'
  if (/403|forbidden|access/i.test(m)) return 'Bạn không có quyền đăng ký thiết bị cho nhà yến này.'
  return m || 'Không thể đăng ký thiết bị.'
}
