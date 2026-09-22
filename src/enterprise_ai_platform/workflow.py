from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from enterprise_ai_platform.ml.inference import PX200Reading, RiskPrediction, get_predictor
from enterprise_ai_platform.observability import measure_stage
from enterprise_ai_platform.rag.generation import generate_grounded_answer
from enterprise_ai_platform.rag.retrieval import ManualHit, search_manuals


class RagState(TypedDict):
    question: str
    equipment_model: str
    hits: NotRequired[list[ManualHit]]
    answer: NotRequired[str]


def retrieve_manuals(state: RagState) -> dict[str, list[ManualHit]]:
    hits = search_manuals(state["question"], state["equipment_model"], top=5)
    return {"hits": hits}


def write_answer(state: RagState) -> dict[str, str]:
    hits = state.get("hits")
    if hits is None:
        raise RuntimeError("The retrieval step must run before answer generation.")

    return {"answer": generate_grounded_answer(state["question"], hits)}


builder = StateGraph(RagState)
builder.add_node("retrieve", retrieve_manuals)
builder.add_node("generate", write_answer)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", END)

rag_graph = builder.compile()


class DiagnosisState(TypedDict):
    question: str
    reading: PX200Reading
    prediction: NotRequired[RiskPrediction]
    hits: NotRequired[list[ManualHit]]
    answer: NotRequired[str]


def build_diagnosis_question(state: DiagnosisState) -> str:
    question = state["question"].strip()
    if not question:
        raise ValueError("Question cannot be empty.")

    reading = state["reading"]
    return (
        f"{question}\n"
        f"Reported {reading.equipment_model} readings: "
        f"casing temperature {reading.casing_temperature_c} C; "
        f"vibration {reading.vibration_mm_s} mm/s; "
        f"discharge pressure {reading.discharge_pressure_bar} bar; "
        f"flow {reading.flow_lpm} L/min; "
        f"motor current {reading.motor_current_a} A; "
        f"hours since maintenance {reading.hours_since_maintenance}."
    )


def predict_risk(state: DiagnosisState) -> dict[str, RiskPrediction]:
    with measure_stage("diagnose.predict"):
        prediction = get_predictor().predict(state["reading"])
    return {"prediction": prediction}


def retrieve_diagnosis_manuals(state: DiagnosisState) -> dict[str, list[ManualHit]]:
    with measure_stage("diagnose.retrieve"):
        hits = search_manuals(
            build_diagnosis_question(state),
            state["reading"].equipment_model,
            top=5,
        )
    return {"hits": hits}


def write_diagnosis_answer(state: DiagnosisState) -> dict[str, str]:
    hits = state.get("hits")
    if hits is None:
        raise RuntimeError("The retrieval step must run before answer generation.")

    with measure_stage("diagnose.generate"):
        answer = generate_grounded_answer(build_diagnosis_question(state), hits)
    return {"answer": answer}


diagnosis_builder = StateGraph(DiagnosisState)
diagnosis_builder.add_node("predict", predict_risk)
diagnosis_builder.add_node("retrieve", retrieve_diagnosis_manuals)
diagnosis_builder.add_node("generate", write_diagnosis_answer)
diagnosis_builder.add_edge(START, "predict")
diagnosis_builder.add_edge("predict", "retrieve")
diagnosis_builder.add_edge("retrieve", "generate")
diagnosis_builder.add_edge("generate", END)

diagnosis_graph = diagnosis_builder.compile()
