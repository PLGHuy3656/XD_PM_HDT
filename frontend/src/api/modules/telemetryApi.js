import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Telemetry API Service (Real-time and historic sensor metrics)
 */
export const telemetryApi = {
  /**
   * Get latest farm telemetry metrics (NB-1)
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmLatest(farmId, options = {}) {
    return apiClient.get(ENDPOINTS.TELEMETRY.FARM_LATEST(farmId), options)
  },

  /**
   * Get farm telemetry history
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmHistory(farmId, options = {}) {
    return apiClient.get(ENDPOINTS.TELEMETRY.FARM_HISTORY(farmId), options)
  },

  /**
   * Get latest telemetry for specific device
   * @param {string} deviceId
   * @param {Object} [options]
   */
  async getDeviceLatest(deviceId, options = {}) {
    return apiClient.get(ENDPOINTS.TELEMETRY.DEVICE_LATEST(deviceId), options)
  },

  /**
   * Get device telemetry history
   * @param {string} deviceId
   * @param {Object} [options]
   */
  async getDeviceHistory(deviceId, options = {}) {
    return apiClient.get(ENDPOINTS.TELEMETRY.DEVICE_HISTORY(deviceId), options)
  },
}

export default telemetryApi
