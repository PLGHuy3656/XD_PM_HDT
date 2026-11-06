function ConnectionVerification({
  items,
  verification,
  onToggle,
}) {
  const completed = items.filter(
    (item) => verification[item.id],
  ).length

  return (
    <div className="installation-card">
      <div className="installation-card__heading">
        <div>
          <span className="installation-eyebrow">
            Bước 4 · Kiểm tra
          </span>

          <h2>Xác minh sau lắp đặt</h2>
        </div>

        <strong className="installation-verification-count">
          {completed}/{items.length} PASS
        </strong>
      </div>

      <p className="installation-step-description">
        Mô phỏng quá trình kiểm tra kỹ thuật trước khi thiết
        bị được bàn giao và đưa vào vận hành.
      </p>

      <div className="installation-check-list">
        {items.map((item) => {
          const checked = Boolean(
            verification[item.id],
          )

          return (
            <button
              type="button"
              key={item.id}
              className={`installation-check ${
                checked ? 'is-passed' : ''
              }`}
              onClick={() => onToggle(item.id)}
            >
              <span className="installation-check__icon">
                {checked ? '✓' : '○'}
              </span>

              <span className="installation-check__copy">
                <strong>{item.label}</strong>
                <small>{item.description}</small>
              </span>

              <span className="installation-check__state">
                {checked
                  ? 'PASS'
                  : 'CHƯA KIỂM TRA'}
              </span>
            </button>
          )
        })}
      </div>

      <div className="installation-verification-note">
        <strong>
          {completed === items.length
            ? 'Thiết bị đã vượt qua toàn bộ kiểm tra.'
            : 'Cần hoàn thành toàn bộ kiểm tra.'}
        </strong>

        <span>
          {completed === items.length
            ? 'Bạn có thể tiếp tục sang bước hoàn tất.'
            : `${completed}/${items.length} hạng mục đã được xác nhận.`}
        </span>
      </div>
    </div>
  )
}

export default ConnectionVerification