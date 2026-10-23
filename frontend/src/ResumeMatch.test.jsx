import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ResumeMatch, { MAX_INPUT_LENGTH } from './ResumeMatch'
import { makeApplication, mockFetch, requestBody } from './test/mockFetch'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ResumeMatch', () => {
  it('labels the result as a heuristic score', async () => {
    mockFetch({
      'POST /resume/match': {
        score: 72,
        matched_keywords: ['python'],
        missing_keywords: ['react'],
        suggestions: ['Mention React experience.'],
      },
    })
    render(<ResumeMatch />)

    fireEvent.change(screen.getByLabelText('Your Resume'), {
      target: { value: 'python developer' },
    })
    fireEvent.change(screen.getByLabelText('Job Description'), {
      target: { value: 'python react' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Match' }))

    expect(
      await screen.findByRole('heading', {
        name: 'Heuristic Match Score: 72%',
      })
    ).toBeTruthy()
    expect(screen.getByText(/not an assessment of your suitability/)).toBeTruthy()
    expect(
      screen
        .getByRole('progressbar', { name: 'Heuristic resume match score' })
        .getAttribute('aria-valuenow')
    ).toBe('72')
  })
})

describe('ResumeMatch limits', () => {
  function submit() {
    fireEvent.change(screen.getByLabelText('Your Resume'), {
      target: { value: 'python' },
    })
    fireEvent.change(screen.getByLabelText('Job Description'), {
      target: { value: 'python' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Match' }))
  }

  it('caps both inputs at the backend limit', () => {
    render(<ResumeMatch />)

    expect(MAX_INPUT_LENGTH).toBe(20000)
    for (const label of ['Your Resume', 'Job Description']) {
      expect(screen.getByLabelText(label).getAttribute('maxlength')).toBe(
        '20000'
      )
    }
  })

  it('explains a rate-limit response', async () => {
    mockFetch({ 'POST /resume/match': { status: 429, body: {} } })
    render(<ResumeMatch />)
    submit()

    expect((await screen.findByRole('alert')).textContent).toMatch(
      /Too many match requests/
    )
  })

  it('explains an oversized-input response', async () => {
    mockFetch({ 'POST /resume/match': { status: 413, body: {} } })
    render(<ResumeMatch />)
    submit()

    expect((await screen.findByRole('alert')).textContent).toMatch(
      /at most 20,000 characters/
    )
  })
})

describe('ResumeMatch saved applications', () => {
  const matchResult = {
    score: 50,
    matched_keywords: [],
    missing_keywords: [],
    suggestions: [],
  }

  it('lists only applications with a job description', async () => {
    mockFetch({
      'GET /applications': [
        makeApplication({ id: 1, job_description: 'React and TypeScript' }),
        makeApplication({
          id: 2,
          company_name: 'Globex',
          job_title: 'Data Analyst',
          job_description: '   ',
        }),
        makeApplication({ id: 3, company_name: 'Initech', job_description: null }),
      ],
    })
    render(<ResumeMatch />)

    const select = await screen.findByLabelText('Saved Job Application')
    const labels = Array.from(select.options).map((option) => option.textContent)
    expect(labels).toEqual([
      'Select a saved application...',
      'Acme Corp — Frontend Engineer',
    ])
  })

  it('copies the selected job description and still allows editing', async () => {
    const fetchMock = mockFetch({
      'GET /applications': [
        makeApplication({ id: 7, job_description: 'React and TypeScript' }),
      ],
      'POST /resume/match': matchResult,
    })
    render(<ResumeMatch />)

    fireEvent.change(await screen.findByLabelText('Saved Job Application'), {
      target: { value: '7' },
    })
    const jobDescription = screen.getByLabelText('Job Description')
    expect(jobDescription.value).toBe('React and TypeScript')

    fireEvent.change(jobDescription, {
      target: { value: 'React and TypeScript, plus GraphQL' },
    })
    fireEvent.change(screen.getByLabelText('Your Resume'), {
      target: { value: 'react developer' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Match' }))

    await screen.findByRole('heading', { name: 'Heuristic Match Score: 50%' })
    expect(requestBody(fetchMock, 'POST', '/resume/match')).toEqual({
      resume_text: 'react developer',
      job_description: 'React and TypeScript, plus GraphQL',
    })
  })

  it('allows manual entry when saved applications fail to load', async () => {
    const fetchMock = mockFetch({
      'GET /applications': { status: 500, body: {} },
      'POST /resume/match': matchResult,
    })
    render(<ResumeMatch />)

    expect(
      await screen.findByText(/Saved applications could not be loaded/)
    ).toBeTruthy()
    expect(screen.queryByLabelText('Saved Job Application')).toBeNull()

    fireEvent.change(screen.getByLabelText('Your Resume'), {
      target: { value: 'python developer' },
    })
    fireEvent.change(screen.getByLabelText('Job Description'), {
      target: { value: 'python' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Analyze Match' }))

    await screen.findByRole('heading', { name: 'Heuristic Match Score: 50%' })
    expect(screen.queryByRole('alert')).toBeNull()
    expect(requestBody(fetchMock, 'POST', '/resume/match')).toEqual({
      resume_text: 'python developer',
      job_description: 'python',
    })
  })

  it('aborts the application request on unmount', () => {
    const fetchMock = mockFetch({ 'GET /applications': [] })
    const { unmount } = render(<ResumeMatch />)

    const [, options] = fetchMock.mock.calls[0]
    expect(options.signal.aborted).toBe(false)
    unmount()
    expect(options.signal.aborted).toBe(true)
  })
})


describe('ResumeMatch saved resumes', () => {
  it('does not load saved resumes in read-only mode', () => {
    const fetchMock = mockFetch({
      'GET /applications': [],
    })

    render(<ResumeMatch readOnly={true} />)

    expect(screen.queryByLabelText('Saved Resume')).toBeNull()
    expect(
      fetchMock.mock.calls.some(([url]) => url.includes('/resumes'))
    ).toBe(false)
  })

  it('loads a saved resume and allows manual editing', async () => {
    mockFetch({
      'GET /applications': [],
      'GET /resumes': [
        {
          id: 1,
          name: 'Software Engineer Resume',
          content: 'Python and FastAPI experience',
        },
      ],
    })

    render(<ResumeMatch readOnly={false} />)

    const select = await screen.findByLabelText('Saved Resume')

    fireEvent.change(select, {
      target: { value: '1' },
    })

    const resumeText = screen.getByLabelText('Your Resume')
    expect(resumeText.value).toBe('Python and FastAPI experience')

    fireEvent.change(resumeText, {
      target: { value: 'Python, FastAPI, and React experience' },
    })

    expect(resumeText.value).toBe(
      'Python, FastAPI, and React experience'
    )
  })

  it('allows manual entry when saved resumes fail to load', async () => {
    const fetchMock = mockFetch({
      'GET /applications': [],
      'GET /resumes': { status: 500, body: {} },
      'POST /resume/match': {
        score: 50,
        matched_keywords: [],
        missing_keywords: [],
        suggestions: [],
      },
    })

    render(<ResumeMatch readOnly={false} />)

    expect(
      await screen.findByText(/Saved resumes could not be loaded/)
    ).toBeTruthy()

    expect(screen.queryByLabelText('Saved Resume')).toBeNull()

    fireEvent.change(screen.getByLabelText('Your Resume'), {
      target: { value: 'Python developer' },
    })
    fireEvent.change(screen.getByLabelText('Job Description'), {
      target: { value: 'Python and FastAPI' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Analyze Match' }))

    await screen.findByRole('heading', {
      name: 'Heuristic Match Score: 50%',
    })

    expect(requestBody(fetchMock, 'POST', '/resume/match')).toEqual({
      resume_text: 'Python developer',
      job_description: 'Python and FastAPI',
    })
  })
})
