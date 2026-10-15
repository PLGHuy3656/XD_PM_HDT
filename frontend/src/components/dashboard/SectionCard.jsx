import { useState } from 'react'

function ChevronIcon({ collapsed }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`card-chevron${collapsed ? ' collapsed' : ''}`}
    >
      <path d="m6 15 6-6 6 6" />
    </svg>
  )
}

function SectionCard({
  title,
  subtitle,
  action,
  collapsible = true,
  defaultCollapsed = false,
  className = '',
  children,
}) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)

  return (
    <section
      className={[
        'dashboard-card',
        collapsed ? 'dashboard-card-collapsed' : '',
        className,
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div className="dashboard-card-header">
        <div className="dashboard-card-heading">
          <div>
            {title && (
              <h2 className="dashboard-card-title">
                {title}
              </h2>
            )}

            {subtitle && !collapsed && (
              <p className="dashboard-card-subtitle">
                {subtitle}
              </p>
            )}
          </div>

          {action && !collapsed && (
            <div className="dashboard-card-action">
              {action}
            </div>
          )}
        </div>

        {collapsible && (
          <button
            type="button"
            className="dashboard-collapse-button"
            aria-label={collapsed ? `Mở ${title}` : `Thu gọn ${title}`}
            aria-expanded={!collapsed}
            onClick={() => setCollapsed((current) => !current)}
          >
            <ChevronIcon collapsed={collapsed} />
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="dashboard-card-content">
          {children}
        </div>
      )}
    </section>
  )
}

export default SectionCard