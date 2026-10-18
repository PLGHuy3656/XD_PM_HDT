function ZoneDensityPanel({ zones }) {
  return (
    <section className="analytics-card zone-density-card">
      <header className="analytics-card-heading compact">
        <div>
          <span className="analytics-card-eyebrow">
            AI ACTIVITY
          </span>

          <h2>Mật độ hoạt động theo khu vực</h2>

          <p>
            Mức độ hoạt động tương đối từ dữ liệu camera AI.
          </p>
        </div>
      </header>

      <div className="zone-density-list">
        {zones.map((zone) => (
          <article key={zone.id}>
            <div className="zone-density-heading">
              <div>
                <strong>{zone.name}</strong>
                <span>{zone.description}</span>
              </div>

              <strong>{zone.value}%</strong>
            </div>

            <div className="zone-density-track">
              <span
                style={{
                  width: `${zone.value}%`,
                }}
              />
            </div>
          </article>
        ))}
      </div>

      <p className="analytics-data-note">
        Dữ liệu minh họa từ AI Vision trong frontend
        prototype.
      </p>
    </section>
  )
}

export default ZoneDensityPanel