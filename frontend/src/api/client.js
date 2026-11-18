/**
 * Central HTTP API Client for SwiftletCare Frontend
 * Built on native Fetch API with JWT injection, error normalization, AbortSignal support, and strict error handling.
 */

import { API_BASE_URL, DEFAULT_TIMEOUT_MS } from './config.js'
import { ApiError, normalizeError } from './errors.js'

let currentToken =
  typeof window !== 'undefined' ? localStorage.getItem('swiftletcare_token') : null
let onUnauthorizedCallback = null

/**
 * Configure active access token for Bearer authentication.
 * @param {string|null} token
 */
export function setAuthToken(token) {
  currentToken = token
}

/**
 * Get the currently configured access token.
 * @returns {string|null}
 */
export function getAuthToken() {
  return (
    currentToken ||
    (typeof window !== 'undefined'
      ? localStorage.getItem('swiftletcare_token')
      : null)
  )
}

/**
 * Register a listener for 401 Unauthorized responses (e.g. trigger logout or token refresh).
 * @param {() => void} callback
 */
export function setUnauthorizedHandler(callback) {
  onUnauthorizedCallback = callback
}

/**
 * Core HTTP Request Function
 * @param {string} endpoint - API path (e.g. '/api/auth/me') or full URL
 * @param {Object} [options]
 * @param {string} [options.method='GET']
 * @param {any} [options.body] - Request body (will be serialized as JSON if object)
 * @param {Record<string, any>} [options.params] - URL query parameters to serialize safely
 * @param {Record<string, string>} [options.headers]
 * @param {AbortSignal} [options.signal] - External abort signal
 * @param {number} [options.timeout=DEFAULT_TIMEOUT_MS] - Timeout in milliseconds
 * @param {boolean} [options.skipAuth=false] - Do not attach Authorization header
 * @param {number} [options.retries=0] - Only used for safe idempotent GET requests
 * @param {string} [options.baseUrl] - Custom base URL override
 * @returns {Promise<any>}
 */
export async function request(endpoint, options = {}) {
  const {
    method = 'GET',
    body,
    params,
    headers = {},
    signal,
    timeout = DEFAULT_TIMEOUT_MS,
    skipAuth = false,
    retries = 0,
    baseUrl = API_BASE_URL,
  } = options

  const isMutation = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method.toUpperCase())
  const effectiveRetries = isMutation ? 0 : Math.max(0, retries)

  let url = endpoint.startsWith('http')
    ? endpoint
    : `${baseUrl.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`

  // Safe query parameter serialization
  if (params && typeof params === 'object') {
    const searchParams = new URLSearchParams()
    Object.entries(params).forEach(([key, val]) => {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val))
      }
    })
    const queryString = searchParams.toString()
    if (queryString) {
      url += (url.includes('?') ? '&' : '?') + queryString
    }
  }

  const requestHeaders = new Headers(headers)

  // Attach content type for payload requests if not already set
  if (body !== undefined && !requestHeaders.has('Content-Type')) {
    if (!(body instanceof FormData)) {
      requestHeaders.set('Content-Type', 'application/json')
    }
  }

  // Attach Authorization header if token is present and not explicitly skipped
  const effectiveToken = getAuthToken()
  if (!skipAuth && effectiveToken && !requestHeaders.has('Authorization')) {
    requestHeaders.set('Authorization', `Bearer ${effectiveToken}`)
  }

  // Setup timeout controller combined with caller's signal
  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => {
    timeoutController.abort(new Error(`Request timeout after ${timeout}ms`))
  }, timeout)

  // If caller provided an AbortSignal, abort when it aborts
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId)
      throw normalizeError(signal.reason || new Error('Request aborted'), endpoint)
    }
    signal.addEventListener('abort', () => timeoutController.abort(signal.reason), { once: true })
  }

  const serializedBody =
    body !== undefined && !(body instanceof FormData) && typeof body === 'object'
      ? JSON.stringify(body)
      : body

  let attempt = 0
  while (attempt <= effectiveRetries) {
    attempt += 1
    try {
      const response = await fetch(url, {
        method,
        headers: requestHeaders,
        body: serializedBody,
        signal: timeoutController.signal,
      })

      clearTimeout(timeoutId)

      // Handle empty responses (e.g. 204 No Content)
      if (response.status === 204) {
        return null
      }

      const contentType = response.headers.get('content-type') || ''
      const isJson = contentType.includes('application/json')
      const responseData = isJson ? await response.json().catch(() => null) : await response.text()

      if (!response.ok) {
        // Extract error message from body if possible
        const errorMessage =
          responseData?.detail ||
          responseData?.message ||
          `HTTP ${response.status}: ${response.statusText || 'Yêu cầu thất bại'}`

        const errorCode =
          response.status === 401
            ? 'UNAUTHORIZED'
            : response.status === 403
              ? 'FORBIDDEN'
              : response.status === 404
                ? 'NOT_FOUND'
                : response.status >= 500
                  ? 'SERVER_ERROR'
                  : 'CLIENT_ERROR'

        if (response.status === 401 && typeof onUnauthorizedCallback === 'function') {
          try {
            onUnauthorizedCallback()
          } catch {
            // Prevent callback errors from masking the original HTTP error
          }
        }

        throw new ApiError(
          errorMessage,
          response.status,
          errorCode,
          responseData,
          null,
          endpoint,
        )
      }

      return responseData
    } catch (err) {
      clearTimeout(timeoutId)
      const normalized = normalizeError(err, endpoint)

      // Only retry idempotent GET requests on network failure or 5xx error
      if (!isMutation && attempt <= effectiveRetries && (normalized.isNetworkError || normalized.isServerError)) {
        await new Promise((res) => setTimeout(res, 500 * attempt))
        continue
      }

      throw normalized
    }
  }
}

export const apiClient = {
  get: (endpoint, options = {}) => request(endpoint, { ...options, method: 'GET' }),
  post: (endpoint, body, options = {}) => request(endpoint, { ...options, method: 'POST', body }),
  put: (endpoint, body, options = {}) => request(endpoint, { ...options, method: 'PUT', body }),
  patch: (endpoint, body, options = {}) => request(endpoint, { ...options, method: 'PATCH', body }),
  delete: (endpoint, options = {}) => request(endpoint, { ...options, method: 'DELETE' }),
}

export default apiClient
