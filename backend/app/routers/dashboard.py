
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import JobApplication
from backend.app.schemas import (
    ApplicationStatus,
    DashboardResponse,
    DashboardStatusCounts,
)


router = APIRouter(tags=["Dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)):
    total = db.scalar(
        select(func.count()).select_from(JobApplication)
    ) or 0

    status_rows = db.execute(
        select(
            JobApplication.status,
            func.count(JobApplication.id),
        ).group_by(JobApplication.status)
    ).all()

    counts = {
        status.value: 0
        for status in ApplicationStatus
    }

    for application_status, count in status_rows:
        counts[application_status] = count

    upcoming_interviews = db.scalars(
        select(JobApplication)
        .where(
            JobApplication.interview_at >= datetime.now(timezone.utc)
        )
        .order_by(JobApplication.interview_at.asc())
        .limit(5)
    ).all()

    recent_applications = db.scalars(
        select(JobApplication)
        .order_by(
            JobApplication.created_at.desc(),
            JobApplication.id.desc(),
        )
        .limit(5)
    ).all()

    return DashboardResponse(
        total=total,
        by_status=DashboardStatusCounts(**counts),
        upcoming_interviews=upcoming_interviews,
        recent_applications=recent_applications,
    )
