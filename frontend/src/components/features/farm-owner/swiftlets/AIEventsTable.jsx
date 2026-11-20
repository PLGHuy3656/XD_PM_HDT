import { USE_MOCK } from '../../../../api/config.js'
import { formatRelativeTime } from '../../../../features/telemetry/provenance.js'

const STATE_TEXT = {
  IDLE: 'Chọn nhà yến để xem sự kiện AI.',
  LOADING: 'Đang tải sự kiện AI…',
  EMPTY: 'Chưa ghi nhận sự kiện AI nào cho nhà yến này.',
  FORBIDDEN: 'Không có quyền xem sự kiện AI của nhà yến này.',
  UNAVAILABLE: 'AI Service không khả dụng — chưa đọc được sự kiện AI.',
  ERROR: 'Không tải được sự kiện AI.',
}

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

/**
 * INT02-F03: real mode renders canonical AIEvent rows (PREDATOR_DETECTED) from the farm-scoped
 * Gateway route; bird counting is statistics, not an event, so it never appears here.
 */
function AIEventsTable({ events = [], state = 'OK' }) {
  const showState = !USE_MOCK && events.length === 0
  return (
    <section className="swiftlet-card swiftlet-events-card">
      <div className="swiftlet-card-heading">
        <div>
          <h2>Sự kiện AI gần đây</h2>
          <p>
            {USE_MOCK
              ? 'Phát hiện từ camera và hệ thống phân tích âm thanh'
              : 'Sự kiện thiên địch do AI camera phát hiện (đếm chim là thống kê, không phải sự kiện)'}
          </p>
        </div>

        {USE_MOCK && (
          <span className="swiftlet-mock-label">
            Dữ liệu minh họa
          </span>
        )}
      </div>

      {showState && (
        <p className="ai-events-empty" data-testid="ai-events-state" data-state={state}>
          {STATE_TEXT[state] || STATE_TEXT.EMPTY}
        </p>
      )}

      <div className="swiftlet-events-table-wrap" data-testid="ai-events-table" hidden={showState}>
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
              const meta = eventMeta[event.type] || eventMeta.PREDATOR

              return (
                <tr key={event.id}>
                  <td>
                    <div className="swiftlet-event-name">
                      <span className={`event-icon ${event.status || 'critical'}`}>
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
                  <td title={event.detectedAt || undefined}>{event.detectedAt ? formatRelativeTime(event.detectedAt) : event.time || '--'}</td>

                  <td>
                    <strong>{event.confidence != null ? `${event.confidence}%` : '--'}</strong>
                  </td>

                  <td>
                    {event.status == null ? (
                      <span className="ai-muted" title="Contract AIEvent V1 không có trường trạng thái">--</span>
                    ) : (
                    <span
                      className={`swiftlet-event-status ${event.status}`}
                    >
                      {event.status === 'critical'
                        ? 'Cảnh báo'
                        : event.status === 'warning'
                          ? 'Chú ý'
                          : 'Bình thường'}
                    </span>
                    )}
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