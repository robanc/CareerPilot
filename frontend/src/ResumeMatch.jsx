
import { useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL ?? '/api'

function ResumeMatch() {
  const [resumeText, setResumeText] = useState('')
  const [jobDescription, setJobDescription] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    setResult(null)

    try {
      const response = await fetch(`${API_URL}/resume/match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_text: resumeText,
          job_description: jobDescription,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`)
      }

      setResult(await response.json())
    } catch {
      setError('Unable to analyze resume. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h3>Resume Match Analysis</h3>
      <p>Compare your resume against a job description to identify matching and missing skills.</p>

      <form className="resume-form" onSubmit={handleSubmit}>
        <label>
          Your Resume
          <textarea
            required
            rows={8}
            value={resumeText}
            onChange={(event) => setResumeText(event.target.value)}
            placeholder="Paste your resume text here..."
          />
        </label>

        <label>
          Job Description
          <textarea
            required
            rows={8}
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            placeholder="Paste the job description here..."
          />
        </label>

        <button type="submit" disabled={loading}>
          {loading ? 'Analyzing...' : 'Analyze Match'}
        </button>
      </form>

      {error && <p role="alert">{error}</p>}

      {result && (
        <div className="resume-results">
          <h3>Match Results</h3>
          <h2>{result.score}% Match</h2>
          <div
  className="match-progress"
  role="progressbar"
  aria-label="Resume match score"
  aria-valuenow={result.score}
  aria-valuemin={0}
  aria-valuemax={100}
>
  <div
    className="match-progress-fill"
    style={{ width: `${result.score}%` }}
  />
</div>

          <h4>Matched Skills</h4>
<div className="skill-list">
  {result.matched_keywords.length > 0 ? (
    result.matched_keywords.map((skill) => (
      <span key={skill} className="skill-badge matched">
        {skill}
      </span>
    ))
  ) : (
    <p>No matching skills found.</p>
  )}
</div>

          <h4>Missing Skills</h4>
<div className="skill-list">
  {result.missing_keywords.length > 0 ? (
    result.missing_keywords.map((skill) => (
      <span key={skill} className="skill-badge missing">
        {skill}
      </span>
    ))
  ) : (
    <p>No missing skills identified.</p>
  )}
</div>

          <h4>Suggestions</h4>
          {result.suggestions.length > 0 ? (
            <ul>
              {result.suggestions.map((suggestion, index) => (
                <li key={index}>{suggestion}</li>
              ))}
            </ul>
          ) : (
            <p>No additional suggestions.</p>
          )}
        </div>
      )}
    </div>
  )
}

export default ResumeMatch
