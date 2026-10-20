"""GET /version: the deployed commit, used by the release smoke test."""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import GIT_COMMIT_ENV_VAR, app


client = TestClient(app)

SHA = "0123456789abcdef0123456789abcdef01234567"


def test_version_reports_the_render_commit(monkeypatch):
    monkeypatch.setenv(GIT_COMMIT_ENV_VAR, SHA)

    assert client.get("/version").json() == {"commit": SHA}


def test_version_is_null_outside_render(monkeypatch):
    monkeypatch.delenv(GIT_COMMIT_ENV_VAR, raising=False)

    assert client.get("/version").json() == {"commit": None}


@pytest.mark.parametrize(
    "value",
    ["", "abc123", SHA.upper(), SHA + "0", f"{SHA[:-1]}g", f"{SHA} extra"],
    ids=["empty", "short", "uppercase", "long", "non-hex", "trailing-text"],
)
def test_version_rejects_anything_but_a_full_sha(monkeypatch, value):
    monkeypatch.setenv(GIT_COMMIT_ENV_VAR, value)

    assert client.get("/version").json() == {"commit": None}
