from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from enterprise_ai_platform import main
from enterprise_ai_platform.ml.inference import RiskPrediction

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


def test_predict_returns_model_result(monkeypatch: pytest.MonkeyPatch) -> None:
    prediction = RiskPrediction(
        equipment_model="PX-200",
        failure_score=0.9,
        flagged_for_review=True,
        decision_threshold=0.5,
        note="Synthetic demonstration only.",
    )
    predictor = Mock()
    predictor.predict.return_value = prediction
    monkeypatch.setattr(main, "get_predictor", lambda: predictor)

    response = client.post("/predict", json=VALID_READING)

    assert response.status_code == 200
    assert response.json() == prediction.model_dump()
    predictor.predict.assert_called_once()


@pytest.mark.parametrize(
    "invalid_reading",
    [
        {**VALID_READING, "equipment_model": "AX-100"},
        {**VALID_READING, "vibration_mm_s": -1.0},
    ],
)
def test_predict_rejects_invalid_reading(
    monkeypatch: pytest.MonkeyPatch,
    invalid_reading: dict[str, str | float],
) -> None:
    get_predictor = Mock()
    monkeypatch.setattr(main, "get_predictor", get_predictor)

    response = client.post("/predict", json=invalid_reading)

    assert response.status_code == 422
    get_predictor.assert_not_called()


def test_predict_reports_missing_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "get_predictor",
        Mock(side_effect=FileNotFoundError()),
    )

    response = client.post("/predict", json=VALID_READING)

    assert response.status_code == 503
    assert response.json() == {"detail": "Model artifact is unavailable."}
