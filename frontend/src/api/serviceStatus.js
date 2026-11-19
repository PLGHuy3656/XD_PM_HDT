import { useEffect, useRef } from 'react'

export const SERVICE_STATE = {
  LOADING: 'LOADING',
  AVAILABLE: 'AVAILABLE',
  EMPTY: 'EMPTY',
  UNAVAILABLE: 'UNAVAILABLE',
  ERROR: 'ERROR',
  UNKNOWN: 'UNKNOWN',
}

/**
 * Classifies an API error into UNAVAILABLE (502/503/504/network/timeout) vs ERROR.
 * Never treats ABORTED requests as service failures.
 * @param {any} err
 * @returns {'UNAVAILABLE' | 'ERROR' | null}
 */
export function classifyServiceError(err) {
  if (!err) return null
  if (err?.code === 'ABORTED' || err?.name === 'AbortError') return null

  const status = Number(err?.status ?? err?.statusCode ?? 0)
  if (status === 502 || status === 503 || status === 504 || status === 0) {
    return SERVICE_STATE.UNAVAILABLE
  }
  const code = String(err?.code || '').toUpperCase()
  if (code === 'NETWORK_ERROR' || code === 'TIMEOUT' || code === 'SERVICE_UNAVAILABLE') {
    return SERVICE_STATE.UNAVAILABLE
  }
  const msg = String(err?.message || '')
  if (/upstream|unreachable|service unavailable|503|failed to fetch|network/i.test(msg)) {
    return SERVICE_STATE.UNAVAILABLE
  }
  return SERVICE_STATE.ERROR
}

/**
 * Resolves a canonical service state from hook flags.
 */
export function resolveServiceState({ loading, error, hasData, isEmpty = false }) {
  if (loading && !hasData && !error) return SERVICE_STATE.LOADING
  if (error) {
    return classifyServiceError(error) || SERVICE_STATE.ERROR
  }
  if (hasData) return SERVICE_STATE.AVAILABLE
  if (isEmpty) return SERVICE_STATE.EMPTY
  return SERVICE_STATE.UNKNOWN
}

/**
 * Re-triggers a fetch callback when the browser tab becomes visible again or
 * network connectivity returns, with a minimum cooldown to prevent 503 spam.
 */
export function useRevalidateOnFocus(callback, { enabled = true, minIntervalMs = 15000 } = {}) {
  const lastRunRef = useRef(0)

  useEffect(() => {
    if (!enabled || typeof window === 'undefined' || typeof document === 'undefined') {
      return undefined
    }

    const trigger = () => {
      if (document.visibilityState && document.visibilityState !== 'visible') return
      const now = Date.now()
      if (now - lastRunRef.current < minIntervalMs) return
      lastRunRef.current = now
      callback?.()
    }

    const onVisibilityChange = () => {
      if (document.visibilityState === 'visible') trigger()
    }

    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('online', trigger)

    return () => {
      document.removeEventListener('visibilitychange', onVisibilityChange)
      window.removeEventListener('online', trigger)
    }
  }, [callback, enabled, minIntervalMs])
}
