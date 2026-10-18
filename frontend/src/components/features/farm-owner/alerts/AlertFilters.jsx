function FilterGroup({
  options,
  value,
  onChange,
  ariaLabel,
}) {
  return (
    <div
      className="alert-filter-group"
      role="group"
      aria-label={ariaLabel}
    >
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={
            value === option.value ? 'active' : ''
          }
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}

function AlertFilters({
  status,
  severity,
  statusOptions,
  severityOptions,
  onStatusChange,
  onSeverityChange,
}) {
  return (
    <section className="alert-filters">
      <FilterGroup
        options={statusOptions}
        value={status}
        onChange={onStatusChange}
        ariaLabel="Lọc theo trạng thái"
      />

      <span className="alert-filter-divider" />

      <FilterGroup
        options={severityOptions}
        value={severity}
        onChange={onSeverityChange}
        ariaLabel="Lọc theo mức độ"
      />
    </section>
  )
}

export default AlertFilters