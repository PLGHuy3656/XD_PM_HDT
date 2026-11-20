/**
 * INT01-R1: one authenticated, farm-scoped polling loop per farm, shared by every consumer
 * (Header, Environment pages, Control page). Prevents duplicate intervals when navigating and
 * keeps the Header and the Environment page on exactly the same snapshot.
 */
import { useCallback, useEffect, useState } from 'react'
import { telemetryApi } from '../../api/modules/telemetryApi.js'
import { getAuthToken } from '../../api/client.js'
import { normalizeTelemetry } from './adapters/telemetryAdapter.js'
import { TELEMETRY_STALE_AFTER_MS } from './provenance.js'

export const POLL_INTERVAL_MS = 3000

const INITIAL = Object.freeze({
  status: 'idle', // idle | loading | ok | empty | stale | unavailable | forbidden | error
  telemetry: null,
  error: null,
  httpStatus: null,
  fetchedAt: null,
  freshAt: null,
})

const channels = new Map() // farmId -> { state, listeners, timer, inFlight, lastReceivedAt }

function classify(err) {
  const status = Number(err?.status ?? err?.statusCode ?? 0)
  if (status === 404) return 'empty'
  if (status === 401 || status === 403) return 'forbidden'
  if (status === 0 || status === 502 || status === 503 || status === 504) return 'unavailable'
  const code = String(err?.code || '').toUpperCase()
  if (code === 'NETWORK_ERROR' || code === 'TIMEOUT') return 'unavailable'
  return 'error'
}

function publish(ch, patch) {
  ch.state = { ...ch.state, ...patch }
  ch.listeners.forEach((l) => l(ch.state))
}

function withStaleness(ch, now = Date.now()) {
  if (ch.state.status !== 'ok' || !ch.state.freshAt) return
  if (now - ch.state.freshAt > TELEMETRY_STALE_AFTER_MS) publish(ch, { status: 'stale' })
}

async function poll(farmId) {
  const ch = channels.get(farmId)
  if (!ch || ch.inFlight || !getAuthToken()) return
  ch.inFlight = true
  try {
    const response = await telemetryApi.getFarmLatest(farmId)
    const telemetry = normalizeTelemetry(response, false)
    const now = Date.now()
    const receivedAt = telemetry?.timestamp || null
    let freshAt = ch.state.freshAt
    if (receivedAt && receivedAt !== ch.lastReceivedAt) {
      ch.lastReceivedAt = receivedAt
      const serverAge = now - new Date(receivedAt).getTime()
      // first sample older than the stale window is already stale
      freshAt = Number.isFinite(serverAge) && serverAge > TELEMETRY_STALE_AFTER_MS ? now - serverAge : now
    }
    const hasMetric = telemetry && [telemetry.temperature, telemetry.humidity, telemetry.co2, telemetry.light].some((v) => v != null)
    publish(ch, {
      status: hasMetric ? 'ok' : 'empty',
      telemetry: hasMetric ? telemetry : null,
      error: null,
      httpStatus: 200,
      fetchedAt: now,
      freshAt,
    })
    withStaleness(ch, now)
  } catch (err) {
    if (err?.code === 'ABORTED') return
    const status = classify(err)
    publish(ch, {
      status,
      // keep the last snapshot visible only as stale data for transient outages; never for 403/404
      telemetry: status === 'unavailable' || status === 'error' ? ch.state.telemetry : null,
      error: err?.message || 'Không thể tải số liệu cảm biến.',
      httpStatus: Number(err?.status ?? err?.statusCode ?? 0) || null,
      fetchedAt: Date.now(),
    })
  } finally {
    ch.inFlight = false
  }
}

export function subscribeFarmTelemetry(farmId, listener) {
  if (!farmId) return () => {}
  let ch = channels.get(farmId)
  if (!ch) {
    ch = { state: { ...INITIAL, status: 'loading' }, listeners: new Set(), timer: null, inFlight: false, lastReceivedAt: null }
    channels.set(farmId, ch)
  }
  ch.listeners.add(listener)
  listener(ch.state)
  if (!ch.timer) {
    poll(farmId)
    ch.timer = setInterval(() => poll(farmId), POLL_INTERVAL_MS)
  }
  return () => {
    ch.listeners.delete(listener)
    if (ch.listeners.size === 0) {
      clearInterval(ch.timer)
      channels.delete(farmId)
    }
  }
}

export function refreshFarmTelemetry(farmId) {
  if (farmId && channels.has(farmId)) return poll(farmId)
  return Promise.resolve()
}

/** Test/diagnostic helper: number of active polling loops. */
export function activeFarmPollerCount() {
  return channels.size
}

export function useFarmTelemetry(farmId) {
  // State is tagged with the farm it belongs to, so a farm switch never shows the previous farm's data
  const [entry, setEntry] = useState({ farmId: null, state: INITIAL })

  useEffect(() => {
    if (!farmId) return undefined
    return subscribeFarmTelemetry(farmId, (state) => setEntry({ farmId, state }))
  }, [farmId])

  const refresh = useCallback(() => refreshFarmTelemetry(farmId), [farmId])
  const state = !farmId
    ? INITIAL
    : entry.farmId === farmId
      ? entry.state
      : { ...INITIAL, status: 'loading' }
  return { ...state, refresh }
}
