import Toggle from './Toggle'

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

function ActuatorControlPanel({
  actuators,
  isManual,
  onActuatorChange,
}) {
  return (
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
          const isOn = actuators[key]

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
                  onChange={(value) => onActuatorChange(key, value)}
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
  )
}

export default ActuatorControlPanel