function EnvironmentSummary({ summary }) {
  const cards = [
    {
      label: 'Khu vực giám sát',
      value: summary.totalZones,
      note: 'Trong phạm vi được phân công',
    },
    {
      label: 'Môi trường ổn định',
      value: summary.normalZones,
      note: 'Telemetry trong ngưỡng',
      tone: 'normal',
    },
    {
      label: 'Cần kiểm tra',
      value: summary.warningZones,
      note: 'Có dữ liệu bất thường',
      tone: 'warning',
    },
    {
      label: 'Sensor bất thường',
      value: summary.sensorIssues,
      note: 'Cần chẩn đoán kỹ thuật',
      tone: 'danger',
    },
  ]

  return (
    <section className="tech-env-summary">
      {cards.map((card) => (
        <article
          className={`tech-env-summary-card ${card.tone ?? ''}`}
          key={card.label}
        >
          <span>{card.label}</span>
          <strong>{card.value}</strong>
          <small>{card.note}</small>
        </article>
      ))}
    </section>
  )
}

export default EnvironmentSummary