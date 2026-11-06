import { useState } from 'react'

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
import { MAX_COMPARE_ZONES, monitoringFarms as farms, comparisonColors } from '../../../components/features/farm-owner/environment/environmentMockData'

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