import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Farms API Service
 */
export const farmsApi = {
  /**
   * List all accessible farms
   * @param {Object} [options]
   */
  async getFarms(options = {}) {
    return apiClient.get(ENDPOINTS.FARMS.LIST, options)
  },

  /**
   * Get single farm details
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmById(farmId, options = {}) {
    return apiClient.get(ENDPOINTS.FARMS.DETAIL(farmId), options)
  },

  /**
   * Get farm zones
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmZones(farmId, options = {}) {
    return apiClient.get(ENDPOINTS.FARMS.ZONES(farmId), options)
  },
}

export default farmsApi
