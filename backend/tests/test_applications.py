
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_get_nonexistent_application():
    response = client.get("/applications/999999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Application not found"
    }


def test_create_application_missing_required_fields():
    response = client.post(
        "/applications",
        json={
            "company_name": "Demo Technologies"
        },
    )

    assert response.status_code == 422


def test_create_application_invalid_status():
    response = client.post(
        "/applications",
        json={
            "company_name": "Demo Technologies",
            "job_title": "Network Engineer",
            "application_date": "2026-10-14",
            "status": "Unknown",
        },
    )

    assert response.status_code == 422


def test_update_application_empty_body():
    response = client.patch(
        "/applications/999999",
        json={},
    )

    assert response.status_code == 422
