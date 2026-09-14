from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from enterprise_ai_platform import main
from enterprise_ai_platform.ml.inference import PX200Reading, RiskPrediction

client = TestClient(main.app)

VALID_READING: dict[str, str | float] = {
    "equipment_model": "PX-200",
    "casing_temperature_c": 96.0,
    "vibration_mm_s": 7.8,
    "discharge_pressure_bar": 4.0,
    "flow_lpm": 150.0,
    "motor_current_a": 16.0,
    "hours_since_maintenance": 800.0,
}


def test_diagnose_returns_prediction_and_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    prediction = RiskPrediction(
        equipment_model="PX-200",
        failure_score=0.9,
        flagged_for_review=True,
        decision_threshold=0.5,
        note="Synthetic demonstration only.",
    )
    graph = Mock()
    graph.invoke.return_value = {
        "prediction": prediction,
        "answer": "Inspect the bearings [1].",
    }
    monkeypatch.setattr(main, "diagnosis_graph", graph)

    response = client.post(
        "/diagnose",
        json={"question": "What should we inspect?", "reading": VALID_READING},
    )

    assert response.status_code == 200
    assert response.json() == {
        "prediction": prediction.model_dump(),
        "answer": "Inspect the bearings [1].",
    }
    graph.invoke.assert_called_once_with(
        {
            "question": "What should we inspect?",
            "reading": PX200Reading.model_validate(VALID_READING),
        }
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   ", "reading": VALID_READING},
        {
            "question": "What should we inspect?",
            "reading": {**VALID_READING, "equipment_model": "AX-100"},
        },
    ],
)
def test_diagnose_rejects_invalid_input(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object],
) -> None:
    graph = Mock()
    monkeypatch.setattr(main, "diagnosis_graph", graph)

    response = client.post("/diagnose", json=payload)

    assert response.status_code == 422
    graph.invoke.assert_not_called()


def test_diagnose_reports_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    graph = Mock()
    graph.invoke.side_effect = FileNotFoundError()
    monkeypatch.setattr(main, "diagnosis_graph", graph)

    response = client.post(
        "/diagnose",
        json={"question": "What should we inspect?", "reading": VALID_READING},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Model artifact is unavailable."}
