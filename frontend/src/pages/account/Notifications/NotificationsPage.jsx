import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import AppLayout from '../../../components/layout/AppLayout'
import { useAuth } from '../../../context/AuthContext'
import apiClient from '../../../api/client.js'
import { useNotifications } from '../../../features/notifications/useNotifications.js'
import {
  SEVERITY_LABELS,
  filterNotifications,
  toPopoverItem,
} from '../../../features/notifications/notificationAdapter.js'
import './NotificationsPage.css'

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

function NotificationTypeIcon({ eventType = '', source = '', severity = 'INFO' }) {
  const t = String(eventType)
  let paths

  if (source === 'AI' || t.startsWith('ai.')) {
    // Camera / vision alert
    paths = (
      <>
        <rect x="3" y="6" width="18" height="13" rx="2" />
        <circle cx="12" cy="12.5" r="3" />
        <path d="M8 6l1.5-2h5L16 6" />
      </>
    )
  } else if (t === 'iot.device.offline') {
    paths = (
      <>
        <path d="M2 8.82a15 15 0 0 1 20 0" />
        <path d="M5 12.86a10 10 0 0 1 14 0" />
        <path d="M12 20h.01" />
        <path d="M3 3l18 18" />
      </>
    )
  } else if (source === 'IoT' || t.startsWith('iot.')) {
    paths = (
      <>
        <path d="M12 3 3.5 19h17L12 3Z" />
        <path d="M12 9v4" />
        <path d="M12 16h.01" />
      </>
    )
  } else if (t.startsWith('management.inspection_request.')) {
    paths = (
      <>
        <rect x="5" y="3" width="14" height="18" rx="2" />
        <path d="M9 8h6" />
        <path d="M9 12h6" />
        <path d="M9 16h4" />
      </>
    )
  } else if (t.startsWith('management.farm.')) {
    paths = (
      <>
        <path d="M3 20V9l5-4 5 4v11" />
        <path d="M13 12l4-3 4 3v8" />
        <path d="M2 20h20" />
      </>
    )
  } else if (t.startsWith('management.technician.') || t.startsWith('management.user.')) {
    paths = (
      <>
        <circle cx="12" cy="8" r="3.5" />
        <path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6" />
      </>
    )
  } else if (t.startsWith('management.device.')) {
    paths = (
      <>
        <rect x="5" y="6" width="14" height="12" rx="2" />
        <circle cx="12" cy="12" r="2.2" />
        <path d="M9 3h6v3" />
      </>
    )
  } else {
    paths = (
      <>
        <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
        <path d="M10 21h4" />
      </>
    )
  }

  return (
    <span className={`nc-item__icon nc-item__icon--${severity.toLowerCase()}`} aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        {paths}
      </svg>
    </span>
  )
}

/**
 * INT03-R2: Compact operational Notification Center for ADMIN / FARM_OWNER / TECHNICIAN.
 * Lists ONLY the caller's own persisted notifications (server-scoped); never merges distinct eventIds.
 */
function NotificationsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const paramId = searchParams.get('id')
  const live = useNotifications(user?.id || null, { limit: 100 })

  const [readFilter, setReadFilter] = useState('ALL')
  const [sourceFilter, setSourceFilter] = useState('ALL')
  const [query, setQuery] = useState('')
  const [manualSelection, setManualSelection] = useState({ paramId, id: paramId })
  const [farmNames, setFarmNames] = useState({})
  const [actionError, setActionError] = useState(null)
  const rowRefs = useRef({})

  const selectedId = manualSelection.paramId === paramId ? manualSelection.id : paramId
  const setSelectedId = (id) => setManualSelection({ paramId, id })

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

  useEffect(() => {
    if (!selectedId) return undefined
    const onKeyDown = (e) => {
      if (e.key === 'Escape') setManualSelection({ paramId, id: null })
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [selectedId, paramId])

  const items = useMemo(
    () => live.items.map((n) => toPopoverItem(n, { farmNames, role: user?.role })),
    [live.items, farmNames, user?.role],
  )
  const filtered = useMemo(
    () => filterNotifications(items, { readFilter, sourceFilter, query }),
    [items, readFilter, sourceFilter, query],
  )
  const selected = items.find((n) => n.id === selectedId) || null
  const unread = items.filter((n) => n.unread).length
  const hasActiveFilter = readFilter !== 'ALL' || sourceFilter !== 'ALL' || query.trim().length > 0

  async function select(n) {
    setSelectedId(n.id)
    if (n.unread) {
      const res = await live.markRead(n.id)
      setActionError(res.success ? null : res.message)
    }
  }

  function handleRowKeyDown(event, index) {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      const next = filtered[index + 1]
      if (next) rowRefs.current[next.id]?.focus()
    } else if (event.key === 'ArrowUp') {
      event.preventDefault()
      const prev = filtered[index - 1]
      if (prev) rowRefs.current[prev.id]?.focus()
    }
  }

  return (
    <AppLayout>
      <div className="nc-page">
        <header className="nc-header">
          <div>
            <span className="nc-eyebrow">Trung tâm thông báo</span>
            <div className="nc-title-row">
              <h1>Thông báo</h1>
              {unread > 0 && (
                <span className="nc-unread-pill" data-testid="notification-unread-pill">
                  {unread} chưa đọc
                </span>
              )}
            </div>
            <p className="nc-subtitle">
              Luồng thông báo nghiệp vụ (Quản lý) và cảnh báo vận hành (IoT/AI) gửi đến tài khoản của bạn.
            </p>
          </div>

          <div className="nc-header-actions">
            <button
              type="button"
              className="nc-btn"
              disabled={unread === 0}
              onClick={async () => {
                const res = await live.markAllRead()
                setActionError(res.success ? null : res.message)
              }}
            >
              Đánh dấu tất cả đã đọc
            </button>
            <button type="button" className="nc-btn" onClick={() => live.refresh()}>
              Làm mới
            </button>
          </div>
        </header>

        <div className="nc-toolbar" role="region" aria-label="Bộ lọc thông báo">
          <div className="nc-toolbar__filters">
            <div className="nc-segmented" role="group" aria-label="Lọc trạng thái đọc">
              {READ_FILTERS.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  className={`nc-segmented__btn ${readFilter === f.value ? 'nc-segmented__btn--active' : ''}`}
                  aria-pressed={readFilter === f.value}
                  onClick={() => setReadFilter(f.value)}
                >
                  {f.label}
                  {f.value === 'UNREAD' && unread > 0 ? ` (${unread})` : ''}
                </button>
              ))}
            </div>

            <select
              className="nc-select"
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              aria-label="Lọc nguồn"
            >
              {SOURCE_FILTERS.map((s) => (
                <option key={s} value={s}>
                  {s === 'ALL' ? 'Mọi nguồn' : s}
                </option>
              ))}
            </select>
          </div>

          <div className="nc-search">
            <svg className="nc-search__icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <circle cx="11" cy="11" r="6.5" />
              <path d="m16 16 4 4" />
            </svg>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm tiêu đề, nội dung, nhà yến, thiết bị…"
              aria-label="Tìm kiếm thông báo"
              data-testid="notification-search-input"
            />
            {query && (
              <button
                type="button"
                className="nc-search__clear"
                aria-label="Xóa từ khóa tìm kiếm"
                onClick={() => setQuery('')}
              >
                ×
              </button>
            )}
          </div>
        </div>

        {actionError && (
          <div className="nc-alert-banner" role="alert">
            <span>{actionError}</span>
            <button type="button" className="nc-btn" onClick={() => setActionError(null)}>
              Đóng
            </button>
          </div>
        )}

        <div className={`nc-layout ${selected ? 'nc-layout--split' : ''}`}>
          <section className="nc-feed-card" data-testid="notification-center-list" data-state={live.state}>
            {live.state === 'LOADING' && items.length === 0 ? (
              <div aria-busy="true" aria-label="Đang tải thông báo">
                {[0, 1, 2].map((idx) => (
                  <div key={idx} className="nc-skeleton-row">
                    <div className="nc-skel nc-skel--icon" />
                    <div>
                      <div className="nc-skel nc-skel--line nc-skel--short" />
                      <div className="nc-skel nc-skel--line nc-skel--long" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (live.state === 'UNAVAILABLE' || live.state === 'ERROR') && items.length === 0 ? (
              <div className="nc-state nc-state--error" role="alert">
                <p>
                  {live.state === 'UNAVAILABLE'
                    ? 'Notification Service hiện không khả dụng.'
                    : live.error || 'Không tải được danh sách thông báo.'}
                </p>
                <button type="button" className="nc-btn" onClick={() => live.refresh()}>
                  Thử lại
                </button>
              </div>
            ) : filtered.length === 0 ? (
              <div className="nc-state">
                <p>{hasActiveFilter ? 'Không có thông báo khớp bộ lọc hiện tại.' : 'Chưa có thông báo nào.'}</p>
                {hasActiveFilter && (
                  <button
                    type="button"
                    className="nc-btn"
                    onClick={() => {
                      setReadFilter('ALL')
                      setSourceFilter('ALL')
                      setQuery('')
                    }}
                  >
                    Xóa bộ lọc
                  </button>
                )}
              </div>
            ) : (
              <ul className="nc-feed" role="list">
                {filtered.map((n, index) => {
                  const sevClass = n.severity.toLowerCase()
                  const metaParts = [n.farmName, n.zoneLabel, n.device].filter(Boolean)
                  return (
                    <li key={n.id}>
                      <button
                        ref={(el) => {
                          if (el) rowRefs.current[n.id] = el
                          else delete rowRefs.current[n.id]
                        }}
                        type="button"
                        className={`nc-item nc-item--${sevClass} ${n.unread ? 'nc-item--unread' : ''} ${selectedId === n.id ? 'nc-item--selected' : ''}`}
                        aria-current={selectedId === n.id ? 'true' : undefined}
                        data-notification-id={n.id}
                        data-event-id={n.eventId || undefined}
                        data-unread={n.unread ? 'true' : 'false'}
                        onClick={() => select(n)}
                        onKeyDown={(e) => handleRowKeyDown(e, index)}
                      >
                        <NotificationTypeIcon eventType={n.eventType} source={n.source} severity={n.severity} />

                        <span className="nc-item__body">
                          <span className="nc-item__top">
                            <span className="nc-item__title-wrap">
                              {n.unread && <span className="nc-dot" aria-label="Chưa đọc" />}
                              <span className="nc-item__title">{n.title}</span>
                            </span>
                            <time
                              className="nc-item__time"
                              dateTime={n.createdAt || undefined}
                              title={formatAbsolute(n.createdAt)}
                            >
                              {n.time}
                            </time>
                          </span>

                          {n.message && <span className="nc-item__message">{n.message}</span>}

                          <span className="nc-item__meta">
                            <span className={`nc-badge nc-badge--${sevClass}`}>{SEVERITY_LABELS[n.severity]}</span>
                            <span className="nc-chip">{n.source}</span>
                            {metaParts.map((part, idx) => (
                              <span key={`${n.id}-m-${idx}`} className="nc-meta-text">
                                <span className="nc-meta-sep">· </span>
                                {part}
                              </span>
                            ))}
                          </span>
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>

          {selected && (
            <aside
              className="nc-detail"
              aria-label="Chi tiết thông báo"
              data-testid="notification-center-detail"
              data-notification-id={selected.id}
            >
              <header className="nc-detail__header">
                <div className="nc-detail__heading">
                  <NotificationTypeIcon
                    eventType={selected.eventType}
                    source={selected.source}
                    severity={selected.severity}
                  />
                  <div>
                    <span className="nc-detail__eyebrow">
                      {selected.source} · {selected.eventTypeLabel}
                    </span>
                    <h2>{selected.title}</h2>
                  </div>
                </div>
                <button
                  type="button"
                  className="nc-detail__close"
                  aria-label="Đóng chi tiết thông báo"
                  onClick={() => setSelectedId(null)}
                >
                  ×
                </button>
              </header>

              <p className="nc-detail__message">{selected.message || '--'}</p>

              <dl className="nc-detail__grid">
                <dt>Mức độ</dt>
                <dd>
                  <span className={`nc-badge nc-badge--${selected.severity.toLowerCase()}`}>
                    {SEVERITY_LABELS[selected.severity]}
                  </span>
                </dd>
                <dt>Nguồn</dt>
                <dd>{selected.source}</dd>
                <dt>Nhà yến</dt>
                <dd>{selected.farmName || '--'}</dd>
                <dt>Khu vực</dt>
                <dd>{selected.zoneLabel || '--'}</dd>
                <dt>Thiết bị</dt>
                <dd>{selected.device || '--'}</dd>
                <dt>Thời điểm</dt>
                <dd>{formatAbsolute(selected.createdAt)}</dd>
                <dt>Trạng thái</dt>
                <dd>
                  {selected.unread
                    ? 'Chưa đọc'
                    : `Đã đọc${selected.readAt ? ` lúc ${formatAbsolute(selected.readAt)}` : ''}`}
                </dd>
              </dl>

              <div className="nc-detail__actions">
                {selected.unread && (
                  <button
                    type="button"
                    className="nc-btn"
                    onClick={async () => {
                      const res = await live.markRead(selected.id)
                      setActionError(res.success ? null : res.message)
                    }}
                  >
                    Đánh dấu đã đọc
                  </button>
                )}
                {selected.link && (
                  <button
                    type="button"
                    className="nc-btn nc-btn--primary"
                    onClick={() => navigate(selected.link)}
                  >
                    Mở trang liên quan
                  </button>
                )}
              </div>
            </aside>
          )}
        </div>
      </div>
    </AppLayout>
  )
}

export default NotificationsPage
