function FarmDetailPanel({ farm }) {
  if (!farm) {
    return (
      <section className="farm-detail farm-detail--empty">
        <div>
          <span className="farm-detail__empty-icon">⌂</span>
          <h3>Chọn một nhà yến</h3>
          <p>Chọn nhà yến bên trái để xem thông tin chi tiết.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="farm-detail">
      <div className="farm-detail__header">
        <div>
          <span className="farm-detail__eyebrow">CHI TIẾT NHÀ YẾN</span>
          <h2>{farm.name}</h2>
          <p>
            {farm.code} · {farm.address}
          </p>
        </div>

        <span className="farm-detail__active">
          <i />
          Đang hoạt động
        </span>
      </div>

      <div className="farm-detail__summary">
        <article>
          <span>Khu vực</span>
          <strong>{farm.zones.length}</strong>
          <small>Đang được giám sát</small>
        </article>

        <article>
          <span>Thiết bị</span>
          <strong>
            {farm.onlineDevices}/{farm.totalDevices}
          </strong>
          <small>Thiết bị trực tuyến</small>
        </article>

        <article>
          <span>Nhiệt độ TB</span>
          <strong>{farm.temperature}°C</strong>
          <small>Trong ngưỡng vận hành</small>
        </article>

        <article>
          <span>Độ ẩm TB</span>
          <strong>{farm.humidity}%</strong>
          <small>Mức hiện tại</small>
        </article>
      </div>

      <div className="farm-detail__section-heading">
        <div>
          <h3>Khu vực giám sát</h3>
          <p>Tình trạng môi trường và thiết bị theo từng khu vực.</p>
        </div>

        <span>{farm.zones.length} khu vực</span>
      </div>

      <div className="farm-zone-list">
        {farm.zones.map((zone) => (
          <article
            className="farm-zone"
            key={zone.id}
          >
            <div className="farm-zone__identity">
              <span className="farm-zone__icon">Z</span>

              <div>
                <h4>{zone.name}</h4>
                <p>{zone.floor}</p>
              </div>
            </div>

            <div className="farm-zone__metric">
              <span>Nhiệt độ</span>
              <strong>{zone.temperature}°C</strong>
            </div>

            <div className="farm-zone__metric">
              <span>Độ ẩm</span>
              <strong>{zone.humidity}%</strong>
            </div>

            <div className="farm-zone__metric">
              <span>Thiết bị</span>
              <strong>{zone.devices}</strong>
            </div>

            <span
              className={`farm-zone__status ${
                zone.status === 'Ổn định'
                  ? 'farm-zone__status--good'
                  : 'farm-zone__status--warning'
              }`}
            >
              {zone.status}
            </span>
          </article>
        ))}
      </div>
    </section>
  )
}

export default FarmDetailPanel