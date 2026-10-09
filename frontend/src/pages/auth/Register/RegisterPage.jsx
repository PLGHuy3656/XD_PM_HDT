import { Link, useNavigate } from 'react-router-dom'
import '../Login/LoginPage.css'
import './RegisterPage.css'

function RegisterPage() {
  const navigate = useNavigate()

  const handleSubmit = (event) => {
    event.preventDefault()

    navigate('/login')
  }

  return (
    <main className="register-page">
      <div className="register-background" />

      <div className="register-side register-side-left" />
      <div className="register-side register-side-right" />

      <section className="register-panel">
        <div className="register-container">
          <img
            className="register-logo"
            src="/NestMate Swiftlet Flight Logo.png"
            alt="NestMate"
          />

          <div className="register-heading">
            <h1>Tạo tài khoản</h1>
          </div>

          <form
            className="register-form"
            onSubmit={handleSubmit}
          >
            <div className="register-field">
              <label htmlFor="fullName">Họ và tên</label>

              <input
                id="fullName"
                name="fullName"
                type="text"
                placeholder="Họ và tên"
                autoComplete="name"
                required
              />
            </div>

            <div className="register-field">
              <label htmlFor="email">Email</label>

              <input
                id="email"
                name="email"
                type="email"
                placeholder="Email"
                autoComplete="email"
                required
              />
            </div>

            <div className="register-field">
              <label htmlFor="phone">Số điện thoại</label>

              <input
                id="phone"
                name="phone"
                type="tel"
                placeholder="Số điện thoại"
                autoComplete="tel"
              />
            </div>

            <div className="register-password-grid">
              <div className="register-field">
                <label htmlFor="password">Mật khẩu</label>

                <input
                  id="password"
                  name="password"
                  type="password"
                  placeholder="Mật khẩu"
                  autoComplete="new-password"
                  required
                />
              </div>

              <div className="register-field">
                <label htmlFor="confirmPassword">
                  Xác nhận mật khẩu
                </label>

                <input
                  id="confirmPassword"
                  name="confirmPassword"
                  type="password"
                  placeholder="Xác nhận mật khẩu"
                  autoComplete="new-password"
                  required
                />
              </div>
            </div>

            <button
              type="submit"
              className="register-submit"
            >
              Đăng ký
              <span>→</span>
            </button>
          </form>

          <p className="register-switch">
            Đã có tài khoản?
            <Link to="/login">Đăng nhập ngay</Link>
          </p>
        </div>
      </section>
    </main>
  )
}

export default RegisterPage