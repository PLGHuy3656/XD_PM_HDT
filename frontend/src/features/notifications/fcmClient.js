/**
 * INT03-R2: Firebase Cloud Messaging Web Push client lifecycle.
 *
 * Security & UX invariants:
 * - Never auto-prompts Notification.requestPermission() on page load or login.
 * - App works normally when Firebase client env vars are not configured.
 * - Never embeds Firebase Admin / private credentials.
 * - Binds token registration to the currently authenticated user only (server derives user from JWT).
 * - Unregisters and deletes local token on logout or user switch on a shared Chrome profile.
 * - Foreground messages trigger a custom event so Notification Bell/Center refresh from the real API
 *   without creating duplicate DB rows or duplicate OS notifications.
 */

import { getApps, initializeApp } from 'firebase/app'
import { deleteToken, getMessaging, getToken, isSupported, onMessage } from 'firebase/messaging'

import { alertsApi } from '../../api/modules/alertsApi.js'
import {
  WEB_PUSH_STATUS,
  isFirebaseClientConfigured,
  readFirebaseClientConfig,
  sanitizeNotificationRoute,
} from './fcmConfig.js'

const STORAGE_KEY_FCM = 'swiftletcare_fcm_registration'
export const NOTIFICATIONS_SYNC_EVENT = 'swiftletcare:notifications-sync'
export const NOTIFICATION_CLICK_EVENT = 'swiftletcare:notification-click'

let cachedMessaging = null
let foregroundListenersBound = false

export function readStoredFcmRegistration() {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY_FCM)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed.token === 'string' && parsed.token && parsed.userId) {
      return { token: parsed.token, userId: String(parsed.userId) }
    }
    return null
  } catch {
    return null
  }
}

function writeStoredFcmRegistration(userId, token) {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(
      STORAGE_KEY_FCM,
      JSON.stringify({ userId: String(userId), token, updatedAt: new Date().toISOString() }),
    )
  } catch {
    // Ignore storage quota errors
  }
}

export function clearStoredFcmRegistration() {
  if (typeof window === 'undefined') return
  try {
    localStorage.removeItem(STORAGE_KEY_FCM)
  } catch {
    // Ignore
  }
}

export function getFirebaseRuntimeConfig() {
  return readFirebaseClientConfig(import.meta.env)
}

export function isWebPushConfigured() {
  return isFirebaseClientConfigured(import.meta.env)
}

export async function isBrowserPushSupported() {
  if (typeof window === 'undefined') return false
  if (!('Notification' in window) || !('serviceWorker' in navigator) || !('PushManager' in window)) {
    return false
  }
  try {
    return await isSupported()
  } catch {
    return false
  }
}

async function getFirebaseMessagingInstance() {
  if (cachedMessaging) return cachedMessaging
  const cfg = getFirebaseRuntimeConfig()
  if (!isFirebaseClientConfigured(import.meta.env)) return null

  const app = getApps().length
    ? getApps()[0]
    : initializeApp({
        apiKey: cfg.apiKey,
        authDomain: cfg.authDomain || `${cfg.projectId}.firebaseapp.com`,
        projectId: cfg.projectId,
        messagingSenderId: cfg.messagingSenderId,
        appId: cfg.appId,
      })
  cachedMessaging = getMessaging(app)
  return cachedMessaging
}

async function registerPushServiceWorker() {
  const existing = await navigator.serviceWorker.getRegistration('/firebase-messaging-sw.js')
  if (existing) {
    existing.update().catch(() => {})
    return existing
  }
  return navigator.serviceWorker.register('/firebase-messaging-sw.js', { scope: '/' })
}

export function ensureForegroundPushListeners() {
  if (typeof window === 'undefined' || foregroundListenersBound) return
  foregroundListenersBound = true

  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
      const msg = event.data
      if (!msg || typeof msg !== 'object') return
      if (msg.type === 'FCM_FOREGROUND_SYNC') {
        window.dispatchEvent(new CustomEvent(NOTIFICATIONS_SYNC_EVENT, { detail: msg }))
      } else if (msg.type === 'FCM_NOTIFICATION_CLICK') {
        const safeRoute = sanitizeNotificationRoute(msg.link, msg.notificationId)
        window.dispatchEvent(new CustomEvent(NOTIFICATION_CLICK_EVENT, { detail: { link: safeRoute } }))
      }
    })
  }
}

async function bindFirebaseOnMessage() {
  const messaging = await getFirebaseMessagingInstance()
  if (!messaging) return
  onMessage(messaging, (payload) => {
    // Foreground: refresh Notification Bell/Center from authoritative API; never create DB rows or duplicate OS alerts
    window.dispatchEvent(
      new CustomEvent(NOTIFICATIONS_SYNC_EVENT, {
        detail: {
          notificationId: payload?.data?.notification_id || '',
          eventId: payload?.data?.event_id || '',
          eventType: payload?.data?.event_type || '',
        },
      }),
    )
  })
}

/**
 * Explicitly enable Web Push for the currently authenticated user (triggered by user click).
 */
export async function enableBrowserPush(userId) {
  if (!userId) {
    return { ok: false, status: WEB_PUSH_STATUS.UNAVAILABLE, message: 'Bạn cần đăng nhập để bật thông báo.' }
  }
  if (!isWebPushConfigured()) {
    return {
      ok: false,
      status: WEB_PUSH_STATUS.UNCONFIGURED,
      message: 'Chưa cấu hình Firebase Web Push (VITE_FIREBASE_*).',
    }
  }
  const supported = await isBrowserPushSupported()
  if (!supported) {
    return {
      ok: false,
      status: WEB_PUSH_STATUS.UNAVAILABLE,
      message: 'Trình duyệt hiện tại không hỗ trợ Web Push / Service Worker.',
    }
  }

  let permission = Notification.permission
  if (permission === 'default') {
    permission = await Notification.requestPermission()
  }
  if (permission === 'denied') {
    clearStoredFcmRegistration()
    return {
      ok: false,
      status: WEB_PUSH_STATUS.BLOCKED,
      message: 'Trình duyệt đang chặn quyền thông báo. Hãy bật lại trong cài đặt trang web của Chrome.',
    }
  }
  if (permission !== 'granted') {
    return {
      ok: false,
      status: WEB_PUSH_STATUS.DISABLED,
      message: 'Bạn chưa cấp quyền hiển thị thông báo cho trình duyệt.',
    }
  }

  try {
    ensureForegroundPushListeners()
    const swReg = await registerPushServiceWorker()
    const messaging = await getFirebaseMessagingInstance()
    const cfg = getFirebaseRuntimeConfig()
    const fcmToken = await getToken(messaging, {
      vapidKey: cfg.vapidKey,
      serviceWorkerRegistration: swReg,
    })
    if (!fcmToken) {
      return {
        ok: false,
        status: WEB_PUSH_STATUS.UNAVAILABLE,
        message: 'Không lấy được FCM registration token từ Firebase.',
      }
    }

    const stored = readStoredFcmRegistration()
    const alreadySynced = stored && stored.userId === String(userId) && stored.token === fcmToken
    if (!alreadySynced) {
      await alertsApi.registerFcmToken(fcmToken, 'web')
      writeStoredFcmRegistration(userId, fcmToken)
    }

    await bindFirebaseOnMessage()
    return { ok: true, status: WEB_PUSH_STATUS.ENABLED, message: null }
  } catch (err) {
    return {
      ok: false,
      status: WEB_PUSH_STATUS.UNAVAILABLE,
      message: err?.message || 'Không thể đăng ký thông báo trình duyệt lúc này.',
    }
  }
}

/**
 * Re-sync existing opted-in registration silently (NO permission prompt!) if token rotated.
 */
export async function syncExistingBrowserPush(userId) {
  if (!userId || !isWebPushConfigured()) return
  const stored = readStoredFcmRegistration()
  if (!stored || stored.userId !== String(userId)) return
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return

  const supported = await isBrowserPushSupported()
  if (!supported) return

  try {
    ensureForegroundPushListeners()
    const swReg = await registerPushServiceWorker()
    const messaging = await getFirebaseMessagingInstance()
    const cfg = getFirebaseRuntimeConfig()
    const currentToken = await getToken(messaging, {
      vapidKey: cfg.vapidKey,
      serviceWorkerRegistration: swReg,
    })
    if (currentToken && currentToken !== stored.token) {
      await alertsApi.registerFcmToken(currentToken, 'web')
      writeStoredFcmRegistration(userId, currentToken)
    }
    await bindFirebaseOnMessage()
  } catch {
    // Non-blocking best-effort sync; in-app notifications stay unaffected
  }
}

/**
 * Explicitly disable Web Push for the current user and remove token from backend + browser.
 */
export async function disableBrowserPush() {
  const stored = readStoredFcmRegistration()
  try {
    if (stored?.token) {
      await alertsApi.unregisterFcmToken(stored.token)
    }
  } catch {
    // Best-effort backend deletion; still clear local state
  }

  try {
    const messaging = await getFirebaseMessagingInstance()
    if (messaging) {
      await deleteToken(messaging)
    }
  } catch {
    // Ignore if Firebase messaging wasn't initialized
  }

  clearStoredFcmRegistration()
  return { ok: true, status: WEB_PUSH_STATUS.DISABLED }
}

/**
 * Called during logout BEFORE JWT is cleared so the previous user stops receiving push
 * on this Chrome profile immediately.
 */
export async function unregisterBrowserPushOnLogout() {
  await disableBrowserPush()
}

/**
 * Called on login of a new user on the same Chrome profile: if a leftover registration belongs
 * to another user, clear it immediately so cross-user push cannot occur.
 */
export async function clearForeignBrowserPushOnLogin(newUserId) {
  const stored = readStoredFcmRegistration()
  if (!stored || !newUserId) return
  if (stored.userId !== String(newUserId)) {
    try {
      const messaging = await getFirebaseMessagingInstance()
      if (messaging) await deleteToken(messaging)
    } catch {
      // Best-effort local token rotation
    }
    clearStoredFcmRegistration()
  }
}
