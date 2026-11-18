import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Devices & IoT Actuation API Service
 */
export const devicesApi = {
  /**
   * List devices
   * @param {Object} [options]
   */
  async getDevices(options = {}) {
    return apiClient.get(ENDPOINTS.DEVICES.LIST, options)
  },

  /**
   * Get single device details
   * @param {string} deviceId
   * @param {Object} [options]
   */
  async getDeviceById(deviceId, options = {}) {
    return apiClient.get(ENDPOINTS.DEVICES.DETAIL(deviceId), options)
  },

  /**
   * Get device config
   * @param {string} deviceId
   * @param {Object} [options]
   */
  async getDeviceConfig(deviceId, options = {}) {
    return apiClient.get(ENDPOINTS.DEVICES.CONFIG(deviceId), options)
  },

  /**
   * Send relay control command to IoT device
   * Note: Mutations never auto-retry.
   * @param {string} deviceId
   * @param {{ relay_index: number, state: boolean | string }} command
   * @param {Object} [options]
   */
  async sendRelayCommand(deviceId, command, options = {}) {
    return apiClient.post(ENDPOINTS.DEVICES.COMMAND_RELAY(deviceId), command, options)
  },

  /**
   * Query device presence status
   * @param {string} [deviceId]
   * @param {Object} [options]
   */
  async getPresence(deviceId, options = {}) {
    const endpoint = deviceId
      ? ENDPOINTS.DEVICES.PRESENCE_DEVICE(deviceId)
      : ENDPOINTS.DEVICES.PRESENCE_ALL
    return apiClient.get(endpoint, options)
  },

  async createDevice(payload, options = {}) {
    return apiClient.post(ENDPOINTS.DEVICES.LIST, payload, options)
  },

  async updateDevice(deviceId, payload, options = {}) {
    return apiClient.put(ENDPOINTS.DEVICES.DETAIL(deviceId), payload, options)
  },

  async deleteDevice(deviceId, options = {}) {
    return apiClient.delete(ENDPOINTS.DEVICES.DETAIL(deviceId), options)
  },
}

export default devicesApi
