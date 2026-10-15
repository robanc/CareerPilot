
from fastapi import APIRouter

from backend.app.schemas import (
    ResumeMatchRequest,
    ResumeMatchResponse,
)
from backend.app.services.resume_matcher import match_resume


router = APIRouter(prefix="/resume", tags=["Resume Matching"])


@router.post("/match", response_model=ResumeMatchResponse)
def resume_match(request: ResumeMatchRequest):
    return match_resume(
        resume_text=request.resume_text,
        job_description=request.job_description,
    )
