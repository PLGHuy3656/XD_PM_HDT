import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * System Health & Observability API Service
 */
export const systemApi = {
  /**
   * Get API Gateway and microservice upstream health status
   * @param {Object} [options]
   */
  async getHealth(options = {}) {
    return apiClient.get(ENDPOINTS.SYSTEM.HEALTH, options)
  },

  /**
   * INT01-R1: live per-service status probed by the Gateway (Admin only)
   * @param {Object} [options]
   */
  async getStatus(options = {}) {
    return apiClient.get(ENDPOINTS.SYSTEM.STATUS, options)
  },
}

export default systemApi
