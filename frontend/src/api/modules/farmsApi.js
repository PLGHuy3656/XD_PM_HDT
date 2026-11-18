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

  async createFarm(payload, options = {}) {
    return apiClient.post(ENDPOINTS.FARMS.LIST, payload, options)
  },

  async updateFarm(farmId, payload, options = {}) {
    return apiClient.put(ENDPOINTS.FARMS.DETAIL(farmId), payload, options)
  },

  async deleteFarm(farmId, options = {}) {
    return apiClient.delete(ENDPOINTS.FARMS.DETAIL(farmId), options)
  },

  async createZone(farmId, payload, options = {}) {
    return apiClient.post(ENDPOINTS.FARMS.ZONES(farmId), payload, options)
  },

  async updateZone(zoneId, payload, options = {}) {
    return apiClient.put(ENDPOINTS.FARMS.ZONE_DETAIL(zoneId), payload, options)
  },

  async deleteZone(zoneId, options = {}) {
    return apiClient.delete(ENDPOINTS.FARMS.ZONE_DETAIL(zoneId), options)
  },
}

export default farmsApi
