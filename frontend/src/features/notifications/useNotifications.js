import { useCallback, useEffect, useState } from 'react'
import { alertsApi } from '../../api/modules/alertsApi.js'
import { USE_MOCK } from '../../api/config.js'
import { NOTIFICATIONS_SYNC_EVENT } from './fcmClient.js'

const POLL_MS = 15000

/**
 * INT03: the caller's own notifications from the Notification Service (via Gateway).
 * Server-side scoping: the service derives the user from the bearer token; recipients were
 * resolved from Management (farm owner + assigned technicians) when the event was ingested.
 * state: IDLE | LOADING | OK | EMPTY | UNAVAILABLE | ERROR
 */
export function useNotifications(userId, { limit = 50 } = {}) {
  const [entry, setEntry] = useState({ userId: null, state: 'IDLE', items: [], error: null })

  const load = useCallback(async (uid, signal) => {
    try {
      const data = await alertsApi.getNotifications({ params: { userId: uid, limit }, signal, retries: 0 })
      if (signal?.aborted) return
      const items = Array.isArray(data) ? data : data?.items || []
      setEntry({ userId: uid, state: items.length ? 'OK' : 'EMPTY', items, error: null })
    } catch (err) {
      if (signal?.aborted || err?.code === 'ABORTED') return
      const s = Number(err?.status ?? 0)
      setEntry((prev) => ({
        userId: uid,
        state: s === 0 || s === 408 || s >= 502 || err?.code === 'TIMEOUT' ? 'UNAVAILABLE' : 'ERROR',
        items: prev.userId === uid ? prev.items : [],
        error: err?.message || 'Không tải được thông báo.',
      }))
    }
  }, [limit])

  useEffect(() => {
    if (USE_MOCK || !userId) return undefined
    const controller = new AbortController()
    const first = setTimeout(() => load(userId, controller.signal), 0)
    const t = setInterval(() => load(userId, controller.signal), POLL_MS)
    const onPushSync = () => load(userId, controller.signal)
    window.addEventListener(NOTIFICATIONS_SYNC_EVENT, onPushSync)
    return () => {
      clearTimeout(first)
      clearInterval(t)
      window.removeEventListener(NOTIFICATIONS_SYNC_EVENT, onPushSync)
      controller.abort()
    }
  }, [userId, load])

  const markRead = useCallback(async (id) => {
    try {
      await alertsApi.markNotificationRead(id)
      const now = new Date().toISOString()
      setEntry((prev) => ({ ...prev, items: prev.items.map((n) => (n.id === id ? { ...n, read_at: n.read_at || now } : n)) }))
      return { success: true }
    } catch (err) {
      return { success: false, message: err?.message || 'Không đánh dấu được đã đọc.' }
    }
  }, [])

  const markAllRead = useCallback(async () => {
    try {
      await alertsApi.markAllNotificationsRead()
      const now = new Date().toISOString()
      setEntry((prev) => ({ ...prev, items: prev.items.map((n) => ({ ...n, read_at: n.read_at || now })) }))
      return { success: true }
    } catch (err) {
      return { success: false, message: err?.message || 'Không đánh dấu được đã đọc.' }
    }
  }, [])

  const refresh = useCallback(() => {
    if (userId && !USE_MOCK) load(userId)
  }, [userId, load])

  const current = entry.userId === userId ? entry : { state: userId ? 'LOADING' : 'IDLE', items: [], error: null }
  return { ...current, markRead, markAllRead, refresh }
}

export default useNotifications
