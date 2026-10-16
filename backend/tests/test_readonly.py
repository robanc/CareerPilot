import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.database import get_db
from backend.app.main import app
from backend.app.readonly import READ_ONLY_MESSAGE, ReadOnlyMiddleware
from backend.app.routers.applications import router as applications_router
from backend.app.settings import Mode, Settings


client = TestClient(app)

LOCAL = Settings(mode=Mode.LOCAL, on_render=False)
PUBLIC_DEMO = Settings(mode=Mode.PUBLIC_DEMO, on_render=False)

APPLICATION = {
    "company_name": "Synthetic Demo Corp",
    "job_title": "Backend Engineer",
    "application_date": "2026-10-16",
    "status": "Applied",
}

RESUME_MATCH = {
    "resume_text": "Python and Docker",
    "job_description": "Python, Docker, AWS",
}


@pytest.fixture
def set_mode():
    """Set app.state.settings for a test and restore the previous value."""
    previous = getattr(app.state, "settings", None)

    def _set(settings):
        app.state.settings = settings

    yield _set
    app.state.settings = previous


@pytest.fixture
def existing_id(set_mode):
    set_mode(LOCAL)
    response = client.post("/applications", json=APPLICATION)
    assert response.status_code == 201
    return response.json()["id"]


@pytest.fixture
def demo(set_mode, existing_id):
    set_mode(PUBLIC_DEMO)
    return existing_id


@pytest.fixture
def db_must_not_be_used():
    def fail():
        pytest.fail("a blocked request opened a database session")
        yield  # pragma: no cover

    original = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = fail
    yield
    app.dependency_overrides[get_db] = original


def assert_read_only(response):
    assert response.status_code == 403
    assert response.json() == {"detail": READ_ONLY_MESSAGE}


def assert_unchanged(application_id):
    response = client.get(f"/applications/{application_id}")
    assert response.status_code == 200
    assert response.json()["company_name"] == APPLICATION["company_name"]
    assert len(client.get("/applications").json()) == 1


# --- public_demo: blocked writes --------------------------------------------


def test_demo_blocks_create(demo):
    assert_read_only(client.post("/applications", json=APPLICATION))
    assert_unchanged(demo)


def test_demo_blocks_patch(demo):
    assert_read_only(
        client.patch(f"/applications/{demo}", json={"company_name": "Changed"})
    )
    assert_unchanged(demo)


def test_demo_blocks_put(demo):
    assert_read_only(client.put(f"/applications/{demo}", json=APPLICATION))
    assert_unchanged(demo)


def test_demo_blocks_delete(demo):
    assert_read_only(client.delete(f"/applications/{demo}"))
    assert_unchanged(demo)


@pytest.mark.parametrize("method", ["TRACE", "PROPFIND", "MKCOL", "LINK"])
def test_demo_blocks_unusual_methods(demo, method):
    assert_read_only(client.request(method, f"/applications/{demo}"))


@pytest.mark.parametrize(
    "path",
    [
        "/applications/",
        "//applications",
        "/applications/1/",
        "/health",
        "/dashboard",
        "/docs",
        "/openapi.json",
        "/does-not-exist",
        "/",
        "/resume/match/",
        "//resume/match",
        "/resume//match",
        "/resume/match%2F",
        "/Resume/Match",
        "/RESUME/MATCH",
        "/resume/match/extra",
        "/resume/matches",
        "/resume",
        "/api/resume/match",
    ],
)
def test_demo_blocks_post_to_any_other_path(demo, path):
    assert_read_only(client.post(path, json=RESUME_MATCH))
    assert_unchanged(demo)


@pytest.mark.parametrize("method", ["PUT", "PATCH", "DELETE"])
def test_demo_blocks_non_post_writes_to_resume_match(demo, method):
    assert_read_only(client.request(method, "/resume/match", json=RESUME_MATCH))


def test_demo_blocks_before_handlers_or_database(demo, db_must_not_be_used):
    assert_read_only(client.post("/applications", json=APPLICATION))
    assert_read_only(client.patch(f"/applications/{demo}", json={"notes": "x"}))
    assert_read_only(client.delete(f"/applications/{demo}"))


def test_demo_blocks_invalid_bodies_with_403_not_422(demo):
    response = client.post(
        "/applications",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert_read_only(response)


# --- public_demo: bypass attempts -------------------------------------------


BYPASS_HEADERS = [
    {"X-HTTP-Method-Override": "GET"},
    {"X-HTTP-Method": "GET"},
    {"X-Method-Override": "GET"},
    {"X-Original-Method": "GET"},
    {"X-Forwarded-Method": "GET"},
    {"X-Original-URL": "/resume/match"},
    {"X-Rewrite-URL": "/resume/match"},
    {"X-Forwarded-Prefix": "/resume/match"},
    {"X-Forwarded-Path": "/resume/match"},
    {"X-Forwarded-Uri": "/resume/match"},
    {"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"},
    {"X-Forwarded-Host": "localhost", "X-Forwarded-Proto": "https"},
    {"Forwarded": "for=127.0.0.1;host=localhost;proto=https"},
    {"Host": "localhost"},
    {"Origin": "http://localhost:5173"},
]


@pytest.mark.parametrize("headers", BYPASS_HEADERS)
def test_demo_header_bypass_attempts_on_writes_are_blocked(demo, headers):
    assert_read_only(client.post("/applications", json=APPLICATION, headers=headers))
    assert_read_only(
        client.patch(
            f"/applications/{demo}", json={"notes": "x"}, headers=headers
        )
    )
    assert_read_only(client.delete(f"/applications/{demo}", headers=headers))
    assert_unchanged(demo)


@pytest.mark.parametrize("override", ["DELETE", "PATCH", "PUT", "POST"])
def test_demo_method_override_on_get_does_not_write(demo, override):
    for header in ("X-HTTP-Method-Override", "X-HTTP-Method", "X-Method-Override"):
        response = client.get(f"/applications/{demo}", headers={header: override})
        assert response.status_code == 200

    assert_unchanged(demo)


def test_demo_method_override_query_parameter_is_ignored(demo):
    assert_read_only(client.post("/applications?_method=GET", json=APPLICATION))
    response = client.get(f"/applications/{demo}?_method=DELETE")
    assert response.status_code == 200
    assert_unchanged(demo)


# --- public_demo: permitted requests ----------------------------------------


def test_demo_allows_reads(demo):
    assert client.get("/health").json() == {"status": "ok"}

    listing = client.get("/applications", params={"status": "Applied"})
    assert listing.status_code == 200
    assert [a["id"] for a in listing.json()] == [demo]

    assert client.get(f"/applications/{demo}").status_code == 200
    assert client.get("/applications/999999").status_code == 404

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert dashboard.json()["total"] == 1


def test_demo_allows_resume_match(demo):
    response = client.post("/resume/match", json=RESUME_MATCH)

    assert response.status_code == 200
    assert response.json()["matched_keywords"] == ["docker", "python"]


def test_demo_allows_head_and_options_through_to_routing(demo):
    # The router decides these (e.g. 405); the read-only layer must not.
    assert client.head("/health").status_code != 403
    assert client.options("/applications").status_code != 403


def test_demo_allows_cors_preflight(demo):
    response = client.options(
        "/resume/match",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# --- require_writable works without the middleware --------------------------


@pytest.fixture
def router_only_client():
    """The applications router alone: no ReadOnlyMiddleware in the stack."""
    bare_app = FastAPI()
    bare_app.include_router(applications_router)
    bare_app.state.settings = PUBLIC_DEMO

    def fail():
        pytest.fail("require_writable let a write reach the database")
        yield  # pragma: no cover

    bare_app.dependency_overrides[get_db] = fail
    return TestClient(bare_app)


def test_require_writable_blocks_create_without_middleware(router_only_client):
    assert_read_only(router_only_client.post("/applications", json=APPLICATION))


def test_require_writable_blocks_update_without_middleware(router_only_client):
    assert_read_only(
        router_only_client.patch("/applications/1", json={"notes": "x"})
    )


def test_require_writable_blocks_delete_without_middleware(router_only_client):
    assert_read_only(router_only_client.delete("/applications/1"))


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_every_write_route_has_require_writable(method):
    from backend.app.readonly import require_writable

    routes = [
        route
        for route in applications_router.routes
        if method in route.methods
    ]
    assert routes
    for route in routes:
        calls = [d.call for d in route.dependant.dependencies]
        assert require_writable in calls, route.path


# --- configuration edge cases -----------------------------------------------


def test_settings_from_environment_when_startup_did_not_run(set_mode, monkeypatch):
    set_mode(None)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CAREERPILOT_ADMIN_DATABASE_URL", raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "public_demo")
    # Placeholder only; settings validation never connects to it.
    monkeypatch.setenv(
        "CAREERPILOT_DEMO_DATABASE_URL",
        "postgresql+psycopg://demo_reader:placeholder@db.invalid:5432/demo",
    )

    assert_read_only(client.post("/applications", json=APPLICATION))


def test_public_demo_database_misconfiguration_fails_closed(
    set_mode, monkeypatch, db_must_not_be_used
):
    """A missing demo database URL returns 503 rather than falling back to local."""
    set_mode(None)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.delenv("CAREERPILOT_DEMO_DATABASE_URL", raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "public_demo")

    assert client.post("/applications", json=APPLICATION).status_code == 503
    assert client.get("/applications").status_code == 503


def test_invalid_mode_fails_closed(set_mode, monkeypatch, db_must_not_be_used):
    set_mode(None)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("CAREERPILOT_MODE", "bogus")

    response = client.post("/applications", json=APPLICATION)

    assert response.status_code == 503


def _run_asgi(scope):
    sent = []

    async def inner(scope, receive, send):
        pytest.fail("request reached the application")

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"app": app, "headers": [], "query_string": b"", **scope}
    asyncio.run(ReadOnlyMiddleware(inner)(scope, receive, send))
    return sent


@pytest.mark.parametrize("method", ["get", "post", "Post", "GeT"])
def test_demo_methods_are_case_sensitive(set_mode, method):
    set_mode(PUBLIC_DEMO)

    sent = _run_asgi({"type": "http", "method": method, "path": "/resume/match"})

    assert sent[0]["status"] == 403


def test_demo_refuses_websockets(set_mode):
    set_mode(PUBLIC_DEMO)

    sent = _run_asgi({"type": "websocket", "path": "/applications"})

    assert sent == [{"type": "websocket.close", "code": 1008}]


# --- local mode: full CRUD unchanged ----------------------------------------


def test_local_mode_full_crud(set_mode):
    set_mode(LOCAL)

    created = client.post("/applications", json=APPLICATION)
    assert created.status_code == 201
    application_id = created.json()["id"]

    updated = client.patch(
        f"/applications/{application_id}", json={"status": "Interview"}
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "Interview"

    assert client.delete(f"/applications/{application_id}").status_code == 204
    assert client.get(f"/applications/{application_id}").status_code == 404


def test_local_mode_keeps_normal_error_codes(set_mode):
    set_mode(LOCAL)

    assert client.put("/applications/1", json=APPLICATION).status_code == 405
    assert client.post("/applications", json={}).status_code == 422
    assert client.delete("/applications/999999").status_code == 404


# --- CORS: cross-origin frontend in public_demo -----------------------------
# CORS headers only let an allowed browser origin read responses. They never
# authorize a request: blocked writes stay 403 whatever the origin.

ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
DISALLOWED_ORIGINS = [
    "https://evil.example",
    "http://localhost:5174",
    "http://localhost:5173.evil.example",
    "null",
]


def preflight(path, method, origin, request_headers="Content-Type"):
    return client.options(
        path,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": method,
            "Access-Control-Request-Headers": request_headers,
        },
    )


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
def test_cors_demo_allowed_origin_get(demo, origin):
    response = client.get("/applications", headers={"Origin": origin})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "origin" in response.headers["vary"].lower()


@pytest.mark.parametrize("origin", ALLOWED_ORIGINS)
@pytest.mark.parametrize("method", ["POST", "PATCH", "PUT", "DELETE"])
def test_cors_demo_blocked_write_is_403_with_cors_headers(demo, origin, method):
    path = "/applications" if method == "POST" else f"/applications/{demo}"

    response = client.request(
        method, path, json=APPLICATION, headers={"Origin": origin}
    )

    assert_read_only(response)
    assert response.headers["access-control-allow-origin"] == origin
    assert_unchanged(demo)


def test_cors_demo_allowed_origin_resume_match(demo):
    origin = ALLOWED_ORIGINS[0]

    assert preflight("/resume/match", "POST", origin).status_code == 200

    response = client.post(
        "/resume/match", json=RESUME_MATCH, headers={"Origin": origin}
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize("method", ["POST", "PATCH", "DELETE"])
def test_cors_demo_preflight_is_not_authorization(demo, method):
    origin = ALLOWED_ORIGINS[0]
    path = "/applications" if method == "POST" else f"/applications/{demo}"

    response = preflight(path, method, origin)

    # The preflight succeeds so the browser can send the request and read
    # the read-only message; the request itself is still refused.
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin

    actual = client.request(method, path, json=APPLICATION, headers={"Origin": origin})
    assert_read_only(actual)
    assert_unchanged(demo)


def test_cors_demo_preflight_rejects_unlisted_method(demo):
    response = preflight(f"/applications/{demo}", "PUT", ALLOWED_ORIGINS[0])

    assert response.status_code == 400
    assert "method" in response.text


@pytest.mark.parametrize(
    "header", ["X-HTTP-Method-Override", "X-Original-URL", "Authorization"]
)
def test_cors_demo_preflight_rejects_unlisted_headers(demo, header):
    response = preflight(
        "/applications", "POST", ALLOWED_ORIGINS[0], request_headers=header
    )

    assert response.status_code == 400
    assert "headers" in response.text


@pytest.mark.parametrize("origin", DISALLOWED_ORIGINS)
def test_cors_demo_disallowed_origin(demo, origin):
    rejected_preflight = preflight("/resume/match", "POST", origin)
    assert rejected_preflight.status_code == 400
    assert "access-control-allow-origin" not in rejected_preflight.headers

    read = client.get("/applications", headers={"Origin": origin})
    assert read.status_code == 200
    assert "access-control-allow-origin" not in read.headers

    write = client.post("/applications", json=APPLICATION, headers={"Origin": origin})
    assert_read_only(write)
    assert "access-control-allow-origin" not in write.headers
    assert_unchanged(demo)


def test_cors_local_mode_allowed_origin_crud(set_mode):
    set_mode(LOCAL)
    headers = {"Origin": ALLOWED_ORIGINS[0]}

    created = client.post("/applications", json=APPLICATION, headers=headers)
    assert created.status_code == 201
    assert created.headers["access-control-allow-origin"] == ALLOWED_ORIGINS[0]
    application_id = created.json()["id"]

    updated = client.patch(
        f"/applications/{application_id}", json={"notes": "x"}, headers=headers
    )
    assert updated.status_code == 200

    deleted = client.delete(f"/applications/{application_id}", headers=headers)
    assert deleted.status_code == 204
