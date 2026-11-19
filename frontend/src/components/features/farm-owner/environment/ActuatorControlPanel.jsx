import Toggle from './Toggle'

const actuatorMeta = {
  misting: {
    name: 'Phun sương',
    code: 'MISTING',
    description: 'Duy trì độ ẩm tối ưu trong khu vực.',
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
    description: 'Lưu thông không khí và giảm nhiệt độ.',
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
    description: 'Bổ sung nhiệt khi nhiệt độ xuống thấp.',
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
  disabled = false,
  commandStatus = {},
  onActuatorChange,
}) {
  return (
    <section className="actuator-panel" aria-label="Điều khiển thiết bị thủ công">
      <div className="actuator-grid">
        {Object.entries(actuatorMeta).map(([key, actuator]) => {
          const isOn = disabled ? false : Boolean(actuators[key])
          const cmd = commandStatus[key] || { state: 'idle' }
          const isPending = cmd.state === 'pending'
          const isFailed = cmd.state === 'failed'
          const isAcked = cmd.state === 'acked'

          const badgeClass = disabled
            ? 'stopped'
            : isPending
              ? 'pending'
              : isFailed
                ? 'failed'
                : isOn
                  ? 'running'
                  : 'stopped'

          const badgeLabel = disabled
            ? 'CHƯA KẾT NỐI'
            : isPending
              ? 'ĐANG CHỜ ACK'
              : isFailed
                ? 'LỖI LỆNH'
                : isOn
                  ? isAcked
                    ? 'ĐANG BẬT · ACK'
                    : 'ĐANG BẬT'
                  : isAcked
                    ? 'ĐANG TẮT · ACK'
                    : 'ĐANG TẮT'

          const canToggle = !disabled && isManual && !isPending

          return (
            <article
              className={`actuator-card ${isOn && !disabled ? 'running' : ''}`.trim()}
              key={key}
            >
              <div className="actuator-card-top">
                <span className="actuator-icon">{actuator.icon}</span>

                <span className={`actuator-state ${badgeClass}`}>
                  <i />
                  {badgeLabel}
                </span>
              </div>

              <span className="actuator-code">{actuator.code}</span>
              <h3>{actuator.name}</h3>
              <p>{actuator.description}</p>

              <div className="actuator-control-row">
                <div>
                  <span>Điều khiển</span>
                  <strong>
                    {disabled
                      ? 'Chưa kết nối IoT'
                      : isPending
                        ? 'Đang gửi lệnh...'
                        : isManual
                          ? 'Thủ công (MANUAL)'
                          : 'Khóa · Đang ở AUTO'}
                  </strong>
                </div>

                <Toggle
                  checked={disabled ? false : Boolean(isOn)}
                  disabled={!canToggle}
                  onChange={(value) => onActuatorChange?.(key, value)}
                  label={`${isOn ? 'Tắt' : 'Bật'} ${actuator.name}`}
                />
              </div>

              {isFailed && cmd.message ? (
                <div className="actuator-lock-note actuator-lock-note--error">
                  {cmd.message}
                </div>
              ) : (disabled || !isManual) && (
                <div className="actuator-lock-note">
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <rect x="5" y="10" width="14" height="10" rx="2" />
                    <path d="M8 10V7a4 4 0 0 1 8 0v3" />
                  </svg>

                  {disabled
                    ? 'Tạm khóa do chưa kết nối IoT Service'
                    : 'Chuyển bộ điều khiển sang MANUAL để bật/tắt'}
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
