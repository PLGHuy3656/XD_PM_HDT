function InstallationSummary({
  installation,
  farm,
  zone,
  deviceType,
  confirmed,
  onConfirm,
}) {
  return (
    <div className="installation-card installation-completion">
      <div className="installation-card__heading">
        <div>
          <span className="installation-eyebrow">
            Bước 5 · Hoàn tất
          </span>

          <h2>Bàn giao thiết bị</h2>
        </div>

        <span
          className={`installation-status ${
            confirmed
              ? 'installation-status--success'
              : ''
          }`}
        >
          {confirmed ? 'ACTIVATED' : 'READY'}
        </span>
      </div>

      <div
        className={`installation-completion__state ${
          confirmed ? 'is-complete' : ''
        }`}
      >
        <span className="installation-completion__icon">
          {confirmed ? '✓' : '✓'}
        </span>

        <div>
          <strong>
            {confirmed
              ? 'Thiết bị đã được kích hoạt'
              : 'Sẵn sàng bàn giao'}
          </strong>

          <p>
            {confirmed
              ? 'Mock installation đã hoàn tất. Thiết bị hiện được xem là sẵn sàng vận hành.'
              : 'Toàn bộ bước kiểm tra kỹ thuật đã PASS. Kiểm tra lại thông tin trước khi xác nhận.'}
          </p>
        </div>
      </div>

      <div className="installation-completion__grid">
        <div>
          <span>Device ID</span>
          <strong>{installation.deviceId}</strong>
        </div>

        <div>
          <span>Loại thiết bị</span>
          <strong>{deviceType?.label}</strong>
        </div>

        <div>
          <span>Nhà yến</span>
          <strong>{farm?.name}</strong>
        </div>

        <div>
          <span>Khu vực</span>
          <strong>{zone?.name}</strong>
        </div>

        <div>
          <span>Serial / MAC</span>
          <strong>
            {installation.serialNumber}
          </strong>
        </div>

        <div>
          <span>Firmware</span>
          <strong>{installation.firmware}</strong>
        </div>

        <div>
          <span>MQTT Topic</span>
          <strong>{installation.mqttTopic}</strong>
        </div>

        <div>
          <span>Telemetry</span>
          <strong>
            {installation.samplingInterval} giây
          </strong>
        </div>
      </div>

      <div className="installation-handover-note">
        <strong>Lưu ý triển khai</strong>

        <span>
          Đây là mock workflow ở Frontend. Khi tích hợp
          Backend, thao tác xác nhận sẽ gọi API đăng ký/kích
          hoạt thiết bị và kiểm tra quyền Technician.
        </span>
      </div>

      <button
        type="button"
        className="installation-confirm-button"
        onClick={onConfirm}
        disabled={confirmed}
      >
        {confirmed
          ? 'Đã xác nhận lắp đặt'
          : 'Xác nhận lắp đặt'}
      </button>
    </div>
  )
}

export default InstallationSummary