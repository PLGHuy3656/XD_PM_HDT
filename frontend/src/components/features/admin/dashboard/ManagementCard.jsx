function ArrowIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

function ManagementCard({ item, onOpen }) {
  return (
    <button
      type="button"
      className="admin-management-card"
      onClick={() => onOpen(item.path)}
    >
      <div className="admin-management-card__top">
        <span className="admin-management-card__icon">
          {item.icon}
        </span>

        <span className="admin-management-card__arrow">
          <ArrowIcon />
        </span>
      </div>

      <span className="admin-management-card__eyebrow">
        {item.eyebrow}
      </span>

      <h3>{item.title}</h3>

      <div className="admin-management-card__stats">
        <strong>{item.value}</strong>
        <span>{item.description}</span>
      </div>
    </button>
  )
}

export default ManagementCard
