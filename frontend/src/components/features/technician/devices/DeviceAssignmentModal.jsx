import EnvironmentSelect from '../../../ui/Select'

function DeviceAssignmentModal({
  device,
  currentZoneName,
  farmName,
  zoneId,
  zoneOptions,
  onZoneChange,
  onClose,
  onConfirm,
}) {
  const handleBackdropMouseDown = (event) => {
    if (event.target === event.currentTarget) {
      onClose()
    }
  }

  return (
    <div
      className="tech-modal-backdrop"
      onMouseDown={handleBackdropMouseDown}
    >
      <section className="tech-device-modal assignment">
        <div className="tech-modal-header">
          <div>
            <span>ZONE ASSIGNMENT</span>
            <h2>Chuyển thiết bị</h2>

            <p>
              {device.id} · {device.name}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Đóng chuyển khu vực"
          >
            ×
          </button>
        </div>

        <div className="tech-current-assignment">
          <span>VỊ TRÍ HIỆN TẠI</span>
          <strong>{currentZoneName}</strong>
          <small>{farmName}</small>
        </div>

        <EnvironmentSelect
          label="Chuyển sang khu vực"
          value={zoneId}
          options={zoneOptions}
          onChange={onZoneChange}
        />

        <div className="tech-assignment-warning">
          <strong>Lưu ý</strong>

          <p>
            Đây đang là thao tác mock phía Frontend. Khi tích hợp
            Backend, quyền Technician và việc gán Zone phải được kiểm
            tra lại tại API.
          </p>
        </div>

        <div className="tech-modal-footer">
          <button
            type="button"
            className="tech-action-secondary"
            onClick={onClose}
          >
            Hủy
          </button>

          <button
            type="button"
            className="tech-action-primary"
            onClick={onConfirm}
          >
            Xác nhận chuyển Zone
          </button>
        </div>
      </section>
    </div>
  )
}

export default DeviceAssignmentModal