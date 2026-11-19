/**
 * SwiftletCare Frontend API Configuration
 * Supports environment variables with safe development defaults.
 * Works across both Vite browser runtime and Node test environments.
 */

const viteEnv = import.meta.env
const nodeEnv = typeof globalThis !== 'undefined' && globalThis.process ? globalThis.process.env || {} : {}
const env = viteEnv || nodeEnv

const isProd = import.meta.env?.PROD ?? (nodeEnv.MODE === 'production' || nodeEnv.NODE_ENV === 'production')

const configuredApiBaseUrl =
  env.VITE_API_BASE_URL !== undefined
    ? env.VITE_API_BASE_URL
    : env.VITE_API_URL !== undefined
      ? env.VITE_API_URL
      : isProd
        ? ''
        : 'http://localhost:8000'

export const API_BASE_URL = String(configuredApiBaseUrl).trim()

const defaultWsBase = API_BASE_URL
  ? API_BASE_URL.replace(/^http/, 'ws')
  : typeof window !== 'undefined' && window.location
    ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`
    : isProd
      ? ''
      : 'ws://localhost:8000'

export const WS_BASE_URL =
  env.VITE_WS_BASE_URL !== undefined
    ? String(env.VITE_WS_BASE_URL).trim()
    : defaultWsBase

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
