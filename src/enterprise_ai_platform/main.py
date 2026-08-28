from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


app = FastAPI(
    title="Azure Enterprise AI Platform",
    description="A reusable platform for enterprise AI applications.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service="azure-enterprise-ai-platform",
        version=app.version,
    )
