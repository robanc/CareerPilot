
from fastapi import FastAPI

from backend.app.routers.applications import router as applications_router
from backend.app.routers.dashboard import router as dashboard_router


app = FastAPI(
    title="CareerPilot API",
    description="Job application tracking and career preparation API",
    version="1.0.0",
)

app.include_router(applications_router)
app.include_router(dashboard_router)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
