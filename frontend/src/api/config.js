/**
 * SwiftletCare Frontend API Configuration
 * Supports environment variables with safe development defaults.
 * Works across both Vite browser runtime and Node test environments.
 */

const env =
  typeof import.meta !== 'undefined' && import.meta.env
    ? import.meta.env
    : typeof process !== 'undefined' && process.env
      ? process.env
      : {}

export const API_BASE_URL =
  env.VITE_API_BASE_URL ||
  env.VITE_API_URL ||
  'http://localhost:8000'

export const WS_BASE_URL =
  env.VITE_WS_BASE_URL ||
  API_BASE_URL.replace(/^http/, 'ws')

/**
 * Global mock mode flag:
 * Set VITE_USE_MOCK=false to target the real API Gateway.
 * If unset in development, defaults to true so offline development works out of the box.
 */
export const USE_MOCK =
  env.VITE_USE_MOCK === 'true' ||
  env.VITE_USE_MOCK === true ||
  (env.VITE_USE_MOCK !== 'false' &&
    env.VITE_USE_MOCK !== false &&
    env.MODE === 'development')

export const DEFAULT_TIMEOUT_MS = 15000
