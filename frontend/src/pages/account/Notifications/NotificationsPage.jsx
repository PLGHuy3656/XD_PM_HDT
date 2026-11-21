import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import AppLayout from '../../../components/layout/AppLayout'
import { useAuth } from '../../../context/AuthContext'
import apiClient from '../../../api/client.js'
import { useNotifications } from '../../../features/notifications/useNotifications.js'
import { SEVERITY_LABELS, toPopoverItem } from '../../../features/notifications/notificationAdapter.js'
import '../../../components/features/inspections/InspectionRequestPanel.css'

const READ_FILTERS = [
  { value: 'ALL', label: 'Tất cả' },
  { value: 'UNREAD', label: 'Chưa đọc' },
  { value: 'READ', label: 'Đã đọc' },
]
const SOURCE_FILTERS = ['ALL', 'Quản lý', 'IoT', 'AI', 'Hệ thống']

function formatAbsolute(iso) {
  if (!iso) return '--'
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '--' : d.toLocaleString('vi-VN', { hour12: false })
}

/**
 * INT03-R1: notification center for ADMIN / FARM_OWNER / TECHNICIAN.
 * Lists ONLY the caller's own notifications (the Notification Service derives the user from the
 * bearer token; the Gateway rejects foreign userId queries). Read state is persisted server-side.
 */
function NotificationsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const live = useNotifications(user?.id || null, { limit: 100 })
  const [readFilter, setReadFilter] = useState('ALL')
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [selectedId, setSelectedId] = useState(searchParams.get('id'))
  const [farmNames, setFarmNames] = useState({})
  const [actionError, setActionError] = useState(null)

  useEffect(() => {
    if (!user?.id) return undefined
    const controller = new AbortController()
    apiClient
      .get('/api/farms', { signal: controller.signal, retries: 0 })
      .then((list) => {
        const arr = Array.isArray(list) ? list : list?.items || []
        setFarmNames(Object.fromEntries(arr.map((f) => [f.farm_id || f.id, f.farm_name || f.name])))
      })
      .catch(() => {})
    return () => controller.abort()
  }, [user?.id])

  const items = useMemo(() => live.items.map((n) => toPopoverItem(n, { farmNames, role: user?.role })), [live.items, farmNames, user?.role])
  const filtered = items.filter(
    (n) => (readFilter === 'ALL' || (readFilter === 'UNREAD' ? n.unread : !n.unread)) && (sourceFilter === 'ALL' || n.source === sourceFilter),
  )
  const selected = items.find((n) => n.id === selectedId) || null
  const unread = items.filter((n) => n.unread).length

  async function select(n) {
    setSelectedId(n.id)
    if (n.unread) {
      const res = await live.markRead(n.id)
      setActionError(res.success ? null : res.message)
    }
  }

  return (
    <AppLayout>
      <div style={{ padding: '24px', maxWidth: 1100 }}>
        <span className="ir-eyebrow">TRUNG TÂM THÔNG BÁO</span>
        <h1 style={{ margin: '4px 0 4px' }}>Thông báo</h1>
        <p className="ir-muted">Thông báo nghiệp vụ (Quản lý) và cảnh báo vận hành (IoT/AI) gửi đến tài khoản của bạn. {unread > 0 ? `${unread} chưa đọc.` : ''}</p>

        <div className="ir-panel__tools" style={{ margin: '12px 0' }}>
          <select value={readFilter} onChange={(e) => setReadFilter(e.target.value)} aria-label="Lọc đã đọc">
            {READ_FILTERS.map((f) => <option key={f.value} value={f.value}>{f.label}</option>)}
          </select>
          <select value={sourceFilter} onChange={(e) => setSourceFilter(e.target.value)} aria-label="Lọc nguồn">
            {SOURCE_FILTERS.map((s) => <option key={s} value={s}>{s === 'ALL' ? 'Mọi nguồn' : s}</option>)}
          </select>
          <button type="button" className="ir-btn ir-btn--ghost" disabled={unread === 0} onClick={async () => {
            const res = await live.markAllRead()
            setActionError(res.success ? null : res.message)
          }}>Đánh dấu tất cả đã đọc</button>
          <button type="button" className="ir-btn ir-btn--ghost" onClick={() => live.refresh()}>Làm mới</button>
        </div>
        {actionError && <p className="ir-error">{actionError}</p>}

        <div style={{ display: 'grid', gridTemplateColumns: selected ? 'minmax(0,1fr) minmax(0,1fr)' : '1fr', gap: '16px' }}>
          <div data-testid="notification-center-list" data-state={live.state}>
            {live.state === 'LOADING' && items.length === 0 ? (
              <p className="ir-muted">Đang tải thông báo…</p>
            ) : (live.state === 'UNAVAILABLE' || live.state === 'ERROR') && items.length === 0 ? (
              <p className="ir-error">{live.state === 'UNAVAILABLE' ? 'Notification Service hiện không khả dụng.' : live.error}</p>
            ) : filtered.length === 0 ? (
              <p className="ir-muted">Không có thông báo phù hợp.</p>
            ) : (
              <ul className="ir-list">
                {filtered.map((n) => (
                  <li key={n.id}>
                    <button type="button" className={`ir-row ${selectedId === n.id ? 'ir-row--active' : ''}`} onClick={() => select(n)} data-notification-id={n.id} style={n.unread ? { borderLeft: '4px solid #0f766e' } : undefined}>
                      <span className="ir-row__main">
                        <strong>{n.title}</strong>
                        <span className="ir-muted">{n.message}</span>
                        <span className="ir-muted">{n.source} · {n.eventTypeLabel}{n.farmName ? ` · ${n.farmName}` : ''}{n.zoneLabel ? ` · ${n.zoneLabel}` : ''}</span>
                      </span>
                      <span className="ir-row__side">
                        <span className={`ir-badge ${n.severity === 'CRITICAL' ? 'ir-badge--in_progress' : n.severity === 'WARNING' ? 'ir-badge--accepted' : 'ir-badge--new'}`}>{SEVERITY_LABELS[n.severity]}</span>
                        <span className="ir-muted">{n.unread ? 'Chưa đọc' : 'Đã đọc'}</span>
                        <span className="ir-muted">{n.time}</span>
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {selected && (
            <div className="ir-detail" style={{ marginTop: 0 }} data-testid="notification-center-detail" data-notification-id={selected.id}>
              <header>
                <div>
                  <span className="ir-muted">{selected.source} · {selected.eventTypeLabel}</span>
                  <h4>{selected.title}</h4>
                </div>
                <button type="button" className="ir-close" aria-label="Đóng" onClick={() => setSelectedId(null)}>×</button>
              </header>
              <p className="ir-desc">{selected.message}</p>
              <dl className="ir-grid">
                <dt>Mức độ</dt><dd>{SEVERITY_LABELS[selected.severity]}</dd>
                <dt>Nhà yến</dt><dd>{selected.farmName || '--'}</dd>
                <dt>Khu vực</dt><dd>{selected.zoneLabel || '--'}</dd>
                <dt>Thiết bị</dt><dd>{selected.device || '--'}</dd>
                <dt>Thời điểm</dt><dd>{formatAbsolute(selected.createdAt)}</dd>
                <dt>Trạng thái</dt><dd>{selected.unread ? 'Chưa đọc' : `Đã đọc${selected.readAt ? ` lúc ${formatAbsolute(selected.readAt)}` : ''}`}</dd>
              </dl>
              {selected.link && (
                <div className="ir-actions">
                  <button type="button" className="ir-btn ir-btn--primary" onClick={() => navigate(selected.link)}>Mở trang liên quan</button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  )
}

export default NotificationsPage
