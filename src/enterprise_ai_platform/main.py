from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.ml.inference import PX200Reading, RiskPrediction, get_predictor
from enterprise_ai_platform.workflow import diagnosis_graph, rag_graph

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


class DiagnoseRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, pattern=r"\S")
    reading: PX200Reading


class DiagnoseResponse(BaseModel):
    prediction: RiskPrediction
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


@app.post("/predict", response_model=RiskPrediction, tags=["ml"])
def predict_failure(reading: PX200Reading) -> RiskPrediction:
    try:
        return get_predictor().predict(reading)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Model artifact is unavailable.") from exc


@app.post("/diagnose", response_model=DiagnoseResponse, tags=["workflow"])
def diagnose(request: DiagnoseRequest) -> DiagnoseResponse:
    try:
        result = diagnosis_graph.invoke(
            {
                "question": request.question,
                "reading": request.reading,
            }
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Model artifact is unavailable.") from exc

    prediction = result.get("prediction")
    answer = result.get("answer")
    if not isinstance(prediction, RiskPrediction) or not isinstance(answer, str):
        raise RuntimeError("The diagnosis workflow did not return a prediction and answer.")

    return DiagnoseResponse(prediction=prediction, answer=answer)
