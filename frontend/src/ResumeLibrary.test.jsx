
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ResumeLibrary from './ResumeLibrary'
import { mockFetch, requestBody } from './test/mockFetch'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('ResumeLibrary', () => {
  it('displays saved resumes', async () => {
    mockFetch({
      'GET /resumes': [
        {
          id: 1,
          name: 'Software Engineer Resume',
          content: 'Python, React, and FastAPI experience',
        },
      ],
    })

    render(<ResumeLibrary />)

    expect(
      await screen.findByText('Software Engineer Resume')
    ).toBeTruthy()

    expect(
      screen.getByText('Python, React, and FastAPI experience')
    ).toBeTruthy()
  })
  
  it('creates a new resume', async () => {
    mockFetch({
      'GET /resumes': [],
      'POST /resumes': {
        status: 201,
        body: {
          id: 2,
          name: 'Cloud Engineer Resume',
          content: 'AWS, Python, and Docker experience',
        },
      },
    })

    render(<ResumeLibrary />)

    await screen.findByText('No saved resumes yet.')

    
    
    fireEvent.change(screen.getByLabelText('Resume Name'), {
      target: { value: 'Cloud Engineer Resume' },
    })

    fireEvent.change(screen.getByLabelText('Resume Content'), {
      target: { value: 'AWS, Python, and Docker experience' },
    })



    fireEvent.click(
      screen.getByRole('button', { name: 'Save Resume' })
    )

    expect(
      await screen.findByText('Cloud Engineer Resume')
    ).toBeTruthy()

    expect(
      screen.getByText('AWS, Python, and Docker experience')
    ).toBeTruthy()
  })
  
  it('edits an existing resume', async () => {
    const existing = {
      id: 3,
      name: 'Original Resume',
      content: 'Original experience',
    }

    const fetchMock = mockFetch({
      'GET /resumes': [existing],
      'PATCH /resumes/3': (options) => ({
        ...existing,
        ...JSON.parse(options.body),
      }),
    })

    render(<ResumeLibrary />)

    await screen.findByText('Original Resume')

    fireEvent.click(screen.getByRole('button', { name: 'Edit' }))

    
    const editForm = screen
      .getByRole('button', { name: 'Save Changes' })
      .closest('form')

    fireEvent.change(within(editForm).getByLabelText('Resume Name'), {
      target: { value: 'Updated Resume' },
    })

    fireEvent.change(within(editForm).getByLabelText('Resume Content'), {
      target: { value: 'Updated experience' },
    })


    fireEvent.click(
      screen.getByRole('button', { name: 'Save Changes' })
    )

    expect(
      await screen.findByText('Updated Resume')
    ).toBeTruthy()

    expect(
      screen.getByText('Updated experience')
    ).toBeTruthy()

    expect(requestBody(fetchMock, 'PATCH', '/resumes/3')).toEqual({
      name: 'Updated Resume',
      content: 'Updated experience',
    })
  })
  
  it('cancels resume deletion without deleting it', async () => {
    const existing = {
      id: 4,
      name: 'Cloud Resume',
      content: 'AWS and Docker experience',
    }

    const fetchMock = mockFetch({
      'GET /resumes': [existing],
    })

    render(<ResumeLibrary />)

    await screen.findByText('Cloud Resume')

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(
      screen.getByText(/Are you sure you want to delete/)
    ).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.getByText('Cloud Resume')).toBeTruthy()
    expect(
      screen.queryByRole('button', { name: 'Confirm Delete' })
    ).toBeNull()

    expect(
      fetchMock.mock.calls.some(([, options = {}]) =>
        options.method === 'DELETE'
      )
    ).toBe(false)
  })
  
  it('deletes a resume after confirmation', async () => {
    const existing = {
      id: 5,
      name: 'Old Resume',
      content: 'Outdated experience',
    }

    const fetchMock = mockFetch({
      'GET /resumes': [existing],
      'DELETE /resumes/5': {
        status: 204,
      },
    })

    render(<ResumeLibrary />)

    await screen.findByText('Old Resume')

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }))

    expect(
      screen.getByText(/Are you sure you want to delete/)
    ).toBeTruthy()

    fireEvent.click(
      screen.getByRole('button', { name: 'Confirm Delete' })
    )

    expect(
      await screen.findByText('No saved resumes yet.')
    ).toBeTruthy()

    expect(screen.queryByText('Old Resume')).toBeNull()

    expect(
      fetchMock.mock.calls.some(([url, options = {}]) =>
        url.endsWith('/resumes/5') &&
        options.method === 'DELETE'
      )
    ).toBe(true)
  })
})
