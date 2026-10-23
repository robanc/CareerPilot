
import { useEffect, useState } from 'react'
import { createResume, deleteResume, listResumes, updateResume } from './services/api'

function ResumeLibrary() {
  const [resumes, setResumes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editContent, setEditContent] = useState('')
  const [updating, setUpdating] = useState(false)
  const [editError, setEditError] = useState('')
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    const controller = new AbortController()

    async function loadResumes() {
      try {
        const data = await listResumes({
          signal: controller.signal,
        })
        setResumes(data)
        setError('')
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError('Unable to load saved resumes.')
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }

    loadResumes()

    return () => controller.abort()
  }, [])

  async function handleSave(event) {
    event.preventDefault()

    if (!name.trim() || !content.trim() || saving) return

    setSaving(true)
    setSaveError('')

    try {
      const saved = await createResume({ name, content })
      setResumes((previous) => [saved, ...previous])
      setName('')
      setContent('')
    } catch {
      setSaveError('Unable to save resume. Please try again.')
    } finally {
      setSaving(false)
    }
  }


  function startEditing(resume) {
    setEditingId(resume.id)
    setEditName(resume.name)
    setEditContent(resume.content)
    setEditError('')
  }


  async function handleUpdate(event) {
    event.preventDefault()

    if (!editName.trim() || !editContent.trim() || updating) return

    setUpdating(true)
    setEditError('')

    try {
      const updated = await updateResume(editingId, {
        name: editName,
        content: editContent,
      })

      setResumes((previous) =>
        previous.map((resume) =>
          resume.id === updated.id ? updated : resume
        )
      )

      setEditingId(null)
    } catch {
      setEditError('Unable to update resume. Please try again.')
    } finally {
      setUpdating(false)
    }
  }


  function startDeleting(resume) {
    setDeletingId(resume.id)
    setDeleteError('')
    setEditingId(null)
  }

 
  
  async function handleDelete(id) {
    if (deletingId !== id || deleting) return

    setDeleting(true)
    setDeleteError('')

    try {
      await deleteResume(id)

      setResumes((previous) =>
        previous.filter((resume) => resume.id !== id)
      )

      setDeletingId(null)
    } catch {
      setDeleteError('Unable to delete resume. Please try again.')
    } finally {
      setDeleting(false)
    }
  }

 
  
  return (
    <div>
      <h3>Saved Resumes</h3>
      <p>Manage your resume versions in one place.</p>


      <form
        className="application-form"
        onSubmit={handleSave}
      >
        <label>
          Resume Name
          <input
            required
            maxLength={200}
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="e.g. Software Engineer Resume"
          />
        </label>

        <label className="form-wide">
          Resume Content
          <textarea
            required
            maxLength={20000}
            rows={12}
            value={content}
            onChange={(event) => setContent(event.target.value)}
            placeholder="Paste your resume text here..."
          />
        </label>

        
        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save Resume'}
        </button>

      </form>

      {saveError && <p role="alert">{saveError}</p>}

      {loading ? (
        <p>Loading resumes...</p>
      ) : error ? (
        <p role="alert">{error}</p>
      ) : resumes.length === 0 ? (
        <p>No saved resumes yet.</p>
      ) : (
        <div className="applications-list">
          
          {resumes.map((resume) => (
            <div className="application-item" key={resume.id}>
              <h4>{resume.name}</h4>
              <p className="multiline">{resume.content}</p>

              <button
                type="button"
                className="link-button"
                onClick={() => startEditing(resume)}
              >
                Edit
              </button>
              
              
              <button
                type="button"
                className="link-button"
                onClick={() => startDeleting(resume)}
              >
                Delete
              </button>

              
              {deletingId === resume.id && (
                <div className="read-only-note">
                  <p>
                    Are you sure you want to delete "{resume.name}"?
                  </p>

                 
                  <button
                    type="button"
                    disabled={deleting}
                    onClick={() => handleDelete(resume.id)}
                  >
                    {deleting ? 'Deleting...' : 'Confirm Delete'}
                  </button>


                  <button
                    type="button"
                    onClick={() => setDeletingId(null)}
                  >
                    Cancel
                  </button>

                  {deleteError && (
                    <p role="alert">{deleteError}</p>
                  )}
                </div>
              )}



              {editingId === resume.id && (
                <>
                  <form
                    className="application-form edit-form"
                    onSubmit={handleUpdate}
                  >
                    <label>
                      Resume Name
                      <input
                        required
                        maxLength={200}
                        value={editName}
                        onChange={(event) => setEditName(event.target.value)}
                      />
                    </label>

                    <label className="form-wide">
                      Resume Content
                      <textarea
                        required
                        maxLength={20000}
                        rows={12}
                        value={editContent}
                        onChange={(event) => setEditContent(event.target.value)}
                      />
                    </label>

                    <div className="form-actions">
                      <button type="submit" disabled={updating}>
                        {updating ? 'Updating...' : 'Save Changes'}
                      </button>

                      <button
                        type="button"
                        onClick={() => setEditingId(null)}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>

                  {editError && <p role="alert">{editError}</p>}
                </>
              )}

            </div>
          ))}

        </div>
      )}
    </div>
  )
}

export default ResumeLibrary
