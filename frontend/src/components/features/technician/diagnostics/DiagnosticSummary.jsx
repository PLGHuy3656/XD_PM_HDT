function DiagnosticSummary({ summary }) {
  const cards = [
    {
      label: 'Tổng Node',
      value: summary.totalNodes,
      note: 'Thiết bị được phân công',
    },
    {
      label: 'Hoạt động tốt',
      value: summary.healthyNodes,
      note: 'Không phát hiện lỗi',
      tone: 'healthy',
    },
    {
      label: 'Cần chú ý',
      value: summary.warningNodes,
      note: 'Có dấu hiệu bất thường',
      tone: 'warning',
    },
    {
      label: 'Mất kết nối',
      value: summary.offlineNodes,
      note: 'Cần kiểm tra kỹ thuật',
      tone: 'offline',
    },
  ]

  return (
    <section className="diagnostic-summary">
      {cards.map((card) => (
        <article
          className={`diagnostic-summary-card ${card.tone ?? ''}`}
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

export default DiagnosticSummary