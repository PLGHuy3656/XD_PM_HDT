import apiClient from '../client.js'

/**
 * INT03-R1: Inspection Requests (Management Service, via Gateway).
 * Mutations never auto-retry (state transitions are not idempotent).
 */
const BASE = '/api/inspection-requests'

export const inspectionsApi = {
  list(params = {}, options = {}) {
    return apiClient.get(BASE, { ...options, params })
  },
  get(id, options = {}) {
    return apiClient.get(`${BASE}/${encodeURIComponent(id)}`, options)
  },
  create(payload, options = {}) {
    return apiClient.post(BASE, payload, { ...options, retries: 0 })
  },
  transition(id, action, payload = {}, options = {}) {
    return apiClient.post(`${BASE}/${encodeURIComponent(id)}/${action}`, payload, { ...options, retries: 0 })
  },
}

export default inspectionsApi
