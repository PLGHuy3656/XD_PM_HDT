import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import FarmCard from '../../../components/features/farm-owner/farms/FarmCard'
import FarmDetailPanel from '../../../components/features/farm-owner/farms/FarmDetailPanel'
import FarmRequestModal from '../../../components/features/farm-owner/farms/FarmRequestModal'
import { initialFarmRequests } from '../../../components/features/farm-owner/farms/farmsMockData'
import { useFarms } from '../../../features/farms/hooks/useFarms'
import { USE_MOCK } from '../../../api/config.js'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'
import './FarmsPage.css'

function FarmsPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    loading,
    error,
    createFarm,
    updateFarm,
    createZone,
    updateZone,
    deleteZone,
    refetch,
  } = useFarms()

  const [requests, setRequests] = useState(() => (USE_MOCK ? initialFarmRequests : []))
  const [requestModalOpen, setRequestModalOpen] = useState(false)
  const [farmModalMode, setFarmModalMode] = useState(null) // 'create' | 'edit' | null
  const [farmForm, setFarmForm] = useState({ farm_code: '', farm_name: '', address: '' })
  const [zoneForm, setZoneForm] = useState({ zone_code: '', name: '' })
  const [editingZoneId, setEditingZoneId] = useState(null)
  const [actionError, setActionError] = useState('')
  const [actionNotice, setActionNotice] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmitRequest = (form) => {
    const nextNumber = String(requests.length + 15).padStart(3, '0')
    const newRequest = {
      id: `REQ-2026-${nextNumber}`,
      farmName: form.farmName.trim(),
      address: form.address.trim(),
      note: form.note.trim(),
      submittedAt: new Intl.DateTimeFormat('vi-VN').format(new Date()),
      status: 'PENDING',
    }
    setRequests((current) => [newRequest, ...current])
    setRequestModalOpen(false)
  }

  const handleSaveFarm = async (event) => {
    event.preventDefault()
    setActionError('')
    setActionNotice('')
    if (!farmForm.farm_name.trim()) {
      setActionError('Vui lòng nhập tên nhà yến.')
      return
    }
    setSubmitting(true)
    const res =
      farmModalMode === 'create'
        ? await createFarm({
            farm_name: farmForm.farm_name.trim(),
            address: farmForm.address.trim() || null,
          })
        : await updateFarm(selectedFarm.id, {
            farm_name: farmForm.farm_name.trim(),
            address: farmForm.address.trim() || null,
          })
    setSubmitting(false)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể lưu nhà yến.')
      return
    }
    if (farmModalMode === 'create' && res?.data?.farm_code) {
      const approvalMsg =
        res?.data?.approval_status === 'PENDING'
          ? ' — Trạng thái: Chờ Admin phê duyệt'
          : ''
      setActionNotice(
        `Đã đăng ký nhà yến "${res.data.farm_name}" — Mã nhà yến: ${res.data.farm_code}${approvalMsg}`,
      )
    }
    setFarmModalMode(null)
  }

  const handleSaveZone = async (event) => {
    event.preventDefault()
    if (!selectedFarm) return
    setActionError('')
    setActionNotice('')
    if (!zoneForm.name.trim()) {
      setActionError('Vui lòng nhập tên khu vực.')
      return
    }
    setSubmitting(true)
    const res = editingZoneId
      ? await updateZone(editingZoneId, { name: zoneForm.name.trim() })
      : await createZone(selectedFarm.id, { name: zoneForm.name.trim() })
    setSubmitting(false)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể lưu khu vực.')
      return
    }
    if (!editingZoneId && res?.data?.zone_code) {
      setActionNotice(`Đã tạo khu vực "${res.data.name}" — Mã khu vực: ${res.data.zone_code}`)
    }
    setZoneForm({ zone_code: '', name: '' })
    setEditingZoneId(null)
  }

  const handleDeleteZone = async (zone) => {
    if (!window.confirm(`Xác nhận xóa khu vực "${zone.name}"?`)) return
    setActionError('')
    const res = await deleteZone(zone.id)
    if (!res?.success) {
      setActionError(res?.error || 'Không thể xóa khu vực.')
    }
  }

  const totalZones = farms.reduce(
    (total, farm) => total + (farm.zoneCount || farm.zones?.length || 0),
    0,
  )

  const totalDevices = farms.reduce(
    (total, farm) => total + (farm.totalDevices || 0),
    0,
  )

  const onlineDevices = farms.reduce(
    (total, farm) => total + (farm.onlineDevices || 0),
    0,
  )

  return (
    <AppLayout>
      <div className="farms-page">
        <header className="farms-page__header">
          <div>
            <span className="farms-page__eyebrow">
              FARM MANAGEMENT
            </span>

            <h1>Quản lý nhà yến</h1>

            <p>
              Theo dõi nhà yến, khu vực vận hành và trạng thái thiết bị
              trong cùng một không gian quản lý.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {USE_MOCK ? (
              <button
                type="button"
                className="farm-button farm-button--primary farms-page__request-button"
                onClick={() => setRequestModalOpen(true)}
              >
                <span>+</span>
                Yêu cầu thêm nhà yến
              </button>
            ) : (
              <>
                <button
                  type="button"
                  className="farm-button farm-button--primary farms-page__request-button"
                  onClick={() => {
                    setActionError('')
                    setFarmForm({ farm_code: '', farm_name: '', address: '' })
                    setFarmModalMode('create')
                  }}
                >
                  <span>+</span>
                  Thêm nhà yến
                </button>
                {selectedFarm && (
                  <button
                    type="button"
                    className="farm-button"
                    onClick={() => {
                      setActionError('')
                      setFarmForm({
                        farm_code: selectedFarm.code || '',
                        farm_name: selectedFarm.name || '',
                        address: selectedFarm.address || '',
                      })
                      setFarmModalMode('edit')
                    }}
                  >
                    Chỉnh sửa nhà yến
                  </button>
                )}
              </>
            )}
          </div>
        </header>

        {(error || actionError) && (
          <ErrorMessage
            title="Lỗi thao tác nhà yến"
            message={actionError || error}
            onRetry={refetch}
          />
        )}
        {actionNotice && (
          <div style={{ marginBottom: '1rem', padding: '0.75rem 1rem', borderRadius: '10px', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}>
            {actionNotice}
          </div>
        )}

        {loading && farms.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải dữ liệu nhà yến..." />
          </div>
        ) : (
          <>
            <section className="farms-overview">
              <article>
                <span>Nhà yến đang quản lý</span>
                <strong>{farms.length}</strong>
                <small>Đang hoạt động</small>
              </article>

              <article>
                <span>Tổng khu vực</span>
                <strong>{totalZones}</strong>
                <small>Được giám sát</small>
              </article>

              <article>
                <span>Thiết bị trực tuyến</span>
                <strong>{onlineDevices}</strong>
                <small>/ {totalDevices} thiết bị</small>
              </article>

              <article>
                <span>Yêu cầu chờ duyệt</span>
                <strong>
                  {
                    requests.filter(
                      (request) => request.status === 'PENDING',
                    ).length
                  }
                </strong>
                <small>Chờ Administrator xử lý</small>
              </article>
            </section>

            <div className="farms-workspace">
              <section className="farms-list-panel">
                <div className="farms-section-title">
                  <div>
                    <h2>Nhà yến của tôi</h2>
                    <p>{farms.length} nhà yến đang hoạt động</p>
                  </div>
                </div>

                <div className="farms-list">
                  {farms.map((farm) => (
                    <FarmCard
                      key={farm.id}
                      farm={farm}
                      selected={farm.id === selectedFarmId}
                      onSelect={(nextFarm) =>
                        setSelectedFarmId(nextFarm.id)
                      }
                    />
                  ))}
                </div>
              </section>

              <FarmDetailPanel farm={selectedFarm} />
            </div>
          </>
        )}

        {!USE_MOCK && selectedFarm && (
          <section className="farm-requests">
            <div className="farms-section-title">
              <div>
                <span className="farms-page__eyebrow">ZONE MANAGEMENT</span>
                <h2>Quản lý khu vực — {selectedFarm.name}</h2>
              </div>
            </div>
            {(selectedFarm.approvalStatus || 'APPROVED') !== 'APPROVED' ? (
              <div className="zone-approval-notice">
                {selectedFarm.approvalStatus === 'REJECTED'
                  ? `Nhà yến đã bị từ chối${selectedFarm.rejectionReason ? `: ${selectedFarm.rejectionReason}` : ''}. Không thể thêm khu vực mới.`
                  : 'Nhà yến đang chờ Admin phê duyệt. Chức năng tạo khu vực sẽ mở khóa sau khi được duyệt.'}
              </div>
            ) : (
              <form className="zone-form-card" onSubmit={handleSaveZone}>
                <div className="zone-form-field">
                  <label htmlFor="owner-zone-name">Tên khu vực *</label>
                  <input
                    id="owner-zone-name"
                    className="zone-form-input"
                    value={zoneForm.name}
                    onChange={(e) => setZoneForm((z) => ({ ...z, name: e.target.value }))}
                    placeholder="Ví dụ: Tầng 1 - Khu làm tổ"
                  />
                  <small className="zone-form-hint">
                    Mã khu vực (Z-XXXXXX) sẽ được hệ thống tự động cấp duy nhất.
                  </small>
                </div>
                <div className="zone-form-actions">
                  <button type="submit" className="farm-button farm-button--primary" disabled={submitting}>
                    {submitting ? 'Đang lưu...' : editingZoneId ? 'Cập nhật khu vực' : '+ Thêm khu vực'}
                  </button>
                  {editingZoneId && (
                    <button
                      type="button"
                      className="farm-button farm-button--secondary"
                      onClick={() => {
                        setEditingZoneId(null)
                        setZoneForm({ zone_code: '', name: '' })
                      }}
                    >
                      Hủy
                    </button>
                  )}
                </div>
              </form>
            )}
            {(selectedFarm.zones || []).length === 0 ? (
              <EmptyState
                title="Chưa có khu vực nào"
                description="Thêm khu vực đầu tiên để phân vùng cảm biến và thiết bị trong nhà yến."
              />
            ) : (
              <div className="farm-request-table-wrap">
                <table className="farm-request-table">
                  <thead>
                    <tr>
                      <th>Mã khu vực</th>
                      <th>Tên khu vực</th>
                      <th>Thao tác</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(selectedFarm.zones || []).map((z) => (
                      <tr key={z.id}>
                        <td><strong>{z.code || z.zone_code || z.id}</strong></td>
                        <td>{z.name}</td>
                        <td>
                          <div className="farm-table-actions">
                            <button
                              type="button"
                              className="farm-table-action"
                              onClick={() => {
                                setEditingZoneId(z.id)
                                setZoneForm({ zone_code: z.code || '', name: z.name || '' })
                              }}
                            >
                              Sửa
                            </button>
                            <button
                              type="button"
                              className="farm-table-action farm-table-action--danger"
                              onClick={() => handleDeleteZone(z)}
                            >
                              Xóa
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {USE_MOCK && (
          <section className="farm-requests">
            <div className="farms-section-title">
              <div>
                <span className="farms-page__eyebrow">
                  APPROVAL WORKFLOW
                </span>
                <h2>Yêu cầu thêm nhà yến</h2>
                <p>
                  Theo dõi các yêu cầu đang chờ Administrator phê duyệt.
                </p>
              </div>
            </div>

            {requests.length === 0 ? (
              <div className="farm-requests__empty">
                Chưa có yêu cầu nào.
              </div>
            ) : (
              <div className="farm-request-table-wrap">
                <table className="farm-request-table">
                  <thead>
                    <tr>
                      <th>Mã yêu cầu</th>
                      <th>Nhà yến</th>
                      <th>Địa chỉ</th>
                      <th>Ngày gửi</th>
                      <th>Trạng thái</th>
                    </tr>
                  </thead>

                  <tbody>
                    {requests.map((request) => (
                      <tr key={request.id}>
                        <td>
                          <strong>{request.id}</strong>
                        </td>

                        <td>{request.farmName}</td>
                        <td>{request.address}</td>
                        <td>{request.submittedAt}</td>

                        <td>
                          <span className="farm-request-status">
                            Chờ duyệt
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        )}

        {farmModalMode && (
          <div className="admin-farm-modal-backdrop" onMouseDown={() => setFarmModalMode(null)}>
            <form
              className="admin-farm-modal admin-farm-form"
              onSubmit={handleSaveFarm}
              onMouseDown={(e) => e.stopPropagation()}
            >
              <h3>{farmModalMode === 'create' ? 'Thêm nhà yến mới' : 'Chỉnh sửa nhà yến'}</h3>
              {farmModalMode === 'create' && (
                <p style={{ margin: 0, fontSize: '12px', color: '#64748b' }}>
                  Mã nhà yến (Farm Code) sẽ được hệ thống tự động cấp duy nhất sau khi tạo.
                </p>
              )}
              <label>
                Tên nhà yến *
                <input
                  value={farmForm.farm_name}
                  onChange={(e) => setFarmForm((f) => ({ ...f, farm_name: e.target.value }))}
                  placeholder="Tên nhà yến"
                />
              </label>
              <label>
                Địa chỉ
                <input
                  value={farmForm.address}
                  onChange={(e) => setFarmForm((f) => ({ ...f, address: e.target.value }))}
                  placeholder="Địa chỉ"
                />
              </label>
              <div className="admin-farm-modal__actions">
                <button type="button" className="admin-farm-modal__cancel" onClick={() => setFarmModalMode(null)}>Hủy</button>
                <button type="submit" className="admin-farm-modal__save" disabled={submitting}>{submitting ? 'Đang lưu...' : 'Lưu'}</button>
              </div>
            </form>
          </div>
        )}

        <FarmRequestModal
          open={requestModalOpen}
          onClose={() => setRequestModalOpen(false)}
          onSubmit={handleSubmitRequest}
        />
      </div>
    </AppLayout>
  )
}

export default FarmsPage
