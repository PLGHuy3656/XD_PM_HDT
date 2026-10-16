function YieldSummary({ data }) {
  const cards = [
    {
      label: 'Tổng số tổ',
      value: data.totalNests.toLocaleString('vi-VN'),
      suffix: 'tổ',
      description: 'Ghi nhận tại nhà yến',
    },
    {
      label: 'Tổ đã thu hoạch',
      value: data.harvestedNests,
      suffix: 'tổ',
      description: 'Trong kỳ hiện tại',
    },
    {
      label: 'Sản lượng kỳ này',
      value: data.currentYield,
      suffix: 'kg',
      description: 'Tổng sản lượng ghi nhận',
      highlight: true,
    },
    {
      label: 'So với kỳ trước',
      value: `+${data.yieldChange}`,
      suffix: '%',
      description: `${data.previousYield} kg ở kỳ trước`,
    },
  ]

  return (
    <section className="analytics-performance yield-summary">
      <header>
        <div>
          <span className="analytics-card-eyebrow">
            YIELD PERFORMANCE
          </span>

          <h2>Tổng quan năng suất</h2>
        </div>

        <span className="analytics-performance-change">
          +{data.yieldChange}% so với kỳ trước
        </span>
      </header>

      <div className="analytics-performance-grid">
        {cards.map((card) => (
          <article
            key={card.label}
            className={`analytics-performance-item ${
              card.highlight ? 'highlight' : ''
            }`}
          >
            <span>{card.label}</span>

            <strong>
              {card.value}
              <small> {card.suffix}</small>
            </strong>

            <p>{card.description}</p>
          </article>
        ))}
      </div>
    </section>
  )
}

export default YieldSummary