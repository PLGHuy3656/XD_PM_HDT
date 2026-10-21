import {
  farmHealthLabels,
  farmStatusLabels,
  getFarmDeviceCount,
  getFarmOnlineDeviceCount,
} from './adminFarmsMockData'

const deviceStatusLabels = {
  ONLINE: 'Online',
  WARNING: 'Cần chú ý',
  OFFLINE: 'Offline',
}

function FarmDetailPanel({
  farm,
  onClose,
  onEdit,
  onAssignTechnician,
}) {
  if (!farm) return null

  const totalDevices = getFarmDeviceCount(farm)
  const onlineDevices = getFarmOnlineDeviceCount(farm)

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
            onClick={onClose}
            aria-label="Đóng"
          >
            ×
          </button>
        </header>

        <button
          type="button"
          className="admin-farm-edit-button"
          onClick={() => onEdit(farm)}
        >
          Chỉnh sửa nhà yến
        </button>

        <div className="admin-farm-detail__summary">
          <div>
            <span>Trạng thái</span>
            <strong>
              {farmStatusLabels[farm.status]}
            </strong>
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
              <strong>{farm.owner.name}</strong>
              <span>{farm.owner.email}</span>
              <span>{farm.owner.phone}</span>
              <small>{farm.owner.id}</small>
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
            KHU VỰC & THIẾT BỊ
          </span>

          <div className="admin-farm-zones">
            {farm.zones.map((zone) => (
              <article
                key={zone.id}
                className="admin-farm-zone"
              >
                <div className="admin-farm-zone__header">
                  <div>
                    <strong>{zone.name}</strong>
                    <span>{zone.floor}</span>
                  </div>

                  <small>
                    {zone.devices.length} thiết bị
                  </small>
                </div>

                <div className="admin-farm-zone__devices">
                  {zone.devices.map((device) => (
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
                  ))}
                </div>
              </article>
            ))}
          </div>
        </section>
      </aside>
    </div>
  )
}

export default FarmDetailPanel