
import logging
from contextlib import asynccontextmanager

from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from backend.app.database import init_db
from backend.app.routers.applications import router as applications_router
from backend.app.routers.dashboard import router as dashboard_router
from backend.app.routers.resume import router as resume_router
from backend.app.settings import load_settings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate the operating mode before touching the database, so a
    # misconfigured Render deployment fails closed. See settings.py.
    settings = load_settings()
    app.state.settings = settings
    if settings.is_public_demo:
        logger.warning(
            "CAREERPILOT_MODE=public_demo: write restrictions are NOT "
            "implemented yet; this instance is NOT SAFE TO EXPOSE publicly."
        )

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


app.include_router(applications_router)
app.include_router(dashboard_router)
app.include_router(resume_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
