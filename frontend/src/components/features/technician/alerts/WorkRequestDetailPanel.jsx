import {
  workPriorityLabel,
  workSourceLabel,
  workStatusLabel,
} from './alertsMockData'

export default function WorkRequestDetailPanel({
  request,
  onClose,
  onStatusChange,
}) {
  if (!request) return null

  return (
    <aside className="tech-alert-detail">
      <div className="tech-alert-detail-header">
        <div>
          <span className="tech-alert-detail-eyebrow">YÊU CẦU CÔNG VIỆC</span>
          <h2>{request.title}</h2>
        </div>

        <button
          type="button"
          className="tech-alert-close"
          onClick={onClose}
          aria-label="Đóng"
        >
          ×
        </button>
      </div>

      <div className="tech-alert-detail-badges">
        <span className={`tech-request-source ${request.source}`}>
          {workSourceLabel(request.source)}
        </span>

        <span className={`tech-priority ${request.priority}`}>
          {workPriorityLabel(request.priority)}
        </span>

        <span className={`tech-status ${request.status}`}>
          {workStatusLabel(request.status)}
        </span>
      </div>

      <div className="tech-alert-detail-grid">
        <div>
          <span>Nhà yến</span>
          <strong>{request.farm}</strong>
        </div>
        <div>
          <span>Khu vực</span>
          <strong>{request.zone}</strong>
        </div>
        <div>
          <span>Người gửi</span>
          <strong>{request.sender}</strong>
        </div>
        <div>
          <span>Thời gian</span>
          <strong>{request.createdAt}</strong>
        </div>
      </div>

      <section className="tech-alert-detail-section">
        <span>Nội dung yêu cầu</span>
        <p>{request.content}</p>
      </section>

      {request.contact && (
        <section className="tech-alert-detail-section">
          <span>Liên hệ Farm Owner</span>
          <p>{request.contact}</p>
        </section>
      )}

      <div className="tech-work-actions">
        {request.status === 'NEW' && (
          <button
            type="button"
            className="tech-work-primary"
            onClick={() => onStatusChange(request.id, 'IN_PROGRESS')}
          >
            Bắt đầu xử lý
          </button>
        )}

        {request.status === 'IN_PROGRESS' && (
          <button
            type="button"
            className="tech-work-primary"
            onClick={() => onStatusChange(request.id, 'DONE')}
          >
            Đánh dấu hoàn thành
          </button>
        )}

        {request.status === 'DONE' && (
          <div className="tech-work-completed">
            Yêu cầu này đã được hoàn thành.
          </div>
        )}
      </div>
    </aside>
  )
}