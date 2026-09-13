from pathlib import Path

import joblib  # type: ignore[import-untyped]
import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray
from pydantic import ValidationError

from enterprise_ai_platform.ml import inference

MODEL_PATH = Path("unused-model.joblib")
FEATURE_ORDER = (
    "vibration_mm_s",
    "casing_temperature_c",
    "discharge_pressure_bar",
    "flow_lpm",
    "motor_current_a",
    "hours_since_maintenance",
)


class FakePipeline:
    def __init__(self, classes: tuple[int, int] = (1, 0)) -> None:
        self.classes_ = classes
        self.seen_frame: pd.DataFrame | None = None

    def predict_proba(self, frame: pd.DataFrame) -> NDArray[np.float64]:
        self.seen_frame = frame
        return np.array([[0.8, 0.2]], dtype=np.float64)


def reading(**changes: object) -> inference.PX200Reading:
    values: dict[str, object] = {
        "equipment_model": "PX-200",
        "casing_temperature_c": 96.0,
        "vibration_mm_s": 7.8,
        "discharge_pressure_bar": 4.2,
        "flow_lpm": 150.0,
        "motor_current_a": 12.0,
        "hours_since_maintenance": 1000.0,
    }
    values.update(changes)
    return inference.PX200Reading.model_validate(values)


def bundle(pipeline: object) -> dict[str, object]:
    return {
        "pipeline": pipeline,
        "feature_columns": FEATURE_ORDER,
        "equipment_model": "PX-200",
        "decision_threshold": 0.8,
    }


def predictor(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, object]
) -> inference.PX200Predictor:
    def fake_load(path: Path) -> dict[str, object]:
        assert path == MODEL_PATH
        return payload

    monkeypatch.setattr(joblib, "load", fake_load)
    return inference.PX200Predictor(MODEL_PATH)


def test_score_uses_saved_order_and_positive_class(monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline = FakePipeline(classes=(1, 0))
    result = predictor(monkeypatch, bundle(pipeline)).predict(reading())

    frame = pipeline.seen_frame
    assert frame is not None
    assert frame.columns.tolist() == list(FEATURE_ORDER)
    assert frame.iloc[0].tolist() == [7.8, 96.0, 4.2, 150.0, 12.0, 1000.0]
    assert result.failure_score == 0.8  # Class 1 is column 0 in this fake model.
    assert result.flagged_for_review is True  # The threshold comparison includes equality.
    assert result.decision_threshold == 0.8
    assert "Synthetic" in result.note


@pytest.mark.parametrize(
    "changes",
    [
        {"equipment_model": "AX-100"},
        {"vibration_mm_s": -1.0},
        {"casing_temperature_c": float("nan")},
        {"unexpected_field": 1},
    ],
)
def test_rejects_bad_reading(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        reading(**changes)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"equipment_model": "AX-100"}, "not a PX-200"),
        ({"feature_columns": ("vibration_mm_s",)}, "features"),
        ({"pipeline": object()}, "cannot make binary"),
        ({"pipeline": FakePipeline(classes=(1, 2))}, "classes 0 and 1"),
        ({"decision_threshold": float("nan")}, "decision threshold"),
    ],
)
def test_rejects_bad_bundle(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, object], message: str
) -> None:
    payload = bundle(FakePipeline())
    payload.update(changes)
    with pytest.raises(ValueError, match=message):
        predictor(monkeypatch, payload)
