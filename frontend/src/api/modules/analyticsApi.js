import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Analytics API Service (PostgreSQL B4 Analytics backend)
 */
export const analyticsApi = {
  /**
   * Get farm analytics summary
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmSummary(farmId, options = {}) {
    return apiClient.get(ENDPOINTS.ANALYTICS.FARM_SUMMARY(farmId), options)
  },

  /**
   * Get farm trends (harvest and environmental trends)
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmTrends(farmId, options = {}) {
    return apiClient.get(ENDPOINTS.ANALYTICS.FARM_TRENDS(farmId), options)
  },

  /**
   * Get global analytics trends
   * @param {Object} [options]
   */
  async getTrends(options = {}) {
    return apiClient.get(ENDPOINTS.ANALYTICS.TRENDS, options)
  },
}

export default analyticsApi
