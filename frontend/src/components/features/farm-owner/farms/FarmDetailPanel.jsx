import { useEffect, useState } from 'react'

import apiClient from '../../../../api/client.js'
import { USE_MOCK } from '../../../../api/config.js'
import { useAuth } from '../../../../context/AuthContext'
import InspectionRequestPanel from '../../inspections/InspectionRequestPanel'

/**
 * INT03-R1 (R1-06): technicians come from GET /api/farms/{id} (all ACTIVE assignments, primary first).
 * The farm LIST response carries no technician data, which is why the panel used to show
 * "Chưa phân công" for every farm. Nothing is invented when the API returns none.
 */
function useFarmAssignmentDetail(farmId) {
  const [entry, setEntry] = useState({ farmId: null, state: 'IDLE', technicians: [], devices: [], error: null })
  useEffect(() => {
    if (USE_MOCK || !farmId) return undefined
    const controller = new AbortController()
    Promise.all([
      apiClient.get(`/api/farms/${encodeURIComponent(farmId)}`, { signal: controller.signal, retries: 0 }),
      apiClient
        .get('/api/devices', { signal: controller.signal, retries: 0, params: { farm_id: farmId } })
        .catch(() => []),
    ])
      .then(([detail, devices]) => {
        const devs = (Array.isArray(devices) ? devices : devices?.items || []).map((d) => ({
          id: d.device_id || d.id,
          name: d.name,
          nodeId: d.node_id,
          zoneId: d.zone_id || null,
        }))
        setEntry({ farmId, state: 'OK', technicians: Array.isArray(detail?.technicians) ? detail.technicians : [], devices: devs, error: null })
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setEntry({ farmId, state: 'ERROR', technicians: [], devices: [], error: err?.message || 'Không tải được thông tin phân công.' })
      })
    return () => controller.abort()
  }, [farmId])
  return entry.farmId === farmId ? entry : { state: farmId ? 'LOADING' : 'IDLE', technicians: [], devices: [], error: null }
}

function initials(name = '') {
  return String(name || '?')
    .split(' ')
    .filter(Boolean)
    .slice(-2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()
}

function FarmDetailPanel({ farm }) {
  const { user } = useAuth()
  const assignment = useFarmAssignmentDetail(farm?.id || null)

  if (!farm) {
    return (
      <section className="farm-detail farm-detail--empty">
        <div>
          <span className="farm-detail__empty-icon">⌂</span>
          <h3>Chọn một nhà yến</h3>
          <p>Chọn nhà yến bên trái để xem thông tin chi tiết.</p>
        </div>
      </section>
    )
  }

  const technician = farm.assignedTechnician
  const approvalStatus = farm.approvalStatus || 'APPROVED'
  const approvalText =
    approvalStatus === 'PENDING'
      ? 'Chờ Admin phê duyệt'
      : approvalStatus === 'REJECTED'
      ? 'Bị từ chối'
      : 'Đã phê duyệt'

  return (
    <section className="farm-detail">
      <div className="farm-detail__header">
        <div>
          <span className="farm-detail__eyebrow">CHI TIẾT NHÀ YẾN</span>
          <h2>{farm.name}</h2>
          <p>
            {farm.code} · {farm.address}
          </p>
        </div>

        <span
          className="farm-detail__active"
          style={
            approvalStatus === 'PENDING'
              ? { background: '#fef3c7', color: '#92400e' }
              : approvalStatus === 'REJECTED'
              ? { background: '#fef2f2', color: '#991b1b' }
              : undefined
          }
        >
          <i />
          {approvalText}
        </span>
      </div>

      {approvalStatus === 'PENDING' && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fffbeb', color: '#92400e', border: '1px solid #fcd34d' }}>
          Nhà yến đang chờ Admin phê duyệt. Các thao tác tạo khu vực, đăng ký thiết bị và điều khiển thiết bị sẽ khả dụng sau khi được duyệt.
        </div>
      )}
      {approvalStatus === 'REJECTED' && (
        <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '8px', background: '#fef2f2', color: '#991b1b', border: '1px solid #fecaca' }}>
          Nhà yến đã bị từ chối{farm.rejectionReason ? `: ${farm.rejectionReason}` : '.'}
        </div>
      )}

      <div className="farm-detail__summary">
        <article>
          <span>Khu vực</span>
          <strong>{farm.zoneCount ?? farm.zones.length}</strong>
          <small>Đang được giám sát</small>
        </article>

        <article>
          <span>Thiết bị</span>
          <strong>
            {farm.onlineDevices ?? 0}/{farm.totalDevices ?? 0}
          </strong>
          <small>Thiết bị trực tuyến</small>
        </article>

        <article>
          <span>Nhiệt độ TB</span>
          <strong>{farm.temperature != null ? `${farm.temperature}°C` : '--'}</strong>
          <small>{farm.temperature != null ? 'Trong ngưỡng vận hành' : 'Chưa có dữ liệu'}</small>
        </article>

        <article>
          <span>Độ ẩm TB</span>
          <strong>{farm.humidity != null ? `${farm.humidity}%` : '--'}</strong>
          <small>{farm.humidity != null ? 'Mức hiện tại' : 'Chưa có dữ liệu'}</small>
        </article>
      </div>

      <div className="farm-technician" data-testid="farm-technicians" data-state={USE_MOCK ? 'MOCK' : assignment.state}>
        <div className="farm-technician__heading">
          <div>
            <span className="farm-technician__eyebrow">
              HỖ TRỢ KỸ THUẬT
            </span>
            <h3>Kỹ thuật viên phụ trách</h3>
            <p>
              Kỹ thuật viên đang được Admin phân công hỗ trợ nhà yến này.
            </p>
          </div>

          {!USE_MOCK && assignment.technicians.length > 0 && (
            <span className="farm-technician__status">
              <i />
              {assignment.technicians.length} người đang phụ trách
            </span>
          )}
        </div>

        {USE_MOCK && technician ? (
          <div className="farm-technician__profile">
            <div className="farm-technician__identity">
              <div className="farm-technician__avatar">{initials(technician.name)}</div>
              <div>
                <strong>{technician.name}</strong>
                <span>{technician.status}</span>
              </div>
            </div>
          </div>
        ) : assignment.state === 'LOADING' ? (
          <div className="farm-technician__empty">Đang tải thông tin phân công…</div>
        ) : assignment.state === 'ERROR' ? (
          <div className="farm-technician__empty" style={{ color: '#b42318' }}>{assignment.error}</div>
        ) : assignment.technicians.length > 0 ? (
          assignment.technicians.map((t) => (
            <div className="farm-technician__profile" key={t.technician_id}>
              <div className="farm-technician__identity">
                <div className="farm-technician__avatar">{initials(t.full_name)}</div>
                <div>
                  <strong>{t.full_name || 'Kỹ thuật viên'}</strong>
                  <span>{t.is_primary ? 'Kỹ thuật viên chính' : 'Kỹ thuật viên hỗ trợ'} · {t.assignment_status === 'ACTIVE' ? 'Đang phụ trách' : t.assignment_status}</span>
                </div>
              </div>
              <div className="farm-technician__contact">
                <span>Số điện thoại</span>
                <strong>{t.phone || 'Chưa cập nhật'}</strong>
              </div>
              <div className="farm-technician__contact">
                <span>Email</span>
                <strong>{t.email || 'Chưa cập nhật'}</strong>
              </div>
            </div>
          ))
        ) : (
          <div className="farm-technician__empty">
            Chưa phân công. Nhà yến hiện chưa có kỹ thuật viên phụ trách — Admin sẽ phân công kỹ thuật viên.
            {approvalStatus === 'APPROVED' && ' Bạn vẫn có thể gửi "Yêu cầu kiểm tra"; yêu cầu sẽ chờ Admin phân công người xử lý.'}
          </div>
        )}
      </div>

      {!USE_MOCK && (
        <InspectionRequestPanel
          mode="owner"
          user={user}
          farm={farm}
          zones={farm.zones || []}
          devices={assignment.devices}
          title="Yêu cầu kiểm tra của nhà yến"
        />
      )}

      <div className="farm-detail__section-heading">
        <div>
          <h3>Khu vực giám sát</h3>
          <p>Tình trạng môi trường và thiết bị theo từng khu vực.</p>
        </div>

        <span>{farm.zones.length} khu vực</span>
      </div>

      <div className="farm-zone-list">
        {farm.zones.map((zone) => (
          <article
            className="farm-zone"
            key={zone.id}
          >
            <div className="farm-zone__identity">
              <span className="farm-zone__icon">Z</span>

              <div>
                <h4>{zone.name}</h4>
                <p>{zone.floor}</p>
              </div>
            </div>

            <div className="farm-zone__metric">
              <span>Nhiệt độ</span>
              <strong>{zone.temperature}°C</strong>
            </div>

            <div className="farm-zone__metric">
              <span>Độ ẩm</span>
              <strong>{zone.humidity}%</strong>
            </div>

            <div className="farm-zone__metric">
              <span>Thiết bị</span>
              <strong>{zone.devices}</strong>
            </div>

            <span
              className={`farm-zone__status ${
                zone.status === 'Ổn định'
                  ? 'farm-zone__status--good'
                  : 'farm-zone__status--warning'
              }`}
            >
              {zone.status}
            </span>
          </article>
        ))}
      </div>
    </section>
  )
}

export default FarmDetailPanel