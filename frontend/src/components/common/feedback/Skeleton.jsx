import './Skeleton.css'

export function Skeleton({
  variant = 'text',
  width,
  height,
  className = '',
  style = {},
}) {
  const inlineStyles = {
    ...(width ? { width } : {}),
    ...(height ? { height } : {}),
    ...style,
  }

  return (
    <div
      className={`skeleton skeleton--${variant} ${className}`}
      style={inlineStyles}
      aria-hidden="true"
    />
  )
}

export function SkeletonCard({ lines = 3, className = '' }) {
  return (
    <div className={`skeleton-card ${className}`} aria-hidden="true">
      <Skeleton variant="heading" width="60%" />
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} variant="text" width={i === lines - 1 ? '40%' : '100%'} />
      ))}
    </div>
  )
}

export function TableSkeleton({ rows = 5, cols = 4, className = '' }) {
  return (
    <div className={`skeleton-table ${className}`} aria-hidden="true">
      <div className="skeleton-table-header">
        {Array.from({ length: cols }).map((_, j) => (
          <Skeleton key={j} variant="text" width="70%" height="20px" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-table-row">
          {Array.from({ length: cols }).map((_, j) => (
            <Skeleton key={j} variant="text" width={j === 0 ? '80%' : '50%'} height="16px" />
          ))}
        </div>
      ))}
    </div>
  )
}

export default Skeleton
