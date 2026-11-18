import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import ConnectionVerification from '../../../components/features/technician/installation/ConnectionVerification'
import DeviceConfiguration from '../../../components/features/technician/installation/DeviceConfiguration'
import DeviceStep from '../../../components/features/technician/installation/DeviceStep'
import InstallationProgress from '../../../components/features/technician/installation/InstallationProgress'
import InstallationSummary from '../../../components/features/technician/installation/InstallationSummary'
import LocationStep from '../../../components/features/technician/installation/LocationStep'
import {
  deviceTypes,
  initialInstallation,
  installationFarms as defaultInstallationFarms,
  verificationItems,
} from '../../../components/features/technician/installation/installationMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'

import './InstallationPage.css'

function InstallationPage() {
  const { farms, zones, selectedFarm } = useTechnicianData()

  const effectiveFarms = useMemo(() => {
    if (farms.length > 0) {
      return farms.map((f) => ({
        id: f.id,
        name: f.name,
        code: f.code,
        zones:
          zones.length > 0
            ? zones.map((z) => ({ id: z.id, name: z.name }))
            : [
                { id: 'Z01', name: 'Tầng 1' },
                { id: 'Z02', name: 'Tầng 2' },
              ],
      }))
    }
    return defaultInstallationFarms
  }, [farms, zones])

  const [currentStep, setCurrentStep] = useState(1)

  const [installation, setInstallation] = useState(() => ({
    ...initialInstallation,
    farmId: effectiveFarms[0]?.id || initialInstallation.farmId,
    zoneId: effectiveFarms[0]?.zones?.[0]?.id || initialInstallation.zoneId,
  }))

  const [verification, setVerification] = useState({})
  const [confirmed, setConfirmed] = useState(false)

  const activeSelectedFarm = useMemo(
    () =>
      effectiveFarms.find((farm) => farm.id === installation.farmId) ||
      effectiveFarms[0],
    [effectiveFarms, installation.farmId],
  )

  const activeSelectedZone = activeSelectedFarm?.zones?.find(
    (zone) => zone.id === installation.zoneId,
  ) || activeSelectedFarm?.zones?.[0]

  const selectedDeviceType = deviceTypes.find(
    (type) => type.id === installation.deviceType,
  )

  const verificationComplete = verificationItems.every(
    (item) => verification[item.id],
  )

  const handleChange = (field, value) => {
    if (field === 'farmId') {
      const nextFarm = effectiveFarms.find((farm) => farm.id === value)

      setInstallation((current) => ({
        ...current,
        farmId: value,
        zoneId: nextFarm?.zones?.[0]?.id ?? '',
      }))

      setVerification({})
      setConfirmed(false)
      return
    }

    setInstallation((current) => ({
      ...current,
      [field]: value,
    }))

    setConfirmed(false)
  }

  const handleToggleVerification = (id) => {
    setVerification((current) => ({
      ...current,
      [id]: !current[id],
    }))

    setConfirmed(false)
  }

  const canContinue = () => {
    if (currentStep === 1) {
      return Boolean(installation.farmId && installation.zoneId)
    }

    if (currentStep === 2) {
      return Boolean(
        installation.deviceId.trim() &&
          installation.deviceType &&
          installation.serialNumber.trim() &&
          installation.firmware.trim(),
      )
    }

    if (currentStep === 3) {
      return Boolean(
        installation.ipAddress.trim() &&
          installation.macAddress.trim() &&
          installation.wifiSsid.trim(),
      )
    }

    if (currentStep === 4) {
      return verificationComplete
    }

    return true
  }

  const handleNext = () => {
    if (!canContinue()) return
    setCurrentStep((current) => Math.min(5, current + 1))
  }

  const handleBack = () => {
    setCurrentStep((current) => Math.max(1, current - 1))
  }

  const handleConfirm = () => {
    setConfirmed(true)
  }

  const handleReset = () => {
    setInstallation({
      ...initialInstallation,
      farmId: effectiveFarms[0]?.id || initialInstallation.farmId,
      zoneId: effectiveFarms[0]?.zones?.[0]?.id || initialInstallation.zoneId,
    })
    setVerification({})
    setConfirmed(false)
    setCurrentStep(1)
  }

  return (
    <AppLayout>
      <div className="installation-page">
        <header className="installation-hero">
          <div>
            <span className="installation-eyebrow">TECHNICIAN WORKSPACE</span>
            <h1>Lắp đặt thiết bị</h1>
            <p>
              Quy trình chuẩn hóa từng bước để cài đặt, cấu hình và xác thực
              thiết bị IoT tại các nhà yến được phân công.
            </p>
          </div>
        </header>

        <InstallationProgress currentStep={currentStep} />

        <div className="installation-workspace">
          <section className="installation-main-panel">
            {currentStep === 1 && (
              <LocationStep
                farms={effectiveFarms}
                selectedFarmId={installation.farmId}
                selectedZoneId={installation.zoneId}
                onChange={handleChange}
              />
            )}

            {currentStep === 2 && (
              <DeviceStep
                deviceTypes={deviceTypes}
                formData={installation}
                onChange={handleChange}
              />
            )}

            {currentStep === 3 && (
              <DeviceConfiguration
                formData={installation}
                onChange={handleChange}
              />
            )}

            {currentStep === 4 && (
              <ConnectionVerification
                items={verificationItems}
                verification={verification}
                onToggle={handleToggleVerification}
              />
            )}

            {currentStep === 5 && (
              <InstallationSummary
                installation={installation}
                farm={activeSelectedFarm}
                zone={activeSelectedZone}
                deviceType={selectedDeviceType}
                confirmed={confirmed}
                onConfirm={handleConfirm}
                onReset={handleReset}
              />
            )}

            {currentStep < 5 && (
              <div className="installation-nav-buttons">
                {currentStep > 1 && (
                  <button
                    type="button"
                    className="install-button install-button--secondary"
                    onClick={handleBack}
                  >
                    Quay lại
                  </button>
                )}

                <button
                  type="button"
                  className="install-button install-button--primary"
                  disabled={!canContinue()}
                  onClick={handleNext}
                >
                  {currentStep === 4 ? 'Xem lại cấu hình' : 'Tiếp tục'}
                </button>
              </div>
            )}
          </section>

          <aside className="installation-side-panel">
            <div className="installation-context-card">
              <h3>Thông tin triển khai</h3>

              <div className="installation-context-row">
                <span>Nhà yến</span>
                <strong>{activeSelectedFarm?.name ?? 'Chưa chọn'}</strong>
              </div>

              <div className="installation-context-row">
                <span>Khu vực</span>
                <strong>{activeSelectedZone?.name ?? 'Chưa chọn'}</strong>
              </div>

              <div className="installation-context-row">
                <span>Loại thiết bị</span>
                <strong>{selectedDeviceType?.name ?? 'Chưa chọn'}</strong>
              </div>

              <div className="installation-context-row">
                <span>Mã thiết bị</span>
                <strong>{installation.deviceId || 'Chưa nhập'}</strong>
              </div>

              <div className="installation-context-row">
                <span>Bước hiện tại</span>
                <strong>Bước {currentStep} / 5</strong>
              </div>
            </div>
          </aside>
        </div>
      </div>
    </AppLayout>
  )
}

export default InstallationPage
