import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import DiagnosticSummary from '../../../components/features/technician/diagnostics/DiagnosticSummary'
import DiagnosticNodeList from '../../../components/features/technician/diagnostics/DiagnosticNodeList'
import DiagnosticDetailPanel from '../../../components/features/technician/diagnostics/DiagnosticDetailPanel'
import {
  diagnosticNodes,
  diagnosticSummary,
} from '../../../components/features/technician/diagnostics/diagnosticsMockData'

import './DiagnosticsPage.css'

function DiagnosticsPage() {
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedNode, setSelectedNode] = useState(null)

  const filteredNodes = useMemo(() => {
    const keyword = searchTerm.trim().toLowerCase()

    return diagnosticNodes.filter((node) => {
      const matchesStatus =
        statusFilter === 'ALL' || node.status === statusFilter

      const matchesSearch =
        !keyword ||
        node.name.toLowerCase().includes(keyword) ||
        node.id.toLowerCase().includes(keyword) ||
        node.farm.toLowerCase().includes(keyword) ||
        node.zone.toLowerCase().includes(keyword)

      return matchesStatus && matchesSearch
    })
  }, [searchTerm, statusFilter])

  return (
    <AppLayout>
      <main className="technician-diagnostics-page">
        <section className="diagnostics-hero">
          <div>
            <span className="diagnostic-eyebrow">
              TECHNICIAN WORKSPACE
            </span>
            <h1>Chẩn đoán thiết bị</h1>
            <p>
              Kiểm tra kết nối MQTT, Sensor, Actuator và các lỗi kỹ thuật
              của thiết bị tại những nhà yến được phân công.
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

        <DiagnosticSummary summary={diagnosticSummary} />

        <section className="diagnostic-toolbar">
          <div className="diagnostic-search">
            <span>⌕</span>
            <input
              type="search"
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              placeholder="Tìm theo Node, nhà yến hoặc khu vực..."
            />
          </div>

          <div className="diagnostic-filter-group">
            {[
              ['ALL', 'Tất cả'],
              ['HEALTHY', 'Ổn định'],
              ['WARNING', 'Cảnh báo'],
              ['OFFLINE', 'Offline'],
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

        <DiagnosticNodeList
          nodes={filteredNodes}
          selectedNodeId={selectedNode?.id}
          onSelect={setSelectedNode}
        />

        {filteredNodes.length === 0 && (
          <div className="diagnostic-no-result">
            Không tìm thấy thiết bị phù hợp với bộ lọc.
          </div>
        )}

        <DiagnosticDetailPanel
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      </main>
    </AppLayout>
  )
}

export default DiagnosticsPage