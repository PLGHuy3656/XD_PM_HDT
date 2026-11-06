import { useEffect, useMemo, useState } from 'react'

function TechnicianAssignmentModal({
  farm,
  technicians,
  farms,
  onClose,
  onConfirm,
}) {
  const [selectedTechnicianId, setSelectedTechnicianId] =
    useState('')

  useEffect(() => {
    if (!farm) return

    setSelectedTechnicianId(
      farm.technician?.id || '',
    )
  }, [farm])

  const technicianFarmCounts = useMemo(() => {
    return farms.reduce((counts, currentFarm) => {
      const technicianId = currentFarm.technician?.id

      if (!technicianId) return counts

      return {
        ...counts,
        [technicianId]:
          (counts[technicianId] || 0) + 1,
      }
    }, {})
  }, [farms])

  if (!farm) return null

  const selectedTechnician = technicians.find(
    (technician) =>
      technician.id === selectedTechnicianId,
  )

  const hasChanged =
    selectedTechnicianId !==
    (farm.technician?.id || '')

  function handleSubmit(event) {
    event.preventDefault()

    if (!selectedTechnician || !hasChanged) {
      return
    }

    onConfirm(farm, selectedTechnician)
  }

  return (
    <div
      className="admin-assignment-backdrop"
      onMouseDown={onClose}
    >
      <form
        className="admin-assignment-modal"
        onSubmit={handleSubmit}
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        <header className="admin-assignment-modal__header">
          <span>TECHNICIAN ASSIGNMENT</span>
          <h2>Phân công Technician</h2>

          <p>
            Chọn Technician chịu trách nhiệm hỗ trợ kỹ thuật
            cho <strong>{farm.name}</strong>.
          </p>
        </header>

        <section className="admin-assignment-current">
          <span>PHÂN CÔNG HIỆN TẠI</span>

          {farm.technician ? (
            <div>
              <strong>
                {farm.technician.name}
              </strong>

              <p>{farm.technician.email}</p>
            </div>
          ) : (
            <p>Nhà yến chưa được phân công Technician.</p>
          )}
        </section>

        <div className="admin-assignment-list">
          <span className="admin-assignment-list__label">
            TECHNICIAN KHẢ DỤNG
          </span>

          {technicians.map((technician) => {
            const selected =
              technician.id ===
              selectedTechnicianId

            const farmCount =
              technicianFarmCounts[technician.id] || 0

            return (
              <label
                key={technician.id}
                className={`admin-assignment-option ${
                  selected
                    ? 'admin-assignment-option--selected'
                    : ''
                }`}
              >
                <input
                  type="radio"
                  name="technician"
                  value={technician.id}
                  checked={selected}
                  onChange={(event) =>
                    setSelectedTechnicianId(
                      event.target.value,
                    )
                  }
                />

                <div className="admin-assignment-option__avatar">
                  KT
                </div>

                <div className="admin-assignment-option__info">
                  <strong>{technician.name}</strong>
                  <span>{technician.email}</span>
                  <span>{technician.phone}</span>
                </div>

                <div className="admin-assignment-option__load">
                  <strong>{farmCount}</strong>
                  <span>Farm phụ trách</span>
                </div>
              </label>
            )
          })}
        </div>

        {selectedTechnician && hasChanged && (
          <div className="admin-assignment-confirmation">
            <strong>Xác nhận thay đổi</strong>

            <p>
              Technician phụ trách sẽ được thay đổi từ{' '}
              <b>
                {farm.technician?.name ||
                  'Chưa phân công'}
              </b>{' '}
              sang{' '}
              <b>{selectedTechnician.name}</b>.
            </p>

            <small>
              Khi tích hợp Backend, thay đổi này sẽ được ghi
              nhận vào lịch sử phân công và tạo thông báo cho
              Technician liên quan.
            </small>
          </div>
        )}

        <div className="admin-assignment-modal__actions">
          <button
            type="button"
            className="admin-assignment-cancel"
            onClick={onClose}
          >
            Hủy
          </button>

          <button
            type="submit"
            className="admin-assignment-confirm"
            disabled={!selectedTechnician || !hasChanged}
          >
            Xác nhận phân công
          </button>
        </div>
      </form>
    </div>
  )
}

export default TechnicianAssignmentModal