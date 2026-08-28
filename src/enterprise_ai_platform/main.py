from fastapi import FastAPI
from pydantic import BaseModel

from enterprise_ai_platform.config import get_settings

settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


app = FastAPI(
    title=settings.app_name,
    description="A reusable platform for enterprise AI applications.",
    version=settings.app_version,
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.service_name,
        version=settings.app_version,
    )
