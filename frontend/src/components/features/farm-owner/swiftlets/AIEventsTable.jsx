const eventMeta = {
  ENTRY: {
    label: 'Vào tổ',
    icon: '↘',
  },
  EXIT: {
    label: 'Xuất đàn',
    icon: '↗',
  },
  PREDATOR: {
    label: 'Thiên địch',
    icon: '!',
  },
  AUDIO: {
    label: 'Âm thanh',
    icon: '≈',
  },
}

function AIEventsTable({ events }) {
  return (
    <section className="swiftlet-card swiftlet-events-card">
      <div className="swiftlet-card-heading">
        <div>
          <h2>Sự kiện AI gần đây</h2>
          <p>
            Phát hiện từ camera và hệ thống phân tích âm thanh
          </p>
        </div>

        <span className="swiftlet-mock-label">
          Dữ liệu minh họa
        </span>
      </div>

      <div className="swiftlet-events-table-wrap">
        <table className="swiftlet-events-table">
          <thead>
            <tr>
              <th>Sự kiện</th>
              <th>Vị trí</th>
              <th>Thời điểm</th>
              <th>Độ tin cậy</th>
              <th>Trạng thái</th>
            </tr>
          </thead>

          <tbody>
            {events.map((event) => {
              const meta = eventMeta[event.type]

              return (
                <tr key={event.id}>
                  <td>
                    <div className="swiftlet-event-name">
                      <span className={`event-icon ${event.status}`}>
                        {meta.icon}
                      </span>

                      <div>
                        <strong>{event.title}</strong>
                        <small>
                          {event.id} · {meta.label}
                        </small>
                      </div>
                    </div>
                  </td>

                  <td>{event.location}</td>
                  <td>{event.time}</td>

                  <td>
                    <strong>{event.confidence}%</strong>
                  </td>

                  <td>
                    <span
                      className={`swiftlet-event-status ${event.status}`}
                    >
                      {event.status === 'critical'
                        ? 'Cảnh báo'
                        : event.status === 'warning'
                          ? 'Chú ý'
                          : 'Bình thường'}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export default AIEventsTable