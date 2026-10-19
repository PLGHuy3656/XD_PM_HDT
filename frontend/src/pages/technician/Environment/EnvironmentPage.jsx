import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
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

  const farmOptions = useMemo(() => {
    const uniqueFarms = [
      ...new Set(environmentZones.map((zone) => zone.farm)),
    ]

    return [
      { value: 'ALL', label: 'Tất cả nhà yến' },
      ...uniqueFarms.map((farm) => ({
        value: farm,
        label: farm,
      })),
    ]
  }, [])

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
      <div className="technician-environment-page">
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
      </div>
    </AppLayout>
  )
}

export default EnvironmentPage