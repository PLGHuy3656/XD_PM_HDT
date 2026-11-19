import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * AI Cameras & Swiftlet Monitoring API Service
 */
export const camerasApi = {
  /**
   * List AI camera feeds
   * @param {Object} [options]
   */
  async getCameras(options = {}) {
    return apiClient.get(ENDPOINTS.AI.CAMERAS, options)
  },

  /**
   * Get camera details
   * @param {string} cameraId
   * @param {Object} [options]
   */
  async getCameraById(cameraId, options = {}) {
    return apiClient.get(ENDPOINTS.AI.CAMERA_DETAIL(cameraId), options)
  },

  /**
   * Get technical status of camera
   * @param {string} cameraId
   * @param {Object} [options]
   */
  async getCameraStatus(cameraId, options = {}) {
    return apiClient.get(ENDPOINTS.AI.CAMERA_STATUS(cameraId), options)
  },

  /**
   * Get latest bird count from camera feed
   * @param {string} cameraId
   * @param {Object} [options]
   */
  async getLatestBirdCounts(cameraId, options = {}) {
    return apiClient.get(ENDPOINTS.AI.CAMERA_COUNTS_LATEST(cameraId), options)
  },

  /**
   * Get historical bird counts
   * @param {string} cameraId
   * @param {Object} [options]
   */
  async getBirdCountHistory(cameraId, options = {}) {
    return apiClient.get(ENDPOINTS.AI.CAMERA_COUNTS_HISTORY(cameraId), options)
  },

  /**
   * Get latest detection results
   * @param {string} cameraId
   * @param {Object} [options]
   */
  async getLatestDetections(cameraId, options = {}) {
    return apiClient.get(ENDPOINTS.AI.CAMERA_DETECTIONS_LATEST(cameraId), options)
  },

  /**
   * List AI events
   * @param {Object} [options]
   */
  async getEvents(options = {}) {
    return apiClient.get(ENDPOINTS.AI.EVENTS, options)
  },
}

export default camerasApi
