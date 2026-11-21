/**
 * SwiftletCare INT03-R2 — FCM Web Push Service Worker
 *
 * Design notes:
 * - Backend sends data-only FCM payloads ({ title, body, notification_id, event_id, event_type, link })
 *   so this Service Worker is the SINGLE place calling showNotification() — preventing duplicate OS
 *   notifications and avoiding HTTPS-only fcm_options.link limitations on http://localhost:33000.
 * - Foreground (any focused & visible SwiftletCare tab): skips OS notification and sends a
 *   FCM_FOREGROUND_SYNC postMessage so the active tab refreshes from the real Notification API.
 * - Background: shows one OS notification deduplicated by `tag = event_id || notification_id`.
 * - Click: validates link strictly as a same-origin relative path (never opens external domains),
 *   focuses an existing SwiftletCare tab or opens a new one at `${self.location.origin}${safeLink}`.
 */

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

function sanitizeRelativeLink(rawLink, notificationId) {
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

function parsePushPayload(event) {
  if (!event.data) return null
  try {
    const json = event.data.json()
    const data = json?.data || json?.notification || json || {}
    const title = data.title || json?.notification?.title || 'SwiftletCare'
    const body = data.body || data.message || json?.notification?.body || ''
    const notificationId = data.notification_id || data.notificationId || ''
    const eventId = data.event_id || data.eventId || ''
    const eventType = data.event_type || data.eventType || ''
    const link = sanitizeRelativeLink(data.link, notificationId)
    return { title, body, notificationId, eventId, eventType, link }
  } catch {
    const text = event.data.text()
    return {
      title: 'SwiftletCare',
      body: text || 'Bạn có thông báo mới.',
      notificationId: '',
      eventId: '',
      eventType: '',
      link: '/notifications',
    }
  }
}

self.addEventListener('push', (event) => {
  const payload = parsePushPayload(event)
  if (!payload) return

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      const hasFocusedForegroundTab = windowClients.some(
        (client) => client.visibilityState === 'visible' && client.focused,
      )

      // Notify all open SwiftletCare tabs to refresh from the authoritative API
      for (const client of windowClients) {
        client.postMessage({
          type: 'FCM_FOREGROUND_SYNC',
          notificationId: payload.notificationId,
          eventId: payload.eventId,
          eventType: payload.eventType,
        })
      }

      if (hasFocusedForegroundTab) {
        // Active foreground tab will update Bell/Notification Center without duplicate OS alert
        return undefined
      }

      const tag = payload.eventId || payload.notificationId || `swc-${Date.now()}`
      return self.registration.showNotification(payload.title, {
        body: payload.body,
        icon: '/Logo.png',
        badge: '/Logo.png',
        tag,
        renotify: false,
        data: {
          notificationId: payload.notificationId,
          eventId: payload.eventId,
          eventType: payload.eventType,
          link: payload.link,
        },
      })
    }),
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const rawData = event.notification?.data || {}
  const safePath = sanitizeRelativeLink(rawData.link, rawData.notificationId)
  const targetUrl = `${self.location.origin}${safePath}`

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (windowClients) => {
      for (const client of windowClients) {
        if (client.url.startsWith(self.location.origin)) {
          try {
            await client.focus()
            client.postMessage({
              type: 'FCM_NOTIFICATION_CLICK',
              link: safePath,
              notificationId: rawData.notificationId || '',
            })
            return
          } catch {
            // Fall through to openWindow if focus fails
          }
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(targetUrl)
      }
    }),
  )
})
