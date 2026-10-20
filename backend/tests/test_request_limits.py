"""Resume input limits, request body size limit, and rate limiting."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend.app.limits import (
    BODY_TOO_LARGE_MESSAGE,
    DEFAULT_RULE,
    INVALID_LENGTH_MESSAGE,
    MAX_REQUEST_BODY_BYTES,
    RATE_LIMIT_MESSAGE,
    RESUME_MATCH_RULE,
    BodySizeLimitMiddleware,
    Limit,
    RateLimiter,
    RateLimitMiddleware,
)
from backend.app.main import app
from backend.app.schemas import (
    JOB_DESCRIPTION_MAX_LENGTH,
    RESUME_TEXT_MAX_LENGTH,
)
from backend.app.settings import Mode, Settings


client = TestClient(app)

LOCAL = Settings(mode=Mode.LOCAL, on_render=False)
PUBLIC_DEMO = Settings(mode=Mode.PUBLIC_DEMO, on_render=False)

ORIGIN = "http://localhost:5173"


@pytest.fixture
def set_mode():
    """Set app.state.settings for a test and restore the previous value."""
    previous = getattr(app.state, "settings", None)

    def _set(settings):
        app.state.settings = settings

    yield _set
    app.state.settings = previous


def match_body(resume_text="python", job_description="python docker"):
    return {"resume_text": resume_text, "job_description": job_description}


def assert_too_long(response, field):
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert [error["loc"][-1] for error in errors] == [field]
    assert errors[0]["type"] == "string_too_long"


# --- resume input lengths (every mode) ------------------------------------


@pytest.mark.parametrize("settings", [LOCAL, PUBLIC_DEMO], ids=["local", "demo"])
def test_resume_text_at_max_length_is_accepted(set_mode, settings):
    set_mode(settings)
    response = client.post(
        "/resume/match",
        json=match_body(resume_text="python " + "a" * (RESUME_TEXT_MAX_LENGTH - 7)),
    )

    assert response.status_code == 200
    assert response.json()["matched_keywords"] == ["python"]


@pytest.mark.parametrize("settings", [LOCAL, PUBLIC_DEMO], ids=["local", "demo"])
def test_resume_text_over_max_length_is_rejected(set_mode, settings):
    set_mode(settings)
    response = client.post(
        "/resume/match",
        json=match_body(resume_text="a" * (RESUME_TEXT_MAX_LENGTH + 1)),
    )

    assert_too_long(response, "resume_text")


@pytest.mark.parametrize("settings", [LOCAL, PUBLIC_DEMO], ids=["local", "demo"])
def test_job_description_at_max_length_is_accepted(set_mode, settings):
    set_mode(settings)
    response = client.post(
        "/resume/match",
        json=match_body(
            job_description="python " + "b" * (JOB_DESCRIPTION_MAX_LENGTH - 7)
        ),
    )

    assert response.status_code == 200
    assert response.json()["score"] == 100


@pytest.mark.parametrize("settings", [LOCAL, PUBLIC_DEMO], ids=["local", "demo"])
def test_job_description_over_max_length_is_rejected(set_mode, settings):
    set_mode(settings)
    response = client.post(
        "/resume/match",
        json=match_body(job_description="b" * (JOB_DESCRIPTION_MAX_LENGTH + 1)),
    )

    assert_too_long(response, "job_description")


def test_length_limits_count_characters_not_bytes(set_mode):
    # 20,000 two-byte characters: 40,000 bytes of UTF-8, still within limit.
    set_mode(PUBLIC_DEMO)
    response = client.post(
        "/resume/match",
        json=match_body(resume_text="é" * RESUME_TEXT_MAX_LENGTH),
    )

    assert response.status_code == 200


def test_empty_inputs_are_still_rejected(set_mode):
    set_mode(PUBLIC_DEMO)
    response = client.post("/resume/match", json=match_body(resume_text=""))

    assert response.status_code == 422


# --- request body size (public_demo only) ----------------------------------


def body_of_size(size):
    """A JSON resume match body of exactly `size` bytes."""
    empty = json.dumps(match_body(resume_text=""))
    padding = size - len(empty)
    assert padding > 0
    return json.dumps(match_body(resume_text="a" * padding)).encode()


def post_raw(body, headers=None):
    return client.post(
        "/resume/match",
        content=body,
        headers={"Content-Type": "application/json", **(headers or {})},
    )


def test_demo_body_at_limit_reaches_validation(set_mode):
    # Exactly the byte limit passes the size check; the schema then rejects
    # the oversized field with 422, proving the body was not cut off.
    set_mode(PUBLIC_DEMO)
    response = post_raw(body_of_size(MAX_REQUEST_BODY_BYTES))

    assert_too_long(response, "resume_text")


def test_demo_body_over_limit_is_413(set_mode):
    set_mode(PUBLIC_DEMO)
    response = post_raw(body_of_size(MAX_REQUEST_BODY_BYTES + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": BODY_TOO_LARGE_MESSAGE}


def test_demo_413_carries_cors_headers(set_mode):
    set_mode(PUBLIC_DEMO)
    response = post_raw(
        body_of_size(MAX_REQUEST_BODY_BYTES + 1), headers={"Origin": ORIGIN}
    )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_local_mode_has_no_body_size_limit(set_mode):
    set_mode(LOCAL)
    response = post_raw(body_of_size(MAX_REQUEST_BODY_BYTES + 1))

    assert_too_long(response, "resume_text")


def test_demo_blocked_write_is_403_before_body_size(set_mode):
    # Writes are refused by the read-only layer without reading the body.
    set_mode(PUBLIC_DEMO)
    response = client.post(
        "/applications",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 403


class AsgiRun:
    """Drive a middleware directly with a scripted receive channel."""

    def __init__(self, middleware_factory, messages, headers=(), settings=PUBLIC_DEMO):
        self.messages = list(messages)
        self.receive_calls = 0
        self.sent = []
        self.app_bodies = []
        self.scope = {
            "type": "http",
            "method": "POST",
            "path": "/resume/match",
            "headers": list(headers),
            "client": ("203.0.113.5", 40000),
            "app": SimpleNamespace(state=SimpleNamespace(settings=settings)),
        }
        self.middleware = middleware_factory(self.inner_app)

    async def inner_app(self, scope, receive, send):
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body", False):
                break
        self.app_bodies.append(body)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def receive(self):
        self.receive_calls += 1
        if self.messages:
            return self.messages.pop(0)
        return {"type": "http.disconnect"}

    async def send(self, message):
        self.sent.append(message)

    def run(self):
        asyncio.run(self.middleware(self.scope, self.receive, self.send))
        return self

    @property
    def status(self):
        starts = [m for m in self.sent if m["type"] == "http.response.start"]
        return starts[0]["status"] if starts else None

    @property
    def detail(self):
        bodies = [m for m in self.sent if m["type"] == "http.response.body"]
        return json.loads(bodies[0]["body"])["detail"]


def limited(app):
    return BodySizeLimitMiddleware(app, max_bytes=10)


def test_declared_oversized_body_is_refused_without_reading_it():
    run = AsgiRun(limited, [], headers=[(b"content-length", b"11")]).run()

    assert run.status == 413
    assert run.receive_calls == 0
    assert run.app_bodies == []


@pytest.mark.parametrize(
    "headers",
    [
        [(b"content-length", b"abc")],
        [(b"content-length", b"-1")],
        [(b"content-length", b"5"), (b"content-length", b"6")],
    ],
    ids=["not-a-number", "negative", "conflicting"],
)
def test_invalid_content_length_is_400(headers):
    run = AsgiRun(limited, [], headers=headers).run()

    assert run.status == 400
    assert run.detail == INVALID_LENGTH_MESSAGE
    assert run.app_bodies == []


def test_undeclared_streamed_body_over_limit_is_413():
    messages = [
        {"type": "http.request", "body": b"123456", "more_body": True},
        {"type": "http.request", "body": b"78901", "more_body": True},
        {"type": "http.request", "body": b"never read", "more_body": False},
    ]
    run = AsgiRun(limited, messages).run()

    assert run.status == 413
    assert run.app_bodies == []
    assert run.receive_calls == 2


def test_understated_content_length_is_still_capped():
    messages = [{"type": "http.request", "body": b"12345678901", "more_body": False}]
    run = AsgiRun(limited, messages, headers=[(b"content-length", b"3")]).run()

    assert run.status == 413
    assert run.app_bodies == []


def test_streamed_body_within_limit_is_replayed_whole():
    messages = [
        {"type": "http.request", "body": b"12345", "more_body": True},
        {"type": "http.request", "body": b"67890", "more_body": False},
    ]
    run = AsgiRun(limited, messages).run()

    assert run.status == 200
    assert run.app_bodies == [b"1234567890"]


def test_client_disconnect_while_reading_never_calls_the_app():
    messages = [{"type": "http.request", "body": b"123", "more_body": True}]
    run = AsgiRun(limited, messages).run()

    assert run.sent == []
    assert run.app_bodies == []


def test_body_size_middleware_is_inert_in_local_mode():
    messages = [{"type": "http.request", "body": b"x" * 50, "more_body": False}]
    run = AsgiRun(limited, messages, settings=LOCAL).run()

    assert run.status == 200
    assert run.app_bodies == [b"x" * 50]


# --- rate limiter unit tests ------------------------------------------------


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_limiter_allows_up_to_the_limit_then_refuses():
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(requests=3, window_seconds=60)

    assert [limiter.acquire([("k", limit)]) for _ in range(3)] == [None] * 3

    clock.now += 10
    assert limiter.acquire([("k", limit)]) == pytest.approx(50)


def test_limiter_window_resets():
    clock = FakeClock()
    limiter = RateLimiter(clock=clock)
    limit = Limit(requests=1, window_seconds=60)

    assert limiter.acquire([("k", limit)]) is None
    assert limiter.acquire([("k", limit)]) is not None
    clock.now += 60
    assert limiter.acquire([("k", limit)]) is None


def test_limiter_refusal_consumes_nothing():
    # A client over its own limit must not use up the shared total.
    limiter = RateLimiter(clock=FakeClock())
    per_client = Limit(requests=1, window_seconds=60)
    total = Limit(requests=3, window_seconds=60)

    assert limiter.acquire([("a", per_client), ("total", total)]) is None
    for _ in range(5):
        assert limiter.acquire([("a", per_client), ("total", total)]) is not None

    assert limiter.acquire([("b", per_client), ("total", total)]) is None
    assert limiter.acquire([("c", per_client), ("total", total)]) is None
    assert limiter.acquire([("d", per_client), ("total", total)]) is not None


def test_limiter_fails_closed_when_tracking_is_full():
    clock = FakeClock()
    limiter = RateLimiter(clock=clock, max_tracked_keys=2)
    limit = Limit(requests=5, window_seconds=60)

    assert limiter.acquire([("a", limit)]) is None
    assert limiter.acquire([("b", limit)]) is None
    assert limiter.acquire([("c", limit)]) == 60
    # Known keys keep working, and expired windows free space again.
    assert limiter.acquire([("a", limit)]) is None
    clock.now += 60
    assert limiter.acquire([("c", limit)]) is None


def test_rate_limit_middleware_is_inert_in_local_mode():
    limiter = RateLimiter(clock=FakeClock())
    for _ in range(RESUME_MATCH_RULE.per_client.requests + 5):
        run = AsgiRun(
            lambda app: RateLimitMiddleware(app, limiter=limiter),
            [{"type": "http.request", "body": b"", "more_body": False}],
            settings=LOCAL,
        ).run()
        assert run.status == 200


# --- rate limiting through the application ---------------------------------


def test_demo_resume_match_is_rate_limited(set_mode):
    set_mode(PUBLIC_DEMO)
    allowed = RESUME_MATCH_RULE.per_client.requests

    for _ in range(allowed):
        assert client.post("/resume/match", json=match_body()).status_code == 200

    response = client.post("/resume/match", json=match_body())

    assert response.status_code == 429
    assert response.json() == {"detail": RATE_LIMIT_MESSAGE}
    retry_after = int(response.headers["retry-after"])
    assert 1 <= retry_after <= RESUME_MATCH_RULE.per_client.window_seconds


def test_demo_429_carries_cors_headers(set_mode):
    set_mode(PUBLIC_DEMO)
    for _ in range(RESUME_MATCH_RULE.per_client.requests):
        client.post("/resume/match", json=match_body())

    response = client.post(
        "/resume/match", json=match_body(), headers={"Origin": ORIGIN}
    )

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == ORIGIN


def test_demo_resume_match_limit_does_not_block_reads(set_mode):
    set_mode(PUBLIC_DEMO)
    for _ in range(RESUME_MATCH_RULE.per_client.requests + 1):
        client.post("/resume/match", json=match_body())

    assert client.get("/config").status_code == 200


def test_demo_read_endpoints_are_rate_limited(set_mode):
    set_mode(PUBLIC_DEMO)
    for _ in range(DEFAULT_RULE.per_client.requests):
        assert client.get("/config").status_code == 200

    response = client.get("/config")

    assert response.status_code == 429
    assert "retry-after" in response.headers


def test_demo_refused_writes_count_toward_the_limit(set_mode):
    set_mode(PUBLIC_DEMO)
    for _ in range(DEFAULT_RULE.per_client.requests):
        assert client.delete("/applications/1").status_code == 403

    assert client.get("/config").status_code == 429


def test_demo_health_is_never_rate_limited(set_mode):
    set_mode(PUBLIC_DEMO)
    for _ in range(DEFAULT_RULE.per_client.requests + 10):
        assert client.get("/health").status_code == 200


def test_local_mode_is_not_rate_limited(set_mode):
    set_mode(LOCAL)
    for _ in range(RESUME_MATCH_RULE.per_client.requests + 5):
        assert client.post("/resume/match", json=match_body()).status_code == 200


# --- /config ----------------------------------------------------------------


def test_config_local(set_mode):
    set_mode(LOCAL)
    assert client.get("/config").json() == {"mode": "local", "read_only": False}


def test_config_public_demo(set_mode):
    set_mode(PUBLIC_DEMO)
    assert client.get("/config").json() == {
        "mode": "public_demo",
        "read_only": True,
    }
