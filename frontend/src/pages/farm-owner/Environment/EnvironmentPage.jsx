import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import './EnvironmentPage.css'

import EnvironmentTabs from '../../../components/features/farm-owner/environment/EnvironmentTabs'

import MetricCard, {
  MetricIcon,
} from '../../../components/features/farm-owner/environment/MetricCard'
import { getMetricState } from '../../../components/features/farm-owner/environment/metricState'

import EnvironmentChart from '../../../components/features/farm-owner/environment/EnvironmentChart'
import ZoneComparisonChart from '../../../components/features/farm-owner/environment/ZoneComparisonChart'
import EnvironmentSelect from '../../../components/ui/Select'
import { ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'

import {
  MAX_COMPARE_ZONES,
  monitoringFarms as defaultMockFarms,
  comparisonColors,
} from '../../../components/features/farm-owner/environment/environmentMockData'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { useTelemetry } from '../../../features/telemetry/hooks/useTelemetry'
import { SERVICE_STATE } from '../../../api/serviceStatus.js'
import { USE_MOCK } from '../../../api/config.js'

function PlusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 5v14M5 12h14" />
    </svg>
  )
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7 7 10 10M17 7 7 17" />
    </svg>
  )
}

function EnvironmentPage() {
  const {
    farms,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    error: farmsError,
  } = useFarms()

  const {
    telemetry,
    hasData,
    error: telemetryError,
    serviceState: iotState,
    refetch: refetchTelemetry,
  } = useTelemetry(selectedFarmId)

  const iotUnavailable = !USE_MOCK && iotState === SERVICE_STATE.UNAVAILABLE
  const iotConnected = USE_MOCK || iotState === SERVICE_STATE.AVAILABLE

  const effectiveZones = useMemo(() => {
    if (zones.length > 0) {
      const baseMetrics = defaultMockFarms[0]?.zones[0]?.metrics || {}
      return zones.map((z, idx) => {
        const zMetrics = JSON.parse(JSON.stringify(baseMetrics))
        if (!USE_MOCK && !hasData) {
          Object.keys(zMetrics).forEach((k) => {
            zMetrics[k].values = []
            zMetrics[k].value = null
            zMetrics[k].hasData = false
          })
        }
        if (telemetry && telemetry.temperature != null) {
          zMetrics.temperature.value = telemetry.temperature
          zMetrics.temperature.displayValue = `${telemetry.temperature.toFixed(1)}°C`
          zMetrics.temperature.hasData = true
        } else if (!hasData) {
          zMetrics.temperature.displayValue = '--°C'
        }
        if (telemetry && telemetry.humidity != null) {
          zMetrics.humidity.value = telemetry.humidity
          zMetrics.humidity.displayValue = `${Math.round(telemetry.humidity)}%`
          zMetrics.humidity.hasData = true
        } else if (!hasData) {
          zMetrics.humidity.displayValue = '--%'
        }
        if (telemetry && telemetry.co2 != null) {
          zMetrics.co2.value = telemetry.co2
          zMetrics.co2.displayValue = `${Math.round(telemetry.co2)} ppm`
          zMetrics.co2.hasData = true
        } else if (!hasData) {
          zMetrics.co2.displayValue = '-- ppm'
        }
        if (telemetry && telemetry.light != null) {
          zMetrics.light.value = telemetry.light
          zMetrics.light.displayValue = `${Math.round(telemetry.light)} lux`
          zMetrics.light.hasData = true
        } else if (!hasData) {
          zMetrics.light.displayValue = '-- lux'
        }
        return {
          id: z.id,
          name: z.name,
          node: iotConnected ? `ENV-${String(idx + 1).padStart(2, '0')}` : 'Chưa kết nối',
          lastSeen: hasData
            ? telemetry?.timestamp
              ? 'Dữ liệu trực tiếp'
              : 'Đã đồng bộ'
            : iotUnavailable
              ? 'Chưa kết nối dịch vụ IoT'
              : 'Chưa có dữ liệu cảm biến',
          status: hasData ? 'live' : 'offline',
          metrics: zMetrics,
        }
      })
    }
    return USE_MOCK ? defaultMockFarms[0]?.zones || [] : []
  }, [zones, telemetry, hasData, iotConnected, iotUnavailable])

  const [zoneId, setZoneId] = useState('')
  const [selectedMetric, setSelectedMetric] = useState('temperature')
  const [analysisView, setAnalysisView] = useState('trend')
  const [period, setPeriod] = useState('24h')
  const [comparisonMetric, setComparisonMetric] = useState('temperature')
  const [comparisonPeriod, setComparisonPeriod] = useState('24h')
  const [comparisonZoneIds, setComparisonZoneIds] = useState([])
  const [showZonePicker, setShowZonePicker] = useState(false)

  const emptyMetrics = {
    temperature: {
      label: 'Nhiệt độ',
      displayValue: '--°C',
      value: null,
      hasData: false,
      safeMin: 27,
      safeMax: 31,
      unit: '°C',
      values: [],
    },
    humidity: {
      label: 'Độ ẩm',
      displayValue: '--%',
      value: null,
      hasData: false,
      safeMin: 75,
      safeMax: 90,
      unit: '%',
      values: [],
    },
    co2: {
      label: 'CO₂',
      displayValue: '-- ppm',
      value: null,
      hasData: false,
      safeMin: 400,
      safeMax: 1000,
      unit: 'ppm',
      values: [],
    },
    light: {
      label: 'Ánh sáng',
      displayValue: '-- lux',
      value: null,
      hasData: false,
      safeMin: 50,
      safeMax: 180,
      unit: 'lux',
      values: [],
    },
  }

  const activeZoneId = effectiveZones.some((z) => z.id === zoneId)
    ? zoneId
    : effectiveZones[0]?.id || ''

  const selectedZone =
    effectiveZones.find((zone) => zone.id === activeZoneId) ?? {
      id: 'default',
      name: effectiveZones.length === 0 ? 'Chưa có khu vực' : 'Khu vực 1',
      node: iotConnected ? 'ENV-01' : 'Chưa kết nối',
      lastSeen: iotUnavailable
        ? 'Chưa kết nối dịch vụ IoT'
        : 'Chưa có dữ liệu cảm biến',
      metrics: USE_MOCK ? defaultMockFarms[0]?.zones[0]?.metrics : emptyMetrics,
    }

  const selectedMetricData =
    selectedZone.metrics?.[selectedMetric] ||
    (USE_MOCK
      ? defaultMockFarms[0]?.zones[0]?.metrics?.[selectedMetric]
      : emptyMetrics[selectedMetric])

  const selectedMetricState = getMetricState(selectedMetricData)

  const activeComparisonIds = useMemo(() => {
    const valid = comparisonZoneIds.filter((id) =>
      effectiveZones.some((z) => z.id === id),
    )
    return valid.length > 0
      ? valid
      : effectiveZones.slice(0, MAX_COMPARE_ZONES).map((z) => z.id)
  }, [comparisonZoneIds, effectiveZones])

  const comparisonZones = effectiveZones.filter((zone) =>
    activeComparisonIds.includes(zone.id),
  )

  const availableComparisonZones = effectiveZones.filter(
    (zone) => !activeComparisonIds.includes(zone.id),
  )

  const addComparisonZone = (zoneIdToAdd) => {
    if (activeComparisonIds.length >= MAX_COMPARE_ZONES) return
    setComparisonZoneIds([...activeComparisonIds, zoneIdToAdd])
    setShowZonePicker(false)
  }

  const removeComparisonZone = (zoneIdToRemove) => {
    setComparisonZoneIds(
      activeComparisonIds.filter((id) => id !== zoneIdToRemove),
    )
  }

  return (
    <AppLayout>
      <div className="environment-page">
        <header className="env-header-row">
          <div className="env-header-copy">
            <span className="environment-eyebrow">ENVIRONMENT MONITORING</span>
            <h1>Môi trường nhà yến</h1>
            <p>Theo dõi vi khí hậu, ngưỡng an toàn và xu hướng theo từng khu vực.</p>
          </div>

          <EnvironmentTabs />
        </header>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}

        {iotUnavailable && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ IoT"
            message={
              telemetryError && !/upstream|503|unreachable|network/i.test(String(telemetryError))
                ? telemetryError
                : 'Dịch vụ IoT hiện chưa khả dụng. Dữ liệu cảm biến và biểu đồ xu hướng sẽ tự cập nhật khi dịch vụ hoạt động trở lại.'
            }
            onRetry={refetchTelemetry}
          />
        )}

        {farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến nào"
            description="Hãy đăng ký nhà yến và chờ Admin phê duyệt để theo dõi dữ liệu môi trường."
          />
        ) : (
          <>
            <section className="env-context-bar">
              <div className="env-context-fields">
                <EnvironmentSelect
                  label="Nhà yến"
                  value={selectedFarmId || ''}
                  options={farms.map((farm) => ({
                    value: farm.id,
                    label: farm.name,
                  }))}
                  onChange={(nextFarmId) => {
                    setSelectedFarmId(nextFarmId)
                    setZoneId('')
                    setComparisonZoneIds([])
                    setShowZonePicker(false)
                  }}
                />

                <EnvironmentSelect
                  label="Khu vực"
                  value={activeZoneId}
                  options={
                    effectiveZones.length > 0
                      ? effectiveZones.map((zone) => ({
                          value: zone.id,
                          label: zone.name,
                        }))
                      : [{ value: '', label: 'Chưa có khu vực' }]
                  }
                  onChange={(nextZoneId) => {
                    setZoneId(nextZoneId)
                  }}
                />

                <div className="env-node-field">
                  <span>Sensor Node</span>
                  <strong>{selectedZone.node}</strong>
                  <small>
                    <i className={hasData ? 'env-dot-online' : 'env-dot-offline'} />
                    {selectedZone.lastSeen}
                  </small>
                </div>
              </div>
            </section>

            <section className="env-metrics-wrap" aria-label="Chỉ số môi trường hiện tại">
              <div className="environment-metric-grid">
                {Object.entries(selectedZone.metrics || {}).map(([key, metric]) => (
                  <MetricCard
                    key={key}
                    metricKey={key}
                    metric={metric}
                    active={selectedMetric === key}
                    onClick={() => setSelectedMetric(key)}
                  />
                ))}
              </div>
            </section>

            <section className="env-analysis-bar" aria-label="Chế độ xem biểu đồ">
              <div className="env-analysis-tabs" role="tablist" aria-label="Phân tích môi trường">
                <button
                  type="button"
                  role="tab"
                  aria-selected={analysisView === 'trend'}
                  className={`env-analysis-tab ${analysisView === 'trend' ? 'is-active' : ''}`}
                  onClick={() => setAnalysisView('trend')}
                >
                  <strong>Xu hướng theo thời gian</strong>
                  <small>Chi tiết chỉ số đang chọn</small>
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={analysisView === 'compare'}
                  className={`env-analysis-tab ${analysisView === 'compare' ? 'is-active' : ''}`}
                  onClick={() => setAnalysisView('compare')}
                >
                  <strong>So sánh khu vực</strong>
                  <small>Đối chiếu giữa các tầng/phòng</small>
                </button>
              </div>

              {analysisView === 'trend' ? (
                <div className="period-switcher">
                  {['6h', '24h', '7d'].map((p) => (
                    <button
                      key={p}
                      type="button"
                      className={period === p ? 'active' : ''}
                      onClick={() => setPeriod(p)}
                    >
                      {p}
                    </button>
                  ))}
                </div>
              ) : (
                <div className="comparison-controls">
                  <div className="comparison-metric-toggle">
                    {['temperature', 'humidity', 'co2', 'light'].map((key) => (
                      <button
                        key={key}
                        type="button"
                        className={`comp-metric-btn ${
                          comparisonMetric === key ? 'active' : ''
                        }`}
                        onClick={() => setComparisonMetric(key)}
                      >
                        <MetricIcon type={key} />
                        <span>
                          {key === 'temperature'
                            ? 'Nhiệt độ'
                            : key === 'humidity'
                              ? 'Độ ẩm'
                              : key === 'co2'
                                ? 'CO₂'
                                : 'Ánh sáng'}
                        </span>
                      </button>
                    ))}
                  </div>

                  <div className="comparison-period">
                    {['6h', '24h', '7d'].map((p) => (
                      <button
                        key={p}
                        type="button"
                        className={comparisonPeriod === p ? 'active' : ''}
                        onClick={() => setComparisonPeriod(p)}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <div className="env-analysis-stage" role="tabpanel">
              {analysisView === 'trend' ? (
                <EnvironmentChart
                  metric={selectedMetricData}
                  period={period}
                  state={selectedMetricState}
                />
              ) : (
                <>
                  <div className="comparison-chip-bar">
                    <span className="comparison-chip-label">
                      Khu vực đang so sánh ({comparisonZones.length}/{MAX_COMPARE_ZONES}):
                    </span>

                    <div className="comparison-chips">
                      {comparisonZones.map((zone, idx) => (
                        <span
                          key={zone.id}
                          className="zone-chip"
                          style={{
                            borderColor: comparisonColors[idx % comparisonColors.length],
                          }}
                        >
                          <span
                            className="zone-chip-dot"
                            style={{
                              background: comparisonColors[idx % comparisonColors.length],
                            }}
                          />
                          {zone.name}
                          {comparisonZones.length > 1 && (
                            <button
                              type="button"
                              className="zone-chip-remove"
                              onClick={() => removeComparisonZone(zone.id)}
                              aria-label={`Xoá ${zone.name} khỏi so sánh`}
                            >
                              <CloseIcon />
                            </button>
                          )}
                        </span>
                      ))}

                      {comparisonZones.length < MAX_COMPARE_ZONES &&
                        availableComparisonZones.length > 0 && (
                          <div className="zone-picker-wrap">
                            <button
                              type="button"
                              className="zone-chip-add"
                              onClick={() => setShowZonePicker((current) => !current)}
                            >
                              <PlusIcon />
                              Thêm khu vực
                            </button>

                            {showZonePicker && (
                              <div className="zone-picker-dropdown">
                                {availableComparisonZones.map((zone) => (
                                  <button
                                    key={zone.id}
                                    type="button"
                                    className="zone-picker-item"
                                    onClick={() => addComparisonZone(zone.id)}
                                  >
                                    {zone.name}
                                  </button>
                                ))}
                              </div>
                            )}
                          </div>
                        )}
                    </div>
                  </div>

                  <ZoneComparisonChart
                    zones={comparisonZones}
                    metricKey={comparisonMetric}
                    period={comparisonPeriod}
                    colors={comparisonColors}
                  />
                </>
              )}
            </div>
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default EnvironmentPage
