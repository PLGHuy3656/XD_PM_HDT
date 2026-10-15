import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import './EnvironmentPage.css'

import EnvironmentTabs from './EnvironmentTabs'
import './EnvironmentControlPage.css'

import EnvironmentSelect from './EnvironmentSelect'
import './EnvironmentSelect.css'

const MAX_COMPARE_ZONES = 4

const farms = [
  {
    id: 'farm-binh-chanh',
    name: 'Nhà yến Bình Chánh',
    zones: [
      {
        id: 'zone-a',
        name: 'Khu vực A',
        node: 'ENV-01',
        lastSeen: 'Vài giây trước',
        status: 'live',
        metrics: {
          temperature: {
            label: 'Nhiệt độ',
            value: 28.5,
            displayValue: '28.5°C',
            unit: '°C',
            min: 24,
            max: 34,
            safeMin: 27,
            safeMax: 31,
            values: [
              27.1, 27.3, 27.2, 27.6, 27.9, 28.2,
              28.6, 28.9, 29.1, 28.8, 28.6, 28.5,
            ],
          },
          humidity: {
            label: 'Độ ẩm',
            value: 78,
            displayValue: '78%',
            unit: '%',
            min: 60,
            max: 100,
            safeMin: 75,
            safeMax: 90,
            values: [
              80, 79, 79, 78, 77, 76,
              78, 81, 82, 80, 79, 78,
            ],
          },
          co2: {
            label: 'CO₂',
            value: 620,
            displayValue: '620 ppm',
            unit: ' ppm',
            min: 300,
            max: 1400,
            safeMin: 400,
            safeMax: 1000,
            values: [
              510, 525, 548, 580, 620, 665,
              710, 690, 672, 655, 635, 620,
            ],
          },
          light: {
            label: 'Ánh sáng',
            value: 120,
            displayValue: '120 lux',
            unit: ' lux',
            min: 0,
            max: 300,
            safeMin: 50,
            safeMax: 180,
            values: [
              65, 70, 78, 90, 105, 125,
              145, 138, 132, 128, 123, 120,
            ],
          },
        },
      },

      {
        id: 'zone-b',
        name: 'Khu vực B',
        node: 'ENV-02',
        lastSeen: '12 giây trước',
        status: 'live',
        metrics: {
          temperature: {
            label: 'Nhiệt độ',
            value: 29.2,
            displayValue: '29.2°C',
            unit: '°C',
            min: 24,
            max: 34,
            safeMin: 27,
            safeMax: 31,
            values: [
              27.8, 28, 28.1, 28.4, 28.7, 29,
              29.3, 29.5, 29.4, 29.3, 29.2, 29.2,
            ],
          },
          humidity: {
            label: 'Độ ẩm',
            value: 73,
            displayValue: '73%',
            unit: '%',
            min: 60,
            max: 100,
            safeMin: 75,
            safeMax: 90,
            values: [
              78, 77, 76, 76, 75, 74,
              73, 72, 72, 73, 73, 73,
            ],
          },
          co2: {
            label: 'CO₂',
            value: 710,
            displayValue: '710 ppm',
            unit: ' ppm',
            min: 300,
            max: 1400,
            safeMin: 400,
            safeMax: 1000,
            values: [
              560, 575, 590, 620, 650, 690,
              735, 760, 748, 730, 718, 710,
            ],
          },
          light: {
            label: 'Ánh sáng',
            value: 105,
            displayValue: '105 lux',
            unit: ' lux',
            min: 0,
            max: 300,
            safeMin: 50,
            safeMax: 180,
            values: [
              60, 65, 75, 86, 98, 110,
              125, 121, 116, 112, 108, 105,
            ],
          },
        },
      },

      {
        id: 'zone-c',
        name: 'Khu vực C',
        node: 'ENV-03',
        lastSeen: '8 giây trước',
        status: 'live',
        metrics: {
          temperature: {
            label: 'Nhiệt độ',
            value: 27.8,
            displayValue: '27.8°C',
            unit: '°C',
            min: 24,
            max: 34,
            safeMin: 27,
            safeMax: 31,
            values: [
              26.8, 27, 27.2, 27.4, 27.6, 27.9,
              28.1, 28.2, 28, 27.9, 27.8, 27.8,
            ],
          },
          humidity: {
            label: 'Độ ẩm',
            value: 82,
            displayValue: '82%',
            unit: '%',
            min: 60,
            max: 100,
            safeMin: 75,
            safeMax: 90,
            values: [
              79, 80, 80, 81, 82, 83,
              84, 83, 83, 82, 82, 82,
            ],
          },
          co2: {
            label: 'CO₂',
            value: 580,
            displayValue: '580 ppm',
            unit: ' ppm',
            min: 300,
            max: 1400,
            safeMin: 400,
            safeMax: 1000,
            values: [
              470, 485, 500, 525, 550, 575,
              610, 625, 615, 600, 590, 580,
            ],
          },
          light: {
            label: 'Ánh sáng',
            value: 92,
            displayValue: '92 lux',
            unit: ' lux',
            min: 0,
            max: 300,
            safeMin: 50,
            safeMax: 180,
            values: [
              55, 60, 66, 74, 83, 95,
              110, 108, 102, 98, 95, 92,
            ],
          },
        },
      },

      {
        id: 'zone-d',
        name: 'Khu vực D',
        node: 'ENV-04',
        lastSeen: '18 giây trước',
        status: 'live',
        metrics: {
          temperature: {
            label: 'Nhiệt độ',
            value: 30.1,
            displayValue: '30.1°C',
            unit: '°C',
            min: 24,
            max: 34,
            safeMin: 27,
            safeMax: 31,
            values: [
              28.2, 28.4, 28.7, 29, 29.4, 29.7,
              30, 30.3, 30.4, 30.3, 30.2, 30.1,
            ],
          },
          humidity: {
            label: 'Độ ẩm',
            value: 76,
            displayValue: '76%',
            unit: '%',
            min: 60,
            max: 100,
            safeMin: 75,
            safeMax: 90,
            values: [
              80, 79, 79, 78, 78, 77,
              77, 76, 76, 76, 76, 76,
            ],
          },
          co2: {
            label: 'CO₂',
            value: 820,
            displayValue: '820 ppm',
            unit: ' ppm',
            min: 300,
            max: 1400,
            safeMin: 400,
            safeMax: 1000,
            values: [
              620, 640, 670, 700, 735, 770,
              815, 850, 845, 835, 825, 820,
            ],
          },
          light: {
            label: 'Ánh sáng',
            value: 135,
            displayValue: '135 lux',
            unit: ' lux',
            min: 0,
            max: 300,
            safeMin: 50,
            safeMax: 180,
            values: [
              70, 78, 88, 100, 115, 132,
              150, 148, 144, 140, 137, 135,
            ],
          },
        },
      },

      {
        id: 'zone-e',
        name: 'Khu vực E',
        node: 'ENV-05',
        lastSeen: '21 giây trước',
        status: 'live',
        metrics: {
          temperature: {
            label: 'Nhiệt độ',
            value: 28.9,
            displayValue: '28.9°C',
            unit: '°C',
            min: 24,
            max: 34,
            safeMin: 27,
            safeMax: 31,
            values: [
              27.4, 27.5, 27.7, 27.9, 28.2, 28.5,
              28.8, 29, 29.1, 29, 28.9, 28.9,
            ],
          },
          humidity: {
            label: 'Độ ẩm',
            value: 79,
            displayValue: '79%',
            unit: '%',
            min: 60,
            max: 100,
            safeMin: 75,
            safeMax: 90,
            values: [
              81, 81, 80, 80, 79, 79,
              78, 78, 79, 79, 79, 79,
            ],
          },
          co2: {
            label: 'CO₂',
            value: 660,
            displayValue: '660 ppm',
            unit: ' ppm',
            min: 300,
            max: 1400,
            safeMin: 400,
            safeMax: 1000,
            values: [
              520, 540, 560, 590, 620, 650,
              690, 710, 700, 685, 670, 660,
            ],
          },
          light: {
            label: 'Ánh sáng',
            value: 112,
            displayValue: '112 lux',
            unit: ' lux',
            min: 0,
            max: 300,
            safeMin: 50,
            safeMax: 180,
            values: [
              62, 68, 77, 88, 100, 116,
              132, 128, 123, 118, 115, 112,
            ],
          },
        },
      },
    ],
  },
]

const comparisonColors = [
  '#d5a62e',
  '#102a43',
  '#4f8c6b',
  '#b86d4b',
]

function MetricIcon({ type }) {
  if (type === 'temperature') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M10 14.7V5a2 2 0 1 1 4 0v9.7a4 4 0 1 1-4 0Z" />
        <path d="M12 17V8" />
      </svg>
    )
  }

  if (type === 'humidity') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M12 3S6.5 9.2 6.5 14a5.5 5.5 0 0 0 11 0C17.5 9.2 12 3 12 3Z" />
      </svg>
    )
  }

  if (type === 'co2') {
    return (
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7.5 17.5H6a4 4 0 0 1-.4-8A5.8 5.8 0 0 1 16.7 8a4.7 4.7 0 0 1 .8 9.4H16" />
        <path d="M9 14.5h2.2M9 17h2.2M14 14.5h1.5L14 17h2" />
      </svg>
    )
  }

  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}

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

function getMetricState(metric) {
  const normal =
    metric.value >= metric.safeMin &&
    metric.value <= metric.safeMax

  return normal
    ? {
        label: 'Bình thường',
        shortLabel: 'Ổn định',
        className: 'normal',
      }
    : {
        label:
          metric.value < metric.safeMin
            ? 'Dưới ngưỡng'
            : 'Vượt ngưỡng',
        shortLabel: 'Chú ý',
        className: 'warning',
      }
}

function MetricCard({
  metricKey,
  metric,
  active,
  onClick,
}) {
  const state = getMetricState(metric)

  return (
    <button
      type="button"
      className={`environment-metric-card${active ? ' active' : ''}`}
      onClick={onClick}
    >
      <div className={`metric-card-icon ${state.className}`}>
        <MetricIcon type={metricKey} />
      </div>

      <div className="metric-card-heading">
        <span>{metric.label}</span>

        <span className={`metric-state ${state.className}`}>
          <i />
          {state.label}
        </span>
      </div>

      <strong className="metric-card-value">
        {metric.displayValue}
      </strong>

      <div className="metric-card-range">
        Ngưỡng {metric.safeMin}–{metric.safeMax}
        {metric.unit}
      </div>
    </button>
  )
}

function EnvironmentChart({ metric }) {
  const width = 900
  const height = 220
  const padding = 18

  const usableWidth = width - padding * 2
  const usableHeight = height - padding * 2

  const points = useMemo(
    () =>
      metric.values.map((value, index) => {
        const x =
          padding +
          (index / (metric.values.length - 1)) *
            usableWidth

        const y =
          padding +
          (1 -
            (value - metric.min) /
              (metric.max - metric.min)) *
            usableHeight

        return { x, y }
      }),
    [metric, usableHeight, usableWidth]
  )

  const polyline = points
    .map((point) => `${point.x},${point.y}`)
    .join(' ')

  const areaPath = [
    `M ${points[0].x} ${height - padding}`,
    ...points.map(
      (point) => `L ${point.x} ${point.y}`
    ),
    `L ${points[points.length - 1].x} ${height - padding}`,
    'Z',
  ].join(' ')

  const safeTop =
    padding +
    (1 -
      (metric.safeMax - metric.min) /
        (metric.max - metric.min)) *
      usableHeight

  const safeBottom =
    padding +
    (1 -
      (metric.safeMin - metric.min) /
        (metric.max - metric.min)) *
      usableHeight

  return (
    <div className="environment-chart">
      <div className="chart-canvas">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient
              id="environmentArea"
              x1="0"
              y1="0"
              x2="0"
              y2="1"
            >
              <stop
                offset="0%"
                stopColor="currentColor"
                stopOpacity="0.18"
              />
              <stop
                offset="100%"
                stopColor="currentColor"
                stopOpacity="0.01"
              />
            </linearGradient>
          </defs>

          {[0, 1, 2, 3, 4].map((line) => {
            const y =
              padding +
              (line / 4) * usableHeight

            return (
              <line
                key={line}
                x1={padding}
                x2={width - padding}
                y1={y}
                y2={y}
                className="chart-grid-line"
              />
            )
          })}

          <rect
            x={padding}
            y={safeTop}
            width={usableWidth}
            height={safeBottom - safeTop}
            className="chart-safe-zone"
          />

          <path
            d={areaPath}
            className="chart-area"
          />

          <polyline
            points={polyline}
            className="chart-line"
          />

          {points.map((point, index) => (
            <circle
              key={index}
              cx={point.x}
              cy={point.y}
              r={
                index === points.length - 1
                  ? 5
                  : 2.8
              }
              className={
                index === points.length - 1
                  ? 'chart-point current'
                  : 'chart-point'
              }
            />
          ))}
        </svg>
      </div>

      <div className="chart-time-axis">
        <span>00:00</span>
        <span>04:00</span>
        <span>08:00</span>
        <span>12:00</span>
        <span>16:00</span>
        <span>20:00</span>
        <span>Hiện tại</span>
      </div>
    </div>
  )
}

function ZoneComparisonChart({
  zones,
  metricKey,
}) {
  const width = 900
  const height = 230
  const padding = 20

  const metrics = zones.map(
    (zone) => zone.metrics[metricKey]
  )

  const min = Math.min(
    ...metrics.map((metric) => metric.min)
  )

  const max = Math.max(
    ...metrics.map((metric) => metric.max)
  )

  const getPoints = (metric) =>
    metric.values
      .map((value, index) => {
        const x =
          padding +
          (index /
            (metric.values.length - 1)) *
            (width - padding * 2)

        const y =
          padding +
          (1 -
            (value - min) / (max - min)) *
            (height - padding * 2)

        return `${x},${y}`
      })
      .join(' ')

  return (
    <div className="comparison-chart">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
      >
        {[0, 1, 2, 3, 4].map((line) => {
          const y =
            padding +
            (line / 4) *
              (height - padding * 2)

          return (
            <line
              key={line}
              x1={padding}
              x2={width - padding}
              y1={y}
              y2={y}
              className="comparison-grid-line"
            />
          )
        })}

        {metrics.map((metric, index) => (
          <polyline
            key={zones[index].id}
            points={getPoints(metric)}
            className="comparison-line"
            style={{
              stroke:
                comparisonColors[index],
            }}
          />
        ))}
      </svg>
    </div>
  )
}

function EnvironmentPage() {
  const [farmId, setFarmId] = useState(
    farms[0].id
  )

  const [zoneId, setZoneId] = useState(
    farms[0].zones[0].id
  )

  const [selectedMetric, setSelectedMetric] =
    useState('temperature')

  const [period, setPeriod] =
    useState('24h')

  const [
    comparisonMetric,
    setComparisonMetric,
  ] = useState('temperature')

  const [
    comparisonPeriod,
    setComparisonPeriod,
  ] = useState('24h')

  const [
    comparisonZoneIds,
    setComparisonZoneIds,
  ] = useState([
    farms[0].zones[0].id,
    farms[0].zones[1].id,
  ])

  const [showZonePicker, setShowZonePicker] =
    useState(false)

  const selectedFarm =
    farms.find(
      (farm) => farm.id === farmId
    ) ?? farms[0]

  const selectedZone =
    selectedFarm.zones.find(
      (zone) => zone.id === zoneId
    ) ?? selectedFarm.zones[0]

  const selectedMetricData =
    selectedZone.metrics[selectedMetric]

  const selectedMetricState =
    getMetricState(selectedMetricData)

  const comparisonZones =
    selectedFarm.zones.filter((zone) =>
      comparisonZoneIds.includes(zone.id)
    )

  const availableComparisonZones =
    selectedFarm.zones.filter(
      (zone) =>
        !comparisonZoneIds.includes(zone.id)
    )

  const addComparisonZone = (zoneIdToAdd) => {
    if (
      comparisonZoneIds.length >=
      MAX_COMPARE_ZONES
    ) {
      return
    }

    setComparisonZoneIds((current) => [
      ...current,
      zoneIdToAdd,
    ])

    setShowZonePicker(false)
  }

  const removeComparisonZone = (
    zoneIdToRemove
  ) => {
    setComparisonZoneIds((current) =>
      current.filter(
        (id) => id !== zoneIdToRemove
      )
    )
  }

  return (
    <AppLayout>
      <div className="environment-page">
        <section className="environment-page-heading">
          <div>
            <span className="environment-eyebrow">
              ENVIRONMENT MONITORING
            </span>

            <h1>Môi trường nhà yến</h1>

            <p>
              Theo dõi điều kiện vi khí hậu và
              ngưỡng an toàn theo từng khu vực.
            </p>
          </div>

          <div className="environment-live-status">
            <span className="live-indicator">
              <i />
              Dữ liệu trực tiếp
            </span>

            <small>
              Cập nhật {selectedZone.lastSeen}
            </small>
          </div>
        </section>

        <EnvironmentTabs />

        <section className="environment-context-bar">
          <div className="context-select-group">
            <EnvironmentSelect
                label="Nhà yến"
                value={farmId}
                options={farms.map((farm) => ({
                value: farm.id,
                label: farm.name,
                }))}
                onChange={(nextFarmId) => {
                const nextFarm =
                    farms.find(
                    (farm) => farm.id === nextFarmId
                    ) ?? farms[0]

                setFarmId(nextFarmId)
                setZoneId(nextFarm.zones[0].id)

                setComparisonZoneIds(
                    nextFarm.zones
                    .slice(0, 2)
                    .map((zone) => zone.id)
                )

                setShowZonePicker(false)
                }}
            />

            <EnvironmentSelect
                label="Khu vực"
                value={zoneId}
                options={selectedFarm.zones.map((zone) => ({
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
              <span className="section-number">
                01
              </span>

              <div>
                <h2>Điều kiện hiện tại</h2>
                <p>
                  Dữ liệu mới nhất từ{' '}
                  {selectedZone.node}
                </p>
              </div>
            </div>

            <button
              type="button"
              className="refresh-button"
            >
              <RefreshIcon />
              <span>Làm mới</span>
            </button>
          </div>

          <div className="environment-metric-grid">
            {Object.entries(
              selectedZone.metrics
            ).map(([key, metric]) => (
              <MetricCard
                key={key}
                metricKey={key}
                metric={metric}
                active={
                  selectedMetric === key
                }
                onClick={() =>
                  setSelectedMetric(key)
                }
              />
            ))}
          </div>
        </section>

        <section className="environment-detail-grid">
          <article className="environment-chart-card">
            <div className="chart-card-heading">
              <div>
                <span className="section-number">
                  02
                </span>

                <div>
                  <h2>
                    Biến động môi trường
                  </h2>

                  <p>
                    {selectedMetricData.label}
                    {' · '}
                    {selectedZone.name}
                  </p>
                </div>
              </div>

              <div className="period-switcher">
                {['24h', '7d', '30d'].map(
                  (item) => (
                    <button
                      key={item}
                      type="button"
                      className={
                        period === item
                          ? 'active'
                          : ''
                      }
                      onClick={() =>
                        setPeriod(item)
                      }
                    >
                      {item === '24h'
                        ? '24 giờ'
                        : item === '7d'
                          ? '7 ngày'
                          : '30 ngày'}
                    </button>
                  )
                )}
              </div>
            </div>

            <div className="chart-summary">
              <div>
                <span>Hiện tại</span>

                <strong>
                  {
                    selectedMetricData.displayValue
                  }
                </strong>
              </div>

              <span
                className={`chart-summary-status ${selectedMetricState.className}`}
              >
                <i />
                {selectedMetricState.label}
              </span>
            </div>

            <EnvironmentChart
              metric={selectedMetricData}
            />

            <div className="chart-legend">
              <span>
                <i className="legend-current" />
                Dữ liệu cảm biến
              </span>

              <span>
                <i className="legend-safe" />
                Khoảng an toàn
              </span>
            </div>
          </article>

          <aside className="environment-threshold-card">
            <div className="threshold-heading">
              <span className="section-number">
                03
              </span>

              <div>
                <h2>Ngưỡng môi trường</h2>
                <p>Cấu hình đang áp dụng</p>
              </div>
            </div>

            <div className="threshold-list">
              {Object.entries(
                selectedZone.metrics
              ).map(([key, metric]) => {
                const state =
                  getMetricState(metric)

                return (
                  <div
                    className="threshold-row"
                    key={key}
                  >
                    <div className="threshold-metric">
                      <span className="threshold-icon">
                        <MetricIcon
                          type={key}
                        />
                      </span>

                      <div>
                        <strong>
                          {metric.label}
                        </strong>

                        <small>
                          {metric.safeMin}–
                          {metric.safeMax}
                          {metric.unit}
                        </small>
                      </div>
                    </div>

                    <span
                      className={`threshold-state ${state.className}`}
                    >
                      <i />
                      {state.shortLabel}
                    </span>
                  </div>
                )
              })}
            </div>

            <div className="threshold-note">
              <span>i</span>

              <p>
                Ngưỡng được dùng để đánh giá
                môi trường và tạo cảnh báo khi
                dữ liệu vượt giới hạn cấu hình.
              </p>
            </div>
          </aside>
        </section>

        <section className="zone-comparison-card">
          <div className="comparison-heading">
            <div>
              <span className="section-number">
                04
              </span>

              <div>
                <h2>So sánh khu vực</h2>

                <p>
                  Chọn tối đa 4 khu vực để đối
                  chiếu điều kiện vi khí hậu.
                </p>
              </div>
            </div>

            <div className="comparison-period">
              {['24h', '7d', '30d'].map(
                (item) => (
                  <button
                    key={item}
                    type="button"
                    className={
                      comparisonPeriod === item
                        ? 'active'
                        : ''
                    }
                    onClick={() =>
                      setComparisonPeriod(item)
                    }
                  >
                    {item === '24h'
                      ? '24 giờ'
                      : item === '7d'
                        ? '7 ngày'
                        : '30 ngày'}
                  </button>
                )
              )}
            </div>
          </div>

          <div className="comparison-metric-tabs">
            {Object.entries(
              selectedZone.metrics
            ).map(([key, metric]) => (
              <button
                key={key}
                type="button"
                className={
                  comparisonMetric === key
                    ? 'active'
                    : ''
                }
                onClick={() =>
                  setComparisonMetric(key)
                }
              >
                {metric.label}
              </button>
            ))}
          </div>

          {selectedFarm.zones.length < 2 ? (
            <div className="comparison-empty-state">
              <strong>
                Chưa thể so sánh khu vực
              </strong>

              <p>
                Nhà yến cần ít nhất 2 khu vực
                để sử dụng chức năng này.
              </p>
            </div>
          ) : (
            <>
              <div className="comparison-selection">
                <div className="comparison-selection-heading">
                  <div>
                    <span>Khu vực so sánh</span>

                    <small>
                      Chọn ít nhất 2 và tối đa{' '}
                      {MAX_COMPARE_ZONES} khu vực
                    </small>
                  </div>

                  <strong>
                    {comparisonZoneIds.length}/
                    {MAX_COMPARE_ZONES}
                  </strong>
                </div>

                <div className="comparison-zone-chips">
                  {comparisonZones.map(
                    (zone, index) => (
                      <div
                        className="comparison-zone-chip"
                        key={zone.id}
                      >
                        <span
                          className="comparison-zone-dot"
                          style={{
                            background:
                              comparisonColors[
                                index
                              ],
                          }}
                        />

                        <div>
                          <strong>
                            {zone.name}
                          </strong>

                          <small>
                            {zone.node}
                          </small>
                        </div>

                        <button
                          type="button"
                          aria-label={`Bỏ ${zone.name} khỏi so sánh`}
                          onClick={() =>
                            removeComparisonZone(
                              zone.id
                            )
                          }
                        >
                          <CloseIcon />
                        </button>
                      </div>
                    )
                  )}

                  {comparisonZoneIds.length <
                    MAX_COMPARE_ZONES &&
                    availableComparisonZones.length >
                      0 && (
                      <div className="comparison-add-wrapper">
                        <button
                          type="button"
                          className="comparison-add-button"
                          onClick={() =>
                            setShowZonePicker(
                              (current) =>
                                !current
                            )
                          }
                        >
                          <PlusIcon />
                          Thêm khu vực
                        </button>

                        {showZonePicker && (
                          <div className="comparison-zone-picker">
                            <span>
                              Chọn khu vực
                            </span>

                            {availableComparisonZones.map(
                              (zone) => (
                                <button
                                  key={
                                    zone.id
                                  }
                                  type="button"
                                  onClick={() =>
                                    addComparisonZone(
                                      zone.id
                                    )
                                  }
                                >
                                  <div>
                                    <strong>
                                      {
                                        zone.name
                                      }
                                    </strong>

                                    <small>
                                      {
                                        zone.node
                                      }
                                    </small>
                                  </div>

                                  <PlusIcon />
                                </button>
                              )
                            )}
                          </div>
                        )}
                      </div>
                    )}
                </div>
              </div>

              {comparisonZones.length >= 2 ? (
                <>
                  <div className="comparison-current-values">
                    {comparisonZones.map(
                      (zone, index) => {
                        const metric =
                          zone.metrics[
                            comparisonMetric
                          ]

                        const state =
                          getMetricState(
                            metric
                          )

                        return (
                          <div
                            key={zone.id}
                            className="comparison-current-zone"
                          >
                            <span
                              style={{
                                background:
                                  comparisonColors[
                                    index
                                  ],
                              }}
                            />

                            <div>
                              <small>
                                {zone.name}
                              </small>

                              <strong>
                                {
                                  metric.displayValue
                                }
                              </strong>
                            </div>

                            <em
                              className={
                                state.className
                              }
                            >
                              {
                                state.shortLabel
                              }
                            </em>
                          </div>
                        )
                      }
                    )}
                  </div>

                  <ZoneComparisonChart
                    zones={comparisonZones}
                    metricKey={
                      comparisonMetric
                    }
                  />

                  <div className="comparison-axis">
                    <span>00:00</span>
                    <span>04:00</span>
                    <span>08:00</span>
                    <span>12:00</span>
                    <span>16:00</span>
                    <span>20:00</span>
                    <span>Hiện tại</span>
                  </div>
                </>
              ) : (
                <div className="comparison-empty-state compact">
                  <strong>
                    Chọn thêm một khu vực
                  </strong>

                  <p>
                    Cần ít nhất 2 khu vực để
                    hiển thị biểu đồ so sánh.
                  </p>
                </div>
              )}
            </>
          )}
        </section>

        <footer className="environment-source-bar">
          <div className="source-status">
            <span className="source-icon">
              <i />
            </span>

            <div>
              <strong>
                {selectedZone.node}
              </strong>

              <span>
                Sensor môi trường ·{' '}
                {selectedZone.name}
              </span>
            </div>
          </div>

          <div className="source-meta">
            <span>
              Trạng thái

              <strong className="online">
                <i />
                Online
              </strong>
            </span>

            <span>
              Bản ghi cuối

              <strong>
                {selectedZone.lastSeen}
              </strong>
            </span>
          </div>
        </footer>
      </div>
    </AppLayout>
    
  )
}

export default EnvironmentPage