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

  const technician = farm.assignedTechnician

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

      <div className="farm-technician">
        <div className="farm-technician__heading">
          <div>
            <span className="farm-technician__eyebrow">
              HỖ TRỢ KỸ THUẬT
            </span>
            <h3>Kỹ thuật viên phụ trách</h3>
            <p>
              Thông tin kỹ thuật viên đang được phân công hỗ trợ nhà yến này.
            </p>
          </div>

          {technician && (
            <span className="farm-technician__status">
              <i />
              {technician.status}
            </span>
          )}
        </div>

        {technician ? (
          <div className="farm-technician__profile">
            <div className="farm-technician__identity">
              <div className="farm-technician__avatar">
                {technician.name
                  .split(' ')
                  .slice(-2)
                  .map((word) => word[0])
                  .join('')}
              </div>

              <div>
                <strong>{technician.name}</strong>
                <span>{technician.role}</span>
              </div>
            </div>

            <div className="farm-technician__contact">
              <span>Số điện thoại</span>
              <strong>{technician.phone}</strong>
            </div>

            <div className="farm-technician__contact">
              <span>Email</span>
              <strong>{technician.email}</strong>
            </div>
          </div>
        ) : (
          <div className="farm-technician__empty">
            Nhà yến hiện chưa được phân công kỹ thuật viên phụ trách.
          </div>
        )}
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