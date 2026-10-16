import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'

import BirdStatsCards from '../../../components/features/farm-owner/swiftlets/BirdStatsCards'
import BirdTrendChart from '../../../components/features/farm-owner/swiftlets/BirdTrendChart'
import LiveCameraCard from '../../../components/features/farm-owner/swiftlets/LiveCameraCard'
import AIEventsTable from '../../../components/features/farm-owner/swiftlets/AIEventsTable'

import {
  farms,
  cameras,
  birdStats,
  trendData,
  aiEvents,
} from '../../../components/features/farm-owner/swiftlets/swiftletsMockData'

import './SwiftletsPage.css'

function SwiftletsPage() {
  const [searchParams, setSearchParams] = useSearchParams()

  const cameraFromUrl = searchParams.get('camera')

  const initialCameraId = cameras.some(
    (camera) => camera.id === cameraFromUrl,
  )
    ? cameraFromUrl
    : cameras[0].id

  const initialCamera =
    cameras.find((camera) => camera.id === initialCameraId) ??
    cameras[0]

  const [farmId, setFarmId] = useState(farms[0].id)
  const [zoneId, setZoneId] = useState(initialCamera.zoneId)
  const [selectedCameraId, setSelectedCameraId] =
    useState(initialCameraId)

  const selectedFarm =
    farms.find((farm) => farm.id === farmId) ?? farms[0]

  const selectedZone =
    selectedFarm.zones.find((zone) => zone.id === zoneId) ??
    selectedFarm.zones[0]

  const availableCameras = cameras.filter(
    (camera) => camera.zoneId === selectedZone.id,
  )

  const cameraOptions =
    availableCameras.length > 0 ? availableCameras : cameras

  const selectedCamera =
    cameras.find(
      (camera) => camera.id === selectedCameraId,
    ) ?? cameras[0]

  function updateCamera(nextCameraId) {
    const nextCamera = cameras.find(
      (camera) => camera.id === nextCameraId,
    )

    if (!nextCamera) {
      return
    }

    setSelectedCameraId(nextCamera.id)
    setZoneId(nextCamera.zoneId)

    setSearchParams({
      camera: nextCamera.id,
    })
  }

  function handleFarmChange(nextFarmId) {
    const nextFarm =
      farms.find((farm) => farm.id === nextFarmId) ?? farms[0]

    const nextZone = nextFarm.zones[0]

    setFarmId(nextFarm.id)
    setZoneId(nextZone.id)

    const nextCamera = cameras.find(
      (camera) => camera.zoneId === nextZone.id,
    )

    if (nextCamera) {
      updateCamera(nextCamera.id)
    }
  }

  function handleZoneChange(nextZoneId) {
    setZoneId(nextZoneId)

    const nextCamera = cameras.find(
      (camera) => camera.zoneId === nextZoneId,
    )

    if (nextCamera) {
      updateCamera(nextCamera.id)
    }
  }

  return (
    <AppLayout>
      <main className="swiftlets-page">
        <header className="swiftlets-page-heading">
          <div>
            <span className="swiftlets-eyebrow">
              AI VISION & AUDIO
            </span>

            <h1>Giám sát chim yến</h1>

            <p>
              Theo dõi hoạt động ra vào, camera AI và các sự kiện
              bất thường được phát hiện tại nhà yến.
            </p>
          </div>

          <div className="swiftlets-ai-status">
            <span>
              <i />
              {selectedCamera.status === 'ONLINE'
                ? 'Edge AI đang hoạt động'
                : 'Camera mất kết nối'}
            </span>

            <small>
              {selectedCamera.id} ·{' '}
              {selectedCamera.status === 'ONLINE'
                ? 'cập nhật theo thời gian thực'
                : 'không có dữ liệu trực tiếp'}
            </small>
          </div>
        </header>

        <section className="swiftlets-context">
          <div>
            <label>
              <span>Nhà yến</span>

              <EnvironmentSelect
                value={farmId}
                onChange={handleFarmChange}
                options={farms.map((farm) => ({
                  value: farm.id,
                  label: farm.name,
                }))}
              />
            </label>

            <label>
              <span>Khu vực / Camera</span>

              <EnvironmentSelect
                value={zoneId}
                onChange={handleZoneChange}
                options={selectedFarm.zones.map((zone) => ({
                  value: zone.id,
                  label: zone.name,
                }))}
              />
            </label>
          </div>

          <div className="swiftlets-node">
            <span>Nguồn AI</span>

            <strong>
              <i />
              {selectedCamera.node} / Camera Node
            </strong>
          </div>
        </section>

        <BirdStatsCards stats={birdStats} />

        <section className="swiftlets-main-grid">
          <LiveCameraCard
            cameras={cameraOptions}
            selectedCameraId={selectedCameraId}
            onCameraChange={updateCamera}
          />

          <BirdTrendChart data={trendData} />
        </section>

        <AIEventsTable events={aiEvents} />
      </main>
    </AppLayout>
  )
}

export default SwiftletsPage