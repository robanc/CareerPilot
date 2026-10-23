
import pytest

from backend.app.database import get_db
from backend.app.settings import Mode, Settings

from fastapi.testclient import TestClient

from backend.app.main import app


client = TestClient(app)


def test_get_nonexistent_resume():
    response = client.get("/resumes/999999")

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Resume not found"
    }


def test_create_resume_missing_name():
    response = client.post(
        "/resumes",
        json={"content": "Python and SQL experience"},
    )

    assert response.status_code == 422


def test_create_resume_blank_name():
    response = client.post(
        "/resumes",
        json={
            "name": "   ",
            "content": "Python and SQL experience",
        },
    )

    assert response.status_code == 422


def test_create_resume_blank_content():
    response = client.post(
        "/resumes",
        json={
            "name": "Software Engineer Resume",
            "content": "   ",
        },
    )

    assert response.status_code == 422


def test_create_resume_content_too_long():
    response = client.post(
        "/resumes",
        json={
            "name": "Long Resume",
            "content": "A" * 20001,
        },
    )

    assert response.status_code == 422


def test_update_resume_empty_body():
    response = client.patch(
        "/resumes/999999",
        json={},
    )

    assert response.status_code == 422


def test_update_resume_null_name():
    response = client.patch(
        "/resumes/999999",
        json={"name": None},
    )

    assert response.status_code == 422


def test_create_and_get_resume():
    payload = {
        "name": "Software Engineer Resume",
        "content": "Python, SQL, REST APIs, and Git experience.",
    }

    create_response = client.post(
        "/resumes",
        json=payload,
    )

    assert create_response.status_code == 201

    created = create_response.json()
    assert created["id"] > 0
    assert created["name"] == payload["name"]
    assert created["content"] == payload["content"]
    assert created["created_at"]
    assert created["updated_at"]

    resume_id = created["id"]

    get_response = client.get(f"/resumes/{resume_id}")

    assert get_response.status_code == 200
    assert get_response.json()["name"] == payload["name"]
    assert get_response.json()["content"] == payload["content"]


def test_update_resume():
    create_response = client.post(
        "/resumes",
        json={
            "name": "Original Resume",
            "content": "Python and SQL experience.",
        },
    )

    assert create_response.status_code == 201
    resume_id = create_response.json()["id"]

    update_response = client.patch(
        f"/resumes/{resume_id}",
        json={"name": "Updated Software Engineer Resume"},
    )

    assert update_response.status_code == 200

    updated = update_response.json()
    assert updated["name"] == "Updated Software Engineer Resume"
    assert updated["content"] == "Python and SQL experience."

    get_response = client.get(f"/resumes/{resume_id}")

    assert get_response.status_code == 200
    assert get_response.json()["name"] == updated["name"]


def test_delete_resume():
    create_response = client.post(
        "/resumes",
        json={
            "name": "Temporary Resume",
            "content": "Python and SQL experience.",
        },
    )

    assert create_response.status_code == 201
    resume_id = create_response.json()["id"]

    delete_response = client.delete(
        f"/resumes/{resume_id}"
    )

    assert delete_response.status_code == 204

    get_response = client.get(
        f"/resumes/{resume_id}"
    )

    assert get_response.status_code == 404
    assert get_response.json() == {
        "detail": "Resume not found"
    }


@pytest.mark.parametrize(
    "method, path",
    [
        ("GET", "/resumes"),
        ("GET", "/resumes/1"),
        ("POST", "/resumes"),
        ("PATCH", "/resumes/1"),
        ("DELETE", "/resumes/1"),
    ],
)
def test_public_demo_blocks_resume_library(method, path):
    previous_settings = getattr(app.state, "settings", None)
    previous_db_override = app.dependency_overrides.get(get_db)

    def fail_if_database_used():
        pytest.fail("Blocked request accessed the database")
        yield

    try:
        app.state.settings = Settings(
            mode=Mode.PUBLIC_DEMO,
            on_render=False,
        )
        app.dependency_overrides[get_db] = fail_if_database_used

        response = client.request(method, path)

        assert response.status_code == 403

    finally:
        app.state.settings = previous_settings

        if previous_db_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_db_override
