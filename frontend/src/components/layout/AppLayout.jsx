import Header from './Header'
import Sidebar from './Sidebar'

function AppLayout({ children }) {
  return (
    <div className="app-layout">
      <Sidebar />

      <div className="app-content">
        <Header />

        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  )
}

export default AppLayout