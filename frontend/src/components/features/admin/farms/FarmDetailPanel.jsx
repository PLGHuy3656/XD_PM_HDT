import { useState } from 'react'
import {
  farmHealthLabels,
  farmStatusLabels,
  getFarmDeviceCount,
  getFarmOnlineDeviceCount,
} from './adminFarmsMockData'

const approvalStatusLabels = {
  PENDING: 'Chờ Admin phê duyệt',
  APPROVED: 'Đã phê duyệt',
  REJECTED: 'Bị từ chối',
}

const deviceStatusLabels = {
  ONLINE: 'Online',
  WARNING: 'Cần chú ý',
  OFFLINE: 'Offline',
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 6 12 12M18 6 6 18" />
    </svg>
  )
}

function FarmDetailPanel({
  farm,
  onClose,
  onEdit,
  onDelete,
  onApprove,
  onReject,
  onAssignTechnician,
  onUnassignTechnician,
}) {
  const [rejectOpen, setRejectOpen] = useState(false)
  const [rejectReason, setRejectReason] = useState('')
  const [rejectError, setRejectError] = useState('')

  if (!farm) return null

  const totalDevices = getFarmDeviceCount(farm)
  const onlineDevices = getFarmOnlineDeviceCount(farm)
  const approvalStatus = farm.approvalStatus || 'APPROVED'

  return (
    <div
      className="admin-farm-detail-backdrop"
      onMouseDown={onClose}
    >
      <aside
        className="admin-farm-detail"
        onMouseDown={(event) =>
          event.stopPropagation()
        }
      >
        <header className="admin-farm-detail__header">
          <div>
            <span>FARM ADMINISTRATION</span>
            <h2>{farm.name}</h2>
            <p>
              {farm.code} · {farm.address}
            </p>
          </div>

          <button
            type="button"
            className="admin-farm-detail__close"
            onClick={onClose}
            aria-label="Đóng"
          >
            <CloseIcon />
          </button>
        </header>

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            type="button"
            className="admin-farm-edit-button"
            onClick={() => onEdit(farm)}
          >
            Chỉnh sửa nhà yến
          </button>
          {onDelete && (
            <button
              type="button"
              className="admin-farm-edit-button"
              style={{ borderColor: '#dc2626', color: '#dc2626' }}
              onClick={() => onDelete(farm)}
            >
              Xóa nhà yến
            </button>
          )}
          {onUnassignTechnician && farm.technician?.id && (
            <button
              type="button"
              className="admin-farm-edit-button"
              onClick={() => onUnassignTechnician(farm)}
            >
              Hủy phân công KTV
            </button>
          )}
          {onApprove && approvalStatus !== 'APPROVED' && (
            <button
              type="button"
              className="admin-farm-edit-button"
              style={{ background: '#059669', color: '#fff', borderColor: '#059669' }}
              onClick={() => onApprove(farm)}
            >
              Phê duyệt nhà yến
            </button>
          )}
          {onReject && approvalStatus === 'PENDING' && (
            <button
              type="button"
              className="admin-farm-edit-button"
              style={{ borderColor: '#d97706', color: '#b45309' }}
              onClick={() => {
                setRejectError('')
                setRejectOpen((prev) => !prev)
              }}
            >
              Từ chối nhà yến
            </button>
          )}
        </div>

        {rejectOpen && (
          <div style={{ marginTop: '0.75rem', padding: '0.75rem', borderRadius: '8px', background: '#fffbeb', border: '1px solid #fcd34d' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.4rem', color: '#92400e' }}>
              Lý do từ chối *
            </label>
            <textarea
              rows={2}
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Nhập lý do từ chối để Farm Owner nắm thông tin..."
              style={{ width: '100%', padding: '0.5rem', borderRadius: '6px', border: '1px solid #d1d5db', marginBottom: '0.5rem' }}
            />
            {rejectError && (
              <p style={{ color: '#b91c1c', fontSize: '0.8rem', margin: '0 0 0.5rem' }}>{rejectError}</p>
            )}
            <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
              <button
                type="button"
                className="admin-farm-edit-button"
                style={{ width: 'auto', marginTop: 0 }}
                onClick={() => {
                  setRejectOpen(false)
                  setRejectReason('')
                  setRejectError('')
                }}
              >
                Hủy
              </button>
              <button
                type="button"
                className="admin-farm-edit-button"
                style={{ width: 'auto', marginTop: 0, background: '#dc2626', color: '#fff', borderColor: '#dc2626' }}
                onClick={async () => {
                  if (!rejectReason.trim()) {
                    setRejectError('Vui lòng nhập lý do từ chối.')
                    return
                  }
                  const ok = await onReject(farm, rejectReason.trim())
                  if (ok) {
                    setRejectOpen(false)
                    setRejectReason('')
                  }
                }}
              >
                Xác nhận từ chối
              </button>
            </div>
          </div>
        )}

        <div className="admin-farm-detail__summary">
          <div>
            <span>Trạng thái</span>
            <strong>
              {farmStatusLabels[farm.status]}
            </strong>
          </div>
          <div>
            <span>Phê duyệt</span>
            <strong>{approvalStatusLabels[approvalStatus] || approvalStatus}</strong>
            {farm.rejectionReason && (
              <small style={{ display: 'block', color: '#b91c1c', marginTop: '2px' }}>
                Lý do: {farm.rejectionReason}
              </small>
            )}
          </div>

          <div>
            <span>Tình trạng</span>
            <strong>
              {farmHealthLabels[farm.health]}
            </strong>
          </div>

          <div>
            <span>Khu vực</span>
            <strong>{farm.zones.length}</strong>
          </div>

          <div>
            <span>Thiết bị</span>
            <strong>
              {onlineDevices}/{totalDevices} online
            </strong>
          </div>
        </div>

        <section className="admin-farm-detail__section">
          <span className="admin-farm-detail__label">
            FARM OWNER
          </span>

          <div className="admin-farm-contact-card">
            <div className="admin-farm-contact-card__avatar">
              FO
            </div>

            <div>
              <strong>{farm.owner?.name || 'Chưa gán chủ trại'}</strong>
              <span>{farm.owner?.email || '--'}</span>
              <span>{farm.owner?.phone || '--'}</span>
              <small>{farm.owner?.id || '--'}</small>
            </div>
          </div>
        </section>

        <section className="admin-farm-detail__section">
          <div className="admin-farm-detail__section-heading">
            <span className="admin-farm-detail__label">
              TECHNICIAN PHỤ TRÁCH
            </span>

            {farm.technician && (
              <span className="admin-farm-assignment-badge">
                Đang phụ trách
              </span>
            )}
          </div>

          {farm.technician ? (
            <div className="admin-farm-contact-card">
              <div className="admin-farm-contact-card__avatar tech">
                KT
              </div>

              <div>
                <strong>
                  {farm.technician.name}
                </strong>
                <span>
                  {farm.technician.email}
                </span>
                <span>
                  {farm.technician.phone}
                </span>
                <small>
                  {farm.technician.id}
                </small>
              </div>
            </div>
          ) : (
            <div className="admin-farm-no-technician">
              Nhà yến chưa có Technician phụ trách.
            </div>
          )}

          <button
            type="button"
            className="admin-farm-assign-button"
            onClick={() =>
              onAssignTechnician(farm)
            }
          >
            {farm.technician
              ? 'Thay đổi phân công'
              : 'Phân công Technician'}
          </button>
        </section>

        <section className="admin-farm-detail__section">
          <span className="admin-farm-detail__label">
            KHU VỰC &amp; THIẾT BỊ
          </span>

          <div className="admin-farm-zones">
            {farm.zones.length === 0 ? (
              <div style={{ padding: '0.75rem 0', color: '#64748b', fontSize: '0.88rem' }}>
                Nhà yến chưa có khu vực (Zone) nào. Farm Owner quản lý cấu trúc khu vực trực tiếp.
              </div>
            ) : (
              farm.zones.map((zone) => (
                <article
                  key={zone.id}
                  className="admin-farm-zone"
                >
                  <div className="admin-farm-zone__header">
                    <div>
                      <strong>{zone.name}</strong>
                      <span>{zone.code || zone.floor}</span>
                    </div>

                    <small>
                      {zone.devices.length} thiết bị
                    </small>
                  </div>

                  <div className="admin-farm-zone__devices">
                    {zone.devices.length === 0 ? (
                      <div style={{ padding: '0.4rem 0', color: '#8a929c', fontSize: '0.82rem' }}>
                        Chưa có thiết bị trong khu vực này.
                      </div>
                    ) : (
                      zone.devices.map((device) => (
                        <div
                          key={device.id}
                          className="admin-farm-device"
                        >
                          <div>
                            <strong>
                              {device.name}
                            </strong>

                            <span>
                              {device.id} · {device.type}
                            </span>
                          </div>

                          <span
                            className={`admin-farm-device__status admin-farm-device__status--${device.status.toLowerCase()}`}
                          >
                            <i />
                            {
                              deviceStatusLabels[
                                device.status
                              ]
                            }
                          </span>
                        </div>
                      ))
                    )}
                  </div>
                </article>
              ))
            )}

            {farm.unassignedDevices && farm.unassignedDevices.length > 0 && (
              <article className="admin-farm-zone" style={{ borderStyle: 'dashed' }}>
                <div className="admin-farm-zone__header">
                  <div>
                    <strong>Chưa phân bổ Zone</strong>
                    <span>Chờ gán khu vực</span>
                  </div>
                  <small>{farm.unassignedDevices.length} thiết bị</small>
                </div>

                <div className="admin-farm-zone__devices">
                  {farm.unassignedDevices.map((device) => (
                    <div key={device.id} className="admin-farm-device">
                      <div>
                        <strong>{device.name}</strong>
                        <span>{device.id} · {device.type}</span>
                      </div>
                      <span
                        className={`admin-farm-device__status admin-farm-device__status--${device.status.toLowerCase()}`}
                      >
                        <i />
                        {deviceStatusLabels[device.status]}
                      </span>
                    </div>
                  ))}
                </div>
              </article>
            )}
          </div>
        </section>
      </aside>
    </div>
  )
}

export default FarmDetailPanel
