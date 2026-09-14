# Azure Enterprise AI Platform

A working Azure-hosted demonstration that combines a machine-learning score with equipment-manual guidance. All equipment, manuals, readings, and failure labels in this project are synthetic.

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
                     → MLflow metrics → registered model (version 1)
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
| LangGraph | Orchestrates retrieval and generation, and the combined diagnosis workflow |
| LangChain text splitters | Divides the synthetic manuals into searchable sections |
| Microsoft Foundry | Hosts `gpt-5-mini` and `text-embedding-3-small` deployments |
| Azure AI Search | Stores 13 manual sections and runs equipment-filtered hybrid keyword/vector search |
| Azure Machine Learning | Runs training on a versioned synthetic CSV data asset |
| MLflow and Azure ML model registry | Record training metrics and store model version 1 |
| Azure Container Registry and Container Apps | Store and run the `diagnose-v1` Docker image |

The model was trained and registered in Azure ML, then downloaded and copied into the Docker image. **Prediction runs inside the Container App; this project does not use an Azure ML online endpoint.** Azure Functions is not part of the current design.

The deployed Container App has been tested with `GET /health`, `POST /predict`, and `POST /diagnose`. The current local checks pass: **39 offline tests**, Ruff, and strict mypy.

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

Open `http://127.0.0.1:8000/docs` for the interactive API page. To use `/ask` or `/diagnose`, configure your own Foundry deployments and Azure AI Search service in a local `.env` file based on `.env.example`, sign in with `az login`, and prepare the search index:

```bash
python -m enterprise_ai_platform.rag.create_index
python -m enterprise_ai_platform.rag.upload_manuals
```

Those preparation commands and live RAG requests make Azure calls and require suitable access. Do not commit `.env`, credentials, tokens, or connection strings.

The Azure ML job definition is in `azureml-train-job.yml`. It expects an existing Azure ML workspace and a `px200-sensor-readings:1` data asset. The registered model file is not stored in Git. If you have access to the workspace, you can download it with `az ml model download`; otherwise, use the local training command above. Only load joblib model files from trusted sources.

After the model file exists at the expected path, build a Linux image with:

```bash
docker build --platform linux/amd64 \
  --tag azure-enterprise-ai-platform:diagnose-local .
```

The image contains the API code and model, but the manuals are retrieved from Azure AI Search at runtime. A locally running Docker container does not automatically inherit your Azure CLI credentials; the Azure deployment uses managed identity instead.

## Deployment, security, and cost

The image was built locally, pushed to a private Azure Container Registry, and deployed to Azure Container Apps. A GitHub push does **not** update the Azure deployment automatically. The repository does not yet contain infrastructure-as-code or a CI/CD pipeline to recreate and deploy every Azure resource.

The demo ingress has an IP allow rule, but the API has no application-level authentication or rate limiting. It should not be opened broadly without those controls. Generated citations are not automatically verified, retrieval can miss relevant text, and the synthetic score must not drive real maintenance decisions.

The Container App can scale to zero when idle. That does not remove charges from other Azure resources: [Azure documents scale-to-zero billing](https://learn.microsoft.com/en-us/azure/container-apps/scale-app), while [Azure AI Search has its own pricing](https://azure.microsoft.com/en-us/pricing/details/search/). Review costs and remove resources you no longer need. The code, tests, and synthetic data remain on GitHub after the cloud deployment is removed, but the live API will no longer work.

## Next steps

- Add Databricks and Delta Lake to clean and version synthetic sensor data before Azure ML training. The current Azure ML job reads the prepared CSV directly.
- Add automated deployment and infrastructure definitions.
- Improve evaluation, citation checks, model calibration, observability, authentication, and usage controls.