import { useEffect, useState } from 'react'
import { statusMeta } from './devicesMockData'
import { DeviceIcon } from './DeviceTable'
import apiClient from '../../../../api/client.js'
import { telemetryApi } from '../../../../api/modules/telemetryApi.js'
import { USE_MOCK } from '../../../../api/config.js'
import { normalizeTelemetry } from '../../../../features/telemetry/adapters/telemetryAdapter.js'
import {
  formatRelativeTime,
  metricSource,
  sourceLabel,
} from '../../../../features/telemetry/provenance.js'

/**
 * INT01-R1: device detail with live IoT data (presence + latest telemetry, both through the
 * Gateway with farm/device RBAC). Nothing is fabricated: missing values render as "--".
 */
const EMPTY_DETAIL = { loading: false, presence: null, telemetry: null, presenceStatus: null, error: null }

function useDeviceIoTDetail(nodeId) {
  const [entry, setEntry] = useState({ nodeId: null, data: EMPTY_DETAIL })

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
      setEntry({
        nodeId,
        data: {
          loading: false,
          presence: presence.status === 'fulfilled' ? presence.value : null,
          presenceStatus,
          telemetry: telemetry.status === 'fulfilled' ? normalizeTelemetry(telemetry.value, false) : null,
          error: null,
        },
      })
    })
    return () => controller.abort()
  }, [nodeId])

  if (USE_MOCK || !nodeId) return EMPTY_DETAIL
  return entry.nodeId === nodeId ? entry.data : { ...EMPTY_DETAIL, loading: true }
}

function DeviceDetailPanel({ device, zoneName, farmName, onClose }) {
  const iot = useDeviceIoTDetail(device?.nodeId || device?.code || null)

  if (!device) return null

  const status = statusMeta[device.status] || statusMeta.UNKNOWN
  const rssi = iot.telemetry?.networkRssi ?? device.signal ?? null
  const rssiSource = iot.telemetry ? metricSource(iot.telemetry, 'rssi') : null
  const lastHeartbeat = iot.presence?.lastHeartbeatAt || null
  const lastSeen = iot.presence?.lastSeen || device.lastSeenAt || null
  const mqttLabel = USE_MOCK
    ? '--'
    : iot.presenceStatus === 'ok'
      ? iot.presence?.status === 'ONLINE'
        ? 'Đang kết nối'
        : iot.presence?.status === 'STALE'
          ? 'Heartbeat quá hạn'
          : 'Mất kết nối (LWT)'
      : iot.presenceStatus === 'never'
        ? 'Chưa từng kết nối'
        : iot.presenceStatus === 'unavailable'
          ? 'Không xác định (IoT không khả dụng)'
          : '--'

  return (
    <section className="device-detail-panel" data-testid="owner-device-detail">
      <div className="device-detail-heading">
        <div className="device-detail-title">
          <span className={`device-type-icon large ${device.type.toLowerCase()}`}>
            <DeviceIcon type={device.type} />
          </span>

          <div>
            <span className="devices-section-label">DEVICE DETAIL</span>
            <h2>{device.name}</h2>
            <p>{device.nodeId || device.code || device.id}</p>
          </div>
        </div>

        <button type="button" className="device-detail-close" onClick={onClose} aria-label="Đóng chi tiết thiết bị">
          ×
        </button>
      </div>

      <div className="device-detail-grid">
        <div>
          <span>Mã node (node_id)</span>
          <strong>{device.nodeId || device.code || '--'}</strong>
        </div>

        <div>
          <span>Nhà yến</span>
          <strong>{farmName || '--'}</strong>
        </div>

        <div>
          <span>Khu vực</span>
          <strong>{zoneName || '--'}</strong>
        </div>

        <div>
          <span>Loại thiết bị</span>
          <strong>{device.typeLabel}</strong>
        </div>

        <div>
          <span>Trạng thái</span>
          <strong className={`device-detail-status ${status.className}`}>{status.label}</strong>
        </div>

        <div>
          <span>Kết nối MQTT</span>
          <strong>{iot.loading ? 'Đang tải…' : mqttLabel}</strong>
        </div>

        <div>
          <span>Heartbeat gần nhất</span>
          <strong>{lastHeartbeat ? formatRelativeTime(lastHeartbeat) : '--'}</strong>
        </div>

        <div>
          <span>Hoạt động gần nhất</span>
          <strong>{lastSeen ? formatRelativeTime(lastSeen) : device.lastSeen || '--'}</strong>
        </div>

        <div>
          <span>Tín hiệu Wi-Fi (RSSI)</span>
          <strong>
            {rssi != null ? `${rssi} dBm` : '--'}
            {rssi != null && rssiSource && rssiSource !== 'PHYSICAL' && (
              <span className="device-source-chip">{sourceLabel(rssiSource)}</span>
            )}
          </strong>
        </div>

        <div>
          <span>IP thiết bị báo cáo</span>
          <strong>
            {iot.presence?.ip || device.reportedIp || '--'}
            {(iot.presence?.ip || device.reportedIp) && iot.presence?.mockMode === true && (
              <span className="device-source-chip">Mô phỏng</span>
            )}
          </strong>
        </div>

        <div>
          <span>IP đăng ký</span>
          <strong>{device.registeredIp || '--'}</strong>
        </div>

        <div>
          <span>Firmware</span>
          <strong>{device.firmware || '--'}</strong>
        </div>
      </div>

      {iot.presence?.mockMode === true && (
        <div className="device-detail-note">
          <strong>Nguồn dữ liệu</strong>
          <p>Thiết bị báo cáo chế độ mô phỏng (mockMode) — số liệu không phải từ cảm biến vật lý.</p>
        </div>
      )}

      <div className="device-detail-note">
        <strong>Vai trò thiết bị</strong>
        <p>{device.description}</p>
      </div>
    </section>
  )
}

export default DeviceDetailPanel
