import EnvironmentSelect from '../../../ui/Select'

function DeviceStep({
  installation,
  deviceTypes,
  onChange,
}) {
  const deviceTypeOptions = deviceTypes.map((type) => ({
    value: type.id,
    label: type.label,
  }))

  return (
    <div className="installation-card">
      <div className="installation-card__heading">
        <div>
          <span className="installation-eyebrow">
            Bước 2 · Thiết bị
          </span>
          <h2>Đăng ký thiết bị</h2>
        </div>

        <span className="installation-status">
          DEVICE
        </span>
      </div>

      <p className="installation-step-description">
        Xác nhận thông tin nhận dạng của thiết bị trước khi
        tiến hành cấu hình kết nối.
      </p>

      <div className="installation-form-grid">
        <label>
          <span>Device ID</span>

          <input
            value={installation.deviceId}
            onChange={(event) =>
              onChange('deviceId', event.target.value)
            }
          />

          <small>
            Mã định danh duy nhất trong NestMate.
          </small>
        </label>

        <div className="installation-form-field">
          <span>Loại thiết bị</span>

          <EnvironmentSelect
            value={installation.deviceType}
            options={deviceTypeOptions}
            onChange={(value) =>
              onChange('deviceType', value)
            }
          />
        </div>

        <label>
          <span>Serial / MAC</span>

          <input
            value={installation.serialNumber}
            onChange={(event) =>
              onChange(
                'serialNumber',
                event.target.value,
              )
            }
          />
        </label>

        <label>
          <span>Firmware</span>

          <input
            value={installation.firmware}
            onChange={(event) =>
              onChange('firmware', event.target.value)
            }
          />

          <small>
            Phiên bản firmware hiện tại của node.
          </small>
        </label>
      </div>
    </div>
  )
}

export default DeviceStep