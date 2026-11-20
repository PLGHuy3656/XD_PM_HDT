import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentTabs from '../../../components/features/farm-owner/environment/EnvironmentTabs'
import EnvironmentSelect from '../../../components/ui/Select'
import AutomaticRulesPanel from '../../../components/features/farm-owner/environment/AutomaticRulesPanel'
import ActuatorControlPanel from '../../../components/features/farm-owner/environment/ActuatorControlPanel'
import { ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'
import { controlFarms as defaultMockFarms } from '../../../components/features/farm-owner/environment/environmentMockData'
import { useFarms } from '../../../features/farms/hooks/useFarms'
import { useTelemetry } from '../../../features/telemetry/hooks/useTelemetry'
import { SERVICE_STATE } from '../../../api/serviceStatus.js'
import { USE_MOCK } from '../../../api/config.js'
import apiClient from '../../../api/client.js'
import {
  formatRelativeTime,
  isSimulatedTelemetry,
  overallSource,
} from '../../../features/telemetry/provenance.js'
import './EnvironmentControlPage.css'

const ACTUATOR_TO_IOT_TARGET = {
  misting: 'misting',
  ventilation: 'fan',
  heating: 'heater',
  alarm: 'alarm',
}

const TERMINAL_COMMAND_STATUSES = ['SUCCESS', 'FAILED', 'ERROR', 'TIMEOUT']
const ACK_POLL_INTERVAL_MS = 1000
const ACK_POLL_GRACE_MS = 5000
const ACK_POLL_FALLBACK_MS = 30000

/**
 * INT01-R1: follow the SERVER-authoritative command lifecycle until it is terminal.
 * The server owns the deadline (expiresAt) and moves the command to TIMEOUT itself; the UI never
 * invents a TIMEOUT. If the server state cannot be read before expiresAt + grace (network), the
 * result is UNCONFIRMED — not SUCCESS and not a fake TIMEOUT.
 */
async function pollIoTCommandAck(dispatched) {
  const commandId = dispatched?.commandId
  if (!commandId) {
    return { status: 'UNCONFIRMED', ackMessage: 'Máy chủ không trả về mã lệnh.' }
  }
  if (TERMINAL_COMMAND_STATUSES.includes(dispatched.status)) return dispatched
  const expiresAtMs = dispatched.expiresAt ? new Date(dispatched.expiresAt).getTime() : NaN
  const stopAt = Number.isFinite(expiresAtMs)
    ? expiresAtMs + ACK_POLL_GRACE_MS
    : Date.now() + ACK_POLL_FALLBACK_MS
  let last = dispatched
  while (Date.now() <= stopAt) {
    await new Promise((resolve) => setTimeout(resolve, ACK_POLL_INTERVAL_MS))
    try {
      last = await apiClient.get(`/api/iot/commands/${commandId}`)
    } catch {
      continue
    }
    if (last?.isTerminal || TERMINAL_COMMAND_STATUSES.includes(last?.status)) return last
  }
  return {
    ...last,
    status: 'UNCONFIRMED',
    ackMessage: `Chưa đọc được trạng thái cuối từ máy chủ (lần cuối: ${last?.status || 'không rõ'}).`,
  }
}

const COMMAND_RESULT_UI = {
  FAILED: { state: 'failed', label: 'Thiết bị từ chối (FAILED)' },
  ERROR: { state: 'error', label: 'Thiết bị báo lỗi (ERROR)' },
  TIMEOUT: { state: 'timeout', label: 'Hết hạn chờ ACK (TIMEOUT từ máy chủ)' },
  UNCONFIRMED: { state: 'unconfirmed', label: 'Chưa xác nhận' },
}

function describeCommandResult(cmd) {
  const ui = COMMAND_RESULT_UI[cmd?.status] || COMMAND_RESULT_UI.UNCONFIRMED
  const late = cmd?.lateAckStatus ? ` · Thiết bị phản hồi muộn: ${cmd.lateAckStatus} (không được tính)` : ''
  return { state: ui.state, message: `${ui.label}: ${cmd?.ackMessage || 'Không nhận được ACK hợp lệ.'}${late}` }
}

const DEFAULT_ZONE_CONTROL_STATE = {
  mode: 'AUTO',
  rules: {
    temperature: { active: true, target: 28.5, min: 27, max: 31 },
    humidity: { active: true, target: 80, min: 75, max: 90 },
  },
  actuators: {
    misting: false,
    ventilation: false,
    heating: false,
  },
}

function EnvironmentControlPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    error: farmsError,
  } = useFarms()

  const {
    telemetry,
    hasData: hasTelemetry,
    error: telemetryError,
    serviceState: iotState,
    isStale,
    refetch: refetchTelemetry,
  } = useTelemetry(selectedFarmId)

  const iotUnavailable = !USE_MOCK && iotState === SERVICE_STATE.UNAVAILABLE
  const iotConnected = USE_MOCK || iotState === SERVICE_STATE.AVAILABLE
  const liveNodeId = !USE_MOCK ? telemetry?.deviceId || null : null
  // Actuator command execution requires a verified live IoT control API & active device (or explicit mock mode)
  const iotControlAvailable = USE_MOCK || (iotConnected && Boolean(liveNodeId))

  // INT01-R1: controller identity and sync time come from live telemetry only (no generated names)
  const controllerLabel = USE_MOCK ? null : liveNodeId || 'Chưa có bộ điều khiển gửi dữ liệu'
  const syncLabel = USE_MOCK
    ? null
    : iotUnavailable
      ? 'Chưa kết nối dịch vụ IoT'
      : telemetry?.timestamp
        ? `${isStale ? 'Dữ liệu cũ · ' : 'Cập nhật '}${formatRelativeTime(telemetry.timestamp)}`
        : 'Chưa có dữ liệu bộ điều khiển'
  const simulated = !USE_MOCK && isSimulatedTelemetry(telemetry)
  const sourceKind = USE_MOCK ? 'MOCK' : telemetry ? overallSource(telemetry) : null

  const effectiveZones =
    zones.length > 0
      ? zones.map((z) => ({
          ...z,
          controller: controllerLabel,
          lastSync: syncLabel,
        }))
      : selectedFarm?.zones || (USE_MOCK ? defaultMockFarms[0]?.zones : []) || []

  const [selectedZoneId, setSelectedZoneId] = useState('')
  // View tab (AUTO vs MANUAL) is purely for navigation/inspection — never sends commands on switch
  const [activeView, setActiveView] = useState('AUTO')
  const [commandStatus, setCommandStatus] = useState({})

  const [zoneState, setZoneState] = useState(() => {
    if (!USE_MOCK) return {}
    const state = {}
    defaultMockFarms.forEach((farm) => {
      farm.zones.forEach((zone) => {
        state[zone.id] = {
          mode: zone.mode,
          rules: {
            temperature: { ...zone.rules.temperature },
            humidity: { ...zone.rules.humidity },
          },
          actuators: { ...zone.actuators },
        }
      })
    })
    return state
  })

  const [manualConfirmOpen, setManualConfirmOpen] = useState(false)
  const [ruleNotice, setRuleNotice] = useState('')

  const activeZoneId = effectiveZones.some((z) => z.id === selectedZoneId)
    ? selectedZoneId
    : effectiveZones[0]?.id || ''

  const selectedZone =
    effectiveZones.find((zone) => zone.id === activeZoneId) || {
      id: 'default-zone',
      name: effectiveZones.length === 0 ? 'Chưa có khu vực' : 'Khu vực 1',
      controller: controllerLabel || 'Chưa kết nối',
      lastSync: syncLabel || 'Chưa có dữ liệu bộ điều khiển',
    }

  const storedState = zoneState[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE
  // INT01-R1: in real mode the displayed relay states are what the device REPORTS in telemetry,
  // so UI and device can never disagree (e.g. after TIMEOUT or a late execution).
  const reportedActuators = !USE_MOCK && telemetry?.actuators
    ? {
        misting: Boolean(telemetry.actuators.misting),
        ventilation: Boolean(telemetry.actuators.fan),
        heating: Boolean(telemetry.actuators.heater),
      }
    : null
  const currentState = reportedActuators ? { ...storedState, actuators: reportedActuators } : storedState
  // Verified controller mode comes strictly from live telemetry in real mode (never fabricated by tab switch)
  const verifiedMode = USE_MOCK
    ? currentState.mode
    : iotControlAvailable
      ? telemetry?.mode || null
      : null
  const isManualActive = verifiedMode === 'MANUAL'

  const sendModeConfigCommand = async (targetMode) => {
    if (USE_MOCK) return true
    if (!liveNodeId) return false
    const rules = currentState.rules || DEFAULT_ZONE_CONTROL_STATE.rules
    try {
      const dispatched = await apiClient.post(`/api/iot/devices/${liveNodeId}/commands/config`, {
        targetTemp: Number(rules.temperature?.max ?? 28.5),
        targetHum: Number(rules.humidity?.min ?? 80.0),
        isAutoMode: targetMode === 'AUTO',
      })
      const finalCmd = await pollIoTCommandAck(dispatched)
      refetchTelemetry()
      if (finalCmd.status === 'SUCCESS') {
        return true
      }
      setRuleNotice(`Lệnh chuyển chế độ ${targetMode} không thành công — ${describeCommandResult(finalCmd).message}`)
      return false
    } catch (err) {
      setRuleNotice(`Không thể gửi lệnh chuyển chế độ: ${err?.message || 'Lỗi kết nối IoT.'}`)
      return false
    }
  }

  const handleModeAction = async (targetMode) => {
    if (!iotControlAvailable || targetMode === verifiedMode) return

    if (targetMode === 'MANUAL') {
      setManualConfirmOpen(true)
      return
    }

    const ok = await sendModeConfigCommand('AUTO')
    if (!ok) return
    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
        mode: 'AUTO',
      },
    }))
    setActiveView('AUTO')
    setRuleNotice(
      `Đã chuyển ${selectedZone.name} về AUTO (đã nhận ACK từ bộ điều khiển).`,
    )
  }

  const confirmManualMode = async () => {
    if (!iotControlAvailable) {
      setManualConfirmOpen(false)
      return
    }
    setManualConfirmOpen(false)
    const ok = await sendModeConfigCommand('MANUAL')
    if (!ok) return
    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
        mode: 'MANUAL',
      },
    }))
    setActiveView('MANUAL')
    setRuleNotice(
      `${selectedZone.name} đã chuyển sang MANUAL (đã nhận ACK từ bộ điều khiển).`,
    )
  }

  const updateActuator = async (key, value) => {
    if (!iotControlAvailable || !isManualActive) return

    setCommandStatus((prev) => ({ ...prev, [key]: { state: 'pending', message: 'Đang chờ thiết bị xác nhận ACK...' } }))

    if (USE_MOCK) {
      setZoneState((previous) => ({
        ...previous,
        [selectedZone.id]: {
          ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
          actuators: {
            ...(previous[selectedZone.id]?.actuators || DEFAULT_ZONE_CONTROL_STATE.actuators),
            [key]: value,
          },
        },
      }))
      setCommandStatus((prev) => ({ ...prev, [key]: { state: 'acked' } }))
      return
    }

    const iotTarget = ACTUATOR_TO_IOT_TARGET[key] || key
    try {
      const dispatched = await apiClient.post(`/api/iot/devices/${liveNodeId}/commands/relay`, {
        target: iotTarget,
        state: Boolean(value),
      })
      const finalCmd = await pollIoTCommandAck(dispatched)
      if (finalCmd.status === 'SUCCESS') {
        setZoneState((previous) => ({
          ...previous,
          [selectedZone.id]: {
            ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
            actuators: {
              ...(previous[selectedZone.id]?.actuators || DEFAULT_ZONE_CONTROL_STATE.actuators),
              [key]: value,
            },
          },
        }))
        setCommandStatus((prev) => ({
          ...prev,
          [key]: { state: 'acked', status: 'SUCCESS', target: Boolean(value), awaitingConfirm: true, message: 'Thiết bị đã xác nhận ACK.' },
        }))
        // Stop showing "waiting for telemetry" after a bounded window; the badge then shows the device-reported state
        setTimeout(() => {
          setCommandStatus((prev) =>
            prev[key]?.state === 'acked' ? { ...prev, [key]: { ...prev[key], awaitingConfirm: false } } : prev,
          )
        }, 10000)
        refetchTelemetry()
      } else {
        // Displayed relay state stays the DEVICE-REPORTED one (telemetry), never the requested value
        setCommandStatus((prev) => ({
          ...prev,
          [key]: { ...describeCommandResult(finalCmd), status: finalCmd.status },
        }))
        refetchTelemetry()
      }
    } catch (err) {
      setCommandStatus((prev) => ({
        ...prev,
        [key]: { state: 'failed', message: err?.message || 'Gửi lệnh điều khiển thất bại.' },
      }))
    }
  }

  const updateRule = (group, key, value) => {
    if (!iotControlAvailable) return
    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
        rules: {
          ...(previous[selectedZone.id]?.rules || DEFAULT_ZONE_CONTROL_STATE.rules),
          [group]: {
            ...(previous[selectedZone.id]?.rules?.[group] ||
              DEFAULT_ZONE_CONTROL_STATE.rules[group]),
            [key]: value,
          },
        },
      },
    }))
  }

  const handleSaveRules = () => {
    if (!iotControlAvailable) return
    setRuleNotice(`Đã lưu cấu hình quy tắc cho ${selectedZone.name}.`)
  }

  const modeBadgeLabel = verifiedMode
    ? isManualActive
      ? 'Đang vận hành: MANUAL'
      : 'Đang vận hành: AUTO'
    : iotUnavailable
      ? 'Chưa xác định chế độ · Chưa kết nối IoT'
      : 'Chưa xác minh trạng thái bộ điều khiển'

  return (
    <AppLayout>
      <div className="environment-control-page">
        <header className="control-header-row">
          <div className="control-header-copy">
            <span className="environment-control-eyebrow">ENVIRONMENT CONTROLS</span>
            <h1>Điều khiển môi trường</h1>
            <p>Cấu hình ngưỡng tự động hoặc điều khiển thủ công thiết bị theo khu vực.</p>
          </div>

          <EnvironmentTabs />
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}

        {iotUnavailable && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ IoT"
            message={
              telemetryError && !/upstream|503|unreachable|network/i.test(String(telemetryError))
                ? telemetryError
                : 'Bạn vẫn có thể xem trước giao diện AUTO/MANUAL, nhưng mọi thao tác gửi lệnh điều khiển đang tạm khóa cho đến khi IoT Service hoạt động.'
            }
            onRetry={refetchTelemetry}
          />
        )}

        {!USE_MOCK && !iotUnavailable && iotState === SERVICE_STATE.AVAILABLE && simulated && (
          <div className="control-simulation-banner" role="note" data-testid="control-simulation-banner">
            <strong>Điều khiển mô phỏng — ESP32 Simulator</strong>
            <p>
              Bộ điều khiển {liveNodeId || ''} đang là ESP32 Simulator. Lệnh, ACK và trạng thái rơ-le chỉ kiểm thử
              vòng đời lệnh; không có máy phun sương, quạt hay sưởi vật lý nào được điều khiển.
            </p>
          </div>
        )}

        {!USE_MOCK && !iotUnavailable && iotState === SERVICE_STATE.AVAILABLE && !simulated && (
          <ErrorMessage
            variant="info"
            title={sourceKind === 'PHYSICAL' ? 'Đã kết nối bộ điều khiển' : 'Nguồn thiết bị chưa xác minh'}
            message={
              sourceKind === 'PHYSICAL'
                ? `Telemetry và lệnh đang đi qua bộ điều khiển ${liveNodeId || ''} của ${selectedFarm?.name || 'nhà yến'}.`
                : `Thiết bị ${liveNodeId || ''} không khai báo nguồn dữ liệu; chưa xác nhận đây là phần cứng thật.`
            }
          />
        )}

        {farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến nào"
            description="Hãy đăng ký nhà yến và chờ Admin phê duyệt trước khi cấu hình điều khiển môi trường."
          />
        ) : (
          <>
            <section className="control-context-bar control-context-bar--compact">
              <div className="control-context-fields control-context-fields--compact">
                <EnvironmentSelect
                  label="Nhà yến"
                  value={selectedFarmId || ''}
                  options={farms.map((farm) => ({
                    value: farm.id,
                    label: farm.name,
                  }))}
                  onChange={(farmId) => {
                    setSelectedFarmId(farmId)
                    setSelectedZoneId('')
                    setRuleNotice('')
                    setCommandStatus({})
                  }}
                />

                <EnvironmentSelect
                  label="Khu vực"
                  value={activeZoneId}
                  options={
                    effectiveZones.length > 0
                      ? effectiveZones.map((zone) => ({
                          value: zone.id,
                          label: zone.name,
                        }))
                      : [{ value: '', label: 'Chưa có khu vực' }]
                  }
                  onChange={(zoneId) => {
                    setSelectedZoneId(zoneId)
                    setRuleNotice('')
                    setCommandStatus({})
                  }}
                />

                <div className="control-controller-field">
                  <span>Controller Node</span>
                  <strong>{selectedZone.controller}</strong>
                  <small>
                    <i className={iotConnected && hasTelemetry && !isStale ? 'online-dot' : 'offline-dot'} />
                    {selectedZone.lastSync}
                    {simulated && <span className="control-source-chip">Mô phỏng</span>}
                  </small>
                </div>
              </div>
            </section>

            <section className="control-mode-bar" aria-label="Chọn chế độ xem điều khiển">
              <div className="control-mode-tabs" role="tablist" aria-label="Chế độ điều khiển">
                <button
                  type="button"
                  role="tab"
                  aria-selected={activeView === 'AUTO'}
                  className={`control-mode-tab ${activeView === 'AUTO' ? 'is-active' : ''}`}
                  onClick={() => setActiveView('AUTO')}
                >
                  <span className="control-mode-tab__icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 3v3" />
                      <path d="M12 18v3" />
                      <path d="m4.2 4.2 2.1 2.1" />
                      <path d="m17.7 17.7 2.1 2.1" />
                      <path d="M3 12h3" />
                      <path d="M18 12h3" />
                      <path d="m4.2 19.8 2.1-2.1" />
                      <path d="m17.7 6.3 2.1-2.1" />
                      <circle cx="12" cy="12" r="4" />
                    </svg>
                  </span>
                  <span>
                    <strong>AUTO</strong>
                    <small>Quy tắc theo ngưỡng</small>
                  </span>
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={activeView === 'MANUAL'}
                  className={`control-mode-tab ${activeView === 'MANUAL' ? 'is-active is-manual' : ''}`}
                  onClick={() => setActiveView('MANUAL')}
                >
                  <span className="control-mode-tab__icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <rect x="5" y="11" width="14" height="10" rx="2" />
                      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                    </svg>
                  </span>
                  <span>
                    <strong>MANUAL</strong>
                    <small>Bật/tắt thiết bị thủ công</small>
                  </span>
                </button>
              </div>

              <div className="control-mode-meta">
                <span
                  className={`mode-status-badge ${
                    !verifiedMode ? 'unknown' : isManualActive ? 'manual' : 'auto'
                  }`}
                >
                  <i />
                  {modeBadgeLabel}
                </span>

                {iotControlAvailable && verifiedMode !== activeView && (
                  <button
                    type="button"
                    className="control-mode-apply-btn"
                    onClick={() => handleModeAction(activeView)}
                  >
                    {activeView === 'MANUAL'
                      ? 'Kích hoạt MANUAL'
                      : 'Chuyển về AUTO'}
                  </button>
                )}
              </div>
            </section>

            {ruleNotice && (
              <div className="control-mode-note control-mode-note--inline">
                <span>i</span>
                <p>{ruleNotice}</p>
              </div>
            )}

            <div className="control-mode-stage" role="tabpanel">
              {activeView === 'AUTO' ? (
                <AutomaticRulesPanel
                  zone={selectedZone}
                  rules={currentState.rules}
                  disabled={!iotControlAvailable || isManualActive}
                  isConnected={iotConnected}
                  unavailableMessage={
                    !iotControlAvailable
                      ? iotUnavailable
                        ? 'Giá trị ngưỡng hiển thị là mức tham chiếu mặc định (chưa đồng bộ ESP32). Nút lưu sẽ mở khi IoT Service hoạt động.'
                        : 'Chưa xác minh đồng bộ với bộ điều khiển ESP32 cho khu vực này.'
                      : isManualActive
                        ? 'Khu vực đang ở chế độ MANUAL. Chuyển về AUTO để chỉnh sửa và áp dụng ngưỡng tự động.'
                        : null
                  }
                  onRuleChange={updateRule}
                  onSave={handleSaveRules}
                />
              ) : (
                <ActuatorControlPanel
                  actuators={currentState.actuators}
                  isManual={isManualActive}
                  disabled={!iotControlAvailable}
                  commandStatus={commandStatus}
                  onActuatorChange={updateActuator}
                  simulated={simulated}
                />
              )}
            </div>
          </>
        )}

        {manualConfirmOpen && (
          <div className="manual-modal-backdrop">
            <div className="manual-modal" role="dialog" aria-modal="true">
              <div className="manual-modal-icon">!</div>

              <h2>Xác nhận chuyển sang điều khiển thủ công</h2>

              <p>
                Chế độ MANUAL sẽ <strong>tạm dừng quy tắc tự động</strong> của{' '}
                {selectedZone.name}. Thiết bị có thể hoạt động liên tục nếu bạn không chủ động tắt.
              </p>

              <div className="manual-modal-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setManualConfirmOpen(false)}
                >
                  Hủy bỏ
                </button>

                <button
                  type="button"
                  className="primary"
                  onClick={confirmManualMode}
                >
                  Xác nhận chuyển MANUAL
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  )
}

export default EnvironmentControlPage
