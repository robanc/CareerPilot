import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  API_URL,
  createApplication,
  deleteApplication,
  getConfig,
  getDashboard,
  listApplications,
  matchResume,
  updateApplication,
} from './api'
import { mockFetch } from '../test/mockFetch'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api', () => {
  it('sends GET requests without a body and passes the abort signal', async () => {
    const fetchMock = mockFetch({ 'GET /applications': [] })
    const controller = new AbortController()

    await expect(
      listApplications({ signal: controller.signal })
    ).resolves.toEqual([])

    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe(`${API_URL}/applications`)
    expect(options.method).toBe('GET')
    expect(options.signal).toBe(controller.signal)
    expect(options.body).toBeUndefined()
  })

  it('sends JSON bodies for POST and PATCH', async () => {
    const fetchMock = mockFetch({
      'POST /applications': { status: 201, body: { id: 7 } },
      'PATCH /applications/7': { id: 7, status: 'Offer' },
    })

    await createApplication({ company_name: 'Acme' })
    await updateApplication(7, { status: 'Offer' })

    for (const [, options] of fetchMock.mock.calls) {
      expect(options.headers).toEqual({ 'Content-Type': 'application/json' })
    }
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      company_name: 'Acme',
    })
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      status: 'Offer',
    })
  })

  it('returns null for 204 responses', async () => {
    mockFetch({ 'DELETE /applications/3': { status: 204 } })
    await expect(deleteApplication(3)).resolves.toBeNull()
  })

  it('maps resume match arguments to the API field names', async () => {
    const fetchMock = mockFetch({ 'POST /resume/match': { score: 50 } })

    await matchResume('python sql', 'python react')

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      resume_text: 'python sql',
      job_description: 'python react',
    })
  })

  it('throws on non-2xx responses', async () => {
    mockFetch({ 'GET /dashboard': { status: 500, body: {} } })
    await expect(getDashboard()).rejects.toThrow('HTTP 500')
  })

  it('exposes the HTTP status on errors', async () => {
    mockFetch({ 'GET /config': { status: 429, body: {} } })
    await expect(getConfig()).rejects.toMatchObject({ status: 429 })
  })
})
