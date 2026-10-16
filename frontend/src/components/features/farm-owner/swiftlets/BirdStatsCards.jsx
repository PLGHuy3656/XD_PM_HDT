function StatCard({
  icon,
  label,
  hint,
  value,
  unit,
  delta,
  variant = 'default',
}) {
  return (
    <article className={`swiftlet-stat-card ${variant}`}>
      <div className="swiftlet-stat-heading">
        <span className="swiftlet-stat-icon">{icon}</span>

        <div>
          <strong>{label}</strong>
          <small>{hint}</small>
        </div>
      </div>

      <div className="swiftlet-stat-value">
        <strong>{value}</strong>
        <span>{unit}</span>
      </div>

      {delta !== undefined && (
        <span className="swiftlet-stat-delta">
          +{delta}% so với hôm qua
        </span>
      )}
    </article>
  )
}

function BirdStatsCards({ stats }) {
  return (
    <section className="swiftlet-stats-grid">
      <StatCard
        icon="↘"
        label="Vào tổ hôm nay"
        hint="Lượt chim được AI ghi nhận"
        value={stats.entries}
        unit="lượt"
        delta={stats.entriesDelta}
      />

      <StatCard
        icon="↗"
        label="Xuất đàn hôm nay"
        hint="Lượt chim rời nhà yến"
        value={stats.exits}
        unit="lượt"
        delta={stats.exitsDelta}
      />

      <StatCard
        icon="↻"
        label="Tỷ lệ về tổ"
        hint="So với số lượt bay đi"
        value={stats.returnRate}
        unit="%"
        variant="return"
      />
    </section>
  )
}

export default BirdStatsCards