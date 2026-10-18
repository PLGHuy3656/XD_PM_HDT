const environmentIcons = {
  temperature: (
    <>
      <path d="M12 14.5V5a3 3 0 0 0-6 0v9.5a5 5 0 1 0 6 0Z" />
      <path d="M9 8v8" />
    </>
  ),

  humidity: (
    <path d="M12 3s-6 6.5-6 11a6 6 0 0 0 12 0c0-4.5-6-11-6-11Z" />
  ),

  co2: (
    <>
      <path d="M6 17a4 4 0 1 1 1-7.87A5.5 5.5 0 0 1 17.5 11H18a3 3 0 0 1 0 6H6Z" />
      <path d="M9 14h6" />
    </>
  ),

  light: (
    <>
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v2" />
      <path d="M12 20v2" />
      <path d="m4.93 4.93 1.42 1.42" />
      <path d="m17.65 17.65 1.42 1.42" />
      <path d="M2 12h2" />
      <path d="M20 12h2" />
      <path d="m6.35 17.65-1.42 1.42" />
      <path d="m19.07 4.93-1.42 1.42" />
    </>
  ),
}

function EnvironmentIcon({ name }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {environmentIcons[name]}
    </svg>
  )
}

function EnvironmentStrip({ items }) {
  return (
    <section className="environment-strip">
      {items.map((item) => (
        <article
          className="environment-metric"
          key={item.id}
        >
          <div
            className={`environment-metric-icon metric-${item.status}`}
          >
            <EnvironmentIcon name={item.icon} />
          </div>

          <div className="environment-metric-copy">
            <span>{item.label}</span>

            <div>
              <strong>{item.value}</strong>

              {item.unit && (
                <small>{item.unit}</small>
              )}
            </div>
          </div>

          <span
            className={`environment-metric-state metric-state-${item.status}`}
          >
            {item.state}
          </span>
        </article>
      ))}
    </section>
  )
}

export default EnvironmentStrip