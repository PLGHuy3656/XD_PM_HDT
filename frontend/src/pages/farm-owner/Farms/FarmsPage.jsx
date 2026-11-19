import { useState } from 'react'
import AppLayout from '../../../components/layout/AppLayout'
import FarmCard from '../../../components/features/farm-owner/farms/FarmCard'
import FarmDetailPanel from '../../../components/features/farm-owner/farms/FarmDetailPanel'
import FarmRequestModal from '../../../components/features/farm-owner/farms/FarmRequestModal'
import { initialFarmRequests } from '../../../components/features/farm-owner/farms/farmsMockData'
import { useFarms } from '../../../features/farms/hooks/useFarms'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'
import './FarmsPage.css'

function FarmsPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    loading,
    error,
    refetch,
  } = useFarms()

  const [requests, setRequests] = useState(initialFarmRequests)
  const [requestModalOpen, setRequestModalOpen] = useState(false)

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

          <button
            type="button"
            className="farm-button farm-button--primary farms-page__request-button"
            onClick={() => setRequestModalOpen(true)}
          >
            <span>+</span>
            Yêu cầu thêm nhà yến
          </button>
        </header>

        {error && (
          <ErrorMessage
            title="Lỗi tải danh sách nhà yến"
            message={error}
            onRetry={refetch}
          />
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
