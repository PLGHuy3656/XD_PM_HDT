import { useCallback, useEffect, useState } from 'react'
import { analyticsApi } from '../../../api/modules/analyticsApi.js'
import { USE_MOCK } from '../../../api/config.js'
import {
  getMockAnalytics,
  normalizeAnalyticsSummary,
  normalizeBirdPerformance,
} from '../adapters/analyticsAdapter.js'

export function useAnalytics(farmId = null) {
  const [data, setData] = useState(() => getMockAnalytics())
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchAnalytics = useCallback(async (signal) => {
    try {
      setLoading(true)
      setError(null)

      if (USE_MOCK || !farmId) {
        setData(getMockAnalytics())
        return
      }

      // Fetch summary and trends in parallel
      const [summaryResult, trendsResult] = await Promise.allSettled([
        analyticsApi.getFarmSummary(farmId, { signal }),
        analyticsApi.getFarmTrends(farmId, { signal }),
      ])

      const summary = summaryResult.status === 'fulfilled' ? summaryResult.value : null
      const trends = trendsResult.status === 'fulfilled' ? trendsResult.value : null

      setData((prev) => {
        const next = { ...prev }

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
    fetchAnalytics(controller.signal)

    return () => {
      controller.abort()
    }
  }, [fetchAnalytics])

  return {
    analyticsData: data,
    loading,
    error,
    refetch: () => fetchAnalytics(),
  }
}

export default useAnalytics
