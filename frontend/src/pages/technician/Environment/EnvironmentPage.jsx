import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import EnvironmentSummary from '../../../components/features/technician/environment/EnvironmentSummary'
import EnvironmentZoneTable from '../../../components/features/technician/environment/EnvironmentZoneTable'
import EnvironmentDetailPanel from '../../../components/features/technician/environment/EnvironmentDetailPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'
import { environmentZones } from '../../../components/features/technician/environment/environmentMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { USE_MOCK } from '../../../api/config.js'

import '../TechnicianWorkspace.css'
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
    telemetryError,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const [statusFilter, setStatusFilter] = useState('ALL')
  const [selectedZone, setSelectedZone] = useState(null)

  const effectiveZones = useMemo(() => {
    if (zones.length > 0) {
      return zones.map((z) => {
        const temp = telemetry?.temperature != null ? Number(telemetry.temperature.toFixed(1)) : null
        const hum = telemetry?.humidity != null ? Math.round(telemetry.humidity) : null
        const co2 = telemetry?.co2 != null ? Math.round(telemetry.co2) : null
        const light = telemetry?.light != null ? Math.round(telemetry.light) : null
        const hasTelemetry = temp != null || hum != null || co2 != null || light != null
        const node = devices.find((d) => d.zoneId === z.id)

        return {
          id: z.id,
          name: z.name,
          farm: selectedFarm?.name || 'Nhà yến',
          status: hasTelemetry ? 'NORMAL' : 'UNAVAILABLE',
          updatedAt: hasTelemetry
            ? 'Vừa xong'
            : telemetryError
              ? 'Chưa kết nối dịch vụ IoT'
              : 'Chưa có dữ liệu',
          controller: node ? `${node.name} (${node.nodeId})` : 'Chưa gán thiết bị',
          metrics: {
            temperature: { value: temp, unit: '°C', status: temp != null ? 'NORMAL' : 'UNAVAILABLE' },
            humidity: { value: hum, unit: '%', status: hum != null ? 'NORMAL' : 'UNAVAILABLE' },
            co2: { value: co2, unit: 'ppm', status: co2 != null ? 'NORMAL' : 'UNAVAILABLE' },
            light: { value: light, unit: 'lux', status: light != null ? 'NORMAL' : 'UNAVAILABLE' },
          },
          technicalNote: hasTelemetry
            ? 'Telemetry trực tiếp từ IoT Service.'
            : telemetryError
              ? 'Chưa kết nối dịch vụ IoT.'
              : 'Chưa có dữ liệu cảm biến được gửi lên từ thiết bị.',
        }
      })
    }
    return USE_MOCK ? environmentZones : []
  }, [zones, telemetry, telemetryError, selectedFarm, devices])

  const summary = useMemo(
    () => ({
      totalZones: effectiveZones.length,
      normalZones: effectiveZones.filter((z) => z.status === 'NORMAL').length,
      warningZones: effectiveZones.filter((z) => z.status === 'WARNING').length,
      sensorIssues: effectiveZones.filter((z) => z.status === 'WARNING').length,
    }),
    [effectiveZones],
  )

  const filteredZones = useMemo(
    () =>
      effectiveZones.filter((zone) => {
        return statusFilter === 'ALL' || zone.status === statusFilter
      }),
    [effectiveZones, statusFilter],
  )

  return (
    <AppLayout>
      <div className="tech-ws technician-environment-page">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN ENVIRONMENT</span>
            <h1>Giám sát môi trường kỹ thuật</h1>
            <p>Theo dõi cảm biến nhiệt độ, độ ẩm, CO₂ và ánh sáng theo từng khu vực của nhà yến được phân công.</p>
          </div>

          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách</span>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  onChange={(nextId) => {
                    setSelectedFarmId(nextId)
                    setSelectedZone(null)
                  }}
                  options={farms.map((farm) => ({
                    value: farm.id,
                    label: formatFarmOptionLabel(farm),
                  }))}
                />
              </div>
            )}
          </div>
        </header>

        {error && (
          <ErrorMessage
            title="Lỗi tải dữ liệu môi trường"
            message={error}
            onRetry={refetch}
          />
        )}

        {!USE_MOCK && telemetryError && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ IoT"
            message="Chưa kết nối dịch vụ IoT. Dữ liệu cảm biến từng khu vực sẽ hiển thị khi IoT Service hoạt động."
            onRetry={refetch}
          />
        )}

        {loading && effectiveZones.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải dữ liệu khu vực..." />
          </div>
        ) : farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến được phân công"
            description="Admin cần phân công nhà yến để bạn theo dõi môi trường kỹ thuật."
          />
        ) : effectiveZones.length === 0 ? (
          <EmptyState
            title="Chưa có khu vực (Zone) nào"
            description="Nhà yến đang chọn chưa có khu vực được cấu hình."
          />
        ) : (
          <>
            <EnvironmentSummary summary={summary} />

            <section style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
              {[
                ['ALL', 'Tất cả'],
                ['NORMAL', 'Có dữ liệu'],
                ['UNAVAILABLE', 'Chưa có dữ liệu'],
                ['WARNING', 'Cảnh báo'],
              ].map(([val, lbl]) => (
                <button
                  key={val}
                  type="button"
                  className={statusFilter === val ? 'farm-button farm-button--primary' : 'farm-button farm-button--secondary'}
                  style={{ padding: '8px 14px', fontSize: '12px' }}
                  onClick={() => setStatusFilter(val)}
                >
                  {lbl}
                </button>
              ))}
            </section>

            <EnvironmentZoneTable
              zones={filteredZones}
              onSelectZone={setSelectedZone}
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
