from math import isfinite
from pathlib import Path
from typing import Literal

import joblib  # type: ignore[import-untyped]
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field


class PX200Reading(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    equipment_model: Literal["PX-200"]
    casing_temperature_c: float
    vibration_mm_s: float = Field(ge=0)
    discharge_pressure_bar: float = Field(ge=0)
    flow_lpm: float = Field(ge=0)
    motor_current_a: float = Field(ge=0)
    hours_since_maintenance: float = Field(ge=0)


class RiskPrediction(BaseModel):
    equipment_model: Literal["PX-200"]
    failure_score: float
    flagged_for_review: bool
    decision_threshold: float
    note: str


class PX200Predictor:
    def __init__(self, model_path: Path) -> None:
        # Only load a model file you trust; joblib files can execute code.
        bundle = joblib.load(model_path)
        if not isinstance(bundle, dict) or bundle.get("equipment_model") != "PX-200":
            raise ValueError("This is not a PX-200 model bundle.")

        columns = tuple(bundle.get("feature_columns", ()))
        expected = set(PX200Reading.model_fields) - {"equipment_model"}
        if len(columns) != len(expected) or set(columns) != expected:
            raise ValueError("The model's features do not match PX200Reading.")

        model = bundle.get("pipeline")
        if model is None or not hasattr(model, "predict_proba") or not hasattr(model, "classes_"):
            raise ValueError("The model cannot make binary predictions.")
        self._model = model

        classes = list(self._model.classes_)
        if set(classes) != {0, 1}:
            raise ValueError("The model must have classes 0 and 1.")

        self._positive_class_index = classes.index(1)
        self._columns = columns
        self._threshold = float(bundle["decision_threshold"])
        if not isfinite(self._threshold) or not 0 <= self._threshold <= 1:
            raise ValueError("The model has an invalid decision threshold.")

    def predict(self, reading: PX200Reading) -> RiskPrediction:
        values = reading.model_dump()
        frame = pd.DataFrame(
            [{name: values[name] for name in self._columns}],
            columns=list(self._columns),
        )
        score = float(self._model.predict_proba(frame)[0, self._positive_class_index])
        if not isfinite(score) or not 0 <= score <= 1:
            raise ValueError("The model returned an invalid score.")

        return RiskPrediction(
            equipment_model=reading.equipment_model,
            failure_score=score,
            flagged_for_review=score >= self._threshold,
            decision_threshold=self._threshold,
            note="Synthetic demonstration only; not a real-world maintenance decision.",
        )
