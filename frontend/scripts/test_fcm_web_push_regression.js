import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  WEB_PUSH_STATUS,
  WEB_PUSH_STATUS_LABELS,
  deriveInitialWebPushStatus,
  isFirebaseClientConfigured,
  sanitizeNotificationRoute,
} from '../src/features/notifications/fcmConfig.js'
import { ENDPOINTS } from '../src/api/endpoints.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// 1. Endpoint registry includes FCM_TOKENS
assert.equal(ENDPOINTS.NOTIFICATIONS.FCM_TOKENS, '/api/v1/notifications/fcm-tokens')

// 2. Firebase config detection fails closed when incomplete, succeeds when all required fields exist
assert.equal(isFirebaseClientConfigured({}), false)
assert.equal(isFirebaseClientConfigured({ VITE_FIREBASE_API_KEY: 'x', VITE_FIREBASE_PROJECT_ID: 'p' }), false)
assert.equal(
  isFirebaseClientConfigured({
    VITE_FIREBASE_API_KEY: 'AIza-public-client-key',
    VITE_FIREBASE_PROJECT_ID: 'swiftletcare-dev',
    VITE_FIREBASE_MESSAGING_SENDER_ID: '1234567890',
    VITE_FIREBASE_APP_ID: '1:1234567890:web:abcdef',
    VITE_FIREBASE_VAPID_KEY: 'BPublicVapidKeyExample',
  }),
  true,
)

// 3. All 6 required Vietnamese status labels exist
assert.equal(WEB_PUSH_STATUS_LABELS[WEB_PUSH_STATUS.DISABLED], 'Chưa bật')
assert.equal(WEB_PUSH_STATUS_LABELS[WEB_PUSH_STATUS.REGISTERING], 'Đang đăng ký')
assert.equal(WEB_PUSH_STATUS_LABELS[WEB_PUSH_STATUS.ENABLED], 'Đã bật')
assert.equal(WEB_PUSH_STATUS_LABELS[WEB_PUSH_STATUS.BLOCKED], 'Bị trình duyệt chặn')
assert.equal(WEB_PUSH_STATUS_LABELS[WEB_PUSH_STATUS.UNCONFIGURED], 'Chưa cấu hình Firebase')
assert.equal(WEB_PUSH_STATUS_LABELS[WEB_PUSH_STATUS.UNAVAILABLE], 'Không khả dụng')

// 4. Initial status derivation respects unconfigured / unsupported / denied / cross-user isolation
assert.equal(
  deriveInitialWebPushStatus({ configured: false, supported: true, permission: 'default', registeredUserId: null, currentUserId: 'u1' }),
  WEB_PUSH_STATUS.UNCONFIGURED,
)
assert.equal(
  deriveInitialWebPushStatus({ configured: true, supported: false, permission: 'default', registeredUserId: null, currentUserId: 'u1' }),
  WEB_PUSH_STATUS.UNAVAILABLE,
)
assert.equal(
  deriveInitialWebPushStatus({ configured: true, supported: true, permission: 'denied', registeredUserId: 'u1', currentUserId: 'u1' }),
  WEB_PUSH_STATUS.BLOCKED,
)
assert.equal(
  deriveInitialWebPushStatus({ configured: true, supported: true, permission: 'granted', registeredUserId: 'u1', currentUserId: 'u2' }),
  WEB_PUSH_STATUS.DISABLED,
  'User B must NOT inherit User A enabled push state on shared Chrome profile',
)
assert.equal(
  deriveInitialWebPushStatus({ configured: true, supported: true, permission: 'granted', registeredUserId: 'u1', currentUserId: 'u1' }),
  WEB_PUSH_STATUS.ENABLED,
)

// 5. Route sanitization blocks external domains, protocol-relative URLs, and header injection
assert.equal(sanitizeNotificationRoute('/owner/farms?requestId=123', 'n1'), '/owner/farms?requestId=123')
assert.equal(sanitizeNotificationRoute('https://evil.example/steal', 'n1'), '/notifications?id=n1')
assert.equal(sanitizeNotificationRoute('//evil.example/steal', 'n1'), '/notifications?id=n1')
assert.equal(sanitizeNotificationRoute('javascript:alert(1)', 'n1'), '/notifications?id=n1')
assert.equal(sanitizeNotificationRoute('/ok\r\nSet-Cookie: a=1', 'n1'), '/notifications?id=n1')

// 6. Service Worker file exists in public/ and contains push + notificationclick handlers
const swPath = path.resolve(__dirname, '../public/firebase-messaging-sw.js')
assert.ok(fs.existsSync(swPath), 'public/firebase-messaging-sw.js must exist')
const swText = fs.readFileSync(swPath, 'utf-8')
assert.ok(swText.includes("addEventListener('push'"), 'Service worker must handle push event')
assert.ok(swText.includes("addEventListener('notificationclick'"), 'Service worker must handle notificationclick event')

console.log('PASS: FCM web push config, status, route sanitization & SW regression checks (6/6)')
