
import { useEffect, useState } from 'react'
import Applications from './Applications'
import './App.css'

function App() {
  const [page, setPage] = useState('Dashboard')
  const [dashboard, setDashboard] = useState(null)
  const [dashboardError, setDashboardError] = useState('')

  const pages = ['Dashboard', 'Applications', 'Resume Match']

  useEffect(() => {
    const controller = new AbortController()

    async function loadDashboard() {
      try {
        const response = await fetch(
          'http://127.0.0.1:8001/dashboard',
          { signal: controller.signal }
        )

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const data = await response.json()
        setDashboard(data)
        setDashboardError('')
      } catch (error) {
        if (error.name !== 'AbortError') {
          setDashboardError('Unable to load dashboard data.')
        }
      }
    }

    loadDashboard()

    return () => controller.abort()
  }, [page])

  return (
    <div className="app">
      <aside className="sidebar">
        <h1>CareerPilot</h1>
        <p>Your career journey, organized.</p>

        <nav>
          {pages.map((item) => (
            <button
              key={item}
              className={page === item ? 'active' : ''}
              onClick={() => setPage(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        <header>
          <h2>{page}</h2>
          <p>Take control of your next career move.</p>
        </header>

        <section className="content-card">
          {page === 'Dashboard' ? (
            <>
              <h3>Application Overview</h3>

              {dashboardError ? (
                <p role="alert">{dashboardError}</p>
              ) : dashboard === null ? (
                <p>Loading dashboard...</p>
              ) : (
                <>
                  <h2>Total Applications: {dashboard.total}</h2>

                  <div className="dashboard-stats">
                    {Object.entries(dashboard.by_status).map(
                      ([status, count]) => (
                        <div key={status} className="stat-card">
                          <h3>{status}</h3>
                          <p>{count}</p>
                        </div>
                      )
                    )}
                  </div>

                  <h3>Upcoming Interviews</h3>
                  <p>
                    {dashboard.upcoming_interviews.length === 0
                      ? 'No upcoming interviews.'
                      : `${dashboard.upcoming_interviews.length} upcoming interviews`}
                  </p>

                  <h3>Recent Applications</h3>
                  <p>
                    {dashboard.recent_applications.length === 0
                      ? 'No applications yet.'
                      : `${dashboard.recent_applications.length} recent applications`}
                  </p>
                </>
              )}
            </>
          ) : page === 'Applications' ? (
            <Applications />
          ) : (
            <>
              <h3>Resume Match</h3>
              <p>Compare your resume against a job description here.</p>
            </>
          )}
        </section>
      </main>
    </div>
  )
}

export default App
