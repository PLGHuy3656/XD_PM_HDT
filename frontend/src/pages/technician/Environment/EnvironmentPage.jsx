import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSummary from '../../../components/features/technician/environment/EnvironmentSummary'
import EnvironmentZoneTable from '../../../components/features/technician/environment/EnvironmentZoneTable'
import EnvironmentDetailPanel from '../../../components/features/technician/environment/EnvironmentDetailPanel'
import {
  environmentSummary,
  environmentZones,
} from '../../../components/features/technician/environment/environmentMockData'

import './EnvironmentPage.css'

function EnvironmentPage() {
  const [farmFilter, setFarmFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [selectedZone, setSelectedZone] = useState(null)
  const [farmSelectOpen, setFarmSelectOpen] = useState(false)

  const farms = useMemo(
    () => [...new Set(environmentZones.map((zone) => zone.farm))],
    [],
  )

  const filteredZones = useMemo(
    () =>
      environmentZones.filter((zone) => {
        const matchesFarm =
          farmFilter === 'ALL' || zone.farm === farmFilter

        const matchesStatus =
          statusFilter === 'ALL' || zone.status === statusFilter

        return matchesFarm && matchesStatus
      }),
    [farmFilter, statusFilter],
  )

  return (
    <AppLayout>
      <main className="technician-environment-page">
        <section className="tech-env-hero">
          <div>
            <span>TECHNICIAN WORKSPACE</span>
            <h1>Giám sát môi trường</h1>
            <p>
              Theo dõi telemetry môi trường tại các khu vực được phân công
              để hỗ trợ chẩn đoán Sensor, Node và Actuator.
            </p>
          </div>

          <div className="tech-env-live">
            <span className="tech-env-dot normal" />
            <div>
              <strong>Telemetry đang hoạt động</strong>
              <span>Dữ liệu kỹ thuật gần thời gian thực</span>
            </div>
          </div>
        </section>

        <EnvironmentSummary summary={environmentSummary} />

        <section className="tech-env-toolbar">
          <div className="tech-env-farm-filter">
            <label>Nhà yến</label>

            <div className="tech-env-select">
                <button
                type="button"
                className={`tech-env-select-trigger ${
                    farmSelectOpen ? 'open' : ''
                }`}
                onClick={() => setFarmSelectOpen((current) => !current)}
                aria-expanded={farmSelectOpen}
                >
                <span>
                    {farmFilter === 'ALL'
                    ? 'Tất cả nhà yến'
                    : farmFilter}
                </span>

                <span className="tech-env-select-chevron">⌄</span>
                </button>

                {farmSelectOpen && (
                <div className="tech-env-select-menu">
                    <button
                    type="button"
                    className={farmFilter === 'ALL' ? 'active' : ''}
                    onClick={() => {
                        setFarmFilter('ALL')
                        setFarmSelectOpen(false)
                    }}
                    >
                    Tất cả nhà yến
                    </button>

                    {farms.map((farm) => (
                    <button
                        type="button"
                        key={farm}
                        className={farmFilter === farm ? 'active' : ''}
                        onClick={() => {
                        setFarmFilter(farm)
                        setFarmSelectOpen(false)
                        }}
                    >
                        {farm}
                    </button>
                    ))}
                </div>
                )}
            </div>
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
      </main>
    </AppLayout>
  )
}

export default EnvironmentPage