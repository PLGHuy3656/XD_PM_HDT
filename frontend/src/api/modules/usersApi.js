import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Users Management API Service (Admin Only - FR-UAM-05)
 */
export const usersApi = {
  /**
   * Get all registered users
   * @param {Object} [params]
   * @param {number} [params.limit]
   * @param {number} [params.offset]
   * @param {Object} [options]
   * @returns {Promise<Array<any>>}
   */
  async getUsers(params = {}, options = {}) {
    return apiClient.get(ENDPOINTS.USERS.LIST, { params, ...options })
  },

  /**
   * Get details of a single user
   * @param {string} userId
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async getUserById(userId, options = {}) {
    return apiClient.get(ENDPOINTS.USERS.DETAIL(userId), options)
  },

  /**
   * Create a new user account
   * @param {{ email: string, password: str, full_name: string, phone?: string, role: string, status?: string }} userData
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async createUser(userData, options = {}) {
    return apiClient.post(ENDPOINTS.USERS.LIST, userData, options)
  },

  /**
   * Update user details
   * @param {string} userId
   * @param {{ full_name?: string, phone?: string, role?: string, status?: string }} updates
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async updateUser(userId, updates, options = {}) {
    return apiClient.put(ENDPOINTS.USERS.DETAIL(userId), updates, options)
  },

  /**
   * Update user status (ACTIVE / LOCKED)
   * @param {string} userId
   * @param {string} status
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async updateUserStatus(userId, status, options = {}) {
    return apiClient.patch(ENDPOINTS.USERS.STATUS(userId), { status }, options)
  },

  /**
   * Delete user
   * @param {string} userId
   * @param {Object} [options]
   * @returns {Promise<any>}
   */
  async deleteUser(userId, options = {}) {
    return apiClient.delete(ENDPOINTS.USERS.DETAIL(userId), options)
  },
}

export default usersApi
