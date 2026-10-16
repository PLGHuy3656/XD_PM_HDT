function CorrelationPanel({ data }) {
  return (
    <section className="analytics-card correlation-panel">
      <header className="analytics-card-heading compact">
        <div>
          <span className="analytics-card-eyebrow">
            CORRELATION
          </span>

          <h2>Độ ẩm & tỷ lệ quay về</h2>

          <p>
            Đối chiếu dữ liệu môi trường với hoạt động đàn chim.
          </p>
        </div>
      </header>

      <div className="correlation-list">
        {data.map((item) => (
          <article key={item.label}>
            <strong>{item.label}</strong>

            <div className="correlation-values">
              <div>
                <span>Độ ẩm</span>
                <strong>{item.humidity}%</strong>
              </div>

              <div>
                <span>Tỷ lệ quay về</span>
                <strong>{item.returnRate}%</strong>
              </div>
            </div>

            <div className="correlation-track">
              <span
                style={{
                  width: `${item.returnRate}%`,
                }}
              />
            </div>
          </article>
        ))}
      </div>

      <p className="analytics-data-note">
        Chỉ thể hiện tương quan quan sát từ dữ liệu mock,
        không phải kết luận quan hệ nhân quả.
      </p>
    </section>
  )
}

export default CorrelationPanel