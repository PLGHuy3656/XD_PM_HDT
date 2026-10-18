import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentTabs from '../../../components/features/farm-owner/environment/EnvironmentTabs'
import EnvironmentSelect from '../../../components/ui/Select'
import Toggle from '../../../components/features/farm-owner/environment/Toggle'
import AutomaticRulesPanel from '../../../components/features/farm-owner/environment/AutomaticRulesPanel'
import ActuatorControlPanel from '../../../components/features/farm-owner/environment/ActuatorControlPanel'
import { controlFarms as farms } from '../../../components/features/farm-owner/environment/environmentMockData'
import './EnvironmentPage.css'
import './EnvironmentControlPage.css'

function EnvironmentControlPage() {
  const [selectedFarmId, setSelectedFarmId] = useState(farms[0].id)
  const [selectedZoneId, setSelectedZoneId] = useState(farms[0].zones[0].id)

  const [zoneState, setZoneState] = useState(() => {
    const state = {}

    farms.forEach((farm) => {
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

  const selectedFarm =
    farms.find((farm) => farm.id === selectedFarmId) || farms[0]

  const selectedZone =
    selectedFarm.zones.find((zone) => zone.id === selectedZoneId) ||
    selectedFarm.zones[0]

  const currentState = zoneState[selectedZone.id]
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
        ...previous[selectedZone.id],
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
        ...previous[selectedZone.id],
        mode: 'MANUAL',
      },
    }))

    setManualConfirmOpen(false)
    setRuleNotice(
      `${selectedZone.name} đang ở MANUAL. Điều khiển tự động theo ngưỡng đã tạm dừng.`,
    )
  }

  const updateActuator = (key, value) => {
    if (!isManual) return

    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...previous[selectedZone.id],
        actuators: {
          ...previous[selectedZone.id].actuators,
          [key]: value,
        },
      },
    }))
  }

  const updateRule = (group, key, value) => {
    setZoneState((previous) => ({
      ...previous,
      [selectedZone.id]: {
        ...previous[selectedZone.id],
        rules: {
          ...previous[selectedZone.id].rules,
          [group]: {
            ...previous[selectedZone.id].rules[group],
            [key]: Number(value),
          },
        },
      },
    }))

    setRuleNotice('')
  }

  const saveRules = () => {
    setRuleNotice(
      `Đã lưu cấu hình mock cho ${selectedZone.name}. Khi tích hợp Backend, cấu hình sẽ được đồng bộ xuống controller.`,
    )
  }

  return (
    <AppLayout>
      <div className="environment-control-page">
        <section className="environment-control-heading">
          <div>
            <span className="environment-control-eyebrow">
              ENVIRONMENT CONTROL
            </span>

            <h1>Điều khiển môi trường</h1>

            <p>
              Quản lý chế độ vận hành, quy tắc tự động và thiết bị điều khiển
              theo từng khu vực.
            </p>
          </div>

          <div className="environment-control-live">
            <span className="environment-control-live-dot" />
            Controller online
          </div>
        </section>

        <EnvironmentTabs />

        <section className="control-context-card">
          <div className="control-context-copy">
            <span className="control-mini-label">CONTROL CONTEXT</span>
            <h2>Chọn khu vực điều khiển</h2>
            <p>
              Mọi thay đổi bên dưới chỉ áp dụng cho khu vực đang được chọn.
            </p>
          </div>

          <div className="control-context-fields">
            <EnvironmentSelect
                label="Nhà yến"
                value={selectedFarmId}
                options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
                }))}
                onChange={(farmId) => {
                const farm = farms.find((item) => item.id === farmId)

                if (!farm) return

                setSelectedFarmId(farm.id)
                setSelectedZoneId(farm.zones[0].id)
                setRuleNotice('')
                }}
            />

            <EnvironmentSelect
                label="Khu vực"
                value={selectedZone.id}
                options={selectedFarm.zones.map((zone) => ({
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
                      <path d="M8 11V7a2 2 0 0 1 4 0v4" />
                      <path d="M12 10V5a2 2 0 0 1 4 0v6" />
                      <path d="M16 10V7a2 2 0 0 1 4 0v7c0 4-3 7-7 7h-1c-3 0-5-1-7-4l-2-3a2 2 0 0 1 3-2l2 2" />
                    </svg>
                  </span>

                  <span>
                    <strong>MANUAL</strong>
                    <small>Cho phép bật/tắt thiết bị trực tiếp</small>
                  </span>
                </button>
              </div>

              <div className={`control-mode-note ${isManual ? 'warning' : ''}`}>
                <span>
                  {isManual ? '!' : 'i'}
                </span>

                <p>
                  {isManual
                    ? 'Automatic control đang tạm dừng tại Khu vực này. Người dùng chịu trách nhiệm điều khiển các actuator.'
                    : 'Controller thực thi quy tắc ngay tại ESP32 và vẫn có thể tiếp tục AUTO khi mất kết nối cloud.'}
                </p>
              </div>
            </div>

            <div className="controller-health-card">
              <div className="controller-health-header">
                <div>
                  <span className="control-mini-label">CONTROLLER STATUS</span>
                  <h3>{selectedZone.controller}</h3>
                </div>

                <span className="controller-online-badge">ONLINE</span>
              </div>

              <div className="controller-health-grid">
                <div>
                  <span>Nhiệt độ hiện tại</span>
                  <strong>{selectedZone.temperature}°C</strong>
                </div>

                <div>
                  <span>Độ ẩm hiện tại</span>
                  <strong>{selectedZone.humidity}%</strong>
                </div>

                <div>
                  <span>Local control</span>
                  <strong>Available</strong>
                </div>

                <div>
                  <span>Đồng bộ gần nhất</span>
                  <strong>{selectedZone.lastSync}</strong>
                </div>
              </div>
            </div>
          </div>
        </section>

        <AutomaticRulesPanel
          zone={selectedZone}
          rules={currentState.rules}
          onRuleChange={updateRule}
          onSave={saveRules}
        />

        <ActuatorControlPanel
          actuators={currentState.actuators}
          isManual={isManual}
          onActuatorChange={updateActuator}
        />

        {ruleNotice && (
          <div className="control-toast" role="status">
            <span>✓</span>
            <p>{ruleNotice}</p>
            <button type="button" onClick={() => setRuleNotice('')}>
              ×
            </button>
          </div>
        )}

        {manualConfirmOpen && (
          <div
            className="manual-modal-backdrop"
            role="presentation"
            onMouseDown={() => setManualConfirmOpen(false)}
          >
            <div
              className="manual-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="manual-mode-title"
              onMouseDown={(event) => event.stopPropagation()}
            >
              <span className="manual-modal-icon">!</span>

              <span className="control-mini-label">MANUAL OVERRIDE</span>

              <h2 id="manual-mode-title">Chuyển sang MANUAL?</h2>

              <p>
                Điều khiển tự động tại <strong>{selectedZone.name}</strong> sẽ
                tạm dừng. Bạn có thể trực tiếp bật hoặc tắt phun sương, quạt và
                sưởi.
              </p>

              <div className="manual-modal-warning">
                <strong>Lưu ý</strong>
                <span>
                  Hãy theo dõi nhiệt độ và độ ẩm trong thời gian sử dụng chế độ
                  thủ công.
                </span>
              </div>

              <div className="manual-modal-actions">
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setManualConfirmOpen(false)}
                >
                  Hủy
                </button>

                <button
                  type="button"
                  className="primary"
                  onClick={confirmManualMode}
                >
                  Chuyển sang MANUAL
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