import assert from 'node:assert/strict'
import { navigationByRole } from '../src/config/navigation.js'
import { filterNotifications, toPopoverItem } from '../src/features/notifications/notificationAdapter.js'

// 1. Admin sidebar includes "Thông báo" -> /notifications and preserves all 5 existing entries
const adminIds = navigationByRole.ADMIN.map((i) => i.id)
for (const expectedId of ['dashboard', 'users', 'farms', 'devices', 'notifications', 'system']) {
  assert.ok(adminIds.includes(expectedId), `Admin sidebar missing "${expectedId}"`)
}
const adminNotifNav = navigationByRole.ADMIN.find((i) => i.id === 'notifications')
assert.equal(adminNotifNav.path, '/notifications')
assert.equal(adminNotifNav.label, 'Thông báo')
assert.equal(adminNotifNav.icon, 'bell')

// 2. Owner and Technician sidebars keep their Alerts entries without duplicate /notifications
assert.equal(navigationByRole.FARM_OWNER.some((i) => i.path === '/notifications'), false)
assert.equal(navigationByRole.TECHNICIAN.some((i) => i.path === '/notifications'), false)
assert.equal(navigationByRole.FARM_OWNER.some((i) => i.path === '/owner/alerts'), true)
assert.equal(navigationByRole.TECHNICIAN.some((i) => i.path === '/technician/alerts'), true)

// 3. Management, IoT, AI DTO mapping preserves eventId, metadata, and role-safe links
const rawDtos = [
  {
    id: 'n-1',
    event_id: 'evt-1',
    event_type: 'management.farm.approval_requested',
    title: 'Yêu cầu phê duyệt nhà yến',
    message: 'Chủ trại A đăng ký nhà yến mới',
    category: 'warning',
    data: { farmId: 'f1', farmName: 'Nhà yến A', link: '/admin/farms?farmId=f1' },
    created_at: '2026-11-21T06:00:00Z',
    read_at: null,
  },
  {
    id: 'n-2',
    event_id: 'evt-2',
    event_type: 'iot.device.offline',
    title: 'Thiết bị mất kết nối',
    message: 'ESP32-01 mất kết nối',
    category: 'danger',
    data: { farmId: 'f1', farmName: 'Nhà yến A', zoneName: 'Tầng 1', deviceName: 'ESP32-01' },
    created_at: '2026-11-21T06:05:00Z',
    read_at: '2026-11-21T06:06:00Z',
  },
  {
    id: 'n-3',
    event_id: 'evt-3',
    event_type: 'ai.predator.detected',
    title: 'AI phát hiện thiên địch',
    message: 'Phát hiện cú mèo tại Tầng 2',
    category: 'danger',
    data: { farmId: 'f1', farmName: 'Nhà yến A', zoneName: 'Tầng 2', cameraId: 'CAM-01' },
    created_at: '2026-11-21T06:10:00Z',
    read_at: null,
  },
  // Distinct eventId with identical title/message to n-2 -> MUST NOT be merged
  {
    id: 'n-4',
    event_id: 'evt-4',
    event_type: 'iot.device.offline',
    title: 'Thiết bị mất kết nối',
    message: 'ESP32-01 mất kết nối',
    category: 'danger',
    data: { farmId: 'f1', farmName: 'Nhà yến A', zoneName: 'Tầng 1', deviceName: 'ESP32-01' },
    created_at: '2026-11-21T06:15:00Z',
    read_at: null,
  },
]

const mapped = rawDtos.map((d) => toPopoverItem(d, { role: 'ADMIN' }))
assert.equal(mapped.length, 4)
assert.equal(mapped[0].source, 'Quản lý')
assert.equal(mapped[0].link, '/admin/farms?farmId=f1')
assert.equal(mapped[1].source, 'IoT')
assert.equal(mapped[1].device, 'ESP32-01')
assert.equal(mapped[2].source, 'AI')
assert.equal(mapped[2].device, 'CAM-01')
assert.equal(mapped[2].zoneLabel, 'Tầng 2')

// 4. Filter by read state, source, and search query; never merge distinct eventIds
assert.equal(filterNotifications(mapped, { readFilter: 'UNREAD' }).length, 3)
assert.equal(filterNotifications(mapped, { readFilter: 'READ' }).length, 1)
assert.equal(filterNotifications(mapped, { sourceFilter: 'IoT' }).length, 2, 'Two distinct IoT offline events must stay separate')
assert.equal(filterNotifications(mapped, { sourceFilter: 'AI' }).length, 1)
assert.equal(filterNotifications(mapped, { query: 'CAM-01' }).length, 1)
assert.equal(filterNotifications(mapped, { query: 'Tầng 1' }).length, 2)
assert.equal(filterNotifications(mapped, { query: 'không tồn tại' }).length, 0)

console.log('PASS: notification center & admin sidebar regression checks (4/4)')
