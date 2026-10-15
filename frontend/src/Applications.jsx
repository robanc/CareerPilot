
import { useEffect, useState } from 'react'

const API_URL = 'http://127.0.0.1:8001'

function Applications() {
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editStatus, setEditStatus] = useState('Saved')
  const [editInterviewAt, setEditInterviewAt] = useState('')
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')

  const [form, setForm] = useState({
    company_name: '',
    job_title: '',
    application_date: new Date().toLocaleDateString('en-CA'),
    status: 'Saved',
  })

  useEffect(() => {
    const controller = new AbortController()

    async function loadApplications() {
      try {
        const response = await fetch(`${API_URL}/applications`, {
          signal: controller.signal,
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        setApplications(await response.json())
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError('Unable to load applications.')
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }

    loadApplications()
    return () => controller.abort()
  }, [])


async function handleDelete(application) {
  const confirmed = window.confirm(
    `Are you sure you want to delete ${application.job_title} at ${application.company_name}?`
  )

  if (!confirmed) return

  setError('')
  setMessage('')

  try {
    const response = await fetch(
      `${API_URL}/applications/${application.id}`,
      { method: 'DELETE' }
    )

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    setApplications((current) =>
      current.filter((item) => item.id !== application.id)
    )

    if (editingId === application.id) {
      setEditingId(null)
    }

    setMessage('Application deleted successfully!')
  } catch {
    setError('Unable to delete application. Please try again.')
  }
}

  
async function handleSaveChanges() {
  setSaving(true)
  setError('')
  setMessage('')

  try {
    const response = await fetch(
      `${API_URL}/applications/${editingId}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
  status: editStatus,
  interview_at: editInterviewAt
    ? new Date(editInterviewAt).toISOString()
    : null,
}),
      }
    )

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const updated = await response.json()

    setApplications((current) =>
      current.map((application) =>
        application.id === updated.id ? updated : application
      )
    )

    setEditingId(null)
    setMessage('Application updated successfully!')
  } catch {
    setError('Unable to update application. Please try again.')
  } finally {
    setSaving(false)
  }
}

  async function handleSubmit(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')

    try {
      const response = await fetch(`${API_URL}/applications`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      const created = await response.json()
      setApplications((current) => [created, ...current])
      setMessage('Application saved successfully!')
      setForm((current) => ({
        ...current,
        company_name: '',
        job_title: '',
      }))
    } catch {
      setError('Unable to save application. Please try again.')
    } finally {
      setSaving(false)
    }
  }

   const filteredApplications = applications.filter((application) => {
    const search = searchTerm.trim().toLowerCase()

    const matchesSearch =
      application.company_name.toLowerCase().includes(search) ||
      application.job_title.toLowerCase().includes(search)

    const matchesStatus =
      statusFilter === 'All' || application.status === statusFilter

    return matchesSearch && matchesStatus
  })

  return (
    <div>
      <h3>Add Job Application</h3>

      <form className="application-form" onSubmit={handleSubmit}>
        <label>
          Company Name
          <input
            required
            maxLength={200}
            value={form.company_name}
            onChange={(e) =>
              setForm({ ...form, company_name: e.target.value })
            }
            placeholder="e.g. Microsoft"
          />
        </label>

        <label>
          Job Title
          <input
            required
            maxLength={200}
            value={form.job_title}
            onChange={(e) =>
              setForm({ ...form, job_title: e.target.value })
            }
            placeholder="e.g. Software Engineer"
          />
        </label>

        <label>
          Application Date
          <input
            required
            type="date"
            value={form.application_date}
            onChange={(e) =>
              setForm({ ...form, application_date: e.target.value })
            }
          />
        </label>

        <label>
          Status
          <select
            value={form.status}
            onChange={(e) =>
              setForm({ ...form, status: e.target.value })
            }
          >
            {['Saved', 'Applied', 'Interview', 'Offer', 'Rejected'].map(
              (status) => (
                <option key={status} value={status}>{status}</option>
              )
            )}
          </select>
        </label>

        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Add Application'}
        </button>
      </form>

      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}

      <h3>Job Applications</h3>
      <div className="application-filters">
  <label>
    Search Applications
    <input
      type="search"
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search company or job title..."
    />
  </label>

  <label>
    Filter by Status
    <select
      value={statusFilter}
      onChange={(e) => setStatusFilter(e.target.value)}
    >
      {['All', 'Saved', 'Applied', 'Interview', 'Offer', 'Rejected'].map(
        (status) => (
          <option key={status} value={status}>
            {status}
          </option>
        )
      )}
    </select>
  </label>
</div>

      {loading ? (
        <p>Loading applications...</p>
      ) : filteredApplications.length === 0 ? (
  <p>
    {applications.length === 0
      ? 'No applications yet.'
      : 'No applications match your search or filter.'}
  </p>
) : (
        <div className="applications-list">
          {filteredApplications.map((application) => (
            <div className="application-item" key={application.id}>
              <h4>{application.job_title}</h4>
              <p>{application.company_name}</p>
              <p>Status: {application.status}</p>
              
<button
  type="button"
  onClick={() => {
  setEditingId(application.id)
  setEditStatus(application.status)
  setEditInterviewAt(
  application.interview_at
    ? (() => {
        const date = new Date(application.interview_at)
        const localDate = new Date(
          date.getTime() - date.getTimezoneOffset() * 60000
        )
        return localDate.toISOString().slice(0, 16)
      })()
    : ''
)
}}
>
  Edit
</button>

<button
  type="button"
  onClick={() => handleDelete(application)}
>
  Delete
</button>



{editingId === application.id && (
  <div className="edit-form">
    <label>
      Change Status
      <select
        value={editStatus}
        onChange={(e) => setEditStatus(e.target.value)}
      >
        {['Saved', 'Applied', 'Interview', 'Offer', 'Rejected'].map(
          (status) => (
            <option key={status} value={status}>
              {status}
            </option>
          )
        )}
      </select>
    </label>

<label>
  Interview Date and Time
  <input
    type="datetime-local"
    value={editInterviewAt}
    onChange={(e) => setEditInterviewAt(e.target.value)}
  />
</label>

    <button
  type="button"
  onClick={handleSaveChanges}
  disabled={saving}
>
  {saving ? 'Saving...' : 'Save Changes'}
</button>

    <button
      type="button"
      onClick={() => setEditingId(null)}
    >
      Cancel
    </button>
  </div>
)}


            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Applications
