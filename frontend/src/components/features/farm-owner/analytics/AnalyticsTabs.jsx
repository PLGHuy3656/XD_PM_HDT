const tabs = [
  {
    id: 'overview',
    label: 'Tổng quan',
  },
  {
    id: 'detail',
    label: 'Phân tích chi tiết',
  },
  {
    id: 'yield',
    label: 'Năng suất',
  },
]

function AnalyticsTabs({ activeTab, onChange }) {
  return (
    <nav
      className="analytics-tabs"
      aria-label="Các nhóm phân tích"
    >
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={
            activeTab === tab.id ? 'active' : ''
          }
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

export default AnalyticsTabs