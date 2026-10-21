import { useEffect, useState } from 'react'
import Select from '../../../ui/Select'

const farmStatusOptions = [
  { value: 'ACTIVE', label: 'Đang hoạt động' },
  { value: 'INACTIVE', label: 'Ngừng hoạt động' },
]

function FarmEditModal({ farm, onClose, onSave }) {
  const [form, setForm] = useState({
    name: '',
    address: '',
    status: 'ACTIVE',
  })

  const [errors, setErrors] = useState({})

  useEffect(() => {
    if (!farm) return

    setForm({
      name: farm.name,
      address: farm.address,
      status: farm.status,
    })

    setErrors({})
  }, [farm])

  if (!farm) return null

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

  function handleSubmit(event) {
    event.preventDefault()

    const nextErrors = {}

    if (!form.name.trim()) {
      nextErrors.name = 'Vui lòng nhập tên nhà yến.'
    }

    if (!form.address.trim()) {
      nextErrors.address = 'Vui lòng nhập địa chỉ.'
    }

    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) return

    onSave({
      ...farm,
      name: form.name.trim(),
      address: form.address.trim(),
      status: form.status,
    })
  }

  return (
    <div
      className="admin-farm-modal-backdrop"
      onMouseDown={onClose}
    >
      <form
        className="admin-farm-modal"
        onSubmit={handleSubmit}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="admin-farm-modal__header">
          <span>FARM INFORMATION</span>
          <h2>Chỉnh sửa nhà yến</h2>
          <p>
            Cập nhật thông tin quản trị cơ bản của nhà yến.
          </p>
        </header>

        <div className="admin-farm-form">
          <label>
            <span>Mã nhà yến</span>

            <input
              value={farm.code}
              disabled
            />

            <small>
              Mã định danh không thể thay đổi.
            </small>
          </label>

          <label>
            <span>Tên nhà yến *</span>

            <input
              name="name"
              value={form.name}
              onChange={handleChange}
            />

            {errors.name && (
              <small className="admin-farm-form__error">
                {errors.name}
              </small>
            )}
          </label>

          <label>
            <span>Địa chỉ *</span>

            <input
              name="address"
              value={form.address}
              onChange={handleChange}
            />

            {errors.address && (
              <small className="admin-farm-form__error">
                {errors.address}
              </small>
            )}
          </label>

          <div className="admin-farm-form__field">
            <span>Trạng thái</span>

            <Select
              value={form.status}
              options={farmStatusOptions}
              onChange={(nextStatus) =>
                setForm((current) => ({
                  ...current,
                  status: nextStatus,
                }))
              }
            />
          </div>
        </div>

        <div className="admin-farm-edit-note">
          <strong>Phạm vi chỉnh sửa</strong>

          <p>
            Farm Owner, Technician phụ trách, khu vực và thiết bị
            được quản lý bởi các chức năng nghiệp vụ tương ứng và
            không thay đổi tại đây.
          </p>
        </div>

        <div className="admin-farm-modal__actions">
          <button
            type="button"
            className="admin-farm-modal__cancel"
            onClick={onClose}
          >
            Hủy
          </button>

          <button
            type="submit"
            className="admin-farm-modal__save"
          >
            Lưu thay đổi
          </button>
        </div>
      </form>
    </div>
  )
}

export default FarmEditModal
