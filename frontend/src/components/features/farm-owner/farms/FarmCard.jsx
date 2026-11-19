const approvalBadgeMap = {
  PENDING: { label: 'Chờ duyệt', bg: '#fef3c7', color: '#92400e', border: '#fcd34d' },
  APPROVED: { label: 'Đã duyệt', bg: '#ecfdf5', color: '#065f46', border: '#a7f3d0' },
  REJECTED: { label: 'Từ chối', bg: '#fef2f2', color: '#991b1b', border: '#fecaca' },
}

function FarmCard({ farm, selected, onSelect }) {
  const totalDevices = farm.totalDevices ?? 0
  const onlineDevices = farm.onlineDevices ?? 0
  const devicePercent = totalDevices > 0 ? Math.round((onlineDevices / totalDevices) * 100) : 0
  const approvalStatus = farm.approvalStatus || 'APPROVED'
  const approvalBadge = approvalBadgeMap[approvalStatus] || approvalBadgeMap.APPROVED

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

        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
          <span
            className={`farm-health ${
              farm.health === 'Tốt'
                ? 'farm-health--good'
                : 'farm-health--warning'
            }`}
          >
            {farm.health}
          </span>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: '999px',
              fontSize: '0.72rem',
              fontWeight: 600,
              background: approvalBadge.bg,
              color: approvalBadge.color,
              border: `1px solid ${approvalBadge.border}`,
            }}
          >
            {approvalBadge.label}
          </span>
        </div>
      </div>

      <div className="farm-card__metrics">
        <div>
          <span>Nhiệt độ</span>
          <strong>{farm.temperature != null ? `${farm.temperature}°C` : '--'}</strong>
        </div>

        <div>
          <span>Độ ẩm</span>
          <strong>{farm.humidity != null ? `${farm.humidity}%` : '--'}</strong>
        </div>

        <div>
          <span>Chim hôm nay</span>
          <strong>{farm.birdsToday != null ? farm.birdsToday : '--'}</strong>
        </div>
      </div>

      <div className="farm-card__device">
        <div className="farm-card__device-label">
          <span>Thiết bị trực tuyến</span>
          <strong>
            {onlineDevices}/{totalDevices}
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