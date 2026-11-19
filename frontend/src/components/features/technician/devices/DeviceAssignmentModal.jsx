import EnvironmentSelect from '../../../ui/Select'

function DeviceAssignmentModal({
  device,
  currentZoneName = 'Chưa phân bổ Zone',
  farmName = '',
  zoneId = '',
  zoneOptions = [],
  saving = false,
  error = '',
  onZoneChange,
  onClose,
  onConfirm,
}) {
  if (!device) return null

  const safeOptions = Array.isArray(zoneOptions) && zoneOptions.length > 0
    ? zoneOptions
    : [{ value: '', label: 'Chưa phân bổ Zone' }]

  const handleBackdropMouseDown = (event) => {
    if (event.target === event.currentTarget && !saving) {
      onClose?.()
    }
  }

  return (
    <div
      className="tech-modal-backdrop"
      role="presentation"
      onMouseDown={handleBackdropMouseDown}
    >
      <section
        className="tech-device-modal assignment"
        role="dialog"
        aria-modal="true"
        aria-label="Gán / đổi khu vực"
      >
        <div className="tech-modal-header">
          <div>
            <span>DEVICE–ZONE ASSIGNMENT</span>
            <h2>Gán / đổi khu vực</h2>

            <p>
              {device.nodeId || device.id} · {device.name}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            aria-label="Đóng gán hoặc đổi khu vực"
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
          label="Chọn khu vực lắp đặt (Zone)"
          value={zoneId ?? ''}
          options={safeOptions}
          onChange={(val) => onZoneChange?.(val)}
        />

        {error && (
          <div style={{ marginTop: '12px', padding: '10px 12px', borderRadius: '10px', background: '#fef2f2', color: '#b91c1c', fontSize: '12px', fontWeight: 600 }}>
            {error}
          </div>
        )}

        <div className="tech-assignment-warning">
          <strong>Phạm vi phân bổ</strong>

          <p>
            Chỉ được chọn khu vực (Zone) thuộc cùng nhà yến đang phân công. Thay đổi sẽ được lưu trực tiếp vào hệ thống quản lý.
          </p>
        </div>

        <div className="tech-modal-footer">
          <button
            type="button"
            className="tech-action-secondary"
            onClick={onClose}
            disabled={saving}
          >
            Hủy
          </button>

          <button
            type="button"
            className="tech-action-primary"
            onClick={onConfirm}
            disabled={saving}
          >
            {saving ? 'Đang lưu...' : 'Lưu khu vực'}
          </button>
        </div>
      </section>
    </div>
  )
}

export default DeviceAssignmentModal
