/**
 * Authoritative API Endpoint Registry for SwiftletCare
 * Aligned with API Gateway CP11 Explicit Route Allowlist and Upstream Contracts.
 */

export const ENDPOINTS = {
  AUTH: {
    LOGIN: '/api/auth/login',
    LOGOUT: '/api/auth/logout',
    ME: '/api/auth/me',
    REGISTER: '/api/auth/register',
  },

  USERS: {
    LIST: '/api/users',
    DETAIL: (userId) => `/api/users/${userId}`,
    STATUS: (userId) => `/api/users/${userId}/status`,
  },

  FARMS: {
    LIST: '/api/farms',
    DETAIL: (farmId) => `/api/farms/${farmId}`,
    ZONES: (farmId) => `/api/farms/${farmId}/zones`,
  },

  DEVICES: {
    LIST: '/api/devices',
    DETAIL: (deviceId) => `/api/devices/${deviceId}`,
    CONFIG: (deviceId) => `/api/iot/devices/${deviceId}/config`,
    COMMAND_RELAY: (deviceId) => `/api/iot/devices/${deviceId}/commands/relay`,
    COMMAND_CONFIG: (deviceId) => `/api/iot/devices/${deviceId}/commands/config`,
    COMMANDS: (deviceId) => `/api/iot/devices/${deviceId}/commands`,
    COMMAND_STATUS: (commandId) => `/api/iot/commands/${commandId}`,
    PRESENCE_ALL: '/api/iot/devices/presence',
    PRESENCE_DEVICE: (deviceId) => `/api/iot/devices/${deviceId}/presence`,
  },

  TELEMETRY: {
    FARM_LATEST: (farmId) => `/api/iot/farms/${farmId}/telemetry/latest`,
    FARM_HISTORY: (farmId) => `/api/iot/farms/${farmId}/telemetry`,
    DEVICE_LATEST: (deviceId) => `/api/iot/devices/${deviceId}/telemetry/latest`,
    DEVICE_HISTORY: (deviceId) => `/api/iot/devices/${deviceId}/telemetry`,
  },

  AI: {
    CAMERAS: '/api/v1/ai/cameras',
    CAMERA_DETAIL: (cameraId) => `/api/v1/ai/cameras/${cameraId}`,
    CAMERA_STATUS: (cameraId) => `/api/v1/ai/cameras/${cameraId}/status`,
    CAMERA_COUNTS_LATEST: (cameraId) => `/api/v1/ai/cameras/${cameraId}/counts/latest`,
    CAMERA_COUNTS_HISTORY: (cameraId) => `/api/v1/ai/cameras/${cameraId}/counts`,
    CAMERA_DETECTIONS_LATEST: (cameraId) => `/api/v1/ai/cameras/${cameraId}/detections/latest`,
    EVENTS: '/api/v1/ai/events',
    EVENT_DETAIL: (eventId) => `/api/v1/ai/events/${eventId}`,
  },

  ALERTS: {
    LIST: '/api/v1/alerts',
    DETAIL: (alertId) => `/api/v1/alerts/${alertId}`,
    ACKNOWLEDGE: (alertId) => `/api/v1/alerts/${alertId}/acknowledge`,
    RESOLVE: (alertId) => `/api/v1/alerts/${alertId}/resolve`,
  },

  NOTIFICATIONS: {
    LIST: '/api/v1/notifications',
    MARK_READ: (notificationId) => `/api/v1/notifications/${notificationId}/read`,
    READ_ALL: '/api/v1/notifications/read-all',
  },

  ANALYTICS: {
    FARM_SUMMARY: (farmId) => `/api/v1/analytics/farms/${farmId}/summary`,
    FARM_TRENDS: (farmId) => `/api/v1/analytics/farms/${farmId}/trends`,
    TRENDS: '/api/v1/analytics/trends',
  },

  TECHNICIANS: {
    LIST: '/api/technicians',
    DETAIL: (technicianId) => `/api/technicians/${technicianId}`,
    DASHBOARD: (technicianId) => `/api/technicians/${technicianId}/dashboard`,
    FARMS: (technicianId) => `/api/technicians/${technicianId}/farms`,
    FARM_DETAIL: (technicianId, farmId) => `/api/technicians/${technicianId}/farms/${farmId}`,
    FARM_DEVICES: (technicianId, farmId) => `/api/technicians/${technicianId}/farms/${farmId}/devices`,
    FARM_DEVICE_DETAIL: (technicianId, farmId, deviceId) =>
      `/api/technicians/${technicianId}/farms/${farmId}/devices/${deviceId}`,
    ASSIGN_FARM: (technicianId, farmId) => `/api/technicians/${technicianId}/farms/${farmId}/assign`,
  },

  SYSTEM: {
    HEALTH: '/health',
  },
}

export default ENDPOINTS
