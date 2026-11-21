/**
 * INT03-R2: Pure Firebase Web Push configuration, status labels, and route sanitization helpers.
 * Kept free of browser globals so Node unit tests can import and verify all rules directly.
 */

export const WEB_PUSH_STATUS = {
  DISABLED: 'DISABLED',
  REGISTERING: 'REGISTERING',
  ENABLED: 'ENABLED',
  BLOCKED: 'BLOCKED',
  UNCONFIGURED: 'UNCONFIGURED',
  UNAVAILABLE: 'UNAVAILABLE',
}

export const WEB_PUSH_STATUS_LABELS = {
  [WEB_PUSH_STATUS.DISABLED]: 'Chưa bật',
  [WEB_PUSH_STATUS.REGISTERING]: 'Đang đăng ký',
  [WEB_PUSH_STATUS.ENABLED]: 'Đã bật',
  [WEB_PUSH_STATUS.BLOCKED]: 'Bị trình duyệt chặn',
  [WEB_PUSH_STATUS.UNCONFIGURED]: 'Chưa cấu hình Firebase',
  [WEB_PUSH_STATUS.UNAVAILABLE]: 'Không khả dụng',
}

export function readFirebaseClientConfig(env = {}) {
  const apiKey = String(env.VITE_FIREBASE_API_KEY || '').trim()
  const authDomain = String(env.VITE_FIREBASE_AUTH_DOMAIN || '').trim()
  const projectId = String(env.VITE_FIREBASE_PROJECT_ID || '').trim()
  const messagingSenderId = String(env.VITE_FIREBASE_MESSAGING_SENDER_ID || '').trim()
  const appId = String(env.VITE_FIREBASE_APP_ID || '').trim()
  const vapidKey = String(env.VITE_FIREBASE_VAPID_KEY || '').trim()

  return {
    apiKey,
    authDomain,
    projectId,
    messagingSenderId,
    appId,
    vapidKey,
  }
}

export function isFirebaseClientConfigured(env = {}) {
  const cfg = readFirebaseClientConfig(env)
  return Boolean(
    cfg.apiKey &&
      cfg.projectId &&
      cfg.messagingSenderId &&
      cfg.appId &&
      cfg.vapidKey,
  )
}

/**
 * Validate a notification click route strictly as a same-origin relative path.
 * Never allows absolute URLs, protocol-relative URLs (//), or external domains.
 */
export function sanitizeNotificationRoute(rawLink, notificationId = '') {
  const fallback = notificationId
    ? `/notifications?id=${encodeURIComponent(String(notificationId))}`
    : '/notifications'
  if (typeof rawLink !== 'string') return fallback
  const trimmed = rawLink.trim()
  if (
    !trimmed.startsWith('/') ||
    trimmed.startsWith('//') ||
    trimmed.includes('://') ||
    /[\r\n]/.test(trimmed)
  ) {
    return fallback
  }
  return trimmed
}

/**
 * Determine initial Web Push status without prompting Notification.requestPermission().
 */
export function deriveInitialWebPushStatus({
  configured,
  supported,
  permission,
  registeredUserId,
  currentUserId,
}) {
  if (!configured) return WEB_PUSH_STATUS.UNCONFIGURED
  if (!supported) return WEB_PUSH_STATUS.UNAVAILABLE
  if (permission === 'denied') return WEB_PUSH_STATUS.BLOCKED
  if (
    permission === 'granted' &&
    registeredUserId &&
    currentUserId &&
    String(registeredUserId) === String(currentUserId)
  ) {
    return WEB_PUSH_STATUS.ENABLED
  }
  return WEB_PUSH_STATUS.DISABLED
}
