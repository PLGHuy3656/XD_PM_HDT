import { useCallback, useEffect, useState } from 'react'
import { analyticsApi } from '../../../api/modules/analyticsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { SERVICE_STATE, useRevalidateOnFocus } from '../../../api/serviceStatus.js'
import {
  getMockAnalytics,
  normalizeBirdPerformance,
} from '../adapters/analyticsAdapter.js'

const EMPTY_ANALYTICS = {
  birdPerformance: { entries: 0, exits: 0, netChange: 0, returnRate: 0, change: 0 },
  hourlyBirdActivity: [],
  zoneDensity: [],
  microClimateScores: [],
  alertDistribution: [],
  environmentComparison: [],
  birdTrendAnalytics: [],
  alertTrend: [],
  yieldTrend: [],
  yieldSummary: null,
  hasDataGaps: false,
}

export function useAnalytics(farmId = null) {
  const [data, setData] = useState(() => (USE_MOCK ? getMockAnalytics() : EMPTY_ANALYTICS))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [unavailable, setUnavailable] = useState(false)

  const fetchAnalytics = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)
      setUnavailable(false)

      if (USE_MOCK) {
        setData(getMockAnalytics())
        return
      }

      if (!farmId) {
        setData(EMPTY_ANALYTICS)
        return
      }

      // Clear previous farm's analytics immediately on farm switch
      setData(EMPTY_ANALYTICS)

      // Fetch summary and trends in parallel
      const [summaryResult, trendsResult] = await Promise.allSettled([
        analyticsApi.getFarmSummary(farmId, { signal }),
        analyticsApi.getFarmTrends(farmId, { signal }),
      ])

      const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null
      const trends = trendsResult.status === 'fulfilled' ? trendsResult.value : null

      if (!summary && !trends) {
        setUnavailable(true)
        setData(EMPTY_ANALYTICS)
        return
      }

      setData(() => {
        const next = { ...EMPTY_ANALYTICS }

        if (summary) {
          next.birdPerformance = normalizeBirdPerformance(summary.birdPerformance, false)
          if (Array.isArray(summary.microClimateScores) && summary.microClimateScores.length > 0) {
            next.microClimateScores = summary.microClimateScores
          }
          if (Array.isArray(summary.alertDistribution) && summary.alertDistribution.length > 0) {
            next.alertDistribution = summary.alertDistribution
          }
          if (summary.yieldSummary) {
            next.yieldSummary = summary.yieldSummary
          }
          next.hasDataGaps = summary.hasDataGaps
        }

        if (trends) {
          if (Array.isArray(trends.hourlyBirdActivity) && trends.hourlyBirdActivity.length > 0) {
            next.hourlyBirdActivity = trends.hourlyBirdActivity
          }
          if (Array.isArray(trends.environmentComparison) && trends.environmentComparison.length > 0) {
            next.environmentComparison = trends.environmentComparison
          }
          if (Array.isArray(trends.birdTrendAnalytics) && trends.birdTrendAnalytics.length > 0) {
            next.birdTrendAnalytics = trends.birdTrendAnalytics
          }
          if (Array.isArray(trends.alertTrend) && trends.alertTrend.length > 0) {
            next.alertTrend = trends.alertTrend
          }
          if (Array.isArray(trends.yieldTrend) && trends.yieldTrend.length > 0) {
            next.yieldTrend = trends.yieldTrend
          }
        }

        return next
      })
    } catch (err) {
      if (err?.code !== 'ABORTED') {
        setError(err?.message || 'Không thể tải số liệu phân tích.')
      }
    } finally {
      setLoading(false)
    }
  }, [farmId])

  useEffect(() => {
    const controller = new AbortController()
    queueMicrotask(() => {
      if (!controller.signal.aborted) {
        fetchAnalytics(controller.signal)
      }
    })

    return () => {
      controller.abort()
    }
  }, [fetchAnalytics])

  useRevalidateOnFocus(
    useCallback(() => {
      fetchAnalytics()
    }, [fetchAnalytics]),
    { enabled: !USE_MOCK && Boolean(farmId) },
  )

  const serviceState = loading
    ? SERVICE_STATE.LOADING
    : unavailable
      ? SERVICE_STATE.UNAVAILABLE
      : error
        ? SERVICE_STATE.ERROR
        : farmId
          ? SERVICE_STATE.AVAILABLE
          : SERVICE_STATE.UNKNOWN

  return {
    analyticsData: data,
    loading,
    error,
    unavailable,
    serviceState,
    refetch: () => fetchAnalytics(),
  }
}

export default useAnalytics
