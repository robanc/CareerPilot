import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { makeApplication, mockFetch } from './test/mockFetch'

const LOCAL_CONFIG = { mode: 'local', read_only: false }
const DEMO_CONFIG = { mode: 'public_demo', read_only: true }

const EMPTY_DASHBOARD = {
  total: 1,
  by_status: { Saved: 0, Applied: 1, Interview: 0, Offer: 0, Rejected: 0 },
  upcoming_interviews: [],
  recent_applications: [makeApplication({ id: 8 })],
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('App dashboard navigation', () => {
  it('opens the selected application record from the dashboard', async () => {
    const interview = makeApplication({
      id: 4,
      job_title: 'Platform Engineer',
      status: 'Interview',
      interview_at: '2099-01-15T10:00:00Z',
    })
    const recent = makeApplication({ id: 8, job_title: 'Data Analyst' })
    mockFetch({
      'GET /dashboard': {
        total: 2,
        by_status: { Saved: 0, Applied: 1, Interview: 1, Offer: 0, Rejected: 0 },
        upcoming_interviews: [interview],
        recent_applications: [recent],
      },
      'GET /applications': [interview, recent],
      'GET /config': LOCAL_CONFIG,
    })
    const { container } = render(<App />)

    const buttons = await screen.findAllByRole('button', {
      name: 'View Application',
    })
    expect(buttons).toHaveLength(2)

    fireEvent.click(buttons[1])

    expect(
      await screen.findByRole('heading', { name: 'Job Applications' })
    ).toBeTruthy()
    await screen.findByText('Data Analyst')
    const focused = container.querySelector('.application-item.focused')
    expect(focused.id).toBe('application-8')
  })

  it('clears the highlight when Applications is opened from the sidebar', async () => {
    mockFetch({
      'GET /dashboard': {
        total: 1,
        by_status: { Saved: 0, Applied: 1, Interview: 0, Offer: 0, Rejected: 0 },
        upcoming_interviews: [],
        recent_applications: [makeApplication({ id: 8 })],
      },
      'GET /applications': [makeApplication({ id: 8 })],
      'GET /config': LOCAL_CONFIG,
    })
    const { container } = render(<App />)

    fireEvent.click(
      await screen.findByRole('button', { name: 'View Application' })
    )
    await screen.findByText('Status: Applied')
    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    fireEvent.click(screen.getByRole('button', { name: 'Applications' }))

    await screen.findByText('Status: Applied')
    expect(container.querySelector('.application-item.focused')).toBeNull()
  })
})

describe('App public demo awareness', () => {
  async function openApplications() {
    fireEvent.click(
      await screen.findByRole('button', { name: 'View Application' })
    )
    await screen.findByText('Status: Applied')
  }

  it('shows the read-only banner and hides write actions in the demo', async () => {
    mockFetch({
      'GET /dashboard': EMPTY_DASHBOARD,
      'GET /applications': [makeApplication({ id: 8 })],
      'GET /config': DEMO_CONFIG,
    })
    render(<App />)

    const banner = await screen.findByRole('note')
    expect(banner.textContent).toMatch(/Public demo: read-only/)
    expect(banner.textContent).toMatch(/fictional/)

    await openApplications()
    expect(screen.queryByRole('button', { name: 'Add Application' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
    expect(screen.getByText(/This public demo is read-only/)).toBeTruthy()
  })

  it('keeps write actions in local mode, without a banner', async () => {
    mockFetch({
      'GET /dashboard': EMPTY_DASHBOARD,
      'GET /applications': [makeApplication({ id: 8 })],
      'GET /config': LOCAL_CONFIG,
    })
    render(<App />)

    await openApplications()
    expect(
      await screen.findByRole('button', { name: 'Add Application' })
    ).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Edit' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeTruthy()
    expect(screen.queryByRole('note')).toBeNull()
  })

  it('hides write actions when the mode cannot be confirmed', async () => {
    mockFetch({
      'GET /dashboard': EMPTY_DASHBOARD,
      'GET /applications': [makeApplication({ id: 8 })],
      'GET /config': { status: 500, body: {} },
    })
    render(<App />)

    expect((await screen.findByRole('note')).textContent).toMatch(
      /server mode could not be confirmed/
    )
    await openApplications()
    expect(screen.queryByRole('button', { name: 'Add Application' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
  })
})
