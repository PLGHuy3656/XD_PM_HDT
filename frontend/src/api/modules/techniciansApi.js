import apiClient from '../client.js'
import { ENDPOINTS } from '../endpoints.js'

/**
 * Technician Operations API Service
 */
export const techniciansApi = {
  /**
   * List technicians
   * @param {Object} [options]
   */
  async getTechnicians(options = {}) {
    return apiClient.get(ENDPOINTS.TECHNICIANS.LIST, options)
  },

  /**
   * Get technician profile
   * @param {string} technicianId
   * @param {Object} [options]
   */
  async getTechnicianById(technicianId, options = {}) {
    return apiClient.get(ENDPOINTS.TECHNICIANS.DETAIL(technicianId), options)
  },

  /**
   * Get technician dashboard stats
   * @param {string} technicianId
   * @param {Object} [options]
   */
  async getDashboard(technicianId, options = {}) {
    return apiClient.get(ENDPOINTS.TECHNICIANS.DASHBOARD(technicianId), options)
  },

  /**
   * Get technician assigned farms
   * @param {string} technicianId
   * @param {Object} [options]
   */
  async getFarms(technicianId, options = {}) {
    return apiClient.get(ENDPOINTS.TECHNICIANS.FARMS(technicianId), options)
  },

  /**
   * Get single assigned farm details
   * @param {string} technicianId
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmDetail(technicianId, farmId, options = {}) {
    return apiClient.get(ENDPOINTS.TECHNICIANS.FARM_DETAIL(technicianId, farmId), options)
  },

  /**
   * Get devices for assigned farm
   * @param {string} technicianId
   * @param {string} farmId
   * @param {Object} [options]
   */
  async getFarmDevices(technicianId, farmId, options = {}) {
    return apiClient.get(ENDPOINTS.TECHNICIANS.FARM_DEVICES(technicianId, farmId), options)
  },

  /**
   * Get specific device detail in assigned farm
   * @param {string} technicianId
   * @param {string} farmId
   * @param {string} deviceId
   * @param {Object} [options]
   */
  async getFarmDeviceDetail(technicianId, farmId, deviceId, options = {}) {
    return apiClient.get(
      ENDPOINTS.TECHNICIANS.FARM_DEVICE_DETAIL(technicianId, farmId, deviceId),
      options,
    )
  },

  /**
   * Assign technician to farm (Admin only)
   * @param {string} technicianId
   * @param {string} farmId
   * @param {Object} [options]
   */
  async assignFarm(technicianId, farmId, options = {}) {
    return apiClient.post(ENDPOINTS.TECHNICIANS.ASSIGN_FARM(technicianId, farmId), {}, options)
  },

  /**
   * Unassign technician from farm (Admin only)
   * @param {string} technicianId
   * @param {string} farmId
   * @param {Object} [options]
   */
  async unassignFarm(technicianId, farmId, options = {}) {
    return apiClient.delete(ENDPOINTS.TECHNICIANS.ASSIGN_FARM(technicianId, farmId), options)
  },
}

export default techniciansApi
