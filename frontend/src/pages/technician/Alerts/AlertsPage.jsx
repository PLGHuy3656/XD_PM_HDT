import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import TechnicalAlertsTab from '../../../components/features/technician/alerts/TechnicalAlertsTab'
import WorkRequestsTab from '../../../components/features/technician/alerts/WorkRequestsTab'
import AlertDetailPanel from '../../../components/features/technician/alerts/AlertDetailPanel'
import WorkRequestDetailPanel from '../../../components/features/technician/alerts/WorkRequestDetailPanel'
import {
  technicalAlerts,
  workRequests as initialWorkRequests,
} from '../../../components/features/technician/alerts/alertsMockData'

import './AlertsPage.css'

const technicalStatusOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'OPEN', label: 'Chưa xử lý' },
  { value: 'INVESTIGATING', label: 'Đang kiểm tra' },
  { value: 'RESOLVED', label: 'Đã xử lý' },
]

const workStatusOptions = [
  { value: 'ALL', label: 'Tất cả trạng thái' },
  { value: 'NEW', label: 'Mới' },
  { value: 'IN_PROGRESS', label: 'Đang xử lý' },
  { value: 'DONE', label: 'Hoàn thành' },
]

function AlertsPage() {
  const [activeTab, setActiveTab] = useState('technical')
  const [farmFilter, setFarmFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [search, setSearch] = useState('')

  const [selectedAlert, setSelectedAlert] = useState(null)
  const [selectedRequest, setSelectedRequest] = useState(null)

  const [workRequests, setWorkRequests] =
    useState(initialWorkRequests)

  const farmOptions = useMemo(() => {
    const uniqueFarms = [
      ...new Set([
        ...technicalAlerts.map((item) => item.farm),
        ...workRequests.map((item) => item.farm),
      ]),
    ]

    return [
      { value: 'ALL', label: 'Tất cả nhà yến' },
      ...uniqueFarms.map((farm) => ({
        value: farm,
        label: farm,
      })),
    ]
  }, [workRequests])

  const filteredAlerts = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return technicalAlerts.filter((item) => {
      const matchesFarm =
        farmFilter === 'ALL' || item.farm === farmFilter

      const matchesStatus =
        statusFilter === 'ALL' ||
        item.status === statusFilter

      const matchesSearch =
        !keyword ||
        item.title.toLowerCase().includes(keyword) ||
        item.device.toLowerCase().includes(keyword) ||
        item.zone.toLowerCase().includes(keyword)

      return (
        matchesFarm &&
        matchesStatus &&
        matchesSearch
      )
    })
  }, [farmFilter, statusFilter, search])

  const filteredRequests = useMemo(() => {
    const keyword = search.trim().toLowerCase()

    return workRequests.filter((item) => {
      const matchesFarm =
        farmFilter === 'ALL' || item.farm === farmFilter

      const matchesStatus =
        statusFilter === 'ALL' ||
        item.status === statusFilter

      const matchesSearch =
        !keyword ||
        item.title.toLowerCase().includes(keyword) ||
        item.sender.toLowerCase().includes(keyword) ||
        item.zone.toLowerCase().includes(keyword)

      return (
        matchesFarm &&
        matchesStatus &&
        matchesSearch
      )
    })
  }, [
    workRequests,
    farmFilter,
    statusFilter,
    search,
  ])

  const openTechnical = technicalAlerts.filter(
    (item) => item.status !== 'RESOLVED',
  ).length

  const criticalTechnical = technicalAlerts.filter(
    (item) =>
      item.severity === 'CRITICAL' &&
      item.status !== 'RESOLVED',
  ).length

  const newRequests = workRequests.filter(
    (item) => item.status === 'NEW',
  ).length

  const inProgressRequests = workRequests.filter(
    (item) => item.status === 'IN_PROGRESS',
  ).length

  const currentStatusOptions =
    activeTab === 'technical'
      ? technicalStatusOptions
      : workStatusOptions

  const handleTabChange = (tab) => {
    setActiveTab(tab)
    setStatusFilter('ALL')

    setSelectedAlert(null)
    setSelectedRequest(null)
  }

  const handleRequestStatusChange = (id, status) => {
    setWorkRequests((current) =>
      current.map((request) =>
        request.id === id
          ? { ...request, status }
          : request,
      ),
    )

    setSelectedRequest((current) =>
      current?.id === id
        ? { ...current, status }
        : current,
    )
  }

  return (
    <AppLayout>
      <div className="technician-alerts-page">
        <section className="tech-alerts-hero">
          <div>
            <span className="tech-alerts-eyebrow">
              TECHNICAL OPERATIONS
            </span>

            <h1>Cảnh báo & Công việc</h1>

            <p>
              Theo dõi sự cố kỹ thuật và các yêu cầu hỗ
              trợ tại những nhà yến được phân công.
            </p>
          </div>

          <div className="tech-alerts-hero-status">
            <span />
            Theo dõi kỹ thuật
          </div>
        </section>

        <section className="tech-alert-summary">
          <article>
            <span>Cảnh báo đang mở</span>
            <strong>{openTechnical}</strong>
            <small>
              Cần theo dõi hoặc kiểm tra
            </small>
          </article>

          <article>
            <span>Sự cố nghiêm trọng</span>
            <strong>{criticalTechnical}</strong>
            <small>Ưu tiên xử lý</small>
          </article>

          <article>
            <span>Yêu cầu mới</span>
            <strong>{newRequests}</strong>
            <small>Từ Farm Owner / Admin</small>
          </article>

          <article>
            <span>Đang xử lý</span>
            <strong>{inProgressRequests}</strong>
            <small>Công việc hiện tại</small>
          </article>
        </section>

        <section className="tech-alert-tabs">
          <button
            type="button"
            className={
              activeTab === 'technical'
                ? 'active'
                : ''
            }
            onClick={() =>
              handleTabChange('technical')
            }
          >
            Cảnh báo kỹ thuật
            <span>{openTechnical}</span>
          </button>

          <button
            type="button"
            className={
              activeTab === 'work'
                ? 'active'
                : ''
            }
            onClick={() =>
              handleTabChange('work')
            }
          >
            Công việc / Yêu cầu
            <span>{newRequests}</span>
          </button>
        </section>

        <section className="tech-alert-toolbar">
          <div className="tech-alert-search">
            <span>⌕</span>

            <input
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
              placeholder={
                activeTab === 'technical'
                  ? 'Tìm cảnh báo, thiết bị, khu vực...'
                  : 'Tìm công việc, người gửi, khu vực...'
              }
            />
          </div>

          <div className="tech-alert-filter-group">
            <EnvironmentSelect
              value={farmFilter}
              options={farmOptions}
              onChange={setFarmFilter}
            />

            <EnvironmentSelect
              value={statusFilter}
              options={currentStatusOptions}
              onChange={setStatusFilter}
            />
          </div>
        </section>

        <section className="tech-alert-content">
          <div className="tech-alert-list-card">
            <div className="tech-alert-list-title">
              <div>
                <span>
                  {activeTab === 'technical'
                    ? 'TECHNICAL ALERTS'
                    : 'WORK REQUESTS'}
                </span>

                <h2>
                  {activeTab === 'technical'
                    ? 'Sự cố cần theo dõi'
                    : 'Công việc được gửi đến'}
                </h2>
              </div>

              <strong>
                {activeTab === 'technical'
                  ? filteredAlerts.length
                  : filteredRequests.length}
              </strong>
            </div>

            {activeTab === 'technical' ? (
              <TechnicalAlertsTab
                alerts={filteredAlerts}
                selectedId={selectedAlert?.id}
                onSelect={(alert) => {
                  setSelectedAlert(alert)
                  setSelectedRequest(null)
                }}
              />
            ) : (
              <WorkRequestsTab
                requests={filteredRequests}
                selectedId={selectedRequest?.id}
                onSelect={(request) => {
                  setSelectedRequest(request)
                  setSelectedAlert(null)
                }}
              />
            )}
          </div>

          {activeTab === 'technical' &&
            selectedAlert && (
              <AlertDetailPanel
                alert={selectedAlert}
                onClose={() =>
                  setSelectedAlert(null)
                }
              />
            )}

          {activeTab === 'work' &&
            selectedRequest && (
              <WorkRequestDetailPanel
                request={selectedRequest}
                onClose={() =>
                  setSelectedRequest(null)
                }
                onStatusChange={
                  handleRequestStatusChange
                }
              />
            )}
        </section>
      </div>
    </AppLayout>
  )
}

export default AlertsPage