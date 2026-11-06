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

function UserTable({ users, onViewUser }) {
  if (users.length === 0) {
    return (
      <div className="admin-users-empty">
        <div className="admin-users-empty__icon">⌕</div>
        <strong>Không tìm thấy người dùng</strong>
        <p>Thử thay đổi từ khóa hoặc bộ lọc hiện tại.</p>
      </div>
    )
  }

  return (
    <div className="admin-users-table-wrap">
      <table className="admin-users-table">
        <thead>
          <tr>
            <th>Người dùng</th>
            <th>Vai trò</th>
            <th>Liên hệ</th>
            <th>Trạng thái</th>
            <th>Hoạt động gần nhất</th>
            <th />
          </tr>
        </thead>

        <tbody>
          {users.map((user) => (
            <tr key={user.id}>
              <td>
                <div className="admin-user-identity">
                  <div className="admin-user-avatar">
                    {getInitials(user.name)}
                  </div>

                  <div>
                    <strong>{user.name}</strong>
                    <span>{user.email}</span>
                    <small>{user.id}</small>
                  </div>
                </div>
              </td>

              <td>
                <span
                  className={`admin-role-badge admin-role-badge--${user.role.toLowerCase()}`}
                >
                  {userRoleLabels[user.role]}
                </span>
              </td>

              <td>
                <div className="admin-user-contact">
                  <span>{user.phone}</span>
                  <small>Tham gia {user.joinedAt}</small>
                </div>
              </td>

              <td>
                <span
                  className={`admin-user-status admin-user-status--${user.status.toLowerCase()}`}
                >
                  <i />
                  {userStatusLabels[user.status]}
                </span>
              </td>

              <td>
                <span className="admin-user-last-active">
                  {user.lastActive}
                </span>
              </td>

              <td>
                <button
                  type="button"
                  className="admin-user-more"
                  aria-label={`Xem chi tiết ${user.name}`}
                  title="Xem chi tiết"
                  onClick={() => onViewUser(user)}
                >
                  •••
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default UserTable