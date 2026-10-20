"""Read-only HTTP enforcement for public_demo mode.

Two independent layers block writes when CAREERPILOT_MODE=public_demo:

1. ``ReadOnlyMiddleware`` -- a fail-closed method allowlist, wrapped only by
   CORSMiddleware (which adds CORS headers to its responses). Only GET, HEAD,
   and OPTIONS requests pass, plus POST to exactly ``/resume/match``.
   Everything else gets HTTP 403 before routing, so no handler or database
   session runs. The check uses only the ASGI scope's method and path as
   received by the server; headers such as X-HTTP-Method-Override,
   X-Original-URL, or X-Forwarded-Prefix are never consulted. Paths are compared exactly, so trailing-slash, double-slash,
   and case variants of the allowed path are blocked rather than redirected.
2. ``require_writable`` -- a route dependency on every application create,
   update, and delete endpoint. It still blocks writes if the middleware is
   removed, reordered, or bypassed.

In local mode both layers are inert and full CRUD is available.

WARNING: this is HTTP-level protection only. It does not make the database
read-only. Rate limiting and the request body size limit live in limits.py,
and resume input lengths are capped in schemas.py. public_demo is still NOT
SAFE TO DEPLOY until the SELECT-only demo role is provisioned and verified.
"""

import json

from fastapi import HTTPException, Request, status
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.settings import Settings, SettingsError, load_settings


READ_ONLY_MESSAGE = (
    "CareerPilot is running as a read-only public demo; "
    "creating, updating, and deleting data is disabled."
)
CONFIG_ERROR_MESSAGE = (
    "CareerPilot is misconfigured; requests are refused until the "
    "operating mode is fixed."
)

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
ALLOWED_POST_PATHS = frozenset({"/resume/match"})


def current_settings(app) -> Settings:
    """Return the settings stored at startup, or load them from the environment.

    Startup stores settings on ``app.state``. When it has not run (for
    example ``TestClient(app)`` without a ``with`` block), the environment is
    read on every call rather than cached, so nothing stale is reused.
    """
    settings = getattr(app.state, "settings", None) if app is not None else None
    if settings is None:
        settings = load_settings()
    return settings


def is_request_allowed(method: str, path: str) -> bool:
    """Allowlist check for public_demo. Exact, case-sensitive matches only."""
    if method in SAFE_METHODS:
        return True
    return method == "POST" and path in ALLOWED_POST_PATHS


async def send_json_error(
    send: Send,
    status_code: int,
    detail: str,
    headers: tuple[tuple[bytes, bytes], ...] = (),
) -> None:
    """Send a complete {"detail": ...} JSON response from ASGI middleware."""
    body = json.dumps({"detail": detail}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                *headers,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class ReadOnlyMiddleware:
    """Pure ASGI middleware enforcing the public_demo method allowlist."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            await self.app(scope, receive, send)
            return

        try:
            settings = current_settings(scope.get("app"))
        except SettingsError:
            # Fail closed: an invalid mode never falls back to local.
            if scope["type"] == "http":
                await send_json_error(
                    send, status.HTTP_503_SERVICE_UNAVAILABLE, CONFIG_ERROR_MESSAGE
                )
            else:
                await send({"type": "websocket.close", "code": 1011})
            return

        if not settings.is_public_demo:
            await self.app(scope, receive, send)
            return

        if scope["type"] != "http":
            # No websocket (or other) endpoints exist; refuse them outright.
            await send({"type": "websocket.close", "code": 1008})
            return

        if not is_request_allowed(scope["method"], scope["path"]):
            await send_json_error(send, status.HTTP_403_FORBIDDEN, READ_ONLY_MESSAGE)
            return

        await self.app(scope, receive, send)


def require_writable(request: Request) -> None:
    """Route dependency: reject writes in public_demo, independent of middleware."""
    if current_settings(request.app).is_public_demo:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=READ_ONLY_MESSAGE,
        )
