import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentTabs from '../../../components/features/farm-owner/environment/EnvironmentTabs'
import EnvironmentSelect from '../../../components/ui/Select'
import Toggle from '../../../components/features/farm-owner/environment/Toggle'
import AutomaticRulesPanel from '../../../components/features/farm-owner/environment/AutomaticRulesPanel'
import ActuatorControlPanel from '../../../components/features/farm-owner/environment/ActuatorControlPanel'
import { controlFarms as defaultMockFarms } from '../../../components/features/farm-owner/environment/environmentMockData'
import { useFarms } from '../../../features/farms/hooks/useFarms'
import { devicesApi } from '../../../api/modules/devicesApi.js'
import './EnvironmentControlPage.css'

const DEFAULT_ZONE_CONTROL_STATE = {
  mode: 'AUTO',
  rules: {
    temperature: { active: true, target: 28.5, min: 27, max: 31 },
    humidity: { active: true, target: 80, min: 75, max: 90 },
  },
  actuators: {
    misting: false,
    ventilation: true,
    heating: false,
    humidifier: false,
  },
}

function EnvironmentControlPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
  } = useFarms()

  const effectiveZones =
    zones.length > 0
      ? zones.map((z, idx) => ({
          ...z,
          controller: `ESP32-CTRL-${String(idx + 1).padStart(2, '0')}`,
          lastSync: 'Vừa xong',
        }))
      : selectedFarm?.zones || defaultMockFarms[0]?.zones || []

  const [selectedZoneId, setSelectedZoneId] = useState('')

  const [zoneState, setZoneState] = useState(() => {
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

  const selectedZone =
    effectiveZones.find((zone) => zone.id === selectedZoneId) ||
    effectiveZones[0] || {
      id: 'default-zone',
      name: 'Khu vực 1',
      controller: 'ESP32-CTRL-01',
      lastSync: 'Vừa xong',
    }

  const currentState = zoneState[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE
  const isManual = currentState.mode === 'MANUAL'

  const handleModeRequest = (mode) => {
    if (mode === currentState.mode) return

    if (mode === 'MANUAL') {
      setManualConfirmOpen(true)
      return
    }

    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
        mode: 'AUTO',
      },
    }))

    setRuleNotice(
      `Đã chuyển ${selectedZone.name} về AUTO. Controller tiếp tục áp dụng quy tắc cục bộ.`,
    )
  }

  const confirmManualMode = () => {
    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...(previous[selectedZone.id] || DEFAULT_ZONE_CONTROL_STATE),
        mode: 'MANUAL',
      },
    }))

    setManualConfirmOpen(false)
    setRuleNotice(
      `${selectedZone.name} đang ở MANUAL. Điều khiển tự động theo ngưỡng đã tạm dừng.`,
    )
  }

  const updateActuator = async (key, value) => {
    if (!isManual) return

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

    const targetMap = {
      misting: 'misting',
      ventilation: 'fan',
      heating: 'heater',
      alarm: 'alarm',
    }
    const target = targetMap[key] || key
    try {
      await devicesApi.sendRelayCommand('SWC-DEMO-NODE-001', {
        target,
        state: value ? 1 : 0,
      })
      setRuleNotice(`Đã gửi lệnh ${value ? 'BẬT' : 'TẮT'} ${target.toUpperCase()} tới ESP32 thành công.`)
    } catch (err) {
      console.warn('Lỗi gửi lệnh rơ-le:', err)
    }
  }

  const updateRule = (group, key, value) => {
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

  const activeActuatorCount = Object.values(currentState.actuators).filter(
    Boolean,
  ).length

  return (
    <AppLayout>
      <div className="control-page">
        <section className="control-page-heading">
          <div>
            <span className="control-eyebrow">ENVIRONMENT CONTROLS</span>
            <h1>Điều khiển môi trường</h1>
            <p>
              Cấu hình tự động theo ngưỡng an toàn hoặc can thiệp thủ công theo
              từng khu vực.
            </p>
          </div>
        </section>

        <EnvironmentTabs />

        <section className="control-context-bar">
          <div className="control-context-heading">
            <span className="control-step-tag">Khu vực điều khiển</span>
            <h2>Chọn khu vực điều khiển</h2>
            <p>
              Mọi thay đổi bên dưới chỉ áp dụng cho khu vực đang được chọn.
            </p>
          </div>

          <div className="control-context-fields">
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
              }}
            />

            <EnvironmentSelect
              label="Khu vực"
              value={selectedZone.id}
              options={effectiveZones.map((zone) => ({
                value: zone.id,
                label: zone.name,
              }))}
              onChange={(zoneId) => {
                setSelectedZoneId(zoneId)
                setRuleNotice('')
              }}
            />

            <div className="control-controller-field">
              <span>Controller Node</span>
              <strong>{selectedZone.controller}</strong>
              <small>
                <i className="online-dot" />
                Online · {selectedZone.lastSync}
              </small>
            </div>
          </div>
        </section>

        <section className="control-section">
          <div className="control-section-title">
            <span>01</span>
            <div>
              <small>OPERATION MODE</small>
              <h2>Chế độ vận hành</h2>
              <p>
                Xác định controller tự vận hành hay nhận lệnh trực tiếp từ
                người dùng.
              </p>
            </div>
          </div>

          <div className="control-mode-layout">
            <div className="control-mode-card">
              <div className="control-mode-top">
                <div>
                  <span className="control-mini-label">CURRENT MODE</span>
                  <h3>{currentState.mode}</h3>
                </div>

                <span
                  className={`mode-status-badge ${
                    isManual ? 'manual' : 'auto'
                  }`}
                >
                  <i />
                  {isManual ? 'Điều khiển thủ công' : 'Tự động cục bộ'}
                </span>
              </div>

              <div className="control-mode-switcher">
                <button
                  type="button"
                  className={!isManual ? 'active' : ''}
                  onClick={() => handleModeRequest('AUTO')}
                >
                  <span className="mode-option-icon">
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
                    <small>ESP32 tự điều khiển theo ngưỡng</small>
                  </span>
                </button>

                <button
                  type="button"
                  className={isManual ? 'active manual' : ''}
                  onClick={() => handleModeRequest('MANUAL')}
                >
                  <span className="mode-option-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <rect x="5" y="11" width="14" height="10" rx="2" />
                      <path d="M8 11V7a4 4 0 0 1 8 0v4" />
                    </svg>
                  </span>

                  <span>
                    <strong>MANUAL</strong>
                    <small>Bật/tắt thủ công từng thiết bị</small>
                  </span>
                </button>
              </div>

              {ruleNotice && (
                <div className="control-notice-banner">
                  <span className="notice-dot" />
                  <p>{ruleNotice}</p>
                </div>
              )}
            </div>

            <div className="control-fail-safe-card">
              <span className="control-mini-label">FAIL-SAFE MECHANISM</span>
              <h4>Bảo vệ cục bộ ESP32</h4>
              <p>
                Khi mất kết nối Gateway hoặc đám mây, ESP32 tự động giữ ngưỡng an
                toàn cục bộ để đảm bảo đàn yến không bị sốc nhiệt hay thiếu ẩm.
              </p>

              <ul className="fail-safe-checklist">
                <li>
                  <i /> Tự động chuyển AUTO sau 30 phút ở MANUAL
                </li>
                <li>
                  <i /> Cắt phun sương nếu độ ẩm vượt 92%
                </li>
                <li>
                  <i /> Cắt sưởi nếu nhiệt độ vượt 33°C
                </li>
              </ul>
            </div>
          </div>
        </section>

        <section className="control-section">
          <div className="control-section-title">
            <span>02</span>
            <div>
              <small>SETPOINTS & RULES</small>
              <h2>Quy tắc tự động</h2>
              <p>
                Cấu hình ngưỡng kích hoạt và mục tiêu duy trì cho chế độ AUTO.
              </p>
            </div>
          </div>

          <AutomaticRulesPanel
            rules={currentState.rules}
            disabled={isManual}
            onUpdateRule={updateRule}
          />
        </section>

        <section className="control-section">
          <div className="control-section-title">
            <span>03</span>
            <div>
              <small>ACTUATORS</small>
              <h2>Điều khiển thiết bị chấp hành</h2>
              <p>
                Trạng thái rơ-le và công tắc chấp hành tại {selectedZone.name}.
              </p>
            </div>

            <span className="actuators-active-count">
              {activeActuatorCount}/4 thiết bị đang chạy
            </span>
          </div>

          <ActuatorControlPanel
            actuators={currentState.actuators}
            isManual={isManual}
            onToggleActuator={updateActuator}
          />
        </section>

        {manualConfirmOpen && (
          <div className="control-modal-overlay">
            <div className="control-modal-card">
              <div className="control-modal-icon">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z" />
                  <line x1="12" y1="9" x2="12" y2="13" />
                  <line x1="12" y1="17" x2="12.01" y2="17" />
                </svg>
              </div>

              <h3>Xác nhận chuyển sang điều khiển thủ công</h3>

              <p>
                Chế độ MANUAL sẽ <strong>tạm dừng quy tắc tự động</strong> của{' '}
                {selectedZone.name}. Thiết bị có thể hoạt động liên tục nếu bạn
                không chủ động tắt.
              </p>

              <div className="control-modal-actions">
                <button
                  type="button"
                  className="modal-cancel-btn"
                  onClick={() => setManualConfirmOpen(false)}
                >
                  Hủy bỏ
                </button>

                <button
                  type="button"
                  className="modal-confirm-btn"
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
