import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ResumeMatch, { MAX_INPUT_LENGTH } from './ResumeMatch'
import { mockFetch } from './test/mockFetch'

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
