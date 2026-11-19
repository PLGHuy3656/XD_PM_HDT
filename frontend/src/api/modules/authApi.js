import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Authentication API Service
 */
export const authApi = {
  /**
   * Log in user via Gateway proxy to Management Service
   * @param {{ email: string, password: string }} credentials
   * @param {Object} [options]
   * @returns {Promise<{ access_token: string, token_type: string, user: any }>}
   */
  async login(credentials, options = {}) {
    return apiClient.post(ENDPOINTS.AUTH.LOGIN, credentials, {
      skipAuth: true,
      ...options,
    })
  },

  /**
   * Log out user and revoke token on Gateway (FR-UAM-02)
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async logout(options = {}) {
    try {
      return await apiClient.post(ENDPOINTS.AUTH.LOGOUT, {}, options)
    } catch (e) {
      // Best-effort logout: ignore network failures so client still cleans up
      return { status: 'ok', warning: e.message }
    }
  },

  /**
   * Get current authenticated user profile
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async getProfile(options = {}) {
    return apiClient.get(ENDPOINTS.AUTH.ME, options)
  },

  /**
   * Register a new user account
   * @param {any} registrationData
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async register(registrationData, options = {}) {
    return apiClient.post(ENDPOINTS.AUTH.REGISTER, registrationData, {
      skipAuth: true,
      ...options,
    })
  },
}

export default authApi
