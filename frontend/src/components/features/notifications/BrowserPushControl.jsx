import { useAuth } from '../../../context/AuthContext'
import { WEB_PUSH_STATUS } from '../../../features/notifications/fcmConfig.js'
import { useWebPush } from '../../../features/notifications/useWebPush.js'
import './BrowserPushControl.css'

/**
 * INT03-R2: Explicit user-initiated FCM Web Push control ("Bật thông báo trên trình duyệt").
 * Never prompts browser permission automatically; works safely even when Firebase is unconfigured.
 */
function BrowserPushControl({ compact = false }) {
  const { user } = useAuth()
  const push = useWebPush(user?.id || null)

  const helperByStatus = {
    [WEB_PUSH_STATUS.UNCONFIGURED]:
      'Firebase Web Push chưa được cấu hình trên môi trường này. Thông báo trong ứng dụng vẫn hoạt động bình thường.',
    [WEB_PUSH_STATUS.BLOCKED]:
      'Trình duyệt đang chặn thông báo. Hãy mở biểu tượng cài đặt cạnh thanh địa chỉ Chrome để cho phép lại.',
    [WEB_PUSH_STATUS.UNAVAILABLE]:
      'Trình duyệt hoặc môi trường hiện tại không hỗ trợ Push API / Service Worker.',
    [WEB_PUSH_STATUS.ENABLED]:
      'Trình duyệt này đang nhận thông báo đẩy từ SwiftletCare cho tài khoản hiện tại. Sẽ tự hủy khi đăng xuất.',
    [WEB_PUSH_STATUS.REGISTERING]:
      'Đang xin quyền và đăng ký thiết bị với máy chủ thông báo…',
    [WEB_PUSH_STATUS.DISABLED]:
      'Nhận thông báo tức thì trên Chrome ngay cả khi chuyển sang tab khác.',
  }

  return (
    <div
      className={`fcm-push-control ${compact ? 'fcm-push-control--compact' : ''}`}
      data-testid="browser-push-control"
      data-push-status={push.status}
    >
      <div className="fcm-push-control__info">
        <div className="fcm-push-control__title-row">
          <strong>Thông báo trên trình duyệt (Web Push)</strong>
          <span
            className={`fcm-status-badge fcm-status-badge--${push.status.toLowerCase()}`}
            data-testid="browser-push-status"
          >
            {push.statusLabel}
          </span>
        </div>
        <p className="fcm-push-control__desc">{helperByStatus[push.status]}</p>
        {push.detail && (
          <p className="fcm-push-control__detail" role="alert">
            {push.detail}
          </p>
        )}
      </div>

      <div className="fcm-push-control__actions">
        {push.status === WEB_PUSH_STATUS.ENABLED ? (
          <button
            type="button"
            className="fcm-push-btn"
            disabled={!push.canDisable}
            onClick={push.disable}
            data-testid="browser-push-disable-btn"
          >
            Tắt thông báo trình duyệt
          </button>
        ) : (
          <button
            type="button"
            className="fcm-push-btn fcm-push-btn--primary"
            disabled={!push.canEnable}
            onClick={push.enable}
            data-testid="browser-push-enable-btn"
          >
            {push.busy ? 'Đang đăng ký…' : 'Bật thông báo trên trình duyệt'}
          </button>
        )}
      </div>
    </div>
  )
}

export default BrowserPushControl
