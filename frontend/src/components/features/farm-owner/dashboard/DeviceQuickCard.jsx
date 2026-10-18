const deviceIcons = {
  misting: (
    <path d="M12 3s-5 5.5-5 9.5a5 5 0 0 0 10 0C17 8.5 12 3 12 3Z" />
  ),

  fan: (
    <>
      <circle cx="12" cy="12" r="2" />
      <path d="M12 10c-1-5 1-7 3-7 2.5 0 3.5 3.5 1 6.5" />
      <path d="M14 12c5-1 7 1 7 3 0 2.5-3.5 3.5-6.5 1" />
      <path d="M12 14c1 5-1 7-3 7-2.5 0-3.5-3.5-1-6.5" />
      <path d="M10 12c-5 1-7-1-7-3 0-2.5 3.5-3.5 6.5-1" />
    </>
  ),

  heater: (
    <>
      <path d="M7 20c-2-3 2-4 0-7s2-4 0-7" />
      <path d="M12 20c-2-3 2-4 0-7s2-4 0-7" />
      <path d="M17 20c-2-3 2-4 0-7s2-4 0-7" />
    </>
  ),
}

function DeviceQuickCard({
  type,
  name,
  description,
  status = 'off',
  mode = 'AUTO',
  connected = true,
  onToggle,
}) {
  const isOn = status === 'on'
  const isManual = mode === 'MANUAL'

  return (
    <article className="device-quick-card">
      <div className={`device-quick-icon device-${status}`}>
        <svg
          viewBox="0 0 24 24"
          aria-hidden="true"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.7"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {deviceIcons[type]}
        </svg>
      </div>

      <div className="device-quick-copy">
        <div className="device-quick-name">
          <strong>{name}</strong>

          <span
            className={
              connected
                ? 'device-connection online'
                : 'device-connection offline'
            }
            title={connected ? 'Đang kết nối' : 'Mất kết nối'}
          />
        </div>

        <span>{description}</span>
      </div>

      <div className="device-quick-controls">
        <span
          className={
            mode === 'AUTO'
              ? 'device-mode device-mode-auto'
              : 'device-mode device-mode-manual'
          }
        >
          {mode}
        </span>

        <button
          type="button"
          className={`device-toggle ${
            isOn ? 'device-toggle-on' : ''
          }`}
          disabled={!isManual || !connected}
          onClick={onToggle}
          aria-label={`${isOn ? 'Tắt' : 'Bật'} ${name}`}
          title={
            !connected
              ? 'Thiết bị đang mất kết nối'
              : !isManual
                ? 'Chuyển sang MANUAL để điều khiển'
                : isOn
                  ? 'Tắt thiết bị'
                  : 'Bật thiết bị'
          }
        >
          <span className="device-toggle-knob" />
        </button>
      </div>
    </article>
  )
}

export default DeviceQuickCard