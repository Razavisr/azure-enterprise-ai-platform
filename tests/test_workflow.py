import pytest

from enterprise_ai_platform import workflow
from enterprise_ai_platform.ml.inference import PX200Reading, RiskPrediction
from enterprise_ai_platform.rag.retrieval import ManualHit


def test_graph_retrieves_before_generating(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = ManualHit(
        id="example-1",
        equipment_model="PX-200",
        document_title="Example manual",
        section_title="Abnormal vibration",
        content="Synthetic example guidance.",
        source="px-200/example.md",
        score=0.03,
    )
    calls: list[str] = []

    def fake_search(question: str, equipment_model: str, top: int) -> list[ManualHit]:
        assert question == "What should we inspect?"
        assert equipment_model == "PX-200"
        assert top == 5
        calls.append("retrieve")
        return [hit]

    def fake_generate(question: str, hits: list[ManualHit]) -> str:
        assert question == "What should we inspect?"
        assert hits == [hit]
        calls.append("generate")
        return "See the abnormal vibration section [1]."

    monkeypatch.setattr(workflow, "search_manuals", fake_search)
    monkeypatch.setattr(workflow, "generate_grounded_answer", fake_generate)

    result = workflow.rag_graph.invoke(
        {"question": "What should we inspect?", "equipment_model": "PX-200"}
    )

    assert calls == ["retrieve", "generate"]
    assert result["hits"] == [hit]
    assert result["answer"] == "See the abnormal vibration section [1]."


def test_generation_requires_retrieved_hits() -> None:
    with pytest.raises(RuntimeError, match="retrieval step"):
        workflow.write_answer({"question": "What should we inspect?", "equipment_model": "PX-200"})


def test_diagnosis_graph_passes_readings_to_search_and_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reading = PX200Reading(
        equipment_model="PX-200",
        casing_temperature_c=96.0,
        vibration_mm_s=7.8,
        discharge_pressure_bar=4.0,
        flow_lpm=150.0,
        motor_current_a=16.0,
        hours_since_maintenance=800.0,
    )
    prediction = RiskPrediction(
        equipment_model="PX-200",
        failure_score=0.9,
        flagged_for_review=True,
        decision_threshold=0.5,
        note="Synthetic demonstration only.",
    )
    hit = ManualHit(
        id="example-1",
        equipment_model="PX-200",
        document_title="Example manual",
        section_title="Abnormal vibration",
        content="Synthetic example guidance.",
        source="px-200/example.md",
        score=0.03,
    )
    calls: list[str] = []
    queries: list[str] = []

    class FakePredictor:
        def predict(self, received: PX200Reading) -> RiskPrediction:
            assert received == reading
            calls.append("predict")
            return prediction

    def fake_search(question: str, equipment_model: str, top: int) -> list[ManualHit]:
        assert equipment_model == "PX-200"
        assert top == 5
        calls.append("retrieve")
        queries.append(question)
        return [hit]

    def fake_generate(question: str, hits: list[ManualHit]) -> str:
        assert hits == [hit]
        calls.append("generate")
        queries.append(question)
        return "Inspect the pump [1]."

    monkeypatch.setattr(workflow, "get_predictor", lambda: FakePredictor())
    monkeypatch.setattr(workflow, "search_manuals", fake_search)
    monkeypatch.setattr(workflow, "generate_grounded_answer", fake_generate)

    result = workflow.diagnosis_graph.invoke(
        {"question": "What should we inspect?", "reading": reading}
    )

    assert calls == ["predict", "retrieve", "generate"]
    assert queries[0] == queries[1]
    assert "casing temperature 96.0 C" in queries[0]
    assert "vibration 7.8 mm/s" in queries[0]
    assert result["prediction"] == prediction
    assert result["hits"] == [hit]
    assert result["answer"] == "Inspect the pump [1]."
