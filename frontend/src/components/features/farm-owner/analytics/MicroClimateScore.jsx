function MicroClimateScore({ zones }) {
  return (
    <section className="analytics-card micro-climate-card">
      <header className="analytics-card-heading compact">
        <div>
          <span className="analytics-card-eyebrow">
            ENVIRONMENT
          </span>

          <h2>Cân bằng vi khí hậu</h2>

          <p>
            Tổng hợp mức ổn định môi trường trong 24 giờ gần nhất.
          </p>
        </div>

        <span className="analytics-period-badge">
          24 giờ
        </span>
      </header>

      <div className="micro-climate-list">
        {zones.map((zone) => (
          <article key={zone.id}>
            <div className="micro-climate-heading">
              <div>
                <strong>{zone.name}</strong>
                <span>{zone.status}</span>
              </div>

              <strong>
                {zone.score}
                <small>/100</small>
              </strong>
            </div>

            <div className="micro-climate-track">
              <span
                style={{
                  width: `${zone.score}%`,
                }}
              />
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}

export default MicroClimateScore