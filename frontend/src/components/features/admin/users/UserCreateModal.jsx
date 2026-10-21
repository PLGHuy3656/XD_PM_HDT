import { useState } from 'react'
import { userRoleLabels } from './usersMockData'

const initialForm = {
  name: '',
  email: '',
  phone: '',
  role: 'FARM_OWNER',
}

function UserCreateModal({ open, onClose, onCreate }) {
  const [form, setForm] = useState(initialForm)
  const [errors, setErrors] = useState({})

  if (!open) return null

  function handleChange(event) {
    const { name, value } = event.target

    setForm((current) => ({
      ...current,
      [name]: value,
    }))

    setErrors((current) => ({
      ...current,
      [name]: '',
    }))
  }

  function validate() {
    const nextErrors = {}

    if (!form.name.trim()) {
      nextErrors.name = 'Vui lòng nhập họ và tên.'
    }

    if (!form.email.trim()) {
      nextErrors.email = 'Vui lòng nhập email.'
    } else if (
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())
    ) {
      nextErrors.email = 'Email không hợp lệ.'
    }

    if (!form.phone.trim()) {
      nextErrors.phone = 'Vui lòng nhập số điện thoại.'
    }

    setErrors(nextErrors)

    return Object.keys(nextErrors).length === 0
  }

  function handleSubmit(event) {
    event.preventDefault()

    if (!validate()) return

    onCreate({
      name: form.name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      role: form.role,
    })

    setForm(initialForm)
    setErrors({})
  }

  function handleClose() {
    setForm(initialForm)
    setErrors({})
    onClose()
  }

  return (
    <div
      className="admin-user-modal-backdrop"
      onMouseDown={handleClose}
    >
      <form
        className="admin-user-modal"
        onSubmit={handleSubmit}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="admin-user-modal__heading">
          <div>
            <span>CREATE ACCOUNT</span>
            <h2>Thêm người dùng</h2>
          </div>

          <p className="admin-user-modal__description">
            Tạo tài khoản mới và xác định vai trò truy cập
            trong hệ thống NestMate.
          </p>
        </div>

        <div className="admin-user-form">
          <label>
            <span>Họ và tên *</span>

            <input
              name="name"
              value={form.name}
              onChange={handleChange}
              placeholder="Nhập họ và tên"
              autoFocus
            />

            {errors.name && (
              <small className="admin-user-form__error">
                {errors.name}
              </small>
            )}
          </label>

          <label>
            <span>Email *</span>

            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              placeholder="example@nestmate.vn"
            />

            {errors.email && (
              <small className="admin-user-form__error">
                {errors.email}
              </small>
            )}
          </label>

          <label>
            <span>Số điện thoại *</span>

            <input
              name="phone"
              value={form.phone}
              onChange={handleChange}
              placeholder="090 123 4567"
            />

            {errors.phone && (
              <small className="admin-user-form__error">
                {errors.phone}
              </small>
            )}
          </label>

          <label>
            <span>Vai trò *</span>

            <select
              name="role"
              value={form.role}
              onChange={handleChange}
            >
              {Object.entries(userRoleLabels).map(
                ([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ),
              )}
            </select>
          </label>
        </div>

        <div className="admin-user-create-note">
          <strong>Quyền truy cập</strong>

          <p>
            Tài khoản mới sẽ được cấp quyền theo vai trò đã
            chọn. Quyền truy cập thực tế vẫn được kiểm soát
            bởi cơ chế phân quyền của hệ thống.
          </p>
        </div>

        <div className="admin-user-modal__actions">
          <button
            type="button"
            className="admin-user-modal__cancel"
            onClick={handleClose}
          >
            Hủy
          </button>

          <button
            type="submit"
            className="admin-user-modal__confirm"
          >
            Tạo tài khoản
          </button>
        </div>
      </form>
    </div>
  )
}

export default UserCreateModal