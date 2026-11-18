import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import EnvironmentSummary from '../../../components/features/technician/environment/EnvironmentSummary'
import EnvironmentZoneTable from '../../../components/features/technician/environment/EnvironmentZoneTable'
import EnvironmentDetailPanel from '../../../components/features/technician/environment/EnvironmentDetailPanel'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'
import { environmentZones } from '../../../components/features/technician/environment/environmentMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'

import './EnvironmentPage.css'

function EnvironmentPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    devices,
    telemetry,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const [farmFilter, setFarmFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [selectedZone, setSelectedZone] = useState(null)

  const effectiveZones = useMemo(() => {
    if (zones.length > 0) {
      return zones.map((z) => {
        const temp = telemetry?.temperature != null ? Number(telemetry.temperature.toFixed(1)) : null
        const hum = telemetry?.humidity != null ? Math.round(telemetry.humidity) : null
        const co2 = telemetry?.co2 != null ? Math.round(telemetry.co2) : null
        const light = telemetry?.light != null ? Math.round(telemetry.light) : null
        const node = devices.find((d) => d.zoneId === z.id) || devices[0]

        return {
          id: z.id,
          name: z.name,
          farm: selectedFarm?.name || 'Nhà yến',
          status: 'NORMAL',
          updatedAt: telemetry ? 'Vừa xong' : 'Chưa có telemetry',
          controller: node?.name || 'ESP32 Controller',
          metrics: {
            temperature: { value: temp, unit: '°C', status: 'NORMAL' },
            humidity: { value: hum, unit: '%', status: 'NORMAL' },
            co2: { value: co2, unit: 'ppm', status: 'NORMAL' },
            light: { value: light, unit: 'lux', status: 'NORMAL' },
          },
          technicalNote: telemetry
            ? 'Telemetry trực tiếp từ IoT Service.'
            : 'Chưa có dữ liệu cảm biến được gửi lên từ thiết bị.',
        }
      })
    }
    return environmentZones
  }, [zones, telemetry, selectedFarm, devices])

  const summary = useMemo(
    () => ({
      totalZones: effectiveZones.length,
      normalZones: effectiveZones.filter((z) => z.status === 'NORMAL').length,
      warningZones: effectiveZones.filter((z) => z.status === 'WARNING').length,
      sensorIssues: effectiveZones.filter(
        (z) => z.status === 'WARNING' || z.metrics?.temperature?.value == null,
      ).length,
    }),
    [effectiveZones],
  )

  const farmOptions = useMemo(() => {
    return [
      { value: 'ALL', label: 'Tất cả nhà yến phụ trách' },
      ...farms.map((farm) => ({
        value: farm.name,
        label: farm.name,
      })),
    ]
  }, [farms])

  const filteredZones = useMemo(
    () =>
      effectiveZones.filter((zone) => {
        const matchesFarm =
          farmFilter === 'ALL' || zone.farm === farmFilter

        const matchesStatus =
          statusFilter === 'ALL' || zone.status === statusFilter

        return matchesFarm && matchesStatus
      }),
    [effectiveZones, farmFilter, statusFilter],
  )

  return (
    <AppLayout>
      <div className="technician-environment-page">
        <section className="tech-env-hero">
          <div>
            <span>TECHNICIAN WORKSPACE</span>
            <h1>Giám sát môi trường</h1>
            <p>
              Theo dõi telemetry môi trường tại các khu vực được phân công để hỗ
              trợ chẩn đoán Sensor, Node và Actuator.
            </p>
          </div>

          <div className="tech-env-live">
            <span
              className={`tech-env-dot ${telemetry ? 'normal' : 'warning'}`}
            />
            <div>
              <strong>
                {telemetry ? 'Telemetry đang hoạt động' : 'Chưa có telemetry'}
              </strong>
              <span>
                {telemetry
                  ? 'Dữ liệu kỹ thuật gần thời gian thực'
                  : 'Đang đợi bản tin từ Sensor'}
              </span>
            </div>
          </div>
        </section>

        {error && (
          <ErrorMessage
            title="Lỗi tải dữ liệu môi trường"
            message={error}
            onRetry={refetch}
          />
        )}

        {loading && effectiveZones.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải dữ liệu môi trường..." />
          </div>
        ) : (
          <>
            <EnvironmentSummary summary={summary} />

            <section className="tech-env-toolbar">
              <div className="tech-env-farm-filter">
                <EnvironmentSelect
                  label="Nhà yến"
                  value={farmFilter}
                  options={farmOptions}
                  onChange={setFarmFilter}
                />
              </div>

              <div className="tech-env-filter">
                {[
                  ['ALL', 'Tất cả'],
                  ['NORMAL', 'Ổn định'],
                  ['WARNING', 'Cần kiểm tra'],
                ].map(([value, label]) => (
                  <button
                    type="button"
                    key={value}
                    className={statusFilter === value ? 'active' : ''}
                    onClick={() => setStatusFilter(value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </section>

            <EnvironmentZoneTable
              zones={filteredZones}
              onSelect={setSelectedZone}
            />

            <EnvironmentDetailPanel
              zone={selectedZone}
              onClose={() => setSelectedZone(null)}
            />
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default EnvironmentPage
