function StatCard({
  icon,
  label,
  hint,
  value,
  unit,
  delta,
  unavailableLabel,
  variant = 'default',
}) {
  const isUnavailable = value == null || value === '—'

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
        <strong>{value ?? '—'}</strong>
        <span>{isUnavailable ? (unavailableLabel || 'Chưa có dữ liệu') : unit}</span>
      </div>

      {!isUnavailable && delta !== undefined && (
        <span className="swiftlet-stat-delta">
          +{delta}% so với hôm qua
        </span>
      )}
    </article>
  )
}

function BirdStatsCards({ stats }) {
  const unavailableLabel = stats?.noCamera
    ? 'Chưa có camera AI'
    : stats?.unavailable
      ? 'Chưa có dữ liệu'
      : null

  return (
    <section className="swiftlet-stats-grid">
      <StatCard
        icon="↘"
        label={`Vào tổ ${stats.scope || 'hôm nay'}`}
        hint={stats.sourceMode === 'DEMO_VIDEO' ? 'AI đếm trên video kiểm thử tổng hợp (không phải số liệu nhà yến)' : stats.sourceMode === 'UPLOADED_VIDEO' ? 'AI đếm trên video bạn tải lên' : 'Lượt chim được AI ghi nhận'}
        value={stats.entries}
        unit="lượt"
        delta={stats.entriesDelta}
        unavailableLabel={unavailableLabel}
      />

      <StatCard
        icon="↗"
        label={`Xuất đàn ${stats.scope || 'hôm nay'}`}
        hint="Lượt chim rời nhà yến"
        value={stats.exits}
        unit="lượt"
        delta={stats.exitsDelta}
        unavailableLabel={unavailableLabel}
      />

      <StatCard
        icon="↻"
        label="Tỷ lệ về tổ"
        hint="So với số lượt bay đi"
        value={stats.returnRate}
        unit="%"
        unavailableLabel={unavailableLabel}
        variant="return"
      />
    </section>
  )
}

export default BirdStatsCards