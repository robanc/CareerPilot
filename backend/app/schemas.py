
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class ApplicationStatus(str, Enum):
    SAVED = "Saved"
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"


class ApplicationCreate(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    job_title: str = Field(min_length=1, max_length=200)
    job_description: str | None = None
    application_date: date
    status: ApplicationStatus = ApplicationStatus.SAVED
    job_url: HttpUrl | None = None
    notes: str | None = None
    interview_at: datetime | None = None
    interview_notes: str | None = None


class ApplicationUpdate(BaseModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    job_title: str | None = Field(default=None, min_length=1, max_length=200)
    job_description: str | None = None
    application_date: date | None = None
    status: ApplicationStatus | None = None
    job_url: HttpUrl | None = None
    notes: str | None = None
    interview_at: datetime | None = None
    interview_notes: str | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")

        required_fields = {
            "company_name",
            "job_title",
            "application_date",
            "status",
        }

        for field in required_fields:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")

        return self


class ApplicationResponse(ApplicationCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
