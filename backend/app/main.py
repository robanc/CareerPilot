
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI

from backend.app.routers.applications import router as applications_router
from backend.app.routers.dashboard import router as dashboard_router
from backend.app.routers.resume import router as resume_router


app = FastAPI(
    title="CareerPilot API",
    description="Job application tracking and career preparation API",
    version="1.0.0",
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
