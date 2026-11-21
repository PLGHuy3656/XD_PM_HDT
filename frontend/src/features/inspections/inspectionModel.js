export const INSPECTION_STATUS_LABELS = {
  NEW: 'Mới',
  ACCEPTED: 'Đã tiếp nhận',
  IN_PROGRESS: 'Đang kiểm tra',
  COMPLETED: 'Hoàn thành',
  CANCELLED: 'Đã hủy',
}

export const INSPECTION_PRIORITY_LABELS = {
  LOW: 'Thấp',
  MEDIUM: 'Trung bình',
  HIGH: 'Cao',
  URGENT: 'Khẩn cấp',
}

export const INSPECTION_ACTION_LABELS = {
  CREATE: 'Tạo yêu cầu',
  ASSIGN: 'Admin phân công',
  ACCEPT: 'Tiếp nhận',
  START: 'Bắt đầu kiểm tra',
  COMPLETE: 'Hoàn thành',
  CANCEL: 'Hủy yêu cầu',
  REQUEUE: 'Trả về hàng chờ',
}

/** Actions the caller may attempt; the backend still enforces every rule. */
export function availableActions(req, user) {
  if (!req || !user) return []
  const role = user.role
  const uid = String(user.id || '')
  const actions = []
  if (role === 'TECHNICIAN' && req.assigned_technician_id === uid) {
    if (req.status === 'NEW') actions.push('accept')
    if (req.status === 'ACCEPTED') actions.push('start')
    if (req.status === 'IN_PROGRESS') actions.push('complete')
  }
  if (role === 'FARM_OWNER' && (req.status === 'NEW' || req.status === 'ACCEPTED')) actions.push('cancel')
  if (role === 'ADMIN' && req.status === 'NEW') actions.push('assign')
  return actions
}

export function formatDateTime(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '--'
  return d.toLocaleString('vi-VN', { hour12: false })
}

export function errorMessage(err, fallback) {
  const s = Number(err?.status ?? 0)
  if (s === 409) return err?.message || 'Trạng thái yêu cầu đã thay đổi. Vui lòng tải lại.'
  if (s === 403) return 'Bạn không có quyền thực hiện thao tác này.'
  if (s === 404) return 'Không tìm thấy yêu cầu hoặc bạn không có quyền xem.'
  if (s === 0 || s >= 502) return 'Dịch vụ quản lý hiện không khả dụng.'
  return err?.message || fallback
}
