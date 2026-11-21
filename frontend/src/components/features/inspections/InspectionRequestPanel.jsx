import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import apiClient from '../../../api/client.js'
import { inspectionsApi } from '../../../api/modules/inspectionsApi.js'
import { useInspectionRequests } from '../../../features/inspections/useInspectionRequests.js'
import {
  INSPECTION_ACTION_LABELS,
  INSPECTION_PRIORITY_LABELS,
  INSPECTION_STATUS_LABELS,
  MAX_INSPECTION_RESULT_LENGTH,
  availableActions,
  errorMessage,
  formatDateTime,
  validateInspectionResult,
} from '../../../features/inspections/inspectionModel.js'
import './InspectionRequestPanel.css'

const STATUS_FILTERS = [
  { value: '', label: 'Tất cả' },
  { value: 'NEW', label: 'Mới' },
  { value: 'ACCEPTED', label: 'Đã tiếp nhận' },
  { value: 'IN_PROGRESS', label: 'Đang kiểm tra' },
  { value: 'COMPLETED', label: 'Hoàn thành' },
  { value: 'CANCELLED', label: 'Đã hủy' },
]

function StatusBadge({ status }) {
  return <span className={`ir-badge ir-badge--${String(status).toLowerCase()}`}>{INSPECTION_STATUS_LABELS[status] || status}</span>
}

function CreateForm({ farm, zones = [], devices = [], onCreated, onCancel }) {
  const [form, setForm] = useState({ title: '', description: '', priority: 'MEDIUM', zone_id: '', device_id: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const zoneDevices = form.zone_id ? devices.filter((d) => !d.zoneId || d.zoneId === form.zone_id) : devices

  async function submit(event) {
    event.preventDefault()
    if (form.title.trim().length < 3) {
      setError('Tiêu đề cần ít nhất 3 ký tự.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const created = await inspectionsApi.create({
        farm_id: farm.id,
        title: form.title.trim(),
        description: form.description.trim() || null,
        priority: form.priority,
        zone_id: form.zone_id || null,
        device_id: form.device_id || null,
      })
      onCreated(created)
    } catch (err) {
      setError(errorMessage(err, 'Không gửi được yêu cầu kiểm tra.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="ir-form" onSubmit={submit} data-testid="inspection-create-form">
      <h4>Yêu cầu kiểm tra — {farm.name}</h4>
      <label>
        <span>Tiêu đề / lý do *</span>
        <input value={form.title} maxLength={200} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Ví dụ: Độ ẩm khu vực B bất thường" />
      </label>
      <label>
        <span>Mô tả</span>
        <textarea rows={3} maxLength={2000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      </label>
      <div className="ir-form__row">
        <label>
          <span>Mức ưu tiên</span>
          <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
            {Object.entries(INSPECTION_PRIORITY_LABELS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </label>
        <label>
          <span>Khu vực (tùy chọn)</span>
          <select value={form.zone_id} onChange={(e) => setForm({ ...form, zone_id: e.target.value, device_id: '' })}>
            <option value="">— Không chọn —</option>
            {zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
          </select>
        </label>
        <label>
          <span>Thiết bị (tùy chọn)</span>
          <select value={form.device_id} onChange={(e) => setForm({ ...form, device_id: e.target.value })}>
            <option value="">— Không chọn —</option>
            {zoneDevices.map((d) => <option key={d.id} value={d.id}>{d.name || d.nodeId || d.id}</option>)}
          </select>
        </label>
      </div>
      {error && <p className="ir-error" role="alert">{error}</p>}
      <div className="ir-form__actions">
        <button type="button" className="ir-btn ir-btn--ghost" onClick={onCancel} disabled={busy}>Hủy</button>
        <button type="submit" className="ir-btn ir-btn--primary" disabled={busy}>{busy ? 'Đang gửi…' : 'Gửi yêu cầu'}</button>
      </div>
    </form>
  )
}

function Detail({ requestId, user, technicianOptions = [], onChanged, onClose }) {
  const [req, setReq] = useState(null)
  const [state, setState] = useState('LOADING')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [resultNote, setResultNote] = useState('')
  const [assignee, setAssignee] = useState('')
  const [farmTechs, setFarmTechs] = useState(null)

  useEffect(() => {
    const controller = new AbortController()
    inspectionsApi
      .get(requestId, { signal: controller.signal, retries: 0 })
      .then((data) => {
        setReq(data)
        setState('OK')
      })
      .catch((err) => {
        if (controller.signal.aborted) return
        setState('ERROR')
        setError(errorMessage(err, 'Không tải được chi tiết yêu cầu.'))
      })
    return () => controller.abort()
  }, [requestId])

  // Admin assignment: candidates = technicians ACTIVELY assigned to the request's farm (Management)
  const needsTechs = user?.role === 'ADMIN' && req?.status === 'NEW'
  useEffect(() => {
    if (!needsTechs || technicianOptions.length > 0 || !req?.farm_id) return undefined
    const controller = new AbortController()
    apiClient
      .get(`/api/farms/${encodeURIComponent(req.farm_id)}`, { signal: controller.signal, retries: 0 })
      .then((farm) => setFarmTechs(Array.isArray(farm?.technicians) ? farm.technicians : []))
      .catch(() => setFarmTechs([]))
    return () => controller.abort()
  }, [needsTechs, req?.farm_id, technicianOptions.length])
  const assignCandidates = technicianOptions.length > 0 ? technicianOptions : farmTechs || []

  const resultValidation = validateInspectionResult(resultNote)

  async function run(action) {
    if (action === 'complete' && !resultValidation.valid) {
      setError(resultValidation.message)
      return
    }
    setBusy(true)
    setError(null)
    try {
      let payload = {}
      if (action === 'complete') payload = { result_note: resultValidation.trimmed }
      if (action === 'assign') payload = { technician_id: assignee }
      const updated = await inspectionsApi.transition(req.id, action, payload)
      setReq(updated)
      setResultNote('')
      onChanged?.(updated)
    } catch (err) {
      setError(errorMessage(err, 'Thao tác thất bại.'))
    } finally {
      setBusy(false)
    }
  }

  if (state === 'LOADING') return <div className="ir-detail"><p className="ir-muted">Đang tải chi tiết…</p></div>
  if (state === 'ERROR') return <div className="ir-detail"><p className="ir-error">{error}</p><button type="button" className="ir-btn ir-btn--ghost" onClick={onClose}>Đóng</button></div>

  const actions = availableActions(req, user)
  return (
    <div className="ir-detail" data-testid="inspection-detail" data-request-id={req.id}>
      <header>
        <div>
          <span className="ir-muted">{req.request_code}</span>
          <h4>{req.title}</h4>
        </div>
        <button type="button" className="ir-close" onClick={onClose} aria-label="Đóng">×</button>
      </header>
      <dl className="ir-grid">
        <dt>Trạng thái</dt><dd><StatusBadge status={req.status} /></dd>
        <dt>Ưu tiên</dt><dd>{INSPECTION_PRIORITY_LABELS[req.priority] || req.priority}</dd>
        <dt>Nhà yến</dt><dd>{req.farm_name || req.farm_id}</dd>
        <dt>Khu vực</dt><dd>{req.zone_name || 'Không chỉ định'}</dd>
        <dt>Thiết bị</dt><dd>{req.device_name || 'Không chỉ định'}</dd>
        <dt>Người yêu cầu</dt><dd>{req.requested_by_name || req.requested_by}</dd>
        <dt>Kỹ thuật viên</dt><dd>{req.assigned_technician_name || <em>Chờ Admin phân công</em>}</dd>
        <dt>Tạo lúc</dt><dd>{formatDateTime(req.created_at)}</dd>
        {req.completed_at && (<><dt>Hoàn thành</dt><dd>{formatDateTime(req.completed_at)}</dd></>)}
      </dl>
      {req.description && <p className="ir-desc">{req.description}</p>}
      {req.result_note && (
        <div className="ir-result"><strong>Kết quả kiểm tra</strong><p>{req.result_note}</p></div>
      )}
      {actions.includes('complete') && (
        <label className="ir-form">
          <span>Kết quả kiểm tra *</span>
          <textarea
            rows={3}
            maxLength={MAX_INSPECTION_RESULT_LENGTH}
            value={resultNote}
            onChange={(e) => {
              setResultNote(e.target.value)
              if (error) setError(null)
            }}
            placeholder="Mô tả kết quả kiểm tra, xử lý đã thực hiện (ví dụ: ổn, đã vệ sinh cảm biến)"
          />
          <small className="ir-muted" data-testid="inspection-result-hint">
            {resultValidation.valid
              ? `Hợp lệ (${resultValidation.trimmed.length}/${MAX_INSPECTION_RESULT_LENGTH} ký tự).`
              : resultValidation.message}
          </small>
        </label>
      )}
      {actions.includes('assign') && (
        <label className="ir-form">
          <span>Phân công kỹ thuật viên (đang phụ trách nhà yến)</span>
          <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
            <option value="">— Chọn kỹ thuật viên —</option>
            {assignCandidates.map((t) => <option key={t.technician_id} value={t.technician_id}>{t.full_name}{t.is_primary ? ' (chính)' : ''}</option>)}
          </select>
          {farmTechs !== null && assignCandidates.length === 0 && <small className="ir-muted">Nhà yến chưa có kỹ thuật viên được phân công. Hãy phân công kỹ thuật viên cho nhà yến trước.</small>}
        </label>
      )}
      {error && <p className="ir-error" role="alert">{error}</p>}
      <div className="ir-actions">
        {actions.includes('accept') && <button type="button" className="ir-btn ir-btn--primary" disabled={busy} onClick={() => run('accept')}>Tiếp nhận</button>}
        {actions.includes('start') && <button type="button" className="ir-btn ir-btn--primary" disabled={busy} onClick={() => run('start')}>Bắt đầu kiểm tra</button>}
        {actions.includes('complete') && (
          <button
            type="button"
            className="ir-btn ir-btn--primary"
            disabled={busy || !resultValidation.valid}
            title={!resultValidation.valid ? resultValidation.message : ''}
            data-testid="inspection-complete-button"
            onClick={() => run('complete')}
          >
            {busy ? 'Đang xử lý…' : 'Hoàn thành'}
          </button>
        )}
        {actions.includes('assign') && <button type="button" className="ir-btn ir-btn--primary" disabled={busy || !assignee} onClick={() => run('assign')}>Phân công</button>}
        {actions.includes('cancel') && <button type="button" className="ir-btn ir-btn--danger" disabled={busy} onClick={() => run('cancel')}>Hủy yêu cầu</button>}
      </div>
      {Array.isArray(req.history) && req.history.length > 0 && (
        <ol className="ir-history">
          {req.history.map((h, i) => (
            <li key={`${h.created_at}-${i}`}>
              <strong>{INSPECTION_ACTION_LABELS[h.action] || h.action}</strong>
              <span> · {h.from_status ? `${INSPECTION_STATUS_LABELS[h.from_status] || h.from_status} → ` : ''}{INSPECTION_STATUS_LABELS[h.to_status] || h.to_status}</span>
              <span className="ir-muted"> · {h.actor_name || 'Hệ thống'} · {formatDateTime(h.created_at)}</span>
              {h.note && <div className="ir-muted">{h.note}</div>}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

/**
 * INT03-R1 Inspection Request panel.
 *  mode="owner": farm-scoped list + "Yêu cầu kiểm tra" button (farm must be APPROVED)
 *  mode="technician": requests of assigned farms (optionally filtered by farmId)
 *  mode="admin": all requests, default filter = unassigned queue
 */
function InspectionRequestPanel({ mode, user, farm = null, farmId = null, zones = [], devices = [], technicianOptions = [], technicianOptionsByFarm = null, title }) {
  const [searchParams] = useSearchParams()
  const [statusFilter, setStatusFilter] = useState('')
  const [onlyUnassigned, setOnlyUnassigned] = useState(mode === 'admin')
  const [creating, setCreating] = useState(false)
  const [selectedId, setSelectedId] = useState(() => searchParams.get('requestId'))
  const [flash, setFlash] = useState(null)

  const effectiveFarmId = farm?.id || farmId || null
  const list = useInspectionRequests({
    farmId: mode === 'admin' ? null : effectiveFarmId,
    status: statusFilter || null,
    unassigned: mode === 'admin' && onlyUnassigned,
    enabled: mode !== 'owner' || Boolean(effectiveFarmId),
  })

  const selected = useMemo(() => list.items.find((r) => r.id === selectedId) || null, [list.items, selectedId])
  const canCreate = mode === 'owner' && farm && (farm.approvalStatus || 'APPROVED') === 'APPROVED'
  const assignOptions = technicianOptionsByFarm && selected ? technicianOptionsByFarm(selected.farm_id) : technicianOptions

  return (
    <section className="ir-panel" data-testid={`inspection-panel-${mode}`}>
      <div className="ir-panel__heading">
        <div>
          <span className="ir-eyebrow">YÊU CẦU KIỂM TRA</span>
          <h3>{title || 'Yêu cầu kiểm tra'}</h3>
        </div>
        <div className="ir-panel__tools">
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Lọc trạng thái">
            {STATUS_FILTERS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
          {mode === 'admin' && (
            <label className="ir-check"><input type="checkbox" checked={onlyUnassigned} onChange={(e) => setOnlyUnassigned(e.target.checked)} /> Chỉ chờ phân công</label>
          )}
          {mode === 'owner' && (
            <button type="button" className="ir-btn ir-btn--primary" disabled={!canCreate} title={canCreate ? '' : 'Nhà yến cần được Admin phê duyệt trước'} onClick={() => setCreating(true)} data-testid="inspection-create-button">
              Yêu cầu kiểm tra
            </button>
          )}
        </div>
      </div>

      {flash && <p className="ir-flash" role="status">{flash}</p>}

      {creating && canCreate && (
        <CreateForm
          farm={farm}
          zones={zones}
          devices={devices}
          onCancel={() => setCreating(false)}
          onCreated={(created) => {
            setCreating(false)
            setFlash(
              created.assigned_technician_id
                ? `Đã gửi ${created.request_code}. Kỹ thuật viên phụ trách (${created.assigned_technician_name || 'đã liên kết'}) sẽ nhận được thông báo.`
                : `Đã gửi ${created.request_code}. Nhà yến chưa có kỹ thuật viên phụ trách — yêu cầu đang chờ Admin phân công.`,
            )
            setSelectedId(created.id)
            list.refresh()
          }}
        />
      )}

      {list.state === 'LOADING' && list.items.length === 0 ? (
        <p className="ir-muted">Đang tải yêu cầu kiểm tra…</p>
      ) : (list.state === 'UNAVAILABLE' || list.state === 'ERROR') && list.items.length === 0 ? (
        <p className="ir-error">{list.error}</p>
      ) : list.items.length === 0 ? (
        <p className="ir-muted">Chưa có yêu cầu kiểm tra nào{mode === 'admin' && onlyUnassigned ? ' đang chờ phân công' : ''}.</p>
      ) : (
        <ul className="ir-list">
          {list.items.map((r) => (
            <li key={r.id}>
              <button type="button" className={`ir-row ${selectedId === r.id ? 'ir-row--active' : ''}`} onClick={() => setSelectedId(r.id)} data-request-id={r.id}>
                <span className="ir-row__main">
                  <strong>{r.title}</strong>
                  <span className="ir-muted">{r.request_code} · {r.farm_name}{r.zone_name ? ` · ${r.zone_name}` : ''} · {formatDateTime(r.created_at)}</span>
                </span>
                <span className="ir-row__side">
                  <StatusBadge status={r.status} />
                  <span className="ir-muted">{r.assigned_technician_name || 'Chờ phân công'}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selectedId && (selected || list.state !== 'LOADING') && (
        <Detail
          key={selectedId}
          requestId={selectedId}
          user={user}
          technicianOptions={assignOptions || []}
          onClose={() => setSelectedId(null)}
          onChanged={() => list.refresh()}
        />
      )}
    </section>
  )
}

export default InspectionRequestPanel
