# Azure Enterprise AI Platform

A deployed and tested Azure-hosted demonstration that combines a machine-learning score with equipment-manual guidance. All equipment, manuals, readings, and failure labels in this project are synthetic.

## What the platform does

Imagine a PX-200 pump reporting a casing temperature of 96°C, vibration of 7.8 mm/s, and discharge pressure of 4.0 bar. A user asks what to inspect and what action to take.

The `POST /diagnose` API returns two separate results:

- A score from a classifier trained on synthetic sensor readings. In the deployed example, the score was approximately `0.90`, above the demonstration threshold of `0.50`, so the reading was flagged for review.
- An answer based on retrieved PX-200 manual sections. The answer cites the sections it used and, for these example readings, reports the manual’s controlled-shutdown and maintenance-inspection guidance.

**This is not real-world maintenance advice.** The score is not a calibrated probability of failure, and the fictional manual must not be used to operate equipment.

## How it works

Training and document preparation happen before a user sends a request:

```text
Synthetic sensor CSV → Azure ML data asset → Azure ML training job
                     → MLflow metrics → registered model version 1
                     → trusted model file downloaded and bundled into Docker

Synthetic manuals → LangChain text splitting → Foundry embeddings
                  → Azure AI Search index
```

At request time, the deployed FastAPI application runs a LangGraph workflow:

```text
POST /diagnose
  → validate the question and six PX-200 sensor readings
  → predict: score the reading with the model inside the container
  → retrieve: search PX-200 manual sections using keywords and vectors
  → generate: ask Foundry's gpt-5-mini to answer from those sections
  → return {prediction, answer}
```

The model score and the manual answer remain distinct. The answer generator receives the question, sensor readings, and retrieved manual excerpts; it **does not use the model score as evidence** for a manual recommendation.

The cloud application uses a user-assigned managed identity to access Foundry and Azure AI Search. No Azure API keys are stored in the repository or Docker image.

## Current implementation

| Component | Role |
|---|---|
| FastAPI | Exposes `/health`, `/ask`, `/predict`, and `/diagnose` |
| LangGraph | Orchestrates retrieval, generation, and the combined diagnosis workflow |
| LangChain text splitters | Divides the synthetic manuals into searchable sections |
| Microsoft Foundry | Hosts `gpt-5-mini` and `text-embedding-3-small` deployments |
| Azure AI Search | Stores 13 manual sections and runs equipment-filtered hybrid keyword/vector search |
| Azure Machine Learning | Runs training on a versioned synthetic CSV data asset |
| MLflow and Azure ML model registry | Record training metrics and store model version 1 |
| Azure Container Registry and Container Apps | Store commit-tagged Docker images and host the API |
| GitHub Actions | Runs automatic CI checks and manually triggered OIDC-based Azure deployment |
| Structured observability | Logs request metadata, response request IDs, and diagnosis-stage timing |

The model was trained and registered in Azure ML, then downloaded and copied into the Docker image. **Prediction runs inside the Container App; this project does not use an Azure ML online endpoint.** Azure Functions is not part of the current design.

The Container App was previously tested with `GET /health`, `POST /predict`, and `POST /diagnose`. The current source passes **41 offline tests**, Ruff linting and formatting, and strict mypy type checking. The new observability code was verified locally but has not been redeployed to Azure.

## API

| Route | Input | Output |
|---|---|---|
| `GET /health` | None | Service status |
| `POST /ask` | Question and equipment model | Manual-grounded answer |
| `POST /predict` | Six PX-200 sensor readings | Model score and review flag |
| `POST /diagnose` | Question and six PX-200 readings | Prediction plus manual-grounded answer |

`/ask` can retrieve sections for the fictional PX-200 and AX-100 manuals. The trained classifier currently supports **PX-200 only**.

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

The response contains a `prediction` object and an `answer` string with retrieved source references. Search ranking scores are not the same as the ML failure score.

## Data and model

The repository includes two fictional manuals and 800 synthetic PX-200 sensor rows. The classifier uses casing temperature, vibration, discharge pressure, flow, motor current, and hours since maintenance to predict the synthetic `failure_within_7_days` label.

Training uses a standard scaler and logistic regression, compared with a dummy baseline. A stratified split used 600 rows for training and 200 for testing. The Azure ML run recorded:

| Metric | Synthetic-data result |
|---|---:|
| Baseline average precision | 0.190 |
| Model average precision | 0.672 |
| Model ROC-AUC | 0.868 |
| Precision at threshold 0.5 | 0.708 |
| Recall at threshold 0.5 | 0.447 |

These are demonstration metrics, not evidence of real equipment reliability. Recall of `0.447` means the model missed many simulated failures in its test set.

## Evaluation

The live Azure AI Search index was tested with 24 synthetic questions: Hit@1 was 75%, Hit@3 was 100%, MRR@5 was 0.868, and mean Recall@3 was 98%. For questions needing two manual sections, both sections appeared in the top five used by the application.

A separate 12-question answer review covered eight answerable and four unanswerable questions. In this single run, all eight answers cited their expected sections, and the four unanswerable answers said the requested information was missing rather than inventing it.

These are small, self-authored tests of fictional manuals—not real-world accuracy or safety claims. The test cases, saved outputs, methods, and limitations are in [evaluation/README.md](evaluation/README.md).

## Observability

Each API request produces a JSON log with a request ID, method, matched route, status code, and total duration. The response includes the same ID in its `X-Request-ID` header. The `/diagnose` workflow also logs the outcome and duration of its prediction, retrieval, and answer-generation stages.

These logs do not include the question, sensor readings, request body, URL query values, or exception message. A local end-to-end request returned HTTP 200 and produced the three stage logs plus the total-request log. This updated logging code has not been redeployed to Azure.

Stage logs do not yet carry the request ID, so they cannot be reliably matched to a particular request when requests run concurrently.

## Run it locally

Use Python 3.12:

```bash
git clone https://github.com/Razavisr/azure-enterprise-ai-platform.git
cd azure-enterprise-ai-platform
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,ml]'
```

The tests need no Azure account or paid API calls:

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -q
```

To train a local model from the included synthetic data, save it at the path expected by the API and Dockerfile:

```bash
MLFLOW_ALLOW_FILE_STORE=true MLFLOW_TRACKING_URI=./mlruns \
python training/train.py \
  --data data/sensors/px200_sensor_readings.csv \
  --model-output artifacts/px200-failure-model/px200_failure_model.joblib
```

You can then start the API and test `/health` and `/predict` without Azure:

```bash
python -m uvicorn enterprise_ai_platform.main:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API page.

To use `/ask` or `/diagnose`, configure your own Foundry deployments and Azure AI Search service in a local `.env` file based on `.env.example`, sign in with `az login`, and prepare the search index:

```bash
python -m enterprise_ai_platform.rag.create_index
python -m enterprise_ai_platform.rag.upload_manuals
```

Those preparation commands and live RAG requests make Azure calls and require suitable access. Do not commit `.env`, credentials, tokens, or connection strings.

The Azure ML job definition is in `azureml-train-job.yml`. It expects an existing Azure ML workspace and a `px200-sensor-readings:1` data asset.

The registered model file is not stored in Git. If you have access to the workspace, you can download it with `az ml model download`; otherwise, use the local training command above. Only load joblib model files from trusted sources.

After the model file exists at the expected path, build a Linux image with:

```bash
docker build --platform linux/amd64 \
  --tag azure-enterprise-ai-platform:diagnose-local .
```

The image contains the API code and model, but the manuals are retrieved from Azure AI Search at runtime. A locally running Docker container does not automatically inherit Azure CLI credentials; the Azure deployment uses managed identity instead.

## Continuous integration

The `.github/workflows/ci.yml` workflow runs automatically for pushes and pull requests targeting `main`.

It:

1. Checks out the repository.
2. Configures Python 3.12.
3. Installs the project and development dependencies.
4. Checks installed dependency compatibility.
5. Runs Ruff linting.
6. Checks Ruff formatting.
7. Runs strict mypy type checking.
8. Runs the offline pytest suite.

The CI tests do not call Azure OpenAI, Azure AI Search, or other paid Azure services.

## Continuous deployment

The `.github/workflows/deploy.yml` workflow deploys only when manually started from GitHub Actions. A normal Git push does not deploy the application automatically.

The workflow:

1. Authenticates to Azure through OpenID Connect.
2. Downloads `px200-failure-model:1` from the Azure ML model registry.
3. Creates an image tag from the Git commit SHA.
4. Builds a Linux AMD64 Docker image on a GitHub-hosted runner.
5. Pushes the image to Azure Container Registry.
6. Updates the existing Azure Container App.
7. Reports the deployed image, revision, and running state.

The demonstrated deployment used a dedicated temporary user-assigned managed identity. Its permissions were scoped to:

- Pushing images to the project’s Azure Container Registry.
- Reading the registered model from the project’s Azure ML workspace.
- Updating the project’s Azure Container App.

GitHub exchanged its signed OIDC identity for a short-lived Azure access token. No Azure password or long-lived client secret was stored in GitHub.

After the successful deployment and health check, the temporary deployment identity and GitHub environment secrets were removed. The workflow remains in the repository as a reproducible deployment definition, but it requires a newly authorized deployment identity before it can run successfully again.

The deployment created a new Container App revision using a commit-specific image tag. The new revision passed its health check and the Container App was then stopped for cost control.

## Security and limitations

The Container App uses a separate runtime managed identity to call Microsoft Foundry and Azure AI Search. Removing the GitHub deployment identity does not affect the application’s runtime identity.

The Docker container:

- Runs as a non-root Linux user.
- Contains no committed Azure API keys.
- Uses a health check to verify the FastAPI process.
- Includes the trusted model downloaded from the Azure ML registry.

The demo ingress has an IP allow rule, but the API has no application-level authentication or rate limiting. It should not be opened broadly without those controls.

Additional limitations include:

- Citation numbers and expected sections are checked in a small evaluation set, but claim-level support is not automatically verified.
- Retrieval can miss relevant manual sections.
- The model was trained on synthetic data.
- The model score is not a calibrated real-world failure probability.
- The classifier supports only the fictional PX-200 equipment model.
- The synthetic score must not drive real maintenance decisions.

## Cost control

The Container App is stopped when the demonstration is not being used. Its minimum replica count is configured as zero.

That does not eliminate charges for every associated Azure resource:

- Azure AI Search currently uses its free tier.
- Azure Container Registry uses the Basic tier.
- Standard Azure OpenAI model deployments charge for model usage rather than merely storing the deployment.
- Azure ML does not add a separate platform charge, but its dependent Storage, Key Vault, Application Insights, Log Analytics, and compute resources can incur charges.

Review Azure Cost Management and delete resources when they are no longer required. The source code, tests, synthetic data, CI workflow, and CD workflow remain on GitHub after the Azure resources are removed, but the live API and cloud-dependent RAG requests will no longer work.

## Next steps

- Expand evaluation using independently authored questions and repeated runs.
- Correlate diagnosis-stage logs with request IDs.
- Add infrastructure-as-code definitions for recreating the Azure resources.
- Add application authentication, rate limiting, and tighter network controls before any public production use.
- Optionally add Databricks and Delta Lake to clean and version sensor data before Azure ML training. The current training job intentionally reads the prepared CSV directly.