function Toggle({
  checked,
  disabled,
  onChange,
  label,
}) {
  return (
    <button
      type="button"
      className={`control-toggle ${checked ? 'on' : ''}`}
      disabled={disabled}
      onClick={() => {
        if (!disabled) onChange(!checked)
      }}
      aria-pressed={checked}
      aria-label={label}
    >
      <span />
    </button>
  )
}

export default Toggle