function ZoneYieldPanel({ data }) {
  return (
    <section className="analytics-card zone-yield-card">
      <header className="analytics-card-heading compact">
        <div>
          <span className="analytics-card-eyebrow">
            ZONE PERFORMANCE
          </span>

          <h2>Sản lượng theo khu vực</h2>

          <p>
            So sánh đóng góp sản lượng giữa các khu vực.
          </p>
        </div>
      </header>

      <div className="zone-yield-list">
        {data.map((zone) => (
          <article key={zone.id}>
            <div className="zone-yield-heading">
              <div>
                <strong>{zone.name}</strong>
                <span>{zone.description}</span>
              </div>

              <strong>{zone.yield} kg</strong>
            </div>

            <div className="zone-yield-meta">
              <span>{zone.nests} tổ</span>
              <span>{zone.harvested} tổ đã thu hoạch</span>
            </div>

            <div className="zone-yield-track">
              <span
                style={{
                  width: `${zone.contribution}%`,
                }}
              />
            </div>

            <small>
              Đóng góp {zone.contribution}% sản lượng
            </small>
          </article>
        ))}
      </div>
    </section>
  )
}

export default ZoneYieldPanel