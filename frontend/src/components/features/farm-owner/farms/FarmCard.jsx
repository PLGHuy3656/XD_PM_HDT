function FarmCard({ farm, selected, onSelect }) {
  const devicePercent = Math.round(
    (farm.onlineDevices / farm.totalDevices) * 100,
  )

  return (
    <button
      type="button"
      className={`farm-card ${selected ? 'farm-card--selected' : ''}`}
      onClick={() => onSelect(farm)}
    >
      <div className="farm-card__top">
        <div>
          <span className="farm-card__code">{farm.code}</span>
          <h3>{farm.name}</h3>
          <p>{farm.address}</p>
        </div>

        <span
          className={`farm-health ${
            farm.health === 'Tốt'
              ? 'farm-health--good'
              : 'farm-health--warning'
          }`}
        >
          {farm.health}
        </span>
      </div>

      <div className="farm-card__metrics">
        <div>
          <span>Nhiệt độ</span>
          <strong>{farm.temperature}°C</strong>
        </div>

        <div>
          <span>Độ ẩm</span>
          <strong>{farm.humidity}%</strong>
        </div>

        <div>
          <span>Chim hôm nay</span>
          <strong>{farm.birdsToday}</strong>
        </div>
      </div>

      <div className="farm-card__device">
        <div className="farm-card__device-label">
          <span>Thiết bị trực tuyến</span>
          <strong>
            {farm.onlineDevices}/{farm.totalDevices}
          </strong>
        </div>

        <div className="farm-card__progress">
          <span style={{ width: `${devicePercent}%` }} />
        </div>
      </div>
    </button>
  )
}

export default FarmCard