import { vi } from 'vitest'
import { API_URL } from '../services/api'

// Installs a fetch mock that answers "METHOD /path" keys from `routes`.
// A route value is either response data (200), a function of the request
// options returning data, or { status: <number>, body }.
// Unknown requests fail the test with a 599 so they never pass silently.
export function mockFetch(routes) {
  const fetchMock = vi.fn(async (url, options = {}) => {
    const method = options.method ?? 'GET'
    const path = url.startsWith(API_URL) ? url.slice(API_URL.length) : url
    const key = `${method} ${path}`

    if (!(key in routes)) {
      return new Response(null, { status: 599 })
    }

    const route = routes[key]
    const { status = 200, body = route } =
      route && typeof route === 'object' && typeof route.status === 'number'
        ? route
        : {}

    if (status === 204) return new Response(null, { status })

    const data = typeof body === 'function' ? body(options) : body
    return new Response(JSON.stringify(data), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  })

  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// Parsed JSON body of the first call matching METHOD and path.
export function requestBody(fetchMock, method, path) {
  const call = fetchMock.mock.calls.find(
    ([url, options = {}]) =>
      (options.method ?? 'GET') === method && url === `${API_URL}${path}`
  )
  return call ? JSON.parse(call[1].body) : undefined
}

export function makeApplication(overrides = {}) {
  return {
    id: 1,
    company_name: 'Acme Corp',
    job_title: 'Frontend Engineer',
    job_description: null,
    application_date: '2026-10-01',
    status: 'Applied',
    job_url: null,
    notes: null,
    interview_at: null,
    interview_notes: null,
    created_at: '2026-10-01T09:00:00Z',
    updated_at: '2026-10-01T09:00:00Z',
    ...overrides,
  }
}
