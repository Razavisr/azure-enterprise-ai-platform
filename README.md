# Azure AI Equipment Diagnostics Platform - ML & RAG Prototype

A working equipment-diagnostics prototype built and tested on Azure, then decommissioned on September 28, 2026. It combines a machine-learning score from sensor readings with cited guidance retrieved from equipment manuals.

**All equipment, manuals, sensor readings, and failure labels in this project are synthetic.** This is a demonstration, not a system for real maintenance decisions.

**Deployment status:** The Azure resource group was deleted after testing. The source code, synthetic data, tests, evaluation reports, and CI/CD workflows remain here. There is currently no hosted API or Azure AI Search index.

## What it does

Imagine a fictional PX-200 pump reporting a casing temperature of 96°C, vibration of 7.8 mm/s, and discharge pressure of 4.0 bar. A user asks what to inspect and what action to take.

The `POST /diagnose` endpoint returns two distinct results:

1. A score from a classifier trained on synthetic sensor readings. In the deployed test, the score was approximately `0.90`, above the demonstration threshold of `0.50`, so the reading was flagged for review.
2. An answer grounded in retrieved PX-200 manual sections. The answer cites its sources and, for these readings, reports the fictional manual’s controlled-shutdown and maintenance-inspection guidance.

The score is **not a calibrated probability of real equipment failure**, and the fictional manual must not be used to operate equipment.

## How it works

Training and document preparation happened before requests reached the application:

```text
Synthetic sensor CSV
  → Azure ML data asset
  → Azure ML training job and MLflow metrics
  → registered model version
  → trusted model file bundled into Docker

Synthetic equipment manuals
  → text splitting and Azure OpenAI embeddings
  → Azure AI Search index
```

The deployed FastAPI application ran a LangGraph workflow:

```text
POST /diagnose
  → validate question and PX-200 sensor readings
  → predict: score the reading with the model inside the container
  → retrieve: find relevant manual sections with hybrid keyword/vector search
  → generate: ask Azure OpenAI to answer using those sections
  → return {prediction, answer}
```

The model score and manual-grounded answer remain separate. The answer generator receives the question, sensor readings, and retrieved manual excerpts; it does **not** treat the model score as evidence for a manual recommendation.

During deployment, a user-assigned managed identity allowed the Container App to access Microsoft Foundry and Azure AI Search. No Azure API keys were stored in the repository or Docker image.

## Components

| Component | Purpose |
|---|---|
| FastAPI and Pydantic | Validate inputs and expose `/health`, `/ask`, `/predict`, and `/diagnose` |
| LangGraph | Orchestrate retrieval, answer generation, and combined diagnosis |
| Microsoft Foundry / Azure OpenAI | Host `gpt-5-mini` and `text-embedding-3-small` deployments |
| Azure AI Search | Store manual sections and perform equipment-filtered hybrid search |
| Azure Machine Learning | Train the classifier using a versioned synthetic data asset |
| MLflow and Azure ML model registry | Track training metrics and register the model |
| Docker, Azure Container Registry, and Container Apps | Package, store, and host the API |
| GitHub Actions | Run automatic CI and a manually triggered Azure deployment workflow |
| Structured logging | Record request IDs, request latency, and workflow-stage timing |

The model was trained and registered in Azure ML, then downloaded and included in the Docker image. **Prediction ran inside the Container App, not on an Azure ML online endpoint.** Azure Functions was not used.

The deployed API was tested through `/health`, `/predict`, and `/diagnose` before the Azure resources were deleted. The repository has **41 offline tests**. Structured observability was verified locally but was not redeployed to Azure.

## API

| Route | Input | Output |
|---|---|---|
| `GET /health` | None | Service status |
| `POST /ask` | Question and equipment model | Manual-grounded answer |
| `POST /predict` | Six PX-200 sensor readings | Model score and review flag |
| `POST /diagnose` | Question and six PX-200 readings | Prediction and cited manual-grounded answer |

`/ask` supports the fictional PX-200 and AX-100 manuals when an Azure AI Search index is configured. The trained classifier supports **PX-200 only**.

Example `/diagnose` request:

```json
{
  "question": "For this PX-200 pump, what should we inspect and what action should we take?",
  "reading": {
    "equipment_model": "PX-200",
    "casing_temperature_c": 96.0,
    "vibration_mm_s": 7.8,
    "discharge_pressure_bar": 4.0,
    "flow_lpm": 150.0,
    "motor_current_a": 16.0,
    "hours_since_maintenance": 800.0
  }
}
```

The response contains a `prediction` object and an `answer` string with retrieved source references. Search-ranking scores are not the same as the ML model score.

## Data and model

This repository includes two fictional equipment manuals and 800 synthetic PX-200 sensor rows. The classifier uses casing temperature, vibration, discharge pressure, flow, motor current, and hours since maintenance to predict a synthetic `failure_within_7_days` label.

Training compares a standard-scaler and logistic-regression pipeline with a dummy baseline. A stratified split used 600 rows for training and 200 for testing. The Azure ML run recorded:

| Metric | Synthetic-data result |
|---|---:|
| Baseline average precision | 0.190 |
| Model average precision | 0.672 |
| Model ROC-AUC | 0.868 |
| Precision at threshold 0.5 | 0.708 |
| Recall at threshold 0.5 | 0.447 |

These are demonstration metrics, **not evidence of real-world equipment reliability**. The recall of `0.447` means the model missed many simulated failures in its test set.

## Evaluation

Before decommissioning, the Azure AI Search index was evaluated with 24 synthetic questions:

| Retrieval metric | Result |
|---|---:|
| Hit@1 | 75% |
| Hit@3 | 100% |
| MRR@5 | 0.868 |
| Mean Recall@3 | 98% |

A separate 12-question answer review included eight answerable and four unanswerable questions. In that single run, all eight answerable responses cited their expected sections; the four unanswerable responses stated that the requested information was missing rather than inventing it.

These are small, self-authored tests of fictional manuals - not real-world accuracy or safety claims. The cases, saved outputs, methods, and limitations are documented in [evaluation/README.md](evaluation/README.md).

## Observability

The API code emits a JSON log for each request with a request ID, method, matched route, status code, and total duration. Responses handled by the middleware include the same ID in an `X-Request-ID` header.

The `/diagnose` workflow also logs the outcome and duration of prediction, retrieval, and answer generation. These logs do not include questions, sensor readings, request bodies, URL query values, or exception messages.

This logging was verified with a local end-to-end request, but it was **not deployed to Azure**. Stage logs do not yet carry the request ID, so they cannot reliably be matched to a particular request when requests run concurrently.

## Run locally

Use Python 3.12:

```bash
git clone https://github.com/Razavisr/azure-enterprise-ai-platform.git
cd azure-enterprise-ai-platform
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,ml]'
```

Run the offline checks without an Azure account or paid API calls:

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -q
```

Train a local model from the included synthetic CSV and save it where the API and Dockerfile expect it:

```bash
MLFLOW_ALLOW_FILE_STORE=true MLFLOW_TRACKING_URI=./mlruns \
python training/train.py \
  --data data/sensors/px200_sensor_readings.csv \
  --model-output artifacts/px200-failure-model/px200_failure_model.joblib
```

Start the API:

```bash
python -m uvicorn enterprise_ai_platform.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API documentation. With the local model file, `/health` and `/predict` work without Azure.

To use `/ask` or `/diagnose`, you must first create new Microsoft Foundry model deployments and an Azure AI Search service. Configure their endpoints in a local `.env` file based on `.env.example`, sign in with `az login`, and prepare the search index:

```bash
python -m enterprise_ai_platform.rag.create_index
python -m enterprise_ai_platform.rag.upload_manuals
```

Those commands and live RAG requests make Azure calls and require appropriate permissions. **Do not commit** `.env`, credentials, tokens, or connection strings.

The Azure ML job definition is in `azureml-train-job.yml`. It expects an Azure ML workspace and a `px200-sensor-readings:1` data asset. The original workspace and asset were deleted.

The registered model file is not stored in Git and can no longer be downloaded from the deleted workspace. Use the local training command above to create one, and only load joblib files from trusted sources.

After the model file exists, build a Linux image with:

```bash
docker build --platform linux/amd64 \
  --tag azure-enterprise-ai-platform:diagnose-local .
```

The image includes the API code and model. The manuals are retrieved from Azure AI Search at runtime. A local Docker container does not automatically inherit Azure CLI credentials; the former Azure deployment used managed identity.

## CI/CD

The GitHub Actions CI workflow runs automatically on pushes and pull requests targeting `main`. It installs the project, checks dependency compatibility, runs Ruff lint and formatting checks, performs strict mypy checking, and runs the offline pytest suite. CI does not call paid Azure services.

The separate CD workflow is **manually triggered**, not run on every push. During the completed deployment, it used GitHub OIDC authentication to download the registered Azure ML model, build and push a commit-tagged Docker image to Azure Container Registry, and update Azure Container Apps. It used a dedicated deployment identity rather than a stored Azure password or long-lived client secret.

**The CD workflow cannot run successfully as-is today.** The Azure resources and temporary deployment identity were deleted, and the GitHub environment secrets were removed after the demonstration. Reusing it would require new Azure services, a registered model, and a newly authorized identity.

## Security and limitations

During deployment, the Container App used a runtime managed identity to call Microsoft Foundry and Azure AI Search. This identity was separate from the temporary GitHub deployment identity.

The Docker container ran as a non-root Linux user, included no committed Azure API keys, and used a health check. Its model file came from the Azure ML registry during deployment.

The demonstration ingress had an IP allow rule, but the API has no application-level authentication or rate limiting. It should not be opened broadly without those controls.

Other limitations include:

- The classifier supports only the fictional PX-200 equipment model.
- The model was trained on synthetic data; its score is not a calibrated real-world failure probability.
- Retrieval can miss relevant manual sections.
- Citation numbers and expected sections were checked in a small evaluation set, but claim-level support was not automatically verified.
- Neither the synthetic score nor the fictional manual guidance should drive real maintenance decisions.

## Azure cleanup and future work

On September 28, 2026, the project resource group `rg-enterprise-ai-platform-dev` was deleted. `az group exists` returned `false`, and `az resource list` returned no active resources in the selected subscription. This removed the hosted API, registry, search index, model deployments, Azure ML workspace and assets, and supporting resources.

The Azure subscription and historical usage records were separate from the project resources. Cloud-dependent requests will not work until new services are configured.

Possible extensions include broader independent evaluation, request-ID correlation across workflow stages, infrastructure-as-code for recreating Azure resources, and application authentication before public use. Databricks and Delta Lake could optionally be added later for sensor-data preparation; the current training job intentionally reads the prepared CSV directly.