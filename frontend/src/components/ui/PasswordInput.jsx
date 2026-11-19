import { useState } from 'react'
import './PasswordInput.css'

function EyeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7Z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

function EyeOffIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
      <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c6.5 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
      <path d="M6.61 6.61A13.53 13.53 0 0 0 2 12s3.5 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
      <line x1="2" y1="2" x2="22" y2="22" />
    </svg>
  )
}

function PasswordInput({
  id,
  value,
  onChange,
  placeholder = 'Mật khẩu',
  autoComplete = 'current-password',
  required = false,
  disabled = false,
  className = '',
  ...rest
}) {
  const [visible, setVisible] = useState(false)

  return (
    <div className={`password-input-wrap ${className}`.trim()}>
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        placeholder={placeholder}
        autoComplete={autoComplete}
        value={value}
        onChange={onChange}
        required={required}
        disabled={disabled}
        {...rest}
      />

      <button
        type="button"
        className="password-input-toggle"
        onClick={() => setVisible((prev) => !prev)}
        aria-label={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
        aria-pressed={visible}
        title={visible ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
        disabled={disabled}
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  )
}

export default PasswordInput
