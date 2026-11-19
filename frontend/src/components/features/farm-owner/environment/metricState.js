export function getMetricState(metric) {
  if (!metric || metric.value == null || metric.hasData === false || Number.isNaN(Number(metric.value))) {
    return {
      label: 'Chưa có dữ liệu',
      shortLabel: 'Chưa có dữ liệu',
      className: 'offline',
    }
  }

  const normal =
    metric.value >= metric.safeMin &&
    metric.value <= metric.safeMax

  return normal
    ? {
        label: 'Bình thường',
        shortLabel: 'Ổn định',
        className: 'normal',
      }
    : {
        label:
          metric.value < metric.safeMin
            ? 'Dưới ngưỡng'
            : 'Vượt ngưỡng',
        shortLabel: 'Chú ý',
        className: 'warning',
      }
}
