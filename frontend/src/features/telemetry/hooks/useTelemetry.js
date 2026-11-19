import { useCallback, useEffect, useState } from 'react'
import { telemetryApi } from '../../../api/modules/telemetryApi.js'
import { USE_MOCK } from '../../../api/config.js'
import {
  SERVICE_STATE,
  classifyServiceError,
  useRevalidateOnFocus,
} from '../../../api/serviceStatus.js'
import { normalizeTelemetry } from '../adapters/telemetryAdapter.js'

export function useTelemetry(farmId) {
  const [telemetry, setTelemetry] = useState(() => normalizeTelemetry(null, USE_MOCK))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hasData, setHasData] = useState(false)
  const [serviceState, setServiceState] = useState(
    USE_MOCK ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.LOADING,
  )

  const fetchTelemetry = useCallback(async (signal) => {
    if (!farmId) {
      setLoading(false)
      setTelemetry(normalizeTelemetry(null, USE_MOCK))
      setHasData(false)
      setError(null)
      setServiceState(USE_MOCK ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.UNKNOWN)
      return
    }

    try {
      setLoading(true)
      setError(null)
      if (!USE_MOCK) {
        setTelemetry(null)
        setHasData(false)
        setServiceState(SERVICE_STATE.LOADING)
      }

      if (USE_MOCK) {
        setTelemetry(normalizeTelemetry(null, true))
        setHasData(true)
        setServiceState(SERVICE_STATE.AVAILABLE)
        return
      }

      const response = await telemetryApi.getFarmLatest(farmId, { signal })
      const normalized = normalizeTelemetry(response, false)
      const hasAnyMetric =
        normalized &&
        (normalized.temperature != null ||
          normalized.humidity != null ||
          normalized.co2 != null ||
          normalized.light != null)
      setTelemetry(normalized)
      setHasData(Boolean(hasAnyMetric))
      setError(null)
      setServiceState(hasAnyMetric ? SERVICE_STATE.AVAILABLE : SERVICE_STATE.EMPTY)
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        if (err?.status === 404 || err?.statusCode === 404) {
          setTelemetry(normalizeTelemetry(null, false))
          setHasData(false)
          setError(null)
          setServiceState(SERVICE_STATE.EMPTY)
        } else {
          const classified = classifyServiceError(err) || SERVICE_STATE.ERROR
          setServiceState(classified)
          setError(err?.message || 'Không thể tải số liệu cảm biến.')
        }
      }
    } finally {
      setLoading(false)
    }
  }, [farmId])

  useEffect(() => {
    const controller = new AbortController()
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        fetchTelemetry(controller.signal)
      }
    })

    return () => {
      controller.abort()
    }
  }, [fetchTelemetry])

  useRevalidateOnFocus(
    useCallback(() => {
      fetchTelemetry()
    }, [fetchTelemetry]),
    { enabled: !USE_MOCK && Boolean(farmId) },
  )

  return {
    telemetry,
    hasData,
    loading,
    error,
    serviceState,
    refetch: () => fetchTelemetry(),
  }
}

export default useTelemetry
