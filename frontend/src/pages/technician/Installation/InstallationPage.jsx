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
  installationFarms,
  verificationItems,
} from '../../../components/features/technician/installation/installationMockData'

import './InstallationPage.css'

function InstallationPage() {
  const [currentStep, setCurrentStep] = useState(1)

  const [installation, setInstallation] = useState(
    initialInstallation,
  )

  const [verification, setVerification] = useState({})

  const [confirmed, setConfirmed] = useState(false)

  const selectedFarm = useMemo(
    () =>
      installationFarms.find(
        (farm) => farm.id === installation.farmId,
      ),
    [installation.farmId],
  )

  const selectedZone = selectedFarm?.zones.find(
    (zone) => zone.id === installation.zoneId,
  )

  const selectedDeviceType = deviceTypes.find(
    (type) => type.id === installation.deviceType,
  )

  const verificationComplete = verificationItems.every(
    (item) => verification[item.id],
  )

  const handleChange = (field, value) => {
    if (field === 'farmId') {
      const nextFarm = installationFarms.find(
        (farm) => farm.id === value,
      )

      setInstallation((current) => ({
        ...current,
        farmId: value,
        zoneId: nextFarm?.zones[0]?.id ?? '',
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
      return Boolean(
        installation.farmId &&
          installation.zoneId,
      )
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
        installation.mqttTopic.trim() &&
          installation.samplingInterval,
      )
    }

    if (currentStep === 4) {
      return verificationComplete
    }

    return false
  }

  const handleNext = () => {
    if (!canContinue()) {
      return
    }

    setCurrentStep((current) =>
      Math.min(current + 1, 5),
    )
  }

  const handleBack = () => {
    setCurrentStep((current) =>
      Math.max(current - 1, 1),
    )
  }

  const handleStepChange = (step) => {
    if (step <= currentStep) {
      setCurrentStep(step)
    }
  }

  const handleConfirm = () => {
    setConfirmed(true)
  }

  const renderStep = () => {
    if (currentStep === 1) {
      return (
        <LocationStep
          installation={installation}
          farms={installationFarms}
          onChange={handleChange}
        />
      )
    }

    if (currentStep === 2) {
      return (
        <DeviceStep
          installation={installation}
          deviceTypes={deviceTypes}
          onChange={handleChange}
        />
      )
    }

    if (currentStep === 3) {
      return (
        <DeviceConfiguration
          installation={installation}
          onChange={handleChange}
        />
      )
    }

    if (currentStep === 4) {
      return (
        <ConnectionVerification
          items={verificationItems}
          verification={verification}
          onToggle={handleToggleVerification}
        />
      )
    }

    return (
      <InstallationSummary
        installation={installation}
        farm={selectedFarm}
        zone={selectedZone}
        deviceType={selectedDeviceType}
        confirmed={confirmed}
        onConfirm={handleConfirm}
      />
    )
  }

  return (
    <AppLayout>
      <div className="technician-installation-page">
        <section className="installation-hero">
          <div>
            <span className="installation-eyebrow">
              Technician Workspace
            </span>

            <h1>Lắp đặt & kích hoạt thiết bị</h1>

            <p>
              Đăng ký, cấu hình và xác minh thiết bị trước
              khi bàn giao cho hệ thống NestMate.
            </p>
          </div>

          <div className="installation-hero__meta">
            <span>Quy trình kỹ thuật</span>

            <strong>
              Bước {currentStep} / 5
            </strong>
          </div>
        </section>

        <InstallationProgress
          currentStep={currentStep}
          onStepChange={handleStepChange}
        />

        <section className="installation-wizard">
          {renderStep()}

          <div className="installation-wizard__actions">
            <button
              type="button"
              className="installation-button installation-button--secondary"
              onClick={handleBack}
              disabled={currentStep === 1}
            >
              ← Quay lại
            </button>

            <div className="installation-wizard__position">
              Bước {currentStep} trên 5
            </div>

            {currentStep < 5 ? (
              <button
                type="button"
                className="installation-button installation-button--primary"
                onClick={handleNext}
                disabled={!canContinue()}
              >
                Tiếp tục →
              </button>
            ) : (
              <button
                type="button"
                className="installation-button installation-button--secondary"
                onClick={() => setCurrentStep(1)}
              >
                Xem lại từ đầu
              </button>
            )}
          </div>
        </section>
      </div>
    </AppLayout>
  )
}

export default InstallationPage