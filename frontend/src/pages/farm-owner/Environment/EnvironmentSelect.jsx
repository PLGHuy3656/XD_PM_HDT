import { useEffect, useRef, useState } from 'react'

function ChevronIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m7 10 5 5 5-5" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m6 12 4 4 8-9" />
    </svg>
  )
}

function EnvironmentSelect({
  label,
  value,
  options,
  onChange,
  disabled = false,
}) {
  const [isOpen, setIsOpen] = useState(false)
  const selectRef = useRef(null)

  const selectedOption =
    options.find((option) => option.value === value) || options[0]

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (
        selectRef.current &&
        !selectRef.current.contains(event.target)
      ) {
        setIsOpen(false)
      }
    }

    const handleEscape = (event) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleOutsideClick)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleOutsideClick)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [])

  const handleSelect = (option) => {
    if (option.value === value) {
      setIsOpen(false)
      return
    }

    onChange(option.value)
    setIsOpen(false)
  }

  return (
    <div
      ref={selectRef}
      className={`environment-control-select ${
        isOpen ? 'open' : ''
      }`}
    >
      <span className="environment-control-select-label">
        {label}
      </span>

      <button
        type="button"
        className="environment-control-select-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        onClick={() => {
          if (!disabled) {
            setIsOpen((previous) => !previous)
          }
        }}
      >
        <span className="environment-control-select-value">
          {selectedOption?.label || 'Chưa có dữ liệu'}
        </span>

        <span className="environment-control-select-chevron">
          <ChevronIcon />
        </span>
      </button>

      {isOpen && !disabled && (
        <div
          className="environment-control-select-menu"
          role="listbox"
          aria-label={label}
        >
          {options.map((option) => {
            const isSelected = option.value === value

            return (
              <button
                type="button"
                role="option"
                aria-selected={isSelected}
                key={option.value}
                className={`environment-control-select-option ${
                  isSelected ? 'selected' : ''
                }`}
                onClick={() => handleSelect(option)}
              >
                <span>{option.label}</span>

                {isSelected && (
                  <span className="environment-control-select-check">
                    <CheckIcon />
                  </span>
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default EnvironmentSelect