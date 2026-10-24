
import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request

from backend.app.database import (
    init_db,
    verify_demo_role_privileges,
    verify_schema,
)
from backend.app.limits import BodySizeLimitMiddleware, RateLimitMiddleware
from backend.app.observability import ObservabilityMiddleware
from backend.app.readonly import ReadOnlyMiddleware, current_settings
from backend.app.routers.applications import router as applications_router
from backend.app.routers.dashboard import router as dashboard_router
from backend.app.routers.resume import router as resume_router
from backend.app.routers.resume_library import router as resume_library_router
from backend.app.schemas import ConfigResponse, VersionResponse
from backend.app.settings import load_settings


logger = logging.getLogger(__name__)

# Render sets this to the deployed commit at build and run time.
GIT_COMMIT_ENV_VAR = "RENDER_GIT_COMMIT"
GIT_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate the operating mode before touching the database, so a
    # misconfigured Render deployment fails closed. See settings.py.
    settings = load_settings()
    app.state.settings = settings
    if settings.is_public_demo:
        logger.warning(
            "CAREERPILOT_MODE=public_demo: HTTP writes are blocked, database "
            "sessions are read-only, requests are rate limited and size "
            "limited, and startup verifies the database role is SELECT-only, "
            "but the demo role is not yet provisioned and verified; this "
            "instance is NOT SAFE TO EXPOSE publicly."
        )
        # Never create tables in public_demo; only confirm they exist.
        verify_schema()
        # Then refuse to serve unless the connected role is SELECT-only.
        # Its privileges, not the read-only session, are the boundary.
        verify_demo_role_privileges()
    else:
        # Create missing tables so a fresh deployment has a usable schema.
        # Conditional and non-destructive; see database.init_db.
        init_db()
    yield


app = FastAPI(
    title="CareerPilot API",
    description="Job application tracking and career preparation API",
    version="1.0.0",
    lifespan=lifespan,
)


# Middleware order: the last one added is the outermost, so requests pass
# CORSMiddleware -> RateLimitMiddleware -> ReadOnlyMiddleware ->
# BodySizeLimitMiddleware -> routing. CORSMiddleware is outermost so that
# 429, 403, and 413 responses carry CORS headers for allowed origins and the
# cross-origin frontend can read the message. CORS is not authorization:
# preflights are answered by CORSMiddleware without reaching the app, and
# every actual request still passes through the other three. Rate limiting
# comes first so refused writes count too; writes are refused before their
# body is read. The rate and size limits apply only in public_demo.
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(ReadOnlyMiddleware)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


app.add_middleware(ObservabilityMiddleware)
app.include_router(applications_router)
app.include_router(dashboard_router)
app.include_router(resume_router)
app.include_router(resume_library_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


@app.get("/config", tags=["Health"], response_model=ConfigResponse)
def get_config(request: Request):
    """Tell the frontend which mode is active, so it can hide write actions.

    Informational only: the backend enforces read-only mode on its own.
    """
    settings = current_settings(request.app)
    return ConfigResponse(
        mode=settings.mode.value,
        read_only=settings.is_public_demo,
    )


@app.get("/version", tags=["Health"], response_model=VersionResponse)
def get_version():
    """The deployed commit, so a release check can confirm what is live.

    Null unless RENDER_GIT_COMMIT holds a full 40-character commit SHA.
    """
    commit = os.environ.get(GIT_COMMIT_ENV_VAR, "").strip()
    return VersionResponse(
        commit=commit if GIT_COMMIT_PATTERN.fullmatch(commit) else None
    )
