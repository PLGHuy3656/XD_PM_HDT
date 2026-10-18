import {
  roles,
  recentAccounts,
} from './dashboardMockData'

function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

function UserAccessPanel({ onOpen }) {
  return (
    <section className="admin-panel">
      <div className="admin-panel-heading">
        <div>
          <span>USER & ACCESS</span>
          <h2>Người dùng & phân quyền</h2>
          <p>Phân bổ vai trò và các tài khoản gần đây</p>
        </div>

        <button
          type="button"
          className="admin-heading-action"
          onClick={() => onOpen('/admin/users')}
          aria-label="Mở quản lý người dùng"
        >
          <span>Xem tất cả</span>
          <ArrowIcon />
        </button>
      </div>

      <div className="admin-role-grid">
        {roles.map((role) => (
          <article className="admin-role-card" key={role.id}>
            <span className="admin-role-card__icon">
              {role.icon}
            </span>

            <div className="admin-role-card__content">
              <strong>{role.label}</strong>
              <p>{role.description}</p>
            </div>

            <strong className="admin-role-card__value">
              {role.value}
            </strong>
          </article>
        ))}
      </div>

      <div className="admin-recent">
        <div className="admin-recent__heading">
          <div>
            <span>RECENT ACCOUNTS</span>
            <strong>Tài khoản gần đây</strong>
          </div>

          <span>3 tài khoản mới nhất</span>
        </div>

        <div className="admin-account-list">
          {recentAccounts.map((account) => (
            <article
              className="admin-account-row"
              key={account.id}
            >
              <span className="admin-account-avatar">
                {account.name
                  .split(' ')
                  .slice(-2)
                  .map((word) => word[0])
                  .join('')}
              </span>

              <div className="admin-account-identity">
                <strong>{account.name}</strong>
                <span>{account.email}</span>
              </div>

              <span className="admin-account-role">
                {account.role}
              </span>

              <time>{account.time}</time>
            </article>
          ))}
        </div>
      </div>
    </section>
  )
}

export default UserAccessPanel
