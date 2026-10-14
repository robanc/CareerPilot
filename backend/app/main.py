
from fastapi import FastAPI

app = FastAPI(
    title="CareerPilot API",
    description="Job application tracking and career preparation API",
    version="1.0.0",
)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}
