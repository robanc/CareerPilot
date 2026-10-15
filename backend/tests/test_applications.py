
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


def test_create_application_success():
    payload = {
        "company_name": "Test Company",
        "job_title": "Python Developer",
        "application_date": "2026-10-15",
        "status": "Applied",
        "notes": "Created by automated test",
    }

    response = client.post(
        "/applications",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert data["id"] > 0
    assert data["company_name"] == "Test Company"
    assert data["job_title"] == "Python Developer"
    assert data["status"] == "Applied"
    assert data["notes"] == "Created by automated test"


def test_get_application_success():
    payload = {
        "company_name": "CareerPilot Test",
        "job_title": "Software Engineer",
        "application_date": "2026-10-15",
        "status": "Saved",
    }

    # Create an application.
    create_response = client.post(
        "/applications",
        json=payload,
    )

    assert create_response.status_code == 201

    application_id = create_response.json()["id"]

    # Retrieve the same application.
    response = client.get(
        f"/applications/{application_id}"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == application_id
    assert data["company_name"] == "CareerPilot Test"
    assert data["job_title"] == "Software Engineer"
    assert data["status"] == "Saved"


def test_update_application_success():
    # Create a test application.
    payload = {
        "company_name": "CareerPilot Test",
        "job_title": "Network Engineer",
        "application_date": "2026-10-15",
        "status": "Applied",
    }

    create_response = client.post(
        "/applications",
        json=payload,
    )

    assert create_response.status_code == 201

    application_id = create_response.json()["id"]

    # Update its status and interview notes.
    update_payload = {
        "status": "Interview",
        "interview_notes": "Prepare for 5G technical interview.",
    }

    response = client.patch(
        f"/applications/{application_id}",
        json=update_payload,
    )

    assert response.status_code == 200

    data = response.json()

    assert data["id"] == application_id
    assert data["status"] == "Interview"
    assert data["interview_notes"] == "Prepare for 5G technical interview."

    # Verify unchanged fields are preserved.
    assert data["company_name"] == "CareerPilot Test"
    assert data["job_title"] == "Network Engineer"

    # Verify the update was saved in PostgreSQL.
    get_response = client.get(
        f"/applications/{application_id}"
    )

    assert get_response.status_code == 200
    assert get_response.json()["status"] == "Interview"


def test_delete_application_success():
    # Create a test application.
    payload = {
        "company_name": "CareerPilot Delete Test",
        "job_title": "Software Engineer",
        "application_date": "2026-10-15",
        "status": "Saved",
    }

    create_response = client.post(
        "/applications",
        json=payload,
    )

    assert create_response.status_code == 201

    application_id = create_response.json()["id"]

    # Delete the application.
    delete_response = client.delete(
        f"/applications/{application_id}"
    )

    assert delete_response.status_code == 204
    assert delete_response.content == b""

    # Verify the application no longer exists.
    get_response = client.get(
        f"/applications/{application_id}"
    )

    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Application not found"
    }
