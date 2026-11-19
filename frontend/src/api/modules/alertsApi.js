import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Alerts & Notification API Service
 */
export const alertsApi = {
  /**
   * List alerts with optional filtering
   * @param {Object} [options]
   */
  async getAlerts(options = {}) {
    return apiClient.get(ENDPOINTS.ALERTS.LIST, options)
  },

  /**
   * Get single alert detail
   * @param {string} alertId
   * @param {Object} [options]
   */
  async getAlertById(alertId, options = {}) {
    return apiClient.get(ENDPOINTS.ALERTS.DETAIL(alertId), options)
  },

  /**
   * Acknowledge an active alert
   * Note: Mutation never auto-retries.
   * @param {string} alertId
   * @param {{ note?: string }} [data]
   * @param {Object} [options]
   */
  async acknowledge(alertId, data = {}, options = {}) {
    return apiClient.post(ENDPOINTS.ALERTS.ACKNOWLEDGE(alertId), data, options)
  },

  /**
   * Resolve an alert
   * @param {string} alertId
   * @param {{ note?: string }} [data]
   * @param {Object} [options]
   */
  async resolve(alertId, data = {}, options = {}) {
    return apiClient.post(ENDPOINTS.ALERTS.RESOLVE(alertId), data, options)
  },

  /**
   * List notifications for current user
   * @param {Object} [options]
   */
  async getNotifications(options = {}) {
    return apiClient.get(ENDPOINTS.NOTIFICATIONS.LIST, options)
  },

  /**
   * Mark single notification as read
   * @param {string} notificationId
   * @param {Object} [options]
   */
  async markNotificationRead(notificationId, options = {}) {
    return apiClient.post(ENDPOINTS.NOTIFICATIONS.MARK_READ(notificationId), {}, options)
  },

  /**
   * Mark all notifications as read
   * @param {Object} [options]
   */
  async markAllNotificationsRead(options = {}) {
    return apiClient.post(ENDPOINTS.NOTIFICATIONS.READ_ALL, {}, options)
  },
}

export default alertsApi
