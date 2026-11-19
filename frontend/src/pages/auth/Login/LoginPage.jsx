import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../../../context/AuthContext'
import PasswordInput from '../../../components/ui/PasswordInput'
import './LoginPage.css'

function LoginPage() {
  const navigate = useNavigate()
  const { login, authError } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (event) => {
    event.preventDefault()

    try {
      setLoading(true)
      const result = await login(email, password)

      if (!result.success) {
        setError(result.message)
        setLoading(false)
        return
      }

      setError('')

      switch (result.user.role) {
        case 'FARM_OWNER':
          navigate('/owner/dashboard')
          break

        case 'TECHNICIAN':
          navigate('/technician/dashboard')
          break

        case 'ADMIN':
          navigate('/admin/dashboard')
          break

        default:
          navigate('/login')
      }
    } catch (err) {
      setError(err?.message || 'Đăng nhập không thành công.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      {/* LEFT SIDE */}
      <section className="login-visual">
        <img
          src="/NestMate Swiftlet Flight Logo.png"
          alt="NestMate"
          className="login-visual-logo"
        />

        <div className="login-visual-content">
          <span className="login-eyebrow">
            NESTMATE SMART CARE
          </span>

          <h2>
            Môi trường ổn định.
            <br />
            <span>Nhà yến an tâm.</span>
          </h2>

          <p>
            Nền tảng quản trị nhà yến thông minh: theo dõi vi khí hậu, quản lý
            nhà yến, khu vực và thiết bị tập trung cho Chủ trại, Kỹ thuật viên
            và Quản trị hệ thống.
          </p>
        </div>

        <div className="login-curve" />
      </section>

      {/* RIGHT SIDE */}
      <section className="login-panel">
        <div className="login-container">
          <img
            src="/NestMate Swiftlet Flight Logo.png"
            alt="NestMate"
            className="login-form-logo"
          />

          <div className="login-heading">
            <h1>Đăng nhập</h1>
          </div>

          <form
            className="login-form"
            onSubmit={handleSubmit}
          >
            <div className="login-field">
              <label htmlFor="email">Email</label>

              <input
                id="email"
                type="email"
                placeholder="Email"
                autoComplete="email"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value)
                  setError('')
                }}
                required
              />
            </div>

            <div className="login-field">
              <label htmlFor="password">
                Mật khẩu
              </label>

              <PasswordInput
                id="password"
                placeholder="Mật khẩu"
                autoComplete="current-password"
                value={password}
                onChange={(event) => {
                  setPassword(event.target.value)
                  setError('')
                }}
                required
              />
            </div>

            <div className="login-options">
              <label className="remember-option">
                <input type="checkbox" />
                <span>Ghi nhớ đăng nhập</span>
              </label>

              <button
                type="button"
                className="forgot-password"
              >
                Quên mật khẩu?
              </button>
            </div>

              {(error || authError) && (
                <div className="login-alert" role="alert">
                  <span className="login-alert-icon">!</span>

                  <span>{error || authError}</span>
                </div>
              )}
              
            <button
              type="submit"
              className="login-submit"
              disabled={loading}
            >
              {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
              <span>→</span>
            </button>
          </form>

          <p className="login-switch">
            Chưa có tài khoản?
            <Link to="/register">
              Đăng ký ngay
            </Link>
          </p>
        </div>
      </section>
    </div>
  )
}

export default LoginPage