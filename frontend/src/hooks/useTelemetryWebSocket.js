import { useEffect, useState } from 'react'

const WS_URL =
  import.meta.env.VITE_WS_URL ||
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname}:8000/ws/telemetry`

export default function useTelemetryWebSocket() {
  const [connectionStatus, setConnectionStatus] =
    useState('connecting')

  const [latestTelemetry, setLatestTelemetry] =
    useState(null)

  useEffect(() => {
    let socket
    let reconnectTimer
    let stopped = false

    function connect() {
      if (stopped) return

      setConnectionStatus('connecting')

      try {
        socket = new WebSocket(WS_URL)
      } catch {
        setConnectionStatus('disconnected')
        reconnectTimer = setTimeout(connect, 2000)
        return
      }

      socket.onopen = () => {
        setConnectionStatus('connected')
      }

      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data)

          if (
            message.type !== 'telemetry' ||
            !message.metrics ||
            typeof message.metrics !== 'object'
          ) {
            return
          }

          setLatestTelemetry(message)
        } catch {
          console.warn('Ignored invalid telemetry message')
        }
      }

      socket.onerror = () => {
        socket.close()
      }

      socket.onclose = () => {
        if (stopped) return

        setConnectionStatus('disconnected')
        reconnectTimer = setTimeout(connect, 2000)
      }
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
  }, [])

  return {
    connectionStatus,
    latestTelemetry,
  }
}
