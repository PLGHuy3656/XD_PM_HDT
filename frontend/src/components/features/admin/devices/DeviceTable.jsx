import {
  deviceStatusLabels,
  provisioningLabels,
} from './adminDevicesData'

function DeviceTable({ devices, onViewDevice }) {
  if (!devices.length) {
    return (
      <div className="admin-devices-empty">
        Không tìm thấy thiết bị phù hợp.
      </div>
    )
  }

  return (
    <div className="admin-devices-table-wrap">
      <table className="admin-devices-table">
        <thead>
          <tr>
            <th>Thiết bị</th>
            <th>Loại</th>
            <th>Nhà yến</th>
            <th>Khu vực</th>
            <th>Trạng thái</th>
            <th>Provisioning</th>
            <th />
          </tr>
        </thead>

        <tbody>
          {devices.map((device) => (
            <tr
              key={device.id}
              onClick={() => onViewDevice(device)}
            >
              <td>
                <div className="admin-device-name">
                  <strong>{device.name}</strong>
                  <span>{device.id}</span>
                </div>
              </td>

              <td>{device.type}</td>

              <td>
                <div className="admin-device-location">
                  <strong>{device.farm.name}</strong>
                  <span>{device.farm.code}</span>
                </div>
              </td>

              <td>
                <div className="admin-device-location">
                  <strong>{device.zone.name}</strong>
                  <span>{device.zone.floor}</span>
                </div>
              </td>

              <td>
                <span
                  className={`admin-device-status admin-device-status--${device.status.toLowerCase()}`}
                >
                  <i />
                  {deviceStatusLabels[device.status]}
                </span>
              </td>

              <td>
                <span
                  className={`admin-device-provision admin-device-provision--${device.provisioning.toLowerCase()}`}
                >
                  {
                    provisioningLabels[
                      device.provisioning
                    ]
                  }
                </span>
              </td>

              <td>
                <button
                  type="button"
                  className="admin-device-view"
                  onClick={(event) => {
                    event.stopPropagation()
                    onViewDevice(device)
                  }}
                  aria-label={`Xem ${device.name}`}
                >
                  •••
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default DeviceTable