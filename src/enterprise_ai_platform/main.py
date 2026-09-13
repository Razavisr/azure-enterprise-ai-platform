from fastapi import FastAPI
from pydantic import BaseModel, Field

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.workflow import rag_graph

settings = get_settings()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    equipment_model: str = Field(min_length=1, max_length=32, pattern=r"^[A-Za-z0-9-]+$")


class AskResponse(BaseModel):
    answer: str


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


@app.post("/ask", response_model=AskResponse, tags=["rag"])
def ask_question(request: AskRequest) -> AskResponse:
    result = rag_graph.invoke(
        {
            "question": request.question,
            "equipment_model": request.equipment_model,
        }
    )
    answer = result.get("answer")
    if not isinstance(answer, str):
        raise RuntimeError("The workflow did not return an answer.")
    return AskResponse(answer=answer)
