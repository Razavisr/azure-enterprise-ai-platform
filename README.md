# Azure Enterprise AI Platform

## What This Platform Is Building

This project is a decision-support demo for **fictional industrial equipment**. A user provides an equipment model, sensor readings, and a question such as:

> “My PX-200 pump has vibration of 7.8 mm/s and casing temperature of 96°C. Is it at risk of failure, and what should I inspect?”

The **finished platform** will combine two different kinds of information:

1. **A failure-risk prediction** from a small machine-learning model trained on synthetic sensor history.
2. **Manual-grounded guidance** retrieved from the correct equipment manual and cited in the answer.

An illustrative future answer would look like this:

> **Predicted risk:** Elevated failure risk. *(Illustrative—the ML model has not been built yet.)*  
> **Manual evidence:** The fictional PX-200 manual treats vibration above 7.1 mm/s together with casing temperature above 90°C as a high-severity condition [1].  
> **Suggested demo action:** Follow the manual’s controlled-shutdown and maintenance-inspection procedure; inspect bearings, alignment, lubrication, and suction conditions [1][2].

The prediction and the manual evidence have different roles: the **model estimates risk from sensor patterns**, while **RAG finds relevant written guidance**. The manual does not prove that the prediction is correct.

> **Safety:** All equipment, readings, thresholds, and manuals are synthetic. This is a portfolio demonstration, not guidance for operating real equipment.

## What Works Today

**The RAG portion works locally.** A FastAPI `POST /ask` endpoint accepts a question and equipment model. A two-step LangGraph workflow retrieves sections from Azure AI Search and uses `gpt-5-mini` on Microsoft Foundry to generate an answer with manual references.

**The failure-risk prediction does not exist yet.** Sensor readings can be included as text in today’s question, but the application does not currently run an ML model or calculate a failure probability.

| Component | Current status |
|---|---|
| FastAPI | Local typed `GET /health` and `POST /ask` endpoints |
| LangGraph | Working two-step workflow: retrieve manual sections, then generate an answer |
| Microsoft Foundry | Deployed `gpt-5-mini` chat and `text-embedding-3-small` embedding models |
| Azure AI Search | Hybrid keyword and vector search over 13 synthetic manual chunks |
| LangChain | Text splitting during manual preparation |
| Docker | Non-root application image with a health check |
| Azure Container Apps | Runs an earlier **health-only** image; `/ask` is not deployed there |
| Tests | 20 passing offline tests, plus Ruff and strict mypy |
| Databricks, Azure ML, Azure Functions | Planned; not implemented yet |

## Architecture

### Before a user asks a question — planned data and ML pipeline

```text
Synthetic historical sensor readings
    → Azure Databricks data preparation
    → Delta Lake dataset
    → Azure Machine Learning training
    → MLflow experiment tracking and model registration
```

Training happens separately; the platform will **not retrain the model for every question**.

### When a user asks a question

```text
TODAY
Question + equipment model
    → local FastAPI POST /ask
    → LangGraph retrieval step
        → text-embedding-3-small
        → Azure AI Search hybrid query, filtered by equipment model
    → LangGraph generation step
        → gpt-5-mini uses retrieved manual excerpts
    → answer with numbered references
```

```text
PLANNED EXTENSION
Structured sensor readings
    → Azure Function returns a prediction from the trained model
    → LangGraph combines the prediction with retrieved manual evidence
    → answer separates predicted risk from cited manual guidance
```

The current LangGraph workflow is deliberately simple: **retrieve, then generate**. It is not a general-purpose autonomous agent.

## Demonstration Data

The repository contains synthetic operation-and-maintenance manuals for two fictional equipment models, `PX-200` and `AX-100`. The manuals have different operating ranges so equipment-model filtering can be demonstrated.

The preparation code splits the manuals into 13 sections, generates 1,536-dimensional embeddings, and uploads the sections, metadata, and vectors to Azure AI Search. Hybrid search combines word matching with vector similarity. Search scores rank results; they are **not** failure probabilities or confidence percentages.

## Repository Structure

```text
azure-enterprise-ai-platform/
├── data/manuals/
│   ├── ax-100/operation-and-maintenance.md
│   └── px-200/operation-and-maintenance.md
├── src/enterprise_ai_platform/
│   ├── config.py
│   ├── main.py
│   ├── workflow.py
│   └── rag/
│       ├── create_index.py
│       ├── embeddings.py
│       ├── generation.py
│       ├── index_schema.py
│       ├── manual_loader.py
│       ├── retrieval.py
│       └── upload_manuals.py
├── tests/
├── .env.example
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Set Up Locally

You need Python 3.12, Azure CLI, an Azure subscription, and permission to use your Foundry deployments and Azure AI Search index.

```bash
git clone https://github.com/Razavisr/azure-enterprise-ai-platform.git
cd azure-enterprise-ai-platform
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
az login
```

Edit `.env` with your own Azure OpenAI-compatible Foundry endpoint and Azure AI Search endpoint. **Do not commit `.env`, keys, tokens, or connection strings.** The Python code uses Microsoft Entra authentication through `DefaultAzureCredential`; the `OpenAI` Python library is configured to call an **Azure** endpoint.

## Run the Current RAG API

```bash
python -m uvicorn enterprise_ai_platform.main:app --reload
```

Open `http://127.0.0.1:8000/docs`, expand **POST /ask**, and select **Try it out**. Example request supported **today**:

```json
{
  "question": "For a PX-200 pump with vibration of 7.8 mm/s and casing temperature of 96 C, what should we inspect?",
  "equipment_model": "PX-200"
}
```

The response contains an `answer` with manual references and a retrieved-source list. It does **not** contain an ML risk prediction yet. Each real request makes Azure Search and model calls and may consume Azure credit.

The API is for **local testing only** at this stage. It has no authentication or usage controls, so `/ask` must not be deployed publicly yet.

## Prepare the Search Index

These commands make live Azure requests:

```bash
python -m enterprise_ai_platform.rag.create_index
python -m enterprise_ai_platform.rag.upload_manuals
```

The index currently contains 13 synthetic manual chunks. Its fields hold chunk IDs, equipment models, titles, section text, source paths, chunk order, and embedding vectors.

## Run Quality Checks

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -q
```

At this checkpoint, **20 automated tests pass**. They cover configuration, API behavior, index structure, manual loading, embedding and retrieval input checks, and LangGraph step order. Tests use stand-ins instead of making paid Azure calls.

Separate live local checks confirmed manual upload, hybrid retrieval, answer generation, LangGraph execution, and the `/ask` response.

## Cloud Deployment Status

Azure Container Registry stores a private Docker image. Azure Container Apps runs the earlier application image with `/health`, and Log Analytics receives its logs. The Container App uses a managed identity for image pulls and is configured to allow zero minimum replicas.

The newer RAG API code runs **locally** and is in GitHub, but has **not** been deployed to Container Apps. Pushing a commit to GitHub does not update the running Azure container.

Infrastructure as code and automated deployment have not been added.

## Current Limitations

- The ML prediction, Databricks pipeline, and Azure Functions integration are not implemented.
- Model-generated claims and citation numbers are not programmatically verified.
- The retrieved-source list can include sections the answer does not cite.
- Retrieval may miss a relevant manual section.
- The local `/ask` endpoint has no authentication, rate limit, or production authorization policy.
- There is no automated RAG-quality evaluation suite or human-review process.

## Next Milestones

1. Add a small RAG evaluation set and improve source handling.
2. Prepare synthetic sensor data with Azure Databricks and Delta Lake.
3. Train and track a failure-risk model with Azure Machine Learning and MLflow.
4. Use Azure Functions for prediction and combine the result with manual retrieval in LangGraph.
5. Add authentication and usage controls before deploying `/ask` publicly.
6. Add observability, reproducible infrastructure, and CI/CD.