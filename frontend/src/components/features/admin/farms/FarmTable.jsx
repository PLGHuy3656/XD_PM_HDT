import {
  farmHealthLabels,
  farmStatusLabels,
  getFarmDeviceCount,
} from './adminFarmsMockData'

function FarmTable({ farms, onViewFarm }) {
  if (farms.length === 0) {
    return (
      <div className="admin-farms-empty">
        <strong>Không tìm thấy nhà yến</strong>
        <p>Thử thay đổi từ khóa hoặc bộ lọc hiện tại.</p>
      </div>
    )
  }

  return (
    <div className="admin-farms-table-wrap">
      <table className="admin-farms-table">
        <thead>
          <tr>
            <th>Nhà yến</th>
            <th>Farm Owner</th>
            <th>Technician phụ trách</th>
            <th>Khu vực</th>
            <th>Thiết bị</th>
            <th>Trạng thái</th>
            <th />
          </tr>
        </thead>

        <tbody>
          {farms.map((farm) => (
            <tr key={farm.id}>
              <td>
                <div className="admin-farm-name">
                  <strong>{farm.name}</strong>
                  <span>{farm.address}</span>
                  <small>{farm.code}</small>
                </div>
              </td>

              <td>
                <div className="admin-farm-person">
                  <strong>{farm.owner.name}</strong>
                  <span>{farm.owner.email}</span>
                </div>
              </td>

              <td>
                <div className="admin-farm-person">
                  <strong>{farm.technician.name}</strong>
                  <span>{farm.technician.email}</span>
                </div>
              </td>

              <td>
                <strong className="admin-farm-count">
                  {farm.zones.length}
                </strong>
              </td>

              <td>
                <strong className="admin-farm-count">
                  {getFarmDeviceCount(farm)}
                </strong>
              </td>

              <td>
                <div className="admin-farm-status-stack">
                  <span className="admin-farm-status">
                    <i />
                    {farmStatusLabels[farm.status]}
                  </span>

                  <small
                    className={
                      farm.health === 'ATTENTION'
                        ? 'attention'
                        : ''
                    }
                  >
                    {farmHealthLabels[farm.health]}
                  </small>
                </div>
              </td>

              <td>
                <button
                  type="button"
                  className="admin-farm-more"
                  onClick={() => onViewFarm(farm)}
                  aria-label={`Xem ${farm.name}`}
                >
                  •••
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default FarmTable