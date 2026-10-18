import { useState } from 'react'

function FarmRequestModal({ open, onClose, onSubmit }) {
  const [form, setForm] = useState({
    farmName: '',
    address: '',
    note: '',
  })

  if (!open) return null

  const handleChange = (event) => {
    const { name, value } = event.target

    setForm((current) => ({
      ...current,
      [name]: value,
    }))
  }

  const handleSubmit = (event) => {
    event.preventDefault()

    if (!form.farmName.trim() || !form.address.trim()) {
      return
    }

    onSubmit(form)

    setForm({
      farmName: '',
      address: '',
      note: '',
    })
  }

  return (
    <div
      className="farm-modal-backdrop"
      onMouseDown={onClose}
    >
      <div
        className="farm-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="farm-request-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="farm-modal__header">
          <div>
            <span>YÊU CẦU NHÀ YẾN</span>
            <h2 id="farm-request-title">Thêm nhà yến mới</h2>
            <p>
              Gửi thông tin để Administrator kiểm tra và phê duyệt.
            </p>
          </div>

          <button
            type="button"
            className="farm-modal__close"
            onClick={onClose}
            aria-label="Đóng"
          >
            ×
          </button>
        </div>

        <form
          className="farm-modal__form"
          onSubmit={handleSubmit}
        >
          <label>
            <span>Tên nhà yến *</span>
            <input
              name="farmName"
              value={form.farmName}
              onChange={handleChange}
              placeholder="Ví dụ: Nhà yến Bình Minh"
              autoFocus
            />
          </label>

          <label>
            <span>Địa chỉ *</span>
            <input
              name="address"
              value={form.address}
              onChange={handleChange}
              placeholder="Nhập khu vực hoặc địa chỉ nhà yến"
            />
          </label>

          <label>
            <span>Ghi chú</span>
            <textarea
              name="note"
              value={form.note}
              onChange={handleChange}
              rows="4"
              placeholder="Thông tin bổ sung cho Administrator..."
            />
          </label>

          <div className="farm-modal__notice">
            Sau khi gửi, yêu cầu sẽ ở trạng thái chờ duyệt. Nhà yến chỉ
            xuất hiện trong danh sách quản lý sau khi được phê duyệt.
          </div>

          <div className="farm-modal__actions">
            <button
              type="button"
              className="farm-button farm-button--secondary"
              onClick={onClose}
            >
              Hủy
            </button>

            <button
              type="submit"
              className="farm-button farm-button--primary"
            >
              Gửi yêu cầu
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default FarmRequestModal