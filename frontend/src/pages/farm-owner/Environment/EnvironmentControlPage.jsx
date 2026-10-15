import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentTabs from './EnvironmentTabs'
import EnvironmentSelect from './EnvironmentSelect'
import './EnvironmentPage.css'
import './EnvironmentControlPage.css'
import './EnvironmentSelect.css'

const farms = [
  {
    id: 'farm-binh-chanh',
    name: 'Nhà yến Bình Chánh',
    zones: [
      {
        id: 'zone-a',
        name: 'Khu vực A',
        controller: 'ESP32-CTRL-01',
        status: 'online',
        lastSync: 'Vừa xong',
        temperature: 29.1,
        humidity: 82,
        mode: 'AUTO',
        rules: {
          temperature: { min: 27, max: 31 },
          humidity: { min: 75, max: 90 },
        },
        actuators: {
          misting: false,
          ventilation: true,
          heating: false,
        },
      },
      {
        id: 'zone-b',
        name: 'Khu vực B',
        controller: 'ESP32-CTRL-02',
        status: 'online',
        lastSync: '12 giây trước',
        temperature: 30.2,
        humidity: 73,
        mode: 'AUTO',
        rules: {
          temperature: { min: 27, max: 31 },
          humidity: { min: 75, max: 90 },
        },
        actuators: {
          misting: true,
          ventilation: false,
          heating: false,
        },
      },
      {
        id: 'zone-c',
        name: 'Khu vực C',
        controller: 'ESP32-CTRL-03',
        status: 'online',
        lastSync: '8 giây trước',
        temperature: 28.6,
        humidity: 85,
        mode: 'AUTO',
        rules: {
          temperature: { min: 27, max: 31 },
          humidity: { min: 75, max: 90 },
        },
        actuators: {
          misting: false,
          ventilation: false,
          heating: false,
        },
      },
      {
        id: 'zone-d',
        name: 'Khu vực D',
        controller: 'ESP32-CTRL-04',
        status: 'online',
        lastSync: '16 giây trước',
        temperature: 29.4,
        humidity: 80,
        mode: 'AUTO',
        rules: {
          temperature: { min: 27, max: 31 },
          humidity: { min: 75, max: 90 },
        },
        actuators: {
          misting: false,
          ventilation: true,
          heating: false,
        },
      },
      {
        id: 'zone-e',
        name: 'Khu vực E',
        controller: 'ESP32-CTRL-05',
        status: 'online',
        lastSync: '5 giây trước',
        temperature: 28.9,
        humidity: 84,
        mode: 'AUTO',
        rules: {
          temperature: { min: 27, max: 31 },
          humidity: { min: 75, max: 90 },
        },
        actuators: {
          misting: false,
          ventilation: false,
          heating: false,
        },
      },
    ],
  },
]

const actuatorMeta = {
  misting: {
    name: 'Phun sương',
    code: 'MISTING',
    description: 'Điều chỉnh và duy trì độ ẩm trong khu vực.',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3s-5 5.5-5 10a5 5 0 0 0 10 0c0-4.5-5-10-5-10Z" />
        <path d="M9.5 14.5c.5 1.2 1.4 1.8 2.7 1.9" />
      </svg>
    ),
  },
  ventilation: {
    name: 'Quạt thông gió',
    code: 'VENTILATION',
    description: 'Hỗ trợ lưu thông không khí và giảm nhiệt độ.',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="2" />
        <path d="M12 10c-1-4 1-6 3-6 2.5 0 3.5 3.5 1.5 6.5" />
        <path d="M14 12c4-1 6 1 6 3 0 2.5-3.5 3.5-6.5 1.5" />
        <path d="M12 14c1 4-1 6-3 6-2.5 0-3.5-3.5-1.5-6.5" />
        <path d="M10 12c-4 1-6-1-6-3 0-2.5 3.5-3.5 6.5-1.5" />
      </svg>
    ),
  },
  heating: {
    name: 'Sưởi',
    code: 'HEATING',
    description: 'Bổ sung nhiệt khi nhiệt độ xuống dưới ngưỡng.',
    icon: (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M13 3s1 3-1 5-1 4 1 5" />
        <path d="M8 6s1 2-.5 4-1 4 .5 5" />
        <path d="M17 7s1 2-.5 4-1 4 .5 5" />
        <path d="M5 20h14" />
      </svg>
    ),
  },
}

function Toggle({ checked, disabled, onChange, label }) {
  return (
    <button
      type="button"
      className={`control-toggle ${checked ? 'on' : ''}`}
      disabled={disabled}
      onClick={() => {
        if (!disabled) onChange(!checked)
      }}
      aria-pressed={checked}
      aria-label={label}
    >
      <span />
    </button>
  )
}

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

        <section className="control-section">
          <div className="control-section-title">
            <span>02</span>
            <div>
              <small>AUTOMATIC RULES</small>
              <h2>Quy tắc điều khiển tự động</h2>
              <p>
                Cấu hình khoảng môi trường mà controller sử dụng trong chế độ
                AUTO.
              </p>
            </div>
          </div>

          <div className="automatic-rules-card">
            <div className="automatic-rules-header">
              <div>
                <span className="control-mini-label">LOCAL RULE SET</span>
                <h3>{selectedZone.name}</h3>
              </div>

              <span className="rule-sync-badge">
                Đồng bộ với {selectedZone.controller}
              </span>
            </div>

            <div className="rule-list">
              <div className="rule-row">
                <div className="rule-identity temperature">
                  <span className="rule-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M9 14.5V5a3 3 0 0 1 6 0v9.5a5 5 0 1 1-6 0Z" />
                      <path d="M12 17V8" />
                    </svg>
                  </span>

                  <div>
                    <strong>Nhiệt độ</strong>
                    <small>Temperature range</small>
                  </div>
                </div>

                <div className="rule-range">
                  <label>
                    <span>Tối thiểu</span>
                    <div>
                      <input
                        type="number"
                        value={currentState.rules.temperature.min}
                        onChange={(event) =>
                          updateRule('temperature', 'min', event.target.value)
                        }
                      />
                      <b>°C</b>
                    </div>
                  </label>

                  <span className="range-line" />

                  <label>
                    <span>Tối đa</span>
                    <div>
                      <input
                        type="number"
                        value={currentState.rules.temperature.max}
                        onChange={(event) =>
                          updateRule('temperature', 'max', event.target.value)
                        }
                      />
                      <b>°C</b>
                    </div>
                  </label>
                </div>

                <div className="rule-behaviour">
                  <span>AUTO BEHAVIOUR</span>
                  <strong>
                    Sưởi khi thấp · Thông gió khi cao
                  </strong>
                </div>
              </div>

              <div className="rule-row">
                <div className="rule-identity humidity">
                  <span className="rule-icon">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M12 3s-6 6.5-6 11a6 6 0 0 0 12 0c0-4.5-6-11-6-11Z" />
                    </svg>
                  </span>

                  <div>
                    <strong>Độ ẩm</strong>
                    <small>Humidity range</small>
                  </div>
                </div>

                <div className="rule-range">
                  <label>
                    <span>Tối thiểu</span>
                    <div>
                      <input
                        type="number"
                        value={currentState.rules.humidity.min}
                        onChange={(event) =>
                          updateRule('humidity', 'min', event.target.value)
                        }
                      />
                      <b>%</b>
                    </div>
                  </label>

                  <span className="range-line" />

                  <label>
                    <span>Tối đa</span>
                    <div>
                      <input
                        type="number"
                        value={currentState.rules.humidity.max}
                        onChange={(event) =>
                          updateRule('humidity', 'max', event.target.value)
                        }
                      />
                      <b>%</b>
                    </div>
                  </label>
                </div>

                <div className="rule-behaviour">
                  <span>AUTO BEHAVIOUR</span>
                  <strong>Phun sương khi độ ẩm thấp</strong>
                </div>
              </div>
            </div>

            <div className="automatic-rules-footer">
              <div>
                <span className="rules-info-icon">i</span>
                <p>
                  Đây là dữ liệu mock ở Frontend. Khi tích hợp, Backend sẽ lưu
                  cấu hình và đồng bộ xuống ESP32.
                </p>
              </div>

              <button type="button" onClick={saveRules}>
                Lưu cấu hình
              </button>
            </div>
          </div>
        </section>

        <section className="control-section">
          <div className="control-section-title">
            <span>03</span>
            <div>
              <small>ACTUATOR CONTROL</small>
              <h2>Thiết bị điều khiển</h2>
              <p>
                Theo dõi trạng thái actuator. Điều khiển trực tiếp chỉ khả dụng
                trong MANUAL.
              </p>
            </div>
          </div>

          <div className="actuator-grid">
            {Object.entries(actuatorMeta).map(([key, actuator]) => {
              const isOn = currentState.actuators[key]

              return (
                <article
                  className={`actuator-card ${isOn ? 'running' : ''}`}
                  key={key}
                >
                  <div className="actuator-card-top">
                    <span className="actuator-icon">{actuator.icon}</span>

                    <span
                      className={`actuator-state ${
                        isOn ? 'running' : 'stopped'
                      }`}
                    >
                      <i />
                      {isOn ? 'ĐANG BẬT' : 'ĐANG TẮT'}
                    </span>
                  </div>

                  <span className="actuator-code">{actuator.code}</span>
                  <h3>{actuator.name}</h3>
                  <p>{actuator.description}</p>

                  <div className="actuator-control-row">
                    <div>
                      <span>Điều khiển</span>
                      <strong>
                        {isManual ? 'Thủ công' : 'Theo AUTO rule'}
                      </strong>
                    </div>

                    <Toggle
                      checked={isOn}
                      disabled={!isManual}
                      onChange={(value) => updateActuator(key, value)}
                      label={`${isOn ? 'Tắt' : 'Bật'} ${actuator.name}`}
                    />
                  </div>

                  {!isManual && (
                    <div className="actuator-lock-note">
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <rect x="5" y="10" width="14" height="10" rx="2" />
                        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                      </svg>

                      Được điều khiển tự động bởi controller
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </section>

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