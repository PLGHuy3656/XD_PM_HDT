function DeviceConfiguration({
  installation,
  onChange,
}) {
  return (
    <div className="installation-card">
      <div className="installation-card__heading">
        <div>
          <span className="installation-eyebrow">
            Bước 3 · Cấu hình
          </span>

          <h2>Cấu hình kết nối</h2>
        </div>

        <span className="installation-status">
          CONFIGURATION
        </span>
      </div>

      <p className="installation-step-description">
        Thiết lập thông số giao tiếp giữa thiết bị và hệ
        thống NestMate.
      </p>

      <div className="installation-form-grid">
        <label className="installation-field-wide">
          <span>MQTT Topic</span>

          <input
            value={installation.mqttTopic}
            onChange={(event) =>
              onChange(
                'mqttTopic',
                event.target.value,
              )
            }
          />

          <small>
            Topic mock dùng để mô phỏng kết nối thiết bị với
            MQTT Broker.
          </small>
        </label>

        <label>
          <span>Chu kỳ telemetry</span>

          <div className="installation-input-unit">
            <input
              type="number"
              min="5"
              value={installation.samplingInterval}
              onChange={(event) =>
                onChange(
                  'samplingInterval',
                  event.target.value,
                )
              }
            />

            <span>giây</span>
          </div>

          <small>
            Khoảng thời gian gửi telemetry về Backend.
          </small>
        </label>
      </div>

      <div className="installation-note">
        <strong>Backend authorization</strong>

        <span>
          Technician chỉ cấu hình thiết bị trong phạm vi
          Farm/Zone được phân quyền. Frontend không kết nối
          trực tiếp tới ESP32.
        </span>
      </div>
    </div>
  )
}

export default DeviceConfiguration