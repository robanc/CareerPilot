
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Resume
from backend.app.readonly import current_settings, require_writable
from backend.app.schemas import (
    ResumeCreate,
    ResumeUpdate,
    ResumeResponse,
)


def require_local_mode(request: Request) -> None:
    """Prevent access to saved resumes in public demo mode."""
    if current_settings(request.app).is_public_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Resume Library is available only in local mode.",
        )


router = APIRouter(
    prefix="/resumes",
    tags=["Resume Library"],
    dependencies=[Depends(require_local_mode)],
)


@router.post(
    "",
    response_model=ResumeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_writable)],
)
def create_resume(
    resume: ResumeCreate,
    db: Session = Depends(get_db),
):
    new_resume = Resume(**resume.model_dump())
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)
    return new_resume


@router.get(
    "",
    response_model=list[ResumeResponse],
)
def list_resumes(db: Session = Depends(get_db)):
    query = select(Resume).order_by(
        Resume.updated_at.desc(),
        Resume.id.desc(),
    )
    return db.scalars(query).all()


@router.get(
    "/{id}",
    response_model=ResumeResponse,
)
def get_resume(
    id: int,
    db: Session = Depends(get_db),
):
    if id < 1:
        raise HTTPException(
            status_code=422,
            detail="Resume ID must be a positive integer",
        )

    resume = db.get(Resume, id)
    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )
    return resume


@router.patch(
    "/{id}",
    response_model=ResumeResponse,
    dependencies=[Depends(require_writable)],
)
def update_resume(
    id: int,
    updates: ResumeUpdate,
    db: Session = Depends(get_db),
):
    if id < 1:
        raise HTTPException(
            status_code=422,
            detail="Resume ID must be a positive integer",
        )

    resume = db.get(Resume, id)
    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    for field, value in updates.model_dump(
        exclude_unset=True
    ).items():
        setattr(resume, field, value)

    db.commit()
    db.refresh(resume)
    return resume


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_writable)],
)
def delete_resume(
    id: int,
    db: Session = Depends(get_db),
):
    if id < 1:
        raise HTTPException(
            status_code=422,
            detail="Resume ID must be a positive integer",
        )

    resume = db.get(Resume, id)
    if resume is None:
        raise HTTPException(
            status_code=404,
            detail="Resume not found",
        )

    db.delete(resume)
    db.commit()
