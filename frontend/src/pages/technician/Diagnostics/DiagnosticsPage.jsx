import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import DiagnosticSummary from '../../../components/features/technician/diagnostics/DiagnosticSummary'
import DiagnosticNodeList from '../../../components/features/technician/diagnostics/DiagnosticNodeList'
import DiagnosticDetailPanel from '../../../components/features/technician/diagnostics/DiagnosticDetailPanel'
import { LoadingSpinner, ErrorMessage } from '../../../components/common/feedback/index.js'
import { diagnosticNodes as defaultDiagnosticNodes } from '../../../components/features/technician/diagnostics/diagnosticsMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'

import './DiagnosticsPage.css'

function DiagnosticsPage() {
  const { devices, selectedFarm, loading, error, refetch } = useTechnicianData()

  const [statusFilter, setStatusFilter] = useState('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedNode, setSelectedNode] = useState(null)

  const effectiveNodes = useMemo(() => {
    if (devices.length > 0) {
      return devices.map((d) => ({
        id: d.id,
        name: d.name,
        farm: d.farmName || selectedFarm?.name || 'Nhà yến',
        zone: d.zoneName || 'Tầng 1',
        status:
          d.status === 'ONLINE'
            ? 'HEALTHY'
            : d.status === 'WARNING'
              ? 'WARNING'
              : 'OFFLINE',
        nodeType: d.typeLabel || d.type,
        ipAddress: d.ipAddress,
        firmware: d.firmware,
        mqtt: d.mqttStatus,
        lastHeartbeat: d.lastSeen,
        sensors: [
          { name: 'Nhiệt độ (SHT31)', status: 'OK' },
          { name: 'Độ ẩm (SHT31)', status: 'OK' },
        ],
      }))
    }
    return defaultDiagnosticNodes
  }, [devices, selectedFarm])

  const summary = useMemo(
    () => ({
      totalNodes: effectiveNodes.length,
      healthyNodes: effectiveNodes.filter((n) => n.status === 'HEALTHY').length,
      warningNodes: effectiveNodes.filter((n) => n.status === 'WARNING').length,
      offlineNodes: effectiveNodes.filter((n) => n.status === 'OFFLINE').length,
    }),
    [effectiveNodes],
  )

  const filteredNodes = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase()

    return effectiveNodes.filter((node) => {
      const matchesStatus =
        statusFilter === 'ALL' || node.status === statusFilter

      const matchesSearch =
        !keyword ||
        (node.name && node.name.toLowerCase().includes(keyword)) ||
        (node.id && node.id.toLowerCase().includes(keyword)) ||
        (node.farm && node.farm.toLowerCase().includes(keyword)) ||
        (node.zone && node.zone.toLowerCase().includes(keyword))

      return matchesStatus && matchesSearch
    })
  }, [effectiveNodes, searchTerm, statusFilter])

  return (
    <AppLayout>
      <div className="technician-diagnostics-page">
        <section className="diagnostics-hero">
          <div>
            <span className="diagnostic-eyebrow">TECHNICIAN WORKSPACE</span>
            <h1>Chẩn đoán thiết bị</h1>
            <p>
              Kiểm tra kết nối MQTT, Sensor, Actuator và các lỗi kỹ thuật của
              thiết bị tại những nhà yến được phân công.
            </p>
          </div>

          <div className="diagnostics-system-state">
            <span className="diagnostic-status-dot healthy" />
            <div>
              <strong>Hệ thống đang giám sát</strong>
              <span>Heartbeat và trạng thái kỹ thuật</span>
            </div>
          </div>
        </section>

        {error && (
          <ErrorMessage
            title="Lỗi tải danh sách chẩn đoán"
            message={error}
            onRetry={refetch}
          />
        )}

        {loading && effectiveNodes.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang phân tích chẩn đoán thiết bị..." />
          </div>
        ) : (
          <>
            <DiagnosticSummary summary={summary} />

            <section className="diagnostics-toolbar">
              <div className="diagnostics-filter">
                {[
                  ['ALL', 'Tất cả'],
                  ['HEALTHY', 'Hoạt động tốt'],
                  ['WARNING', 'Cảnh báo'],
                  ['OFFLINE', 'Mất kết nối'],
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

              <div className="diagnostics-search">
                <input
                  type="text"
                  placeholder="Tìm node theo mã, tên, khu vực..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </section>

            <DiagnosticNodeList
              nodes={filteredNodes}
              onSelectNode={setSelectedNode}
            />

            <DiagnosticDetailPanel
              node={selectedNode}
              onClose={() => setSelectedNode(null)}
            />
          </>
        )}
      </div>
    </AppLayout>
  )
}

export default DiagnosticsPage
