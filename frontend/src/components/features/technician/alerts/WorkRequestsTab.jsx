function sourceLabel(source) {
  return source === 'ADMIN' ? 'Admin' : 'Farm Owner'
}

function priorityLabel(priority) {
  return {
    URGENT: 'Khẩn cấp',
    HIGH: 'Cao',
    NORMAL: 'Bình thường',
  }[priority]
}

function statusLabel(status) {
  return {
    NEW: 'Mới',
    IN_PROGRESS: 'Đang xử lý',
    DONE: 'Hoàn thành',
  }[status]
}

export default function WorkRequestsTab({
  requests,
  selectedId,
  onSelect,
}) {
  return (
    <div className="tech-alert-list">
      {requests.map((request) => (
        <button
          type="button"
          key={request.id}
          className={`tech-alert-row ${
            selectedId === request.id ? 'active' : ''
          }`}
          onClick={() => onSelect(request)}
        >
          <div className={`tech-request-source ${request.source}`}>
            {sourceLabel(request.source)}
          </div>

          <div className="tech-alert-row-main">
            <div className="tech-alert-row-heading">
              <strong>{request.title}</strong>

              <span className={`tech-priority ${request.priority}`}>
                {priorityLabel(request.priority)}
              </span>
            </div>

            <div className="tech-alert-row-meta">
              <span>{request.farm}</span>
              <span>{request.zone}</span>
              <span>Gửi bởi {request.sender}</span>
            </div>
          </div>

          <div className="tech-alert-row-side">
            <span className={`tech-status ${request.status}`}>
              {statusLabel(request.status)}
            </span>
            <small>{request.createdAt}</small>
          </div>
        </button>
      ))}

      {requests.length === 0 && (
        <div className="tech-alert-empty">
          Không có yêu cầu phù hợp với bộ lọc.
        </div>
      )}
    </div>
  )
}