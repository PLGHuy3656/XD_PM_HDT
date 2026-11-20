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
import { monitoringFarms as defaultMockFarms } from '../../../components/features/farm-owner/environment/environmentMockData'
import { formatRelativeTime, isSimulatedTelemetry, metricSource } from '../../../features/telemetry/provenance.js'

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
    telemetryStatus,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const [statusFilter, setStatusFilter] = useState('ALL')
  const [selectedZone, setSelectedZone] = useState(null)

  // INT01-R1: farm telemetry belongs to ONE reporting node; attribute it only to that node's zone,
  // evaluate against the shared recommended ranges, and never write "Vừa xong" or a blanket NORMAL.
  const effectiveZones = useMemo(() => {
    if (zones.length > 0) {
      const reportingNode = telemetry?.deviceId
        ? devices.find((d) => d.nodeId === telemetry.deviceId || d.id === telemetry.deviceId) || null
        : null
      const ranges = defaultMockFarms[0]?.zones[0]?.metrics || {}
      const evaluate = (key, value) => {
        if (value == null) return 'UNAVAILABLE'
        const r = ranges[key]
        if (!r || r.safeMin == null || r.safeMax == null) return 'NORMAL'
        return value >= r.safeMin && value <= r.safeMax ? 'NORMAL' : 'WARNING'
      }
      return zones.map((z) => {
        const owns = Boolean(reportingNode && reportingNode.zoneId === z.id)
        const t = owns ? telemetry : null
        const temp = t?.temperature != null ? Number(t.temperature.toFixed(1)) : null
        const hum = t?.humidity != null ? Math.round(t.humidity) : null
        const co2 = t?.co2 != null ? Math.round(t.co2) : null
        const light = t?.light != null ? Math.round(t.light) : null
        const metrics = {
          temperature: { value: temp, unit: '°C', status: evaluate('temperature', temp), source: metricSource(t, 'temperature') },
          humidity: { value: hum, unit: '%', status: evaluate('humidity', hum), source: metricSource(t, 'humidity') },
          co2: { value: co2, unit: 'ppm', status: evaluate('co2', co2), source: metricSource(t, 'co2') },
          light: { value: light, unit: 'lux', status: evaluate('light', light), source: metricSource(t, 'light') },
        }
        const statuses = Object.values(metrics).map((m) => m.status).filter((s) => s !== 'UNAVAILABLE')
        const status = statuses.length === 0 ? 'UNAVAILABLE' : statuses.includes('WARNING') ? 'WARNING' : 'NORMAL'
        const zoneNode = devices.find((d) => d.zoneId === z.id)
        const stale = owns && telemetryStatus === 'stale'

        return {
          id: z.id,
          name: z.name,
          farm: selectedFarm?.name || 'Nhà yến',
          status,
          updatedAt: t?.timestamp
            ? `${stale ? 'dữ liệu cũ · ' : ''}${formatRelativeTime(t.timestamp)}${isSimulatedTelemetry(t) ? ' · mô phỏng' : ''}`
            : telemetryError
              ? 'Chưa kết nối dịch vụ IoT'
              : 'Chưa có dữ liệu',
          controller: owns
            ? `${reportingNode.name} (${reportingNode.nodeId})`
            : zoneNode
              ? `${zoneNode.name} (${zoneNode.nodeId}) · chưa gửi telemetry`
              : 'Chưa gán thiết bị',
          metrics,
          technicalNote: owns
            ? `Telemetry trực tiếp từ ${reportingNode.nodeId}${isSimulatedTelemetry(t) ? ' (ESP32 Simulator — dữ liệu mô phỏng, không phải cảm biến thật)' : ''}.`
            : telemetryError
              ? 'Chưa kết nối dịch vụ IoT.'
              : 'Không có thiết bị nào trong khu vực này đang gửi telemetry.',
        }
      })
    }
    return USE_MOCK ? environmentZones : []
  }, [zones, telemetry, telemetryError, telemetryStatus, selectedFarm, devices])

  const unattributedNode =
    !USE_MOCK && telemetry?.deviceId && !devices.some((d) => (d.nodeId === telemetry.deviceId || d.id === telemetry.deviceId) && d.isZoneAssigned)
      ? telemetry.deviceId
      : null

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

        {unattributedNode && (
          <ErrorMessage
            variant="info"
            title="Telemetry chưa gắn với khu vực"
            message={`Node ${unattributedNode} đang gửi telemetry nhưng chưa được phân bổ vào khu vực nào, nên số liệu không được gán cho khu vực cụ thể.`}
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
