# Azure Enterprise AI Platform

## What This Platform Does

This is a decision-support demonstration for **fictional industrial equipment**. Imagine a user reporting that a PX-200 pump has vibration of 7.8 mm/s and casing temperature of 96°C, then asking:

> “Is this pump at risk of failure, and what should I inspect?”

The platform is being built to combine two kinds of evidence:

1. A **failure score** from a machine-learning model trained on synthetic sensor readings.
2. **Manual-grounded guidance** retrieved from the correct equipment manual and cited in an answer.

Both parts now work, but **separately**. The complete six-feature PX-200 reading shown below scores about 0.90 with the downloaded Azure-trained model and is flagged for review. The local RAG API can retrieve PX-200 manual sections and answer the inspection question with references. An Azure Function and an expanded LangGraph workflow will connect these parts later.

> **Safety:** Equipment, readings, labels, manuals, and thresholds in this project are synthetic. A model score is not a validated real-world failure probability, and generated answers are not operating or maintenance advice.

## Current Status

| Component | What works now |
|---|---|
| FastAPI | Local `GET /health` and `POST /ask` endpoints |
| LangGraph | Two-step manual retrieval and answer-generation workflow |
| LangChain | Splits manuals into searchable sections |
| Microsoft Foundry | Deployed `gpt-5-mini` and `text-embedding-3-small` models |
| Azure AI Search | Hybrid keyword/vector search over 13 synthetic manual sections |
| Azure Machine Learning | Completed a cloud training job on a versioned synthetic CSV asset |
| MLflow | Recorded the cloud training metrics |
| Model registry | Registered `px200-failure-model`, version 1 |
| Local inference | Validates a PX-200 reading and scores it using the downloaded Azure-trained model |
| Docker and Azure Container Apps | An earlier **health-only** application image was deployed; the newer RAG and ML code is not deployed there |
| Quality checks | 30 offline tests pass; Ruff and strict mypy pass |
| Azure Functions | Planned for model inference |
| Databricks and Delta Lake | Deferred; the current training job uses the prepared CSV directly |

There is **no combined risk-and-manual API yet**. In particular, `POST /ask` currently answers from manual excerpts; it does not call the ML model.

## How the Pieces Fit Together

Training happens separately from user requests:

```text
Synthetic PX-200 sensor CSV
    → Azure ML data asset, version 1
    → Azure ML CPU training job
    → MLflow metrics and saved joblib bundle
    → registered Azure ML model, version 1
    → downloaded trusted copy for local inference
```

The current question-answering path is:

```text
Question + equipment model
    → local FastAPI POST /ask
    → LangGraph retrieves relevant manual sections
    → Azure AI Search hybrid search, filtered by equipment model
    → gpt-5-mini generates an answer using those sections
    → answer with manual references
```

The planned integration is:

```text
Structured sensor reading → Azure Function → model score
Question + equipment model → Azure AI Search → cited manual guidance
Both results → LangGraph → response that keeps prediction and manual evidence distinct
```

The search score ranks manual sections; it is **not** the model’s failure score. The manual also does not prove that a model prediction is correct.

## Demonstration Data and Model

The repository contains fictional manuals for PX-200 and AX-100 equipment, plus 800 synthetic PX-200 sensor rows. The training script uses six numeric features: casing temperature, vibration, discharge pressure, flow, motor current, and hours since maintenance. The target label is `failure_within_7_days`.

The model is a scaled logistic-regression classifier, compared with a dummy baseline. A stratified split used 600 rows for training and 200 for testing. The Azure ML run recorded:

| Metric | Synthetic-data result |
|---|---:|
| Baseline average precision | 0.190 |
| Model average precision | 0.672 |
| Model ROC-AUC | 0.868 |
| Precision at threshold 0.5 | 0.708 |
| Recall at threshold 0.5 | 0.447 |

These numbers demonstrate the pipeline, **not real equipment reliability**. In particular, recall of `0.447` means the model missed many simulated failures in the test set. The score has not been calibrated or validated for operational decisions.

`azureml-train-job.yml` defines the cloud job. It reads the versioned `px200-sensor-readings:1` data asset, uses one `Standard_D2_v2` instance, and uploads a `custom_model` output. Registering that job output as `px200-failure-model:1` was a separate Azure ML step.

## Repository Layout

```text
azure-enterprise-ai-platform/
├── azureml-train-job.yml
├── data/
│   ├── manuals/
│   └── sensors/px200_sensor_readings.csv
├── training/train.py
├── src/enterprise_ai_platform/
│   ├── config.py
│   ├── main.py
│   ├── workflow.py
│   ├── ml/inference.py
│   └── rag/
├── tests/
├── Dockerfile
├── pyproject.toml
└── README.md
```

Generated model files, local MLflow runs, `.venv`, and `.env` are excluded from Git. The repository contains the code and synthetic input data needed to understand or rerun the work, not private Azure credentials or the downloaded model binary.

## Set Up Locally

Use Python 3.12:

```bash
git clone https://github.com/Razavisr/azure-enterprise-ai-platform.git
cd azure-enterprise-ai-platform
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,ml]'
```

The tests and local model training do not need an Azure account. To use the live RAG API, you also need access to your own Microsoft Foundry deployments and Azure AI Search index. Copy `.env.example` to `.env`, fill in your endpoints, and sign in with `az login`. Never commit `.env`, keys, tokens, or connection strings.

## Run the Local RAG API

```bash
python -m uvicorn enterprise_ai_platform.main:app --reload
```

Open `http://127.0.0.1:8000/docs` and try `POST /ask`:

```json
{
  "question": "For a PX-200 pump with vibration of 7.8 mm/s and casing temperature of 96 C, what should we inspect?",
  "equipment_model": "PX-200"
}
```

The response contains an `answer` with manual references. It does **not** contain an ML score. Each live request may make billable Azure Search and Foundry calls. The endpoint currently has no authentication or usage controls and should not be deployed publicly as-is.

To prepare a search index in an Azure environment where you have appropriate access:

```bash
python -m enterprise_ai_platform.rag.create_index
python -m enterprise_ai_platform.rag.upload_manuals
```

These commands make live Azure requests.

## Train and Score Locally

To train from the synthetic CSV without Azure:

```bash
MLFLOW_ALLOW_FILE_STORE=true MLFLOW_TRACKING_URI=./mlruns \
python training/train.py --data data/sensors/px200_sensor_readings.csv
```

This creates a local model at `artifacts/px200_failure_model.joblib`. The MLflow file-store setting is for this disposable local demonstration.

To use the **registered Azure-trained model** instead, download version 1 from an Azure ML workspace you can access:

```bash
az ml model download \
  --name px200-failure-model \
  --version 1 \
  --download-path artifacts \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --workspace-name <YOUR_WORKSPACE>
```

That places the registered file under `artifacts/px200-failure-model/`. Only load model files from a source you trust; joblib deserialization can execute code.

Example inference with the downloaded Azure-trained model:

```python
from pathlib import Path

from enterprise_ai_platform.ml.inference import PX200Predictor, PX200Reading

predictor = PX200Predictor(Path("artifacts/px200-failure-model/px200_failure_model.joblib"))
reading = PX200Reading(
    equipment_model="PX-200",
    casing_temperature_c=96.0,
    vibration_mm_s=7.8,
    discharge_pressure_bar=4.0,
    flow_lpm=150.0,
    motor_current_a=16.0,
    hours_since_maintenance=800.0,
)
print(predictor.predict(reading).model_dump())
```

The `failure_score` and `flagged_for_review` fields are **synthetic-demo outputs**, not real-world recommendations.

## Run Quality Checks

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -q
```

At this checkpoint, 30 tests pass offline. They cover configuration, API behavior, manual/index preparation, retrieval input checks, LangGraph step order, model input validation, feature ordering, positive-class selection, and malformed-model checks. Tests use stand-ins rather than paid Azure calls or a private model download.

## Deployment, Cost, and Limitations

Azure Container Registry holds a private Docker image. Azure Container Apps was deployed with an earlier health-only version and a zero-minimum-replica setting. A GitHub push does **not** update that Azure deployment automatically.

The newer `/ask` code and the ML predictor currently run locally. No Azure Function or online ML endpoint has been deployed. The registered model is an asset, not a running prediction service.

Azure workspaces, storage, registries, search services, monitoring, and model calls may incur charges. Review your Azure resources when the demonstration is finished; an idle application does not guarantee zero total cost.

Remaining limitations include unverified generated citations, possible retrieval misses, an uncalibrated synthetic ML score, no combined RAG-plus-model response, no API authentication, and no automated deployment or full infrastructure-as-code setup.

## Next Milestones

1. Build a small Azure Function that serves the trusted registered model.
2. Add a LangGraph step that obtains the model score and combines it with cited manual guidance, without confusing a score with evidence.
3. Revisit Databricks and Delta Lake for repeatable sensor-data preparation.
4. Add stronger evaluation, authentication, observability, and CI/CD.
