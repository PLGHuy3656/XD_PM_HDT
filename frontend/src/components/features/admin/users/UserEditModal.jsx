import { useEffect, useState } from 'react'
import Select from '../../../ui/Select'
import { userRoleLabels } from './usersMockData'

const roleOptions = Object.entries(userRoleLabels).map(
  ([value, label]) => ({
    value,
    label,
  }),
)

function UserEditModal({ user, onClose, onSave }) {
  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'FARM_OWNER',
  })

  useEffect(() => {
    if (!user) return

    setForm({
      name: user.name,
      email: user.email,
      phone: user.phone,
      role: user.role,
    })
  }, [user])

  if (!user) return null

  function handleChange(event) {
    const { name, value } = event.target

    setForm((current) => ({
      ...current,
      [name]: value,
    }))
  }

  function handleSubmit(event) {
    event.preventDefault()

    if (
      !form.name.trim() ||
      !form.email.trim() ||
      !form.phone.trim()
    ) {
      return
    }

    onSave({
      ...user,
      name: form.name.trim(),
      email: form.email.trim(),
      phone: form.phone.trim(),
      role: form.role,
    })
  }

  return (
    <div
      className="admin-user-modal-backdrop"
      onMouseDown={onClose}
    >
      <form
        className="admin-user-modal"
        onSubmit={handleSubmit}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="admin-user-modal__heading">
          <div>
            <span>ACCOUNT INFORMATION</span>
            <h2>Chỉnh sửa người dùng</h2>
          </div>
        </div>

        <div className="admin-user-form">
          <label>
            <span>Họ và tên</span>
            <input
              name="name"
              value={form.name}
              onChange={handleChange}
            />
          </label>

          <label>
            <span>Email</span>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
            />
          </label>

          <label>
            <span>Số điện thoại</span>
            <input
              name="phone"
              value={form.phone}
              onChange={handleChange}
            />
          </label>

          <div className="admin-user-form__field">
            <span>Vai trò</span>
            <Select
              value={form.role}
              options={roleOptions}
              onChange={(nextRole) =>
                setForm((current) => ({
                  ...current,
                  role: nextRole,
                }))
              }
            />
          </div>
        </div>

        <div className="admin-user-modal__actions">
          <button
            type="button"
            className="admin-user-modal__cancel"
            onClick={onClose}
          >
            Hủy
          </button>

          <button
            type="submit"
            className="admin-user-modal__confirm"
          >
            Lưu thay đổi
          </button>
        </div>
      </form>
    </div>
  )
}

export default UserEditModal
