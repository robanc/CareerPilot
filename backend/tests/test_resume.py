
from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_resume_match_success():
    response = client.post(
        "/resume/match",
        json={
            "resume_text": "Experience with Python, Docker, and PostgreSQL.",
            "job_description": (
                "Looking for Python, Docker, AWS, and PostgreSQL."
            ),
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["score"] == 75
    assert data["matched_keywords"] == [
        "docker",
        "postgresql",
        "python",
    ]
    assert data["missing_keywords"] == ["aws"]
    assert len(data["suggestions"]) == 1


def test_resume_match_all_skills():
    response = client.post(
        "/resume/match",
        json={
            "resume_text": "Python, Docker, AWS",
            "job_description": "Python, Docker, AWS",
        },
    )

    assert response.status_code == 200
    assert response.json()["score"] == 100
    assert response.json()["missing_keywords"] == []


def test_resume_match_empty_resume():
    response = client.post(
        "/resume/match",
        json={
            "resume_text": "",
            "job_description": "Python and Docker required",
        },
    )

    assert response.status_code == 422
