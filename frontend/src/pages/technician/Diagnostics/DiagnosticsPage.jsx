import { useMemo, useState } from 'react'

import AppLayout from '../../../components/layout/AppLayout'
import EnvironmentSelect from '../../../components/ui/Select'
import DiagnosticSummary from '../../../components/features/technician/diagnostics/DiagnosticSummary'
import DiagnosticNodeList from '../../../components/features/technician/diagnostics/DiagnosticNodeList'
import DiagnosticDetailPanel from '../../../components/features/technician/diagnostics/DiagnosticDetailPanel'
import { LoadingSpinner, ErrorMessage, EmptyState } from '../../../components/common/feedback/index.js'
import { diagnosticNodes as defaultDiagnosticNodes } from '../../../components/features/technician/diagnostics/diagnosticsMockData'

import { useTechnicianData } from '../../../features/technicians/hooks/useTechnicianData'
import { formatFarmOptionLabel } from '../../../features/farms/adapters/farmAdapter.js'
import { USE_MOCK } from '../../../api/config.js'

import '../TechnicianWorkspace.css'
import './DiagnosticsPage.css'

function DiagnosticsPage() {
  const {
    farms,
    selectedFarm,
    selectedFarmId,
    setSelectedFarmId,
    devices,
    telemetryError,
    loading,
    error,
    refetch,
  } = useTechnicianData()

  const [statusFilter, setStatusFilter] = useState('ALL')
  const [searchTerm, setSearchTerm] = useState('')
  const [selectedNode, setSelectedNode] = useState(null)

  const effectiveNodes = useMemo(() => {
    if (devices.length > 0) {
      return devices.map((d) => ({
        id: d.nodeId || d.id,
        deviceId: d.deviceId || d.id,
        name: d.name,
        farm: d.farmName || selectedFarm?.name || 'Nhà yến',
        zone: d.isZoneAssigned ? d.zoneName : 'Chưa phân bổ Zone',
        status:
          d.status === 'ONLINE'
            ? 'HEALTHY'
            : d.status === 'WARNING'
              ? 'WARNING'
              : d.status === 'OFFLINE'
                ? 'OFFLINE'
                : 'REGISTERED',
        nodeType: d.typeLabel || d.type,
        type: d.typeLabel || d.type,
        ipAddress: d.ipAddress || '--',
        firmware: d.firmware || '--',
        mqtt: d.mqttStatus || 'Chưa kết nối IoT',
        lastHeartbeat: d.lastSeen || 'Chưa có dữ liệu',
        connectivity: {
          mqtt: d.mqttStatus || 'Chưa kết nối IoT',
          wifi: '--',
          rssi: d.signal,
          ip: d.ipAddress || '--',
          lastHeartbeat: d.lastSeen || 'Chưa có dữ liệu',
        },
        sensors: [],
        actuators: [],
        issues: [],
        logs: [],
      }))
    }
    return USE_MOCK ? defaultDiagnosticNodes : []
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
      <div className="tech-ws technician-diagnostics-page">
        <header className="tech-ws-header">
          <div className="tech-ws-header__copy">
            <span className="tech-ws-eyebrow">TECHNICIAN DIAGNOSTICS</span>
            <h1>Chẩn đoán thiết bị</h1>
            <p>
              Kiểm tra trạng thái đăng ký, phân bổ khu vực và kết nối IoT của thiết bị tại những nhà yến được phân công.
            </p>
          </div>

          <div className="tech-ws-header__actions">
            {farms.length > 0 && (
              <div className="tech-ws-farm-picker">
                <span>Nhà yến phụ trách</span>
                <EnvironmentSelect
                  value={selectedFarmId || ''}
                  onChange={(nextId) => {
                    setSelectedFarmId(nextId)
                    setSelectedNode(null)
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
            title="Lỗi tải danh sách chẩn đoán"
            message={error}
            onRetry={refetch}
          />
        )}

        {!USE_MOCK && telemetryError && (
          <ErrorMessage
            variant="warning"
            title="Chưa kết nối dịch vụ IoT"
            message="Không thể truy xuất heartbeat/telemetry thời gian thực. Các thiết bị đã đăng ký hiển thị trạng thái chưa có tín hiệu IoT và không bị đánh dấu lỗi phần cứng."
            onRetry={refetch}
          />
        )}

        {loading && effectiveNodes.length === 0 ? (
          <div style={{ padding: '3rem', display: 'flex', justifyContent: 'center' }}>
            <LoadingSpinner size="lg" text="Đang tải danh sách thiết bị chẩn đoán..." />
          </div>
        ) : farms.length === 0 ? (
          <EmptyState
            title="Chưa có nhà yến được phân công"
            description="Liên hệ Admin để được phân công nhà yến trước khi chẩn đoán thiết bị."
          />
        ) : effectiveNodes.length === 0 ? (
          <EmptyState
            title="Chưa có thiết bị nào được đăng ký"
            description="Nhà yến đang chọn chưa có thiết bị nào trong hệ thống."
          />
        ) : (
          <>
            <DiagnosticSummary summary={summary} />

            <section className="diagnostics-toolbar">
              <div className="diagnostics-filter">
                {[
                  ['ALL', 'Tất cả'],
                  ['HEALTHY', 'Trực tuyến'],
                  ['REGISTERED', 'Đã đăng ký (Chưa có IoT)'],
                  ['WARNING', 'Cảnh báo'],
                  ['OFFLINE', 'Ngoại tuyến'],
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
              selectedNodeId={selectedNode?.id}
              onSelect={setSelectedNode}
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
