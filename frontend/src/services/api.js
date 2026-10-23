// Centralized client for the CareerPilot backend (see openapi.yaml).
// Every request goes through request(), which throws on a non-2xx response
// (with the HTTP status on error.status) and lets AbortError propagate so
// callers can ignore cancelled requests.

export const API_URL = import.meta.env.VITE_API_URL ?? '/api'

async function request(path, { method = 'GET', body, signal } = {}) {
  const options = { method, signal }

  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(body)
  }

  const response = await fetch(`${API_URL}${path}`, options)

  if (!response.ok) {
    const error = new Error(`HTTP ${response.status}`)
    error.status = response.status
    throw error
  }

  return response.status === 204 ? null : response.json()
}

export function listApplications({ signal } = {}) {
  return request('/applications', { signal })
}

export function createApplication(application) {
  return request('/applications', { method: 'POST', body: application })
}

export function updateApplication(id, changes) {
  return request(`/applications/${id}`, { method: 'PATCH', body: changes })
}

export function deleteApplication(id) {
  return request(`/applications/${id}`, { method: 'DELETE' })
}

// Operating mode, so the UI can hide write actions in the public demo.
// Informational only: the backend enforces read-only mode itself.
export function getConfig({ signal } = {}) {
  return request('/config', { signal })
}

export function getDashboard({ signal } = {}) {
  return request('/dashboard', { signal })
}

export function matchResume(resumeText, jobDescription) {
  return request('/resume/match', {
    method: 'POST',
    body: { resume_text: resumeText, job_description: jobDescription },
  })
}


export function listResumes({ signal } = {}) {
  return request('/resumes', { signal })
}

export function getResume(id, { signal } = {}) {
  return request(`/resumes/${id}`, { signal })
}

export function createResume(resume) {
  return request('/resumes', { method: 'POST', body: resume })
}

export function updateResume(id, changes) {
  return request(`/resumes/${id}`, { method: 'PATCH', body: changes })
}

export function deleteResume(id) {
  return request(`/resumes/${id}`, { method: 'DELETE' })
}
