import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Applications from './Applications'
import { makeApplication, mockFetch, requestBody } from './test/mockFetch'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function change(label, value, container = document.body) {
  fireEvent.change(within(container).getByLabelText(label), {
    target: { value },
  })
}

describe('Applications', () => {
  it('creates an application with the optional fields', async () => {
    const fetchMock = mockFetch({
      'GET /applications': [],
      'POST /applications': {
        status: 201,
        body: makeApplication({ id: 5, notes: 'Referral from Sam' }),
      },
    })
    render(<Applications />)
    await screen.findByText('No applications yet.')

    const form = screen
      .getByRole('button', { name: 'Add Application' })
      .closest('form')
    change('Company Name', 'Acme Corp', form)
    change('Job Title', 'Frontend Engineer', form)
    change('Application Date', '2026-10-01', form)
    change('Job Posting URL', 'https://example.com/jobs/1', form)
    change('Job Description', 'React and testing', form)
    change('Notes', '  Referral from Sam  ', form)
    fireEvent.submit(form)

    await screen.findByText('Application saved successfully!')
    expect(requestBody(fetchMock, 'POST', '/applications')).toEqual({
      company_name: 'Acme Corp',
      job_title: 'Frontend Engineer',
      application_date: '2026-10-01',
      status: 'Saved',
      job_description: 'React and testing',
      job_url: 'https://example.com/jobs/1',
      notes: 'Referral from Sam',
      interview_at: null,
      interview_notes: null,
    })
    expect(screen.getByText('Notes: Referral from Sam')).toBeTruthy()
  })

  it('shows interview notes and edits them, clearing blank fields', async () => {
    const existing = makeApplication({
      id: 3,
      status: 'Interview',
      notes: 'Old note',
      interview_at: '2026-11-02T15:30:00Z',
      interview_notes: 'Review system design',
    })
    const fetchMock = mockFetch({
      'GET /applications': [existing],
      'PATCH /applications/3': (options) => ({
        ...existing,
        ...JSON.parse(options.body),
      }),
    })
    render(<Applications />)

    expect(
      await screen.findByText('Interview Notes: Review system design')
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))
    const form = screen
      .getByRole('button', { name: 'Save Changes' })
      .closest('form')
    expect(
      within(form).getByLabelText('Interview Preparation Notes').value
    ).toBe('Review system design')

    change('Interview Preparation Notes', 'Practice STAR stories', form)
    change('Notes', '   ', form)
    fireEvent.submit(form)

    await screen.findByText('Application updated successfully!')
    const body = requestBody(fetchMock, 'PATCH', '/applications/3')
    expect(body.interview_notes).toBe('Practice STAR stories')
    expect(body.notes).toBeNull()
    expect(body.status).toBe('Interview')
    expect(body.interview_at).toBe(
      new Date(existing.interview_at).toISOString()
    )
    expect(
      screen.getByText('Interview Notes: Practice STAR stories')
    ).toBeTruthy()
  })

  it('renders only http(s) job URLs as links', async () => {
    mockFetch({
      'GET /applications': [
        makeApplication({ id: 1, job_url: 'https://example.com/a' }),
        makeApplication({ id: 2, job_url: 'javascript:alert(1)' }),
      ],
    })
    render(<Applications />)

    const link = await screen.findByRole('link', {
      name: 'https://example.com/a',
    })
    expect(link.getAttribute('rel')).toBe('noopener noreferrer')
    expect(screen.getAllByRole('link')).toHaveLength(1)
  })

  it('highlights the application opened from the dashboard', async () => {
    mockFetch({
      'GET /applications': [
        makeApplication({ id: 1 }),
        makeApplication({ id: 2, job_title: 'Data Analyst' }),
      ],
    })
    const { container } = render(<Applications focusApplicationId={2} />)

    await screen.findByText('Data Analyst')
    const focused = container.querySelectorAll('.application-item.focused')
    expect(focused).toHaveLength(1)
    expect(focused[0].id).toBe('application-2')
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('reports a dashboard target that no longer exists', async () => {
    mockFetch({ 'GET /applications': [makeApplication({ id: 1 })] })
    render(<Applications focusApplicationId={99} />)

    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toBe(
        'The selected application is no longer available.'
      )
    )
  })
})

describe('Applications read-only mode', () => {
  it('hides create, edit, and delete and explains why', async () => {
    const fetchMock = mockFetch({
      'GET /applications': [makeApplication({ id: 1 })],
    })
    render(<Applications readOnly />)

    await screen.findByText('Frontend Engineer')
    expect(screen.getByText(/This public demo is read-only/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Add Application' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
    // Browsing still works.
    expect(screen.getByLabelText('Search Applications')).toBeTruthy()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
