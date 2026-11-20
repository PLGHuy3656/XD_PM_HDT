import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../../../api/client.js'
import { ENDPOINTS } from '../../../api/endpoints.js'
import { USE_MOCK } from '../../../api/config.js'

const POLL_MS = 5000

/**
 * INT02-F03: recent AIEvent records of ONE farm, via the farm-scoped Gateway route
 * (server-side farm authorisation; the browser never receives other farms' events).
 * state: IDLE | LOADING | OK | EMPTY | FORBIDDEN | UNAVAILABLE | ERROR
 */
export function useFarmAiEvents(farmId, limit = 20) {
  const [entry, setEntry] = useState({ farmId: null, state: 'IDLE', events: [] })

  const load = useCallback(async (id, signal) => {
    try {
      const data = await apiClient.get(ENDPOINTS.AI.FARM_EVENTS(id), { params: { limit }, signal, retries: 0 })
      if (signal?.aborted) return
      const events = Array.isArray(data) ? data : []
      setEntry({ farmId: id, state: events.length ? 'OK' : 'EMPTY', events })
    } catch (err) {
      if (signal?.aborted || err?.code === 'ABORTED') return
      const s = Number(err?.status ?? err?.statusCode ?? 0)
      setEntry({
        farmId: id,
        state: s === 401 || s === 403 ? 'FORBIDDEN' : s === 0 || s === 408 || s >= 502 || err?.code === 'TIMEOUT' ? 'UNAVAILABLE' : 'ERROR',
        events: [],
      })
    }
  }, [limit])

  useEffect(() => {
    if (!farmId || USE_MOCK) return undefined
    const controller = new AbortController()
    const first = setTimeout(() => load(farmId, controller.signal), 0)
    const t = setInterval(() => load(farmId, controller.signal), POLL_MS)
    return () => {
      clearTimeout(first)
      clearInterval(t)
      controller.abort()
    }
  }, [farmId, load])

  if (!farmId || USE_MOCK) return { state: 'IDLE', events: [] }
  // State is tagged with its farm, so a farm switch never shows the previous farm's events
  return entry.farmId === farmId ? { state: entry.state, events: entry.events } : { state: 'LOADING', events: [] }
}

export default useFarmAiEvents
