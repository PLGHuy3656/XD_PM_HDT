function HarvestHistory({ data }) {
  return (
    <section className="analytics-card harvest-history">
      <header className="analytics-card-heading">
        <div>
          <span className="analytics-card-eyebrow">
            HARVEST HISTORY
          </span>

          <h2>Lịch sử thu hoạch</h2>

          <p>
            Các lần thu hoạch được ghi nhận tại nhà yến.
          </p>
        </div>

        <span className="analytics-period-badge">
          {data.length} bản ghi
        </span>
      </header>

      <div className="harvest-table-wrapper">
        <table className="harvest-table">
          <thead>
            <tr>
              <th>Mã</th>
              <th>Ngày</th>
              <th>Khu vực</th>
              <th>Số tổ</th>
              <th>Sản lượng</th>
              <th>Ghi chú</th>
            </tr>
          </thead>

          <tbody>
            {data.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.id}</strong>
                </td>

                <td>{item.date}</td>

                <td>{item.zone}</td>

                <td>{item.nests} tổ</td>

                <td>
                  <strong>{item.yield} kg</strong>
                </td>

                <td>{item.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default HarvestHistory