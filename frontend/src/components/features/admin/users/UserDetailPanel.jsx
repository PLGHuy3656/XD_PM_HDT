import {
  userRoleLabels,
  userStatusLabels,
} from './usersMockData'

function getInitials(name) {
  return name
    .split(' ')
    .slice(-2)
    .map((part) => part[0])
    .join('')
    .toUpperCase()
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  )
}

function EditIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 20 4.5-1 10-10a2.1 2.1 0 0 0-3-3l-10 10L4 20Z" />
      <path d="m14 7 3 3" />
    </svg>
  )
}

function LockIcon({ locked }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="5" y="10" width="14" height="10" rx="2" />
      {locked ? (
        <path d="M8 10V7a4 4 0 0 1 8 0v3" />
      ) : (
        <path d="M9 10V7a4 4 0 0 1 7.5-2" />
      )}
    </svg>
  )
}

function UserDetailPanel({
  user,
  onClose,
  onEdit,
  onChangeStatus,
}) {
  if (!user) return null

  const isLocked = user.status === 'LOCKED'

  return (
    <div
      className="admin-user-detail-backdrop"
      onMouseDown={onClose}
    >
      <aside
        className="admin-user-detail"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="admin-user-detail__header">
          <div>
            <span>USER PROFILE</span>
            <h2>Chi tiết người dùng</h2>
          </div>

          <button
            type="button"
            className="admin-user-detail__close"
            onClick={onClose}
            aria-label="Đóng"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="admin-user-detail__profile">
          <div className="admin-user-detail__avatar">
            {getInitials(user.name)}
          </div>

          <div>
            <h3>{user.name}</h3>
            <p>{user.email}</p>

            <div className="admin-user-detail__badges">
              <span
                className={`admin-role-badge admin-role-badge--${user.role.toLowerCase()}`}
              >
                {userRoleLabels[user.role]}
              </span>

              <span
                className={`admin-user-status admin-user-status--${user.status.toLowerCase()}`}
              >
                <i />
                {userStatusLabels[user.status]}
              </span>
            </div>
          </div>
        </div>

        <div className="admin-user-detail__section">
          <span className="admin-user-detail__section-label">
            THÔNG TIN TÀI KHOẢN
          </span>

          <dl className="admin-user-detail__info">
            <div>
              <dt>Mã người dùng</dt>
              <dd>{user.id}</dd>
            </div>

            <div>
              <dt>Số điện thoại</dt>
              <dd>{user.phone}</dd>
            </div>

            <div>
              <dt>Ngày tham gia</dt>
              <dd>{user.joinedAt}</dd>
            </div>

            <div>
              <dt>Hoạt động gần nhất</dt>
              <dd>{user.lastActive}</dd>
            </div>
          </dl>
        </div>

        <div className="admin-user-detail__notice">
          <strong>Quản lý truy cập</strong>
          <p>
            Khóa tài khoản chỉ vô hiệu hóa quyền đăng nhập và sử
            dụng hệ thống, không đồng nghĩa với việc xóa dữ liệu
            cá nhân của người dùng.
          </p>
        </div>

        <div className="admin-user-detail__actions">
          <button
            type="button"
            className="admin-user-action admin-user-action--secondary"
            onClick={() => onEdit(user)}
          >
            <EditIcon />
            Chỉnh sửa
          </button>

          <button
            type="button"
            className={`admin-user-action ${
              isLocked
                ? 'admin-user-action--unlock'
                : 'admin-user-action--lock'
            }`}
            onClick={() => onChangeStatus(user)}
          >
            <LockIcon locked={!isLocked} />
            {isLocked ? 'Mở khóa tài khoản' : 'Khóa tài khoản'}
          </button>
        </div>
      </aside>
    </div>
  )
}

export default UserDetailPanel