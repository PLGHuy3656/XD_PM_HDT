export function MetricIcon({ type }) {
  if (type === 'temperature') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M10 14.7V5a2 2 0 1 1 4 0v9.7a4 4 0 1 1-4 0Z" />
        <path d="M12 17V8" />
      </svg>
    )
  }

  if (type === 'humidity') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3S6.5 9.2 6.5 14a5.5 5.5 0 0 0 11 0C17.5 9.2 12 3 12 3Z" />
      </svg>
    )
  }

  if (type === 'co2') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.5 17.5H6a4 4 0 0 1-.4-8A5.8 5.8 0 0 1 16.7 8a4.7 4.7 0 0 1 .8 9.4H16" />
        <path d="M9 14.5h2.2M9 17h2.2M14 14.5h1.5L14 17h2" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

export function getMetricState(metric) {
  const normal =
    metric.value >= metric.safeMin &&
    metric.value <= metric.safeMax

  return normal
    ? {
        label: 'Bình thường',
        shortLabel: 'Ổn định',
        className: 'normal',
      }
    : {
        label:
          metric.value < metric.safeMin
            ? 'Dưới ngưỡng'
            : 'Vượt ngưỡng',
        shortLabel: 'Chú ý',
        className: 'warning',
      }
}

function MetricCard({
  metricKey,
  metric,
  active,
  onClick,
}) {
  const state = getMetricState(metric)

  return (
    <button
      type="button"
      className={`environment-metric-card${active ? ' active' : ''}`}
      onClick={onClick}
    >
      <div className={`metric-card-icon ${state.className}`}>
        <MetricIcon type={metricKey} />
      </div>

      <div className="metric-card-heading">
        <span>{metric.label}</span>

        <span className={`metric-state ${state.className}`}>
          <i />
          {state.label}
        </span>
      </div>

      <strong className="metric-card-value">
        {metric.displayValue}
      </strong>

      <div className="metric-card-range">
        Ngưỡng {metric.safeMin}–{metric.safeMax}
        {metric.unit}
      </div>
    </button>
  )
}

export default MetricCard