function UserStatusModal({
  user,
  onClose,
  onConfirm,
}) {
  if (!user) return null

  const isLocked = user.status === 'LOCKED'

  return (
    <div className="admin-user-modal-backdrop">
      <div className="admin-user-modal admin-user-status-modal">
        <div className="admin-user-status-modal__icon">
          !
        </div>

        <h2>
          {isLocked
            ? 'Mở khóa tài khoản?'
            : 'Khóa tài khoản?'}
        </h2>

        <p>
          {isLocked ? (
            <>
              <strong>{user.name}</strong> sẽ có thể đăng nhập và
              tiếp tục sử dụng các chức năng được cấp quyền.
            </>
          ) : (
            <>
              <strong>{user.name}</strong> sẽ không thể đăng nhập
              hoặc tiếp tục sử dụng các chức năng của hệ thống.
            </>
          )}
        </p>

        {!isLocked && (
          <div className="admin-user-legal-note">
            <strong>Lưu ý về dữ liệu cá nhân</strong>

            <p>
              Việc khóa tài khoản không đồng nghĩa với xóa dữ liệu
              cá nhân. Dữ liệu liên quan tiếp tục được quản lý theo
              chính sách lưu trữ của hệ thống và quy định pháp luật
              về bảo vệ dữ liệu cá nhân.
            </p>

            <small>
              Tuân thủ Luật Bảo vệ dữ liệu cá nhân số
              91/2025/QH15 và các quy định pháp luật có liên quan.
            </small>
          </div>
        )}

        <div className="admin-user-modal__actions">
          <button
            type="button"
            className="admin-user-modal__cancel"
            onClick={onClose}
          >
            Hủy
          </button>

          <button
            type="button"
            className={
              isLocked
                ? 'admin-user-modal__confirm'
                : 'admin-user-modal__danger'
            }
            onClick={() => onConfirm(user)}
          >
            {isLocked ? 'Xác nhận mở khóa' : 'Xác nhận khóa'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default UserStatusModal