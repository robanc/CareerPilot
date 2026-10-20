
import { useEffect, useState } from 'react'
import Applications from './Applications'
import ResumeMatch from './ResumeMatch'
import { getConfig, getDashboard } from './services/api'
import './App.css'

function App() {
  const [page, setPage] = useState('Dashboard')
  const [dashboard, setDashboard] = useState(null)
  const [dashboardError, setDashboardError] = useState('')
  const [focusApplicationId, setFocusApplicationId] = useState(null)
  const [config, setConfig] = useState(null)
  const [configError, setConfigError] = useState(false)

  // Write actions stay hidden until the server confirms it is writable.
  // This is presentation only; the backend enforces read-only mode.
  const readOnly = config === null || config.read_only

  useEffect(() => {
    const controller = new AbortController()

    async function loadConfig() {
      try {
        setConfig(await getConfig({ signal: controller.signal }))
      } catch (error) {
        if (error.name !== 'AbortError') setConfigError(true)
      }
    }

    loadConfig()
    return () => controller.abort()
  }, [])

  const pages = ['Dashboard', 'Applications', 'Resume Match']

  function openPage(item) {
    setFocusApplicationId(null)
    setPage(item)
  }

  function openApplication(id) {
    setFocusApplicationId(id)
    setPage('Applications')
  }

  useEffect(() => {
    const controller = new AbortController()

    async function loadDashboard() {
      try {
        const data = await getDashboard({ signal: controller.signal })
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
              onClick={() => openPage(item)}
            >
              {item}
            </button>
          ))}
        </nav>
      </aside>

      <main className="main-content">
        {config?.read_only && (
          <div className="demo-banner" role="note">
            <strong>Public demo: read-only.</strong> All applications shown
            here are fictional. Creating, editing, and deleting applications
            is disabled. Resume matching works, and the text you paste is not
            stored.
          </div>
        )}
        {configError && (
          <div className="demo-banner" role="note">
            Editing is unavailable because the server mode could not be
            confirmed. Reload the page to try again.
          </div>
        )}

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

{dashboard.upcoming_interviews.length === 0 ? (
  <p>No upcoming interviews.</p>
) : (
  <div className="applications-list">
    {dashboard.upcoming_interviews.map((application) => (
      <div className="application-item" key={application.id}>
        <h4>{application.job_title}</h4>
        <p>{application.company_name}</p>
        <p>
          Interview Date:{' '}
          {new Date(application.interview_at).toLocaleString()}
        </p>
        <p>Status: {application.status}</p>
        <button
          type="button"
          className="link-button"
          onClick={() => openApplication(application.id)}
        >
          View Application
        </button>
      </div>
    ))}
  </div>
)}


                  
<h3>Recent Applications</h3>

{dashboard.recent_applications.length === 0 ? (
  <p>No applications yet.</p>
) : (
  <div className="applications-list">
    {dashboard.recent_applications.map((application) => (
      <div className="application-item" key={application.id}>
        <h4>{application.job_title}</h4>
        <p>{application.company_name}</p>
        <p>Status: {application.status}</p>
        <p>Applied: {application.application_date}</p>
        <button
          type="button"
          className="link-button"
          onClick={() => openApplication(application.id)}
        >
          View Application
        </button>
      </div>
    ))}
  </div>
)}

                </>
              )}
            </>
          ) : page === 'Applications' ? (
  <Applications
    focusApplicationId={focusApplicationId}
    readOnly={readOnly}
  />
) : (
  <ResumeMatch />
)}
        </section>
      </main>
    </div>
  )
}

export default App
