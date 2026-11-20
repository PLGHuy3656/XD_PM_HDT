import { useCallback, useMemo } from 'react'
import { USE_MOCK } from '../../../api/config.js'
import { SERVICE_STATE } from '../../../api/serviceStatus.js'
import { normalizeTelemetry } from '../adapters/telemetryAdapter.js'
import { useFarmTelemetry } from '../farmTelemetryPoller.js'

const STATUS_TO_SERVICE_STATE = {
  idle: SERVICE_STATE.UNKNOWN,
  loading: SERVICE_STATE.LOADING,
  ok: SERVICE_STATE.AVAILABLE,
  stale: SERVICE_STATE.AVAILABLE,
  empty: SERVICE_STATE.EMPTY,
  forbidden: SERVICE_STATE.ERROR,
  unavailable: SERVICE_STATE.UNAVAILABLE,
  error: SERVICE_STATE.ERROR,
}

/**
 * Farm-scoped latest telemetry.
 *
 * INT01-R1: real mode subscribes to the shared farm poller (one loop per farm for the whole app),
 * exposes `isStale`, `pollStatus` and provenance-carrying telemetry. Return shape is unchanged.
 */
export function useTelemetry(farmId) {
  const live = useFarmTelemetry(USE_MOCK ? null : farmId)

  const mockTelemetry = useMemo(() => (USE_MOCK ? normalizeTelemetry(null, true) : null), [])
  const refetch = useCallback(() => {
    if (!USE_MOCK) live.refresh()
  }, [live])

  if (USE_MOCK) {
    return {
      telemetry: farmId ? mockTelemetry : normalizeTelemetry(null, true),
      hasData: Boolean(farmId),
      loading: false,
      error: null,
      serviceState: SERVICE_STATE.AVAILABLE,
      isStale: false,
      pollStatus: 'ok',
      refetch,
    }
  }

  if (!farmId) {
    return {
      telemetry: null,
      hasData: false,
      loading: false,
      error: null,
      serviceState: SERVICE_STATE.UNKNOWN,
      isStale: false,
      pollStatus: 'idle',
      refetch,
    }
  }

  const status = live.status
  return {
    telemetry: live.telemetry,
    hasData: Boolean(live.telemetry) && (status === 'ok' || status === 'stale'),
    loading: status === 'loading',
    error: status === 'unavailable' || status === 'error' || status === 'forbidden' ? live.error : null,
    serviceState: STATUS_TO_SERVICE_STATE[status] || SERVICE_STATE.UNKNOWN,
    isStale: status === 'stale',
    pollStatus: status,
    refetch,
  }
}

export default useTelemetry
