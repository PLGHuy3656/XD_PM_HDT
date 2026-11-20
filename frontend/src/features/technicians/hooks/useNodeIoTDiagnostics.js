/**
 * INT01-R1: Technician diagnostics built ONLY from what IoT actually reports for the node
 * (presence + latest telemetry, both through the Gateway with technician assignment RBAC).
 *
 * - Sensor rows show the reading and its provenance; a reading is "REPORTING", never "HEALTHY"
 *   (no hardware self-test exists). A null metric is UNAVAILABLE.
 * - Actuator rows show the reported relay state; actuator health is UNSUPPORTED (no feedback sensor).
 * - Wi-Fi quality / firmware self-diagnostics are not provided by IoT in INT01 -> "--".
 */
import { useEffect, useState } from 'react'
import apiClient from '../../../api/client.js'
import { telemetryApi } from '../../../api/modules/telemetryApi.js'
import { USE_MOCK } from '../../../api/config.js'
import { normalizeTelemetry } from '../../telemetry/adapters/telemetryAdapter.js'
import { formatRelativeTime, metricSource, sourceLabel } from '../../telemetry/provenance.js'

const SENSOR_ROWS = [
  { key: 'temperature', name: 'Nhiệt độ (DHT)', fmt: (v) => `${Number(v).toFixed(1)}°C` },
  { key: 'humidity', name: 'Độ ẩm (DHT)', fmt: (v) => `${Math.round(v)}%` },
  { key: 'co2', name: 'CO₂', fmt: (v) => `${Math.round(v)} ppm` },
  { key: 'light', name: 'Ánh sáng', fmt: (v) => `${Number(v).toFixed(1)} lux` },
]

const ACTUATOR_ROWS = [
  { key: 'misting', name: 'Máy phun sương' },
  { key: 'fan', name: 'Quạt thông gió' },
  { key: 'heater', name: 'Máy sưởi' },
  { key: 'alarm', name: 'Còi báo động' },
]

export function buildNodeDiagnostics(baseNode, presence, presenceStatus, telemetry) {
  const issues = []
  let mqtt = 'Không xác định'
  if (presenceStatus === 'ok') {
    mqtt = presence?.status === 'ONLINE' ? 'Đang kết nối' : presence?.status === 'STALE' ? 'Heartbeat quá hạn' : 'Mất kết nối (LWT)'
    if (presence?.status === 'STALE') issues.push('Heartbeat quá hạn — thiết bị không gửi tín hiệu định kỳ.')
    if (presence?.status === 'OFFLINE') issues.push('Thiết bị đã ngắt kết nối MQTT (LWT offline).')
  } else if (presenceStatus === 'never') {
    mqtt = 'Chưa từng kết nối'
    issues.push('Thiết bị đã đăng ký nhưng chưa từng gửi heartbeat tới IoT Service.')
  } else if (presenceStatus === 'unavailable') {
    mqtt = 'Không xác định (IoT không khả dụng)'
  }

  const rssi = telemetry?.networkRssi ?? null
  const rssiSource = telemetry ? metricSource(telemetry, 'rssi') : null

  const sensors = telemetry
    ? SENSOR_ROWS.map((row) => {
        const value = telemetry[row.key]
        const source = metricSource(telemetry, row.key)
        return value == null
          ? { name: row.name, status: 'UNAVAILABLE', value: 'Không có dữ liệu', source }
          : { name: row.name, status: 'REPORTING', value: `${row.fmt(value)} · ${sourceLabel(source)}`, source }
      })
    : []

  const actuators = telemetry?.actuators
    ? ACTUATOR_ROWS.map((row) => ({
        name: row.name,
        status: 'UNSUPPORTED',
        value: `${telemetry.actuators[row.key] ? 'BẬT' : 'TẮT'} (báo cáo) · chưa hỗ trợ giám sát sức khỏe`,
      }))
    : []

  return {
    ...baseNode,
    lastHeartbeat: presence?.lastHeartbeatAt ? formatRelativeTime(presence.lastHeartbeatAt) : baseNode.lastHeartbeat,
    connectivity: {
      mqtt,
      wifi: '--',
      rssi,
      rssiSource: rssi != null && rssiSource && rssiSource !== 'PHYSICAL' ? sourceLabel(rssiSource) : null,
      ip: presence?.ip ? `${presence.ip}${presence?.mockMode === true ? ' (Mô phỏng)' : ''}` : null,
      lastHeartbeat: presence?.lastHeartbeatAt ? formatRelativeTime(presence.lastHeartbeatAt) : '--',
    },
    sensors,
    actuators,
    issues,
    telemetryTimestamp: telemetry?.timestamp || null,
    mockMode: presence?.mockMode ?? null,
  }
}

export function useNodeIoTDiagnostics(node) {
  const nodeId = node?.id || null
  const [detail, setDetail] = useState({ nodeId: null, loading: false, enriched: null })

  useEffect(() => {
    if (USE_MOCK || !nodeId) return undefined
    const controller = new AbortController()
    const id = encodeURIComponent(nodeId)
    Promise.allSettled([
      apiClient.get(`/api/iot/devices/${id}/presence`, { signal: controller.signal }),
      telemetryApi.getDeviceLatest(nodeId, { signal: controller.signal }),
    ]).then(([presence, telemetry]) => {
      if (controller.signal.aborted) return
      const presenceStatus = presence.status === 'fulfilled'
        ? 'ok'
        : Number(presence.reason?.status ?? presence.reason?.statusCode) === 404
          ? 'never'
          : 'unavailable'
      setDetail({
        nodeId,
        loading: false,
        enriched: { presence: presence.status === 'fulfilled' ? presence.value : null, presenceStatus,
          telemetry: telemetry.status === 'fulfilled' ? normalizeTelemetry(telemetry.value, false) : null },
      })
    })
    return () => controller.abort()
  }, [nodeId])

  if (!node || USE_MOCK) return node
  if (detail.nodeId !== nodeId || detail.loading || !detail.enriched) {
    return { ...node, loading: true }
  }
  return buildNodeDiagnostics(node, detail.enriched.presence, detail.enriched.presenceStatus, detail.enriched.telemetry)
}
