import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import BirdStatsCards from '../../../components/features/farm-owner/swiftlets/BirdStatsCards'
import BirdTrendChart from '../../../components/features/farm-owner/swiftlets/BirdTrendChart'
import LiveCameraCard from '../../../components/features/farm-owner/swiftlets/LiveCameraCard'
import AIEventsTable from '../../../components/features/farm-owner/swiftlets/AIEventsTable'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'

import {
  birdStats as defaultMockStats,
  trendData as defaultMockTrend,
} from '../../../components/features/farm-owner/swiftlets/swiftletsMockData'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { useCameras } from '../../../features/cameras/hooks/useCameras'
import { USE_MOCK } from '../../../api/config.js'

import './SwiftletsPage.css'

const FALLBACK_CAMERA = {
  id: 'CAM-NONE',
  name: 'Chưa có camera AI',
  node: 'Camera Node',
  status: 'OFFLINE',
  detections: [],
}

function SwiftletsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    error: farmsError,
  } = useFarms()

  const [zoneId, setZoneId] = useState('ALL')
  const [selectedCameraId, setSelectedCameraId] = useState(() => searchParams.get('camera') || null)

  const {
    cameras,
    birdStats,
    events,
    loading: camerasLoading,
    error: camerasError,
    refetch: refetchCameras,
  } = useCameras(selectedFarmId, selectedCameraId, { requireFarmId: true })

  const effectiveZones = zones.length > 0 ? zones : selectedFarm?.zones || []

  const availableCameras =
    zoneId && zoneId !== 'ALL'
      ? cameras.filter((camera) => camera.zoneId === zoneId)
      : cameras

  const selectedCamera =
    cameras.find((c) => c.id === selectedCameraId) ||
    availableCameras[0] ||
    cameras[0] ||
    FALLBACK_CAMERA

  const effectiveBirdStats =
    birdStats ||
    (USE_MOCK
      ? defaultMockStats
      : {
          totalCount: '—',
          entries: '—',
          exits: '—',
          returnRate: '—',
          activeNests: '—',
          unavailable: true,
          noCamera: cameras.length === 0,
        })

  function updateCamera(nextCameraId) {
    setSelectedCameraId(nextCameraId)
    setSearchParams({ camera: nextCameraId })
  }

  function handleFarmChange(nextFarmId) {
    setSelectedFarmId(nextFarmId)
    setZoneId('ALL')
    setSelectedCameraId(null)
  }

  function handleZoneChange(nextZoneId) {
    setZoneId(nextZoneId)
    const matchingCamera = cameras.find(
      (camera) => nextZoneId === 'ALL' || camera.zoneId === nextZoneId,
    )
    if (matchingCamera) {
      updateCamera(matchingCamera.id)
    }
  }

  return (
    <AppLayout>
      <div className="swiftlets-page">
        <header className="swiftlets-page-heading">
          <div>
            <span className="swiftlets-eyebrow">AI VISION & AUDIO</span>

            <h1>Giám sát chim yến</h1>

            <p>
              Theo dõi hoạt động ra vào, camera AI và các sự kiện bất thường được
              phát hiện tại nhà yến.
            </p>
          </div>

          <div className={`swiftlets-ai-status ${cameras.length === 0 || selectedCamera.status !== 'ONLINE' ? 'offline' : ''}`}>
            <span>
              <i />
              {cameras.length === 0
                ? 'Chưa có camera AI'
                : selectedCamera.status === 'ONLINE'
                  ? 'Edge AI đang hoạt động'
                  : 'Camera ngoại tuyến'}
            </span>
          </div>
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {camerasError && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ Camera AI"
            message={
              /upstream|503|unreachable|network/i.test(String(camerasError))
                ? 'Chưa kết nối dịch vụ AI Vision / Camera. Dữ liệu đếm chim sẽ hiển thị khi dịch vụ hoạt động trở lại.'
                : camerasError
            }
            onRetry={refetchCameras}
          />
        )}

        <div className="swiftlets-selectors">
          <label>
            <span>Nhà yến</span>
            <EnvironmentSelect
              value={selectedFarmId || ''}
              onChange={handleFarmChange}
              options={farms.map((farm) => ({
                value: farm.id,
                label: formatFarmOptionLabel(farm),
              }))}
            />
          </label>

          <label>
            <span>Khu vực</span>
            <EnvironmentSelect
              value={zoneId}
              onChange={handleZoneChange}
              options={[
                { value: 'ALL', label: 'Tất cả khu vực' },
                ...effectiveZones.map((zone) => ({
                  value: zone.id,
                  label: zone.name,
                })),
              ]}
            />
          </label>

          <label>
            <span>Camera</span>
            <EnvironmentSelect
              value={selectedCamera.id}
              onChange={updateCamera}
              options={
                cameras.length > 0
                  ? cameras.map((camera) => ({
                      value: camera.id,
                      label: `${camera.code || camera.id} · ${camera.name}`,
                    }))
                  : [{ value: 'CAM-NONE', label: 'Không có camera' }]
              }
            />
          </label>
        </div>

        {camerasLoading && cameras.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang kết nối camera AI..." />
          </div>
        ) : (
          <>
            <BirdStatsCards stats={effectiveBirdStats} />

            <div className="swiftlets-media-grid">
              <LiveCameraCard camera={selectedCamera} />
              <BirdTrendChart data={USE_MOCK ? defaultMockTrend : []} />
            </div>

            <AIEventsTable events={events} />
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default SwiftletsPage
