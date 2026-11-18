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
}

export default systemApi
