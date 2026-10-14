
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import JobApplication
from backend.app.schemas import (
    ApplicationCreate,
    ApplicationUpdate,
    ApplicationResponse,
    ApplicationStatus,
)



router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)


@router.post(
    "",
    response_model=ApplicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    application: ApplicationCreate,
    db: Session = Depends(get_db),
):
    new_application = JobApplication(
        **application.model_dump(mode="json")
    )

    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return new_application


@router.get(
    "",
    response_model=list[ApplicationResponse],
)
def list_applications(
    status_filter: ApplicationStatus | None = Query(
        default=None,
        alias="status",
    ),
    search: str | None = None,
    db: Session = Depends(get_db),
):
    query = select(JobApplication)

    if status_filter is not None:
        query = query.where(
            JobApplication.status == status_filter.value
        )

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                JobApplication.company_name.ilike(search_pattern),
                JobApplication.job_title.ilike(search_pattern),
            )
        )

    query = query.order_by(
        JobApplication.created_at.desc(),
        JobApplication.id.desc(),
    )

    return db.scalars(query).all()


@router.get(
    "/{id}",
    response_model=ApplicationResponse,
)
def get_application(
    id: int,
    db: Session = Depends(get_db),
):
    if id < 1:
        raise HTTPException(
            status_code=422,
            detail="Application ID must be a positive integer",
        )

    application = db.get(JobApplication, id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    return application


@router.patch(
    "/{id}",
    response_model=ApplicationResponse,
)
def update_application(
    id: int,
    updates: ApplicationUpdate,
    db: Session = Depends(get_db),
):
    if id < 1:
        raise HTTPException(
            status_code=422,
            detail="Application ID must be a positive integer",
        )

    application = db.get(JobApplication, id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    update_data = updates.model_dump(
        exclude_unset=True,
        mode="json",
    )

    for field, value in update_data.items():
        setattr(application, field, value)

    db.commit()
    db.refresh(application)

    return application


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_application(
    id: int,
    db: Session = Depends(get_db),
):
    if id < 1:
        raise HTTPException(
            status_code=422,
            detail="Application ID must be a positive integer",
        )

    application = db.get(JobApplication, id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Application not found",
        )

    db.delete(application)
    db.commit()
