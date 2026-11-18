import { useEffect, useRef, useState } from 'react'
import { WS_BASE_URL, USE_MOCK } from '../../../api/config.js'
import { getAuthToken } from '../../../api/client.js'
import { normalizeTelemetry } from '../adapters/telemetryAdapter.js'

export function useTelemetryWebSocket(farmId = null) {
  const [connectionStatus, setConnectionStatus] = useState('connecting')
  const [latestTelemetry, setLatestTelemetry] = useState(() => normalizeTelemetry(null))
  const reconnectAttemptsRef = useRef(0)

  useEffect(() => {
    // If in mock mode, simulate live telemetry stream with gentle variation
    if (USE_MOCK) {
      setConnectionStatus('connected')
      const interval = setInterval(() => {
        setLatestTelemetry((prev) => {
          const deltaT = (Math.random() - 0.5) * 0.2
          const deltaH = (Math.random() - 0.5) * 0.5
          return normalizeTelemetry({
            temperature: Math.min(32, Math.max(26, (prev?.temperature || 28.5) + deltaT)),
            humidity: Math.min(90, Math.max(65, (prev?.humidity || 78) + deltaH)),
            co2: Math.min(900, Math.max(500, (prev?.co2 || 620) + (Math.random() - 0.5) * 5)),
            light: Math.min(200, Math.max(80, (prev?.light || 120) + (Math.random() - 0.5) * 2)),
          })
        })
      }, 3000)

      return () => clearInterval(interval)
    }

    let socket = null
    let reconnectTimer = null
    let stopped = false

    function connect() {
      if (stopped) return

      setConnectionStatus('connecting')
      const token = getAuthToken()
      const queryParams = new URLSearchParams()
      if (token) queryParams.set('token', token)
      if (farmId) queryParams.set('farm_id', farmId)

      const qs = queryParams.toString()
      const wsUrl = `${WS_BASE_URL.replace(/\/$/, '')}/ws/telemetry${qs ? `?${qs}` : ''}`

      try {
        socket = new WebSocket(wsUrl)
      } catch {
        scheduleReconnect()
        return
      }

      socket.onopen = () => {
        reconnectAttemptsRef.current = 0
        setConnectionStatus('connected')
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)
          if (message.type === 'telemetry' && message.metrics) {
            setLatestTelemetry(normalizeTelemetry(message))
          }
        } catch {
          // Ignore invalid message
        }
      }

      socket.onerror = () => {
        if (socket) socket.close()
      }

      socket.onclose = () => {
        if (stopped) return
        scheduleReconnect()
      }
    }

    function scheduleReconnect() {
      setConnectionStatus('disconnected')
      reconnectAttemptsRef.current += 1
      const backoffDelay = Math.min(10000, 1000 * Math.pow(1.5, reconnectAttemptsRef.current))
      reconnectTimer = setTimeout(connect, backoffDelay)
    }

    connect()

    return () => {
      stopped = true
      clearTimeout(reconnectTimer)
      if (socket) {
        socket.onclose = null
        socket.close()
      }
    }
  }, [farmId])

  return {
    connectionStatus,
    latestTelemetry,
  }
}

export default useTelemetryWebSocket
