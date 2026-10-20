"""Request rate limiting and body size limits for public_demo mode.

Both middlewares are inert in local mode, so local behavior is unchanged.
In public_demo:

- ``RateLimitMiddleware`` counts requests in fixed windows, per client and
  across all clients, and answers HTTP 429 with Retry-After when a window
  is full. POST /resume/match has a stricter rule than the read endpoints.
  /health is exempt so platform health checks are never throttled.
- ``BodySizeLimitMiddleware`` buffers at most MAX_REQUEST_BODY_BYTES of a
  request body and answers HTTP 413 beyond that, before any handler parses
  JSON. Pydantic max_length checks (schemas.py) run only after the whole
  body has been read, so this is what bounds memory per request.

Limitations (see also docs): counters live in process memory, so they reset
on restart and are per worker process. The client key is the ASGI client
address (scope["client"]); X-Forwarded-For is never trusted here. Behind a
reverse proxy, that address is the proxy's unless the server is configured
to take the client address from a trusted proxy header, in which case all
clients share one per-client budget. The global budget bounds total load
either way.
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import status
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.app.readonly import current_settings, send_json_error
from backend.app.settings import SettingsError


RATE_LIMIT_MESSAGE = "Too many requests to the public demo; please retry later."
BODY_TOO_LARGE_MESSAGE = "Request body is too large for the public demo."
INVALID_LENGTH_MESSAGE = "Invalid Content-Length header."

# Two 20,000-character fields (schemas.py) fit even when every character is
# sent as a 6-byte JSON escape; anything larger is refused before parsing.
MAX_REQUEST_BODY_BYTES = 256 * 1024

EXEMPT_PATHS = frozenset({"/health"})

# Upper bound on tracked windows. When full and nothing has expired, new
# keys are refused (fail closed) rather than growing memory without limit.
MAX_TRACKED_KEYS = 10_000


@dataclass(frozen=True)
class Limit:
    requests: int
    window_seconds: float


@dataclass(frozen=True)
class Rule:
    name: str
    per_client: Limit
    total: Limit


RESUME_MATCH_RULE = Rule(
    name="resume_match",
    per_client=Limit(requests=10, window_seconds=60),
    total=Limit(requests=120, window_seconds=60),
)
DEFAULT_RULE = Rule(
    name="default",
    per_client=Limit(requests=120, window_seconds=60),
    total=Limit(requests=1200, window_seconds=60),
)


def rule_for(method: str, path: str) -> Rule | None:
    """The rate limit rule for a request, or None for exempt paths."""
    if path in EXEMPT_PATHS:
        return None
    if method == "POST" and path == "/resume/match":
        return RESUME_MATCH_RULE
    return DEFAULT_RULE


class RateLimiter:
    """Fixed-window counters keyed by arbitrary hashable keys."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        max_tracked_keys: int = MAX_TRACKED_KEYS,
    ) -> None:
        self._clock = clock
        self._max_tracked_keys = max_tracked_keys
        # key -> (window start, count, window length)
        self._windows: dict[object, tuple[float, int, float]] = {}

    def reset(self) -> None:
        self._windows.clear()

    def _prune(self, now: float) -> None:
        expired = [
            key
            for key, (start, _, window) in self._windows.items()
            if now - start >= window
        ]
        for key in expired:
            del self._windows[key]

    def acquire(self, checks: list[tuple[object, Limit]]) -> float | None:
        """Count one request against every (key, limit) pair.

        Returns None when all limits allow it (and counts it in each), or
        the seconds until a retry can succeed (and counts nothing).
        """
        now = self._clock()
        current = []
        retry_after = 0.0

        for key, limit in checks:
            start, count, _ = self._windows.get(key, (now, 0, limit.window_seconds))
            if now - start >= limit.window_seconds:
                start, count = now, 0
            if count >= limit.requests:
                retry_after = max(retry_after, start + limit.window_seconds - now)
            current.append((key, limit, start, count))

        if retry_after > 0:
            return retry_after

        new_keys = sum(1 for key, *_ in current if key not in self._windows)
        if len(self._windows) + new_keys > self._max_tracked_keys:
            self._prune(now)
            new_keys = sum(1 for key, *_ in current if key not in self._windows)
            if len(self._windows) + new_keys > self._max_tracked_keys:
                return max(limit.window_seconds for _, limit in checks)

        for key, limit, start, count in current:
            self._windows[key] = (start, count + 1, limit.window_seconds)
        return None


# Shared by the application's middleware. Tests reset it between cases.
rate_limiter = RateLimiter()


def _public_demo(scope: Scope) -> bool:
    try:
        return current_settings(scope.get("app")).is_public_demo
    except SettingsError:
        # ReadOnlyMiddleware answers 503 for an invalid configuration.
        return False


class RateLimitMiddleware:
    """Pure ASGI middleware applying rate limits in public_demo."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter | None = None) -> None:
        self.app = app
        self.limiter = limiter if limiter is not None else rate_limiter

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _public_demo(scope):
            await self.app(scope, receive, send)
            return

        rule = rule_for(scope["method"], scope["path"])
        if rule is None:
            await self.app(scope, receive, send)
            return

        client = scope.get("client")
        client_id = client[0] if client else "unknown"
        retry_after = self.limiter.acquire(
            [
                ((rule.name, "client", client_id), rule.per_client),
                ((rule.name, "total"), rule.total),
            ]
        )
        if retry_after is not None:
            seconds = str(max(1, math.ceil(retry_after))).encode("ascii")
            await send_json_error(
                send,
                status.HTTP_429_TOO_MANY_REQUESTS,
                RATE_LIMIT_MESSAGE,
                headers=((b"retry-after", seconds),),
            )
            return

        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Pure ASGI middleware capping request body size in public_demo."""

    def __init__(
        self, app: ASGIApp, max_bytes: int = MAX_REQUEST_BODY_BYTES
    ) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not _public_demo(scope):
            await self.app(scope, receive, send)
            return

        lengths = [
            value for name, value in scope.get("headers", [])
            if name.lower() == b"content-length"
        ]
        if lengths:
            try:
                declared = {int(value) for value in lengths}
            except ValueError:
                declared = None
            if declared is None or len(declared) != 1 or min(declared) < 0:
                await send_json_error(
                    send, status.HTTP_400_BAD_REQUEST, INVALID_LENGTH_MESSAGE
                )
                return
            if declared.pop() > self.max_bytes:
                await send_json_error(
                    send,
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    BODY_TOO_LARGE_MESSAGE,
                )
                return

        # Read the whole body here (bounded), whatever Content-Length said,
        # so chunked or mislabelled bodies are capped too; then replay it.
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            if len(body) > self.max_bytes:
                await send_json_error(
                    send,
                    status.HTTP_413_CONTENT_TOO_LARGE,
                    BODY_TOO_LARGE_MESSAGE,
                )
                return
            if not message.get("more_body", False):
                break

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
