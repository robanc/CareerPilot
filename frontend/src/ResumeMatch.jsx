
import { useState } from 'react'
import { matchResume } from './services/api'

// Matches the backend limits in schemas.py (the backend enforces them).
export const MAX_INPUT_LENGTH = 20000

function errorMessage(status) {
  if (status === 429) {
    return 'Too many match requests. Please wait a minute and try again.'
  }
  if (status === 413 || status === 422) {
    return `Each text can be at most ${MAX_INPUT_LENGTH.toLocaleString('en-US')} characters.`
  }
  return 'Unable to analyze resume. Please try again.'
}

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
      setResult(await matchResume(resumeText, jobDescription))
    } catch (err) {
      setError(errorMessage(err.status))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h3>Resume Match Analysis</h3>
      <p>Compare your resume against a job description to identify matching and missing skills.</p>
      <p className="heuristic-note">
        Up to {MAX_INPUT_LENGTH.toLocaleString('en-US')} characters each. Text
        is analyzed and discarded; it is not stored.
      </p>

      <form className="resume-form" onSubmit={handleSubmit}>
        <label>
          Your Resume
          <textarea
            required
            rows={8}
            maxLength={MAX_INPUT_LENGTH}
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
            maxLength={MAX_INPUT_LENGTH}
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
          <h2>Heuristic Match Score: {result.score}%</h2>
          <p className="heuristic-note">
            This score comes from a simple keyword comparison between your
            resume and the job description. It is a heuristic estimate, not
            an assessment of your suitability for the role.
          </p>
          <div
  className="match-progress"
  role="progressbar"
  aria-label="Heuristic resume match score"
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
