/**
 * Normalized API Error Class and Helpers for SwiftletCare
 */

export class ApiError extends Error {
  /**
   * @param {string} message - Human-readable error message
   * @param {number} status - HTTP status code (0 for network/client failure)
   * @param {string} [code] - Machine-readable error code
   * @param {any} [detail] - Detailed upstream response data
   * @param {Error} [originalError] - Root cause error
   * @param {string} [endpoint] - Target URL or endpoint path
   */
  constructor(message, status = 0, code = 'UNKNOWN_ERROR', detail = null, originalError = null, endpoint = '') {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.detail = detail
    this.originalError = originalError
    this.endpoint = endpoint
    this.timestamp = new Date().toISOString()
  }

  get isNetworkError() {
    return this.status === 0 || this.code === 'NETWORK_ERROR'
  }

  get isTimeout() {
    return this.code === 'TIMEOUT'
  }

  get isAborted() {
    return this.code === 'ABORTED'
  }

  get isUnauthorized() {
    return this.status === 401 || this.code === 'UNAUTHORIZED'
  }

  get isForbidden() {
    return this.status === 403 || this.code === 'FORBIDDEN'
  }

  get isNotFound() {
    return this.status === 404 || this.code === 'NOT_FOUND'
  }

  get isClientError() {
    return this.status >= 400 && this.status < 500
  }

  get isServerError() {
    return this.status >= 500
  }
}

/**
 * Normalizes any caught error into a typed ApiError instance.
 * @param {any} error
 * @param {string} [endpoint]
 * @returns {ApiError}
 */
export function normalizeError(error, endpoint = '') {
  if (error instanceof ApiError) {
    return error
  }

  if (error?.name === 'AbortError') {
    return new ApiError('Yêu cầu đã bị hủy (Request cancelled).', 0, 'ABORTED', null, error, endpoint)
  }

  if (error?.name === 'TimeoutError' || error?.message?.toLowerCase().includes('timeout')) {
    return new ApiError('Hết thời gian chờ phản hồi từ máy chủ.', 408, 'TIMEOUT', null, error, endpoint)
  }

  if (error instanceof TypeError && error.message?.includes('Failed to fetch')) {
    return new ApiError(
      'Không thể kết nối tới máy chủ (Network error). Vui lòng kiểm tra kết nối mạng hoặc Gateway.',
      0,
      'NETWORK_ERROR',
      null,
      error,
      endpoint,
    )
  }

  return new ApiError(
    error?.message || 'Đã xảy ra lỗi không xác định.',
    error?.status || 0,
    error?.code || 'UNKNOWN_ERROR',
    error?.detail || null,
    error,
    endpoint,
  )
}
