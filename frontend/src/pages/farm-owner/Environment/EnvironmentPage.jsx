import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import './EnvironmentPage.css'

import EnvironmentTabs from '../../../components/features/farm-owner/environment/EnvironmentTabs'

import MetricCard, {
  MetricIcon,
  getMetricState,
} from '../../../components/features/farm-owner/environment/MetricCard'

import EnvironmentChart from '../../../components/features/farm-owner/environment/EnvironmentChart'
import ZoneComparisonChart from '../../../components/features/farm-owner/environment/ZoneComparisonChart'
import EnvironmentSelect from '../../../components/ui/Select'
import { ErrorMessage } from '../../../components/common/feedback/index.js'

import {
  MAX_COMPARE_ZONES,
  monitoringFarms as defaultMockFarms,
  comparisonColors,
} from '../../../components/features/farm-owner/environment/environmentMockData'

import { useFarms } from '../../../features/farms/hooks/useFarms'
import { useTelemetry } from '../../../features/telemetry/hooks/useTelemetry'

function RefreshIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20 7v5h-5" />
      <path d="M19 12a7 7 0 1 0-2 5" />
    </svg>
  )
}

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
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    zones,
    error: farmsError,
  } = useFarms()

  const {
    telemetry,
    hasData,
    loading: telemetryLoading,
    error: telemetryError,
    refetch: refetchTelemetry,
  } = useTelemetry(selectedFarmId)

  const effectiveZones = useMemo(() => {
    if (zones.length > 0) {
      const baseMetrics = defaultMockFarms[0]?.zones[0]?.metrics || {}
      return zones.map((z, idx) => {
        const zMetrics = JSON.parse(JSON.stringify(baseMetrics))
        if (telemetry && telemetry.temperature != null) {
          zMetrics.temperature.value = telemetry.temperature
          zMetrics.temperature.displayValue = `${telemetry.temperature.toFixed(1)}°C`
        } else if (!hasData) {
          zMetrics.temperature.displayValue = '--°C'
        }
        if (telemetry && telemetry.humidity != null) {
          zMetrics.humidity.value = telemetry.humidity
          zMetrics.humidity.displayValue = `${Math.round(telemetry.humidity)}%`
        } else if (!hasData) {
          zMetrics.humidity.displayValue = '--%'
        }
        if (telemetry && telemetry.co2 != null) {
          zMetrics.co2.value = telemetry.co2
          zMetrics.co2.displayValue = `${Math.round(telemetry.co2)} ppm`
        } else if (!hasData) {
          zMetrics.co2.displayValue = '-- ppm'
        }
        if (telemetry && telemetry.light != null) {
          zMetrics.light.value = telemetry.light
          zMetrics.light.displayValue = `${Math.round(telemetry.light)} lux`
        } else if (!hasData) {
          zMetrics.light.displayValue = '-- lux'
        }
        return {
          id: z.id,
          name: z.name,
          node: `ENV-${String(idx + 1).padStart(2, '0')}`,
          lastSeen: telemetry?.timestamp ? 'Vừa xong' : 'Chưa có dữ liệu',
          status: hasData ? 'live' : 'offline',
          metrics: zMetrics,
        }
      })
    }
    return defaultMockFarms[0]?.zones || []
  }, [zones, telemetry, hasData])

  const [zoneId, setZoneId] = useState(effectiveZones[0]?.id || '')
  const [selectedMetric, setSelectedMetric] = useState('temperature')
  const [period, setPeriod] = useState('24h')
  const [comparisonMetric, setComparisonMetric] = useState('temperature')
  const [comparisonPeriod, setComparisonPeriod] = useState('24h')
  const [comparisonZoneIds, setComparisonZoneIds] = useState(() =>
    effectiveZones.slice(0, 2).map((z) => z.id),
  )
  const [showZonePicker, setShowZonePicker] = useState(false)

  const selectedZone =
    effectiveZones.find((zone) => zone.id === zoneId) ?? effectiveZones[0] ?? {
      id: 'default',
      name: 'Khu vực 1',
      node: 'ENV-01',
      lastSeen: '---',
      metrics: defaultMockFarms[0]?.zones[0]?.metrics,
    }

  const selectedMetricData =
    selectedZone.metrics?.[selectedMetric] ||
    defaultMockFarms[0]?.zones[0]?.metrics?.[selectedMetric]

  const selectedMetricState = getMetricState(selectedMetricData)

  const comparisonZones = effectiveZones.filter((zone) =>
    comparisonZoneIds.includes(zone.id),
  )

  const availableComparisonZones = effectiveZones.filter(
    (zone) => !comparisonZoneIds.includes(zone.id),
  )

  const addComparisonZone = (zoneIdToAdd) => {
    if (comparisonZoneIds.length >= MAX_COMPARE_ZONES) {
      return
    }

    setComparisonZoneIds((current) => [...current, zoneIdToAdd])
    setShowZonePicker(false)
  }

  const removeComparisonZone = (zoneIdToRemove) => {
    setComparisonZoneIds((current) =>
      current.filter((id) => id !== zoneIdToRemove),
    )
  }

  return (
    <AppLayout>
      <div className="environment-page">
        <section className="environment-page-heading">
          <div>
            <span className="environment-eyebrow">ENVIRONMENT MONITORING</span>

            <h1>Môi trường nhà yến</h1>

            <p>
              Theo dõi điều kiện vi khí hậu và ngưỡng an toàn theo từng khu vực.
            </p>
          </div>

          <div className="environment-live-status">
            <span className="live-indicator">
              <i />
              {hasData ? 'Dữ liệu trực tiếp' : 'Chưa có telemetry'}
            </span>

            <small>Cập nhật {selectedZone.lastSeen}</small>
          </div>
        </section>

        {farmsError && (
          <ErrorMessage title="Lỗi danh sách nhà yến" message={farmsError} />
        )}
        {telemetryError && (
          <ErrorMessage
            title="Lỗi tải dữ liệu cảm biến"
            message={telemetryError}
            onRetry={refetchTelemetry}
          />
        )}

        <EnvironmentTabs />

        <section className="environment-context-bar">
          <div className="context-select-group">
            <EnvironmentSelect
              label="Nhà yến"
              value={selectedFarmId || ''}
              options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
              }))}
              onChange={(nextFarmId) => {
                setSelectedFarmId(nextFarmId)
                setShowZonePicker(false)
              }}
            />

            <EnvironmentSelect
              label="Khu vực"
              value={zoneId}
              options={effectiveZones.map((zone) => ({
                value: zone.id,
                label: zone.name,
              }))}
              onChange={(nextZoneId) => {
                setZoneId(nextZoneId)
              }}
            />
          </div>
        </section>

        <section className="environment-section">
          <div className="environment-section-heading">
            <div>
              <span className="section-number">01</span>

              <div>
                <h2>Điều kiện hiện tại</h2>
                <p>Dữ liệu mới nhất từ {selectedZone.node}</p>
              </div>
            </div>
          </div>

          <div className="metrics-grid">
            {Object.entries(selectedZone.metrics || {}).map(([key, metric]) => (
              <MetricCard
                key={key}
                metricKey={key}
                metric={metric}
                isSelected={selectedMetric === key}
                onSelect={setSelectedMetric}
              />
            ))}
          </div>
        </section>

        <section className="environment-section">
          <div className="environment-section-heading">
            <div>
              <span className="section-number">02</span>

              <div>
                <h2>Biểu đồ chi tiết theo thời gian</h2>
                <p>
                  Theo dõi xu hướng biến động và đối chiếu với ngưỡng an toàn
                  khuyến nghị.
                </p>
              </div>
            </div>

            <div className="period-toggle">
              {['6h', '24h', '7d'].map((p) => (
                <button
                  key={p}
                  type="button"
                  className={`period-btn ${period === p ? 'active' : ''}`}
                  onClick={() => setPeriod(p)}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          <EnvironmentChart
            metric={selectedMetricData}
            period={period}
            state={selectedMetricState}
          />
        </section>

        <section className="environment-section">
          <div className="environment-section-heading">
            <div>
              <span className="section-number">03</span>

              <div>
                <h2>So sánh giữa các khu vực</h2>
                <p>
                  Đối chiếu điều kiện vi khí hậu giữa các tầng và phòng trong nhà
                  yến.
                </p>
              </div>
            </div>

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
                    <MetricIcon metricKey={key} />
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

              <div className="period-toggle">
                {['6h', '24h', '7d'].map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`period-btn ${comparisonPeriod === p ? 'active' : ''}`}
                    onClick={() => setComparisonPeriod(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="comparison-chip-bar">
            <span className="comparison-chip-label">
              Khu vực đang so sánh ({comparisonZones.length}/{MAX_COMPARE_ZONES}
              ):
            </span>

            <div className="comparison-chips">
              {comparisonZones.map((zone, idx) => (
                <span
                  key={zone.id}
                  className="zone-chip"
                  style={{
                    borderColor:
                      comparisonColors[idx % comparisonColors.length],
                  }}
                >
                  <span
                    className="zone-chip-dot"
                    style={{
                      background:
                        comparisonColors[idx % comparisonColors.length],
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
        </section>
      </div>
    </AppLayout>
  )
}

export default EnvironmentPage
