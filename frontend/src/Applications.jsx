
import { useEffect, useState } from 'react'
import {
  createApplication,
  deleteApplication,
  listApplications,
  updateApplication,
} from './services/api'

const STATUSES = ['Saved', 'Applied', 'Interview', 'Offer', 'Rejected']

const OPTIONAL_TEXT_FIELDS = [
  'job_description',
  'job_url',
  'notes',
  'interview_notes',
]

function emptyForm() {
  return {
    company_name: '',
    job_title: '',
    application_date: new Date().toLocaleDateString('en-CA'),
    status: 'Saved',
    job_description: '',
    job_url: '',
    notes: '',
    interview_at: '',
    interview_notes: '',
  }
}

// ISO timestamp -> value for a datetime-local input, in local time.
function toLocalInput(isoValue) {
  if (!isoValue) return ''
  const date = new Date(isoValue)
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60000)
  return localDate.toISOString().slice(0, 16)
}

// Form values -> API body. Blank optional fields are sent as null, which
// the API treats as "no value" (and, on PATCH, clears the stored value).
function toPayload(values) {
  const payload = {
    company_name: values.company_name,
    job_title: values.job_title,
    application_date: values.application_date,
    status: values.status,
    interview_at: values.interview_at
      ? new Date(values.interview_at).toISOString()
      : null,
  }

  for (const field of OPTIONAL_TEXT_FIELDS) {
    const value = values[field].trim()
    payload[field] = value === '' ? null : value
  }

  return payload
}

function toFormValues(application) {
  return {
    company_name: application.company_name,
    job_title: application.job_title,
    application_date: application.application_date,
    status: application.status,
    job_description: application.job_description ?? '',
    job_url: application.job_url ?? '',
    notes: application.notes ?? '',
    interview_at: toLocalInput(application.interview_at),
    interview_notes: application.interview_notes ?? '',
  }
}

// Only http(s) links are rendered as anchors.
function isWebUrl(value) {
  return typeof value === 'string' && /^https?:\/\//i.test(value)
}

function ApplicationFields({ values, onChange }) {
  function update(field) {
    return (event) => onChange({ ...values, [field]: event.target.value })
  }

  return (
    <>
      <label>
        Company Name
        <input
          required
          maxLength={200}
          value={values.company_name}
          onChange={update('company_name')}
          placeholder="e.g. Microsoft"
        />
      </label>

      <label>
        Job Title
        <input
          required
          maxLength={200}
          value={values.job_title}
          onChange={update('job_title')}
          placeholder="e.g. Software Engineer"
        />
      </label>

      <label>
        Application Date
        <input
          required
          type="date"
          value={values.application_date}
          onChange={update('application_date')}
        />
      </label>

      <label>
        Status
        <select value={values.status} onChange={update('status')}>
          {STATUSES.map((status) => (
            <option key={status} value={status}>{status}</option>
          ))}
        </select>
      </label>

      <label>
        Job Posting URL
        <input
          type="url"
          pattern="https?://.+"
          title="An http:// or https:// address"
          value={values.job_url}
          onChange={update('job_url')}
          placeholder="https://..."
        />
      </label>

      <label>
        Interview Date and Time
        <input
          type="datetime-local"
          value={values.interview_at}
          onChange={update('interview_at')}
        />
      </label>

      <label className="form-wide">
        Job Description
        <textarea
          rows={4}
          value={values.job_description}
          onChange={update('job_description')}
          placeholder="Paste the job description (optional)"
        />
      </label>

      <label className="form-wide">
        Notes
        <textarea
          rows={3}
          value={values.notes}
          onChange={update('notes')}
          placeholder="Anything worth remembering (optional)"
        />
      </label>

      <label className="form-wide">
        Interview Preparation Notes
        <textarea
          rows={3}
          value={values.interview_notes}
          onChange={update('interview_notes')}
          placeholder="Topics, questions, interviewers (optional)"
        />
      </label>
    </>
  )
}

// readOnly hides write actions (public demo). Presentation only: the
// backend refuses writes on its own.
function Applications({ focusApplicationId = null, readOnly = false }) {
  const [applications, setApplications] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [saving, setSaving] = useState(false)
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState(emptyForm)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('All')
  const [form, setForm] = useState(emptyForm)

  useEffect(() => {
    const controller = new AbortController()

    async function loadApplications() {
      try {
        setApplications(
          await listApplications({ signal: controller.signal })
        )
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

  const focusMissing =
    focusApplicationId !== null &&
    !loading &&
    !applications.some((item) => item.id === focusApplicationId)

  // Opened from the dashboard: bring the selected record into view.
  useEffect(() => {
    if (focusApplicationId === null || loading) return
    const element = document.getElementById(
      `application-${focusApplicationId}`
    )
    element?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  }, [focusApplicationId, loading])

  async function handleDelete(application) {
    const confirmed = window.confirm(
      `Are you sure you want to delete ${application.job_title} at ${application.company_name}?`
    )

    if (!confirmed) return

    setError('')
    setMessage('')

    try {
      await deleteApplication(application.id)

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

  function startEditing(application) {
    setEditingId(application.id)
    setEditForm(toFormValues(application))
  }

  async function handleSaveChanges(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setMessage('')

    try {
      const updated = await updateApplication(editingId, toPayload(editForm))

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
      const created = await createApplication(toPayload(form))
      setApplications((current) => [created, ...current])
      setMessage('Application saved successfully!')
      setForm((current) => ({
        ...emptyForm(),
        application_date: current.application_date,
        status: current.status,
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
      {readOnly ? (
        <p className="read-only-note">
          This public demo is read-only: you can browse, search, and filter
          the fictional applications below, but not add, edit, or delete them.
        </p>
      ) : (
        <>
          <h3>Add Job Application</h3>

          <form className="application-form" onSubmit={handleSubmit}>
            <ApplicationFields values={form} onChange={setForm} />

            <button type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Add Application'}
            </button>
          </form>
        </>
      )}

      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
      {focusMissing && (
        <p role="alert">The selected application is no longer available.</p>
      )}

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
            {['All', ...STATUSES].map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
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
            <div
              className={
                application.id === focusApplicationId
                  ? 'application-item focused'
                  : 'application-item'
              }
              id={`application-${application.id}`}
              key={application.id}
            >
              <h4>{application.job_title}</h4>
              <p>{application.company_name}</p>
              <p>Status: {application.status}</p>
              <p>Applied: {application.application_date}</p>
              {application.job_url && (
                <p>
                  Job Posting:{' '}
                  {isWebUrl(application.job_url) ? (
                    <a
                      href={application.job_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {application.job_url}
                    </a>
                  ) : (
                    application.job_url
                  )}
                </p>
              )}
              {application.interview_at && (
                <p>
                  Interview:{' '}
                  {new Date(application.interview_at).toLocaleString()}
                </p>
              )}
              {application.interview_notes && (
                <p className="multiline">
                  Interview Notes: {application.interview_notes}
                </p>
              )}
              {application.notes && (
                <p className="multiline">Notes: {application.notes}</p>
              )}
              {application.job_description && (
                <details>
                  <summary>Job Description</summary>
                  <p className="multiline">{application.job_description}</p>
                </details>
              )}

              {!readOnly && (
                <>
                  <button
                    type="button"
                    onClick={() => startEditing(application)}
                  >
                    Edit
                  </button>

                  <button
                    type="button"
                    onClick={() => handleDelete(application)}
                  >
                    Delete
                  </button>
                </>
              )}

              {!readOnly && editingId === application.id && (
                <form
                  className="application-form edit-form"
                  onSubmit={handleSaveChanges}
                >
                  <ApplicationFields
                    values={editForm}
                    onChange={setEditForm}
                  />

                  <div className="form-actions">
                    <button type="submit" disabled={saving}>
                      {saving ? 'Saving...' : 'Save Changes'}
                    </button>

                    <button type="button" onClick={() => setEditingId(null)}>
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default Applications
