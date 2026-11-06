import EnvironmentSelect from '../../../ui/Select'

function LocationStep({
  installation,
  farms,
  onChange,
}) {
  const selectedFarm = farms.find(
    (farm) => farm.id === installation.farmId,
  )

  const farmOptions = farms.map((farm) => ({
    value: farm.id,
    label: farm.name,
  }))

  const zoneOptions =
    selectedFarm?.zones.map((zone) => ({
      value: zone.id,
      label: zone.name,
    })) ?? []

  return (
    <div className="installation-card">
      <div className="installation-card__heading">
        <div>
          <span className="installation-eyebrow">
            Bước 1 · Vị trí
          </span>
          <h2>Chọn vị trí triển khai</h2>
        </div>

        <span className="installation-status">
          LOCATION
        </span>
      </div>

      <p className="installation-step-description">
        Chọn nhà yến và khu vực mà Technician sẽ triển khai
        thiết bị.
      </p>

      <div className="installation-form-grid">
        <div className="installation-form-field">
          <span>Nhà yến</span>

          <EnvironmentSelect
            value={installation.farmId}
            options={farmOptions}
            onChange={(value) =>
              onChange('farmId', value)
            }
          />

          <small>{selectedFarm?.location}</small>
        </div>

        <div className="installation-form-field">
          <span>Khu vực</span>

          <EnvironmentSelect
            value={installation.zoneId}
            options={zoneOptions}
            onChange={(value) =>
              onChange('zoneId', value)
            }
          />

          <small>
            Thiết bị sẽ được liên kết với khu vực này.
          </small>
        </div>
      </div>
    </div>
  )
}

export default LocationStep