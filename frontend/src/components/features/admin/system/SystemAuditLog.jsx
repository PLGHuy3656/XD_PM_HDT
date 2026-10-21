import { useMemo, useState } from 'react'
import Select from '../../../ui/Select'
import { systemAuditLogs } from './systemMockData'

const auditCategoryOptions = [
  { value: 'ALL', label: 'Tất cả nhóm' },
  { value: 'USER', label: 'Người dùng' },
  { value: 'FARM', label: 'Nhà yến' },
  { value: 'ACCESS', label: 'Phân quyền / phân công' },
  { value: 'DEVICE', label: 'Thiết bị' },
]

function SystemAuditLog() {
  const [searchTerm, setSearchTerm] = useState('')
  const [category, setCategory] = useState('ALL')

  const filteredLogs = useMemo(() => {
    const keyword =
      searchTerm.trim().toLowerCase()

    return systemAuditLogs.filter((log) => {
      const matchesSearch =
        !keyword ||
        log.actor.toLowerCase().includes(keyword) ||
        log.action.toLowerCase().includes(keyword) ||
        log.description
          .toLowerCase()
          .includes(keyword) ||
        log.target.toLowerCase().includes(keyword)

      const matchesCategory =
        category === 'ALL' ||
        log.category === category

      return matchesSearch && matchesCategory
    })
  }, [searchTerm, category])

  return (
    <section className="admin-system-card">
      <div className="admin-system-card__heading">
        <div>
          <span>AUDIT LOG</span>
          <h2>Nhật ký hoạt động</h2>
          <p>
            Theo dõi các thay đổi quản trị và sự kiện hệ
            thống quan trọng.
          </p>
        </div>

        <p>
          {filteredLogs.length} /{' '}
          {systemAuditLogs.length} bản ghi
        </p>
      </div>

      <div className="admin-system-audit-toolbar">
        <input
          type="search"
          value={searchTerm}
          onChange={(event) =>
            setSearchTerm(event.target.value)
          }
          placeholder="Tìm hành động, người thực hiện, đối tượng..."
        />

        <Select
          value={category}
          options={auditCategoryOptions}
          onChange={setCategory}
        />
      </div>

      <div className="admin-system-audit-table-wrap">
        <table className="admin-system-audit-table">
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Người thực hiện</th>
              <th>Hành động</th>
              <th>Nội dung</th>
              <th>Đối tượng</th>
            </tr>
          </thead>

          <tbody>
            {filteredLogs.map((log) => (
              <tr key={log.id}>
                <td>{log.time}</td>

                <td>
                  <strong>{log.actor}</strong>
                  <span>{log.role}</span>
                </td>

                <td>
                  <code>{log.action}</code>
                </td>

                <td>{log.description}</td>

                <td>{log.target}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {!filteredLogs.length && (
          <div className="admin-system-audit-empty">
            Không tìm thấy nhật ký phù hợp.
          </div>
        )}
      </div>
    </section>
  )
}

export default SystemAuditLog
