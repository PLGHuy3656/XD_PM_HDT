import { useCallback, useEffect, useState } from 'react'
import { telemetryApi } from '../../../api/modules/telemetryApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { normalizeTelemetry } from '../adapters/telemetryAdapter.js'

export function useTelemetry(farmId) {
  const [telemetry, setTelemetry] = useState(() => normalizeTelemetry(null, USE_MOCK))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [hasData, setHasData] = useState(false)

  const fetchTelemetry = useCallback(async (signal) => {
    if (!farmId) {
      setLoading(false)
      setTelemetry(normalizeTelemetry(null, USE_MOCK))
      setHasData(false)
      return
    }

    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK) {
        setTelemetry(normalizeTelemetry(null, true))
        setHasData(true)
        return
      }

      const response = await telemetryApi.getFarmLatest(farmId, { signal })
      setTelemetry(normalizeTelemetry(response, false))
      setHasData(true)
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        if (err?.status === 404 || err?.statusCode === 404) {
          // Farm has no telemetry records yet - gracefully treat as empty state
          setTelemetry(normalizeTelemetry(null, false))
          setHasData(false)
          setError(null)
        } else {
          setError(err?.message || 'Không thể tải số liệu cảm biến.')
        }
      }
    } finally {
      setLoading(false)
    }
  }, [farmId])

  useEffect(() => {
    const controller = new AbortController()
    fetchTelemetry(controller.signal)

    // Auto-poll every 3 seconds for live ESP32 telemetry updates
    const pollInterval = setInterval(() => {
      fetchTelemetry()
    }, 3000)

    return () => {
      controller.abort()
      clearInterval(pollInterval)
    }
  }, [fetchTelemetry])

  return {
    telemetry,
    hasData,
    loading,
    error,
    refetch: () => fetchTelemetry(),
  }
}

export default useTelemetry
