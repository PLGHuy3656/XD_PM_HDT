import {
  analyticsFarms,
  birdPerformance,
  hourlyBirdActivity,
  zoneDensity,
  microClimateScores,
  alertDistribution,
  environmentMetrics,
  analyticsPeriods,
  environmentComparison,
  birdTrendAnalytics,
  returnRateCorrelation,
  alertTrend,
  yieldSummary,
  yieldTrend,
  zoneYield,
  harvestHistory,
} from '../../../components/features/farm-owner/analytics/analyticsMockData.js'

/**
 * Normalizes bird performance block
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any}
 */
export function normalizeBirdPerformance(raw, isMockMode = false) {
  if (!raw) {
    return isMockMode
      ? birdPerformance
      : { entries: 0, exits: 0, returnRate: 0, difference: 0, change: 0 }
  }
  const bp = raw.birdPerformance || raw
  return {
    entries: Number(bp.entries ?? (isMockMode ? 428 : 0)),
    exits: Number(bp.exits ?? (isMockMode ? 391 : 0)),
    returnRate: Number(bp.returnRate ?? bp.return_rate ?? (isMockMode ? 93.6 : 0)),
    difference: Number(bp.difference ?? (isMockMode ? 37 : 0)),
    change: Number(bp.change ?? (isMockMode ? 8.4 : 0)),
  }
}

/**
 * Normalizes analytics summary DTO from PostgreSQL B4 Analytics backend
 * @param {any} raw
 * @param {boolean} [isMockMode=false]
 * @returns {any}
 */
export function normalizeAnalyticsSummary(raw, isMockMode = false) {
  if (!raw) {
    return getMockAnalytics()
  }

  return {
    birdPerformance: normalizeBirdPerformance(raw.birdPerformance, isMockMode),
    microClimateScores: Array.isArray(raw.microClimateScores)
      ? raw.microClimateScores
      : isMockMode
        ? microClimateScores
        : [],
    alertDistribution: Array.isArray(raw.alertDistribution)
      ? raw.alertDistribution
      : isMockMode
        ? alertDistribution
        : [],
    yieldSummary: raw.yieldSummary || (isMockMode ? yieldSummary : null),
    hasDataGaps: Boolean(raw.hasDataGaps),
    period: raw.period || 'day',
  }
}

export function getMockAnalytics() {
  return {
    farms: analyticsFarms,
    birdPerformance,
    hourlyBirdActivity,
    zoneDensity,
    microClimateScores,
    alertDistribution,
    environmentMetrics,
    analyticsPeriods,
    environmentComparison,
    birdTrendAnalytics,
    returnRateCorrelation,
    alertTrend,
    yieldSummary,
    yieldTrend,
    zoneYield,
    harvestHistory,
  }
}
