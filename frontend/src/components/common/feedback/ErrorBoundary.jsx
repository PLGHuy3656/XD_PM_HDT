import { Component } from 'react'
import './ErrorBoundary.css'

export class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    // Log component stack safely without leaking sensitive tokens
    console.error('ErrorBoundary caught an error:', error?.message, errorInfo?.componentStack)
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null })
    window.location.reload()
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="error-boundary-container" role="alert">
          <div className="error-boundary-card">
            <span className="error-boundary-icon">⚠️</span>
            <h2>Đã xảy ra sự cố hiển thị</h2>
            <p>
              Hệ thống gặp lỗi không mong muốn khi tải phần nội dung này.
              Vui lòng thử tải lại trang hoặc liên hệ quản trị viên nếu lỗi tiếp tục xuất hiện.
            </p>
            {this.state.error?.message && (
              <pre className="error-boundary-details">{this.state.error.message}</pre>
            )}
            <div className="error-boundary-actions">
              <button
                type="button"
                className="error-boundary-btn error-boundary-btn--primary"
                onClick={this.handleReload}
              >
                Tải lại trang
              </button>
              <button
                type="button"
                className="error-boundary-btn error-boundary-btn--secondary"
                onClick={this.handleReset}
              >
                Thử lại
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
