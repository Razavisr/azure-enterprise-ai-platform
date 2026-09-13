import argparse
from pathlib import Path

import joblib
import mlflow
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = (
    "casing_temperature_c",
    "vibration_mm_s",
    "discharge_pressure_bar",
    "flow_lpm",
    "motor_current_a",
    "hours_since_maintenance",
)
TARGET_COLUMN = "failure_within_7_days"


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the synthetic PX-200 failure model.")
    parser.add_argument("--data", required=True, type=Path, help="Path to the sensor CSV")
    parser.add_argument(
        "--model-output",
        type=Path,
        default=Path("artifacts/px200_failure_model.joblib"),
        help="Where to save the trained model",
    )
    args = parser.parse_args()

    frame = pd.read_csv(args.data)

    required = set(FEATURE_COLUMNS) | {TARGET_COLUMN, "equipment_model"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Missing CSV columns: {missing}")
    if frame.empty:
        raise ValueError("The CSV has no readings.")
    if not frame["equipment_model"].eq("PX-200").all():
        raise ValueError("This model currently supports PX-200 readings only.")
    if frame[list(FEATURE_COLUMNS)].isna().any().any():
        raise ValueError("Sensor features contain missing values.")
    if not frame[TARGET_COLUMN].isin([0, 1]).all():
        raise ValueError("The failure label must contain only 0 or 1.")
    if frame[TARGET_COLUMN].nunique() != 2:
        raise ValueError("Training requires examples of both outcomes.")

    features = frame[list(FEATURE_COLUMNS)].astype(float)
    labels = frame[TARGET_COLUMN].astype(int)

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=0.25,
        random_state=42,
        stratify=labels,
    )

    baseline = DummyClassifier(strategy="prior")
    baseline.fit(x_train, y_train)

    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000, solver="liblinear"))
    model.fit(x_train, y_train)

    baseline_probabilities = baseline.predict_proba(x_test)[:, 1]
    probabilities = model.predict_proba(x_test)[:, 1]
    predictions = (probabilities >= 0.5).astype(int)

    metrics = {
        "baseline_average_precision": float(
            average_precision_score(y_test, baseline_probabilities)
        ),
        "model_average_precision": float(average_precision_score(y_test, probabilities)),
        "model_roc_auc": float(roc_auc_score(y_test, probabilities)),
        "precision_at_0_5": float(precision_score(y_test, predictions, zero_division=0)),
        "recall_at_0_5": float(recall_score(y_test, predictions, zero_division=0)),
    }

    print(f"Training rows: {len(x_train)}; test rows: {len(x_test)}")
    for name, value in metrics.items():
        print(f"{name}: {value:.3f}")
    print("These metrics describe synthetic data, not real-world equipment reliability.")
    mlflow.log_metrics(metrics)

    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": model,
            "feature_columns": FEATURE_COLUMNS,
            "equipment_model": "PX-200",
            "decision_threshold": 0.5,
        },
        args.model_output,
    )
    print(f"Saved model: {args.model_output}")


if __name__ == "__main__":
    main()
