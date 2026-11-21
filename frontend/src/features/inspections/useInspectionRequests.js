import { useCallback, useEffect, useState } from 'react'
import { inspectionsApi } from '../../api/modules/inspectionsApi.js'
import { USE_MOCK } from '../../api/config.js'
import { errorMessage } from './inspectionModel.js'

/**
 * INT03-R1: Inspection requests visible to the caller (scope enforced by Management).
 * state: IDLE | LOADING | OK | EMPTY | UNAVAILABLE | ERROR — no mock fallback in real mode.
 */
export function useInspectionRequests({ farmId = null, status = null, unassigned = false, enabled = true } = {}) {
  const [entry, setEntry] = useState({ key: null, state: 'IDLE', items: [], error: null })
  const key = `${farmId || ''}|${status || ''}|${unassigned ? 1 : 0}`

  const load = useCallback(async (signal) => {
    const params = {}
    if (farmId) params.farm_id = farmId
    if (status) params.status = status
    if (unassigned) params.unassigned = 'true'
    try {
      const data = await inspectionsApi.list(params, { signal, retries: 0 })
      if (signal?.aborted) return
      const items = Array.isArray(data) ? data : data?.items || []
      setEntry({ key, state: items.length ? 'OK' : 'EMPTY', items, error: null })
    } catch (err) {
      if (signal?.aborted || err?.code === 'ABORTED') return
      const s = Number(err?.status ?? 0)
      setEntry((prev) => ({
        key,
        state: s === 0 || s >= 502 || err?.code === 'TIMEOUT' ? 'UNAVAILABLE' : 'ERROR',
        items: prev.key === key ? prev.items : [],
        error: errorMessage(err, 'Không tải được danh sách yêu cầu kiểm tra.'),
      }))
    }
  }, [farmId, status, unassigned, key])

  useEffect(() => {
    if (USE_MOCK || !enabled) return undefined
    const controller = new AbortController()
    const first = setTimeout(() => load(controller.signal), 0)
    const t = setInterval(() => load(controller.signal), 20000)
    return () => {
      clearTimeout(first)
      clearInterval(t)
      controller.abort()
    }
  }, [load, enabled])

  const current = entry.key === key ? entry : { state: enabled ? 'LOADING' : 'IDLE', items: [], error: null }
  return { ...current, refresh: () => load() }
}

export default useInspectionRequests
