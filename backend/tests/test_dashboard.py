
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_dashboard_application_counts():
    # Create two applications with different statuses.
    applications = [
        {
            "company_name": "Company A",
            "job_title": "Python Developer",
            "application_date": "2026-10-15",
            "status": "Applied",
        },
        {
            "company_name": "Company B",
            "job_title": "Network Engineer",
            "application_date": "2026-10-15",
            "status": "Interview",
        },
    ]

    for application in applications:
        response = client.post(
            "/applications",
            json=application,
        )
        assert response.status_code == 201

    # Retrieve dashboard statistics.
    response = client.get("/dashboard")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert data["by_status"]["Applied"] == 1
    assert data["by_status"]["Interview"] == 1
    assert data["by_status"]["Saved"] == 0
    assert data["by_status"]["Offer"] == 0
    assert data["by_status"]["Rejected"] == 0

    assert len(data["recent_applications"]) == 2
    assert data["upcoming_interviews"] == []


def test_dashboard_upcoming_interviews():
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)

    future_interview = (
        now + timedelta(days=7)
    ).isoformat()

    past_interview = (
        now - timedelta(days=7)
    ).isoformat()

    applications = [
        {
            "company_name": "Future Interview Company",
            "job_title": "Cloud Engineer",
            "application_date": "2026-10-15",
            "status": "Interview",
            "interview_at": future_interview,
        },
        {
            "company_name": "Past Interview Company",
            "job_title": "Network Engineer",
            "application_date": "2026-10-15",
            "status": "Interview",
            "interview_at": past_interview,
        },
    ]

    for application in applications:
        response = client.post(
            "/applications",
            json=application,
        )
        assert response.status_code == 201

    response = client.get("/dashboard")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 2
    assert len(data["upcoming_interviews"]) == 1

    upcoming = data["upcoming_interviews"][0]

    assert upcoming["company_name"] == "Future Interview Company"
    assert upcoming["job_title"] == "Cloud Engineer"
    assert upcoming["status"] == "Interview"
