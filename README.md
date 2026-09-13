# Azure Enterprise AI Platform

A portfolio project exploring how to build an enterprise AI application on Microsoft Azure. It uses fictional industrial equipment and synthetic manuals to demonstrate retrieval-augmented generation (RAG), cloud deployment, and—over the next milestones—data engineering, machine learning, and workflow orchestration.

> **Status:** Active development. Manual ingestion, Azure AI Search hybrid retrieval, and grounded answer generation work from local Python code. The deployed FastAPI container currently exposes only `/health`; the new RAG workflow has **not** been deployed as an API endpoint.

> **Safety:** All equipment, readings, thresholds, and manuals are fictional. Generated answers are demonstrations, not instructions for operating real equipment.

## What Works Now

| Component | Current state |
|---|---|
| Python API | Packaged Python 3.12 FastAPI app with a typed `GET /health` endpoint |
| Docker | Non-root container image with a health check |
| Azure hosting | Development Container App, Container Registry, managed identity, and Log Analytics |
| Microsoft Foundry | `gpt-5-mini` and `text-embedding-3-small` deployments |
| Azure AI Search | Eight-field `equipment-manuals` index containing 13 synthetic manual chunks |
| Manual ingestion | Markdown splitting, embedding generation, and upload to Azure AI Search |
| Hybrid retrieval | Keyword and vector search combined with equipment-model filtering |
| RAG generation | `gpt-5-mini` answers using retrieved manual excerpts and numbered references |
| Automated checks | 15 passing tests, Ruff, and strict mypy at this checkpoint |
| LangGraph | Dependency declared; workflow not implemented yet |

The RAG code has been tested through local Python calls to Azure. It is not yet available through the deployed Container App.

## Demonstration Scenario

A user asks about a fictional `PX-200` or `AX-100` pump. The application:

1. Converts the question into an embedding with `text-embedding-3-small`.
2. Searches the correct equipment manual using both keywords and vector similarity.
3. Passes the retrieved sections to `gpt-5-mini`.
4. Returns a generated answer with numbered references and a list of retrieved sections.

The manuals deliberately use different equipment models and operating ranges so that equipment-specific filtering can be demonstrated.

The question may contain sensor readings as text. A separately trained failure-risk model and structured sensor-reading API are **not implemented yet**.

## Where Each Part Runs

| Location | Role today |
|---|---|
| GitHub | Source code, tests, Docker configuration, and synthetic manuals |
| Local Python environment | Manual ingestion, hybrid queries, and RAG answer generation |
| Microsoft Foundry | Hosted chat and embedding model deployments |
| Azure AI Search | Stores manual text, metadata, and 1,536-dimensional vectors |
| Azure Container Apps | Runs the earlier health-enabled FastAPI container; currently `/health` only |

Closing VS Code does not remove Azure resources. The development Container App is configured with zero minimum replicas and one maximum replica.

## Current RAG Flow

```text
Synthetic Markdown manuals
    → LangChain text splitters
    → Foundry embedding deployment
    → Azure AI Search index

Question + equipment model
    → question embedding
    → Azure AI Search hybrid query
    → matching manual sections
    → Foundry gpt-5-mini deployment
    → generated answer + retrieved-source list
```

The implementation uses LangChain’s text-splitting utilities. LangGraph is listed as a dependency for the next milestone, but it is not yet orchestrating this flow.

## Repository Structure

```text
azure-enterprise-ai-platform/
├── data/
│   └── manuals/
│       ├── ax-100/operation-and-maintenance.md
│       └── px-200/operation-and-maintenance.md
├── src/enterprise_ai_platform/
│   ├── config.py
│   ├── main.py
│   └── rag/
│       ├── create_index.py
│       ├── embeddings.py
│       ├── generation.py
│       ├── index_schema.py
│       ├── manual_loader.py
│       ├── retrieval.py
│       └── upload_manuals.py
├── tests/
│   ├── test_config.py
│   ├── test_embeddings.py
│   ├── test_health.py
│   ├── test_index_schema.py
│   ├── test_manual_loader.py
│   └── test_retrieval.py
├── .env.example
├── .dockerignore
├── .gitignore
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Set Up Locally

Requirements:

- Python 3.12
- Git
- An Azure subscription and Azure CLI for live Azure operations
- Permission to use the relevant Foundry deployments and Azure AI Search index
- Docker Desktop only if testing the container locally

Clone and install:

```bash
git clone https://github.com/Razavisr/azure-enterprise-ai-platform.git
cd azure-enterprise-ai-platform
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

The virtual environment isolates this project’s Python packages from other projects.

Create your private configuration file:

```bash
cp .env.example .env
```

Edit `.env` to use your own Azure OpenAI-compatible Foundry endpoint and Azure AI Search endpoint. Keep the deployment names aligned with your Azure resources. `.env` is excluded from Git; never commit credentials or access tokens.

Sign in for local Azure development:

```bash
az login
az account show --output table
```

The Python integration uses Microsoft Entra authentication through `DefaultAzureCredential`. The `OpenAI` Python library is configured to call the **Azure** endpoint; this project does not require an OpenAI API key.

## Run the API

```bash
python -m uvicorn enterprise_ai_platform.main:app --reload
```

Open:

- Health check: `http://127.0.0.1:8000/health`
- API documentation: `http://127.0.0.1:8000/docs`

At this checkpoint, the API exposes only `/health`. The RAG functions are called from Python, not from an API route.

## Create the Search Index and Upload Manuals

These commands make live Azure requests. Use a subscription and resources you are authorized to access.

```bash
python -m enterprise_ai_platform.rag.create_index
python -m enterprise_ai_platform.rag.upload_manuals
```

The current synthetic manuals produce 13 chunks: five for `AX-100` and eight for `PX-200`. Each chunk has text, source metadata, and an embedding in the `equipment-manuals` index.

The index has eight fields: `id`, `equipment_model`, `document_title`, `section_title`, `content`, `source`, `chunk_order`, and `content_vector`. The vector field has 1,536 dimensions and is not returned in ordinary search results.

## Try the RAG Flow

With `.env` configured and Azure CLI signed in:

```bash
python -c "from enterprise_ai_platform.rag.retrieval import search_manuals; from enterprise_ai_platform.rag.generation import generate_grounded_answer; q = 'For a PX-200 pump with vibration of 7.8 mm/s and casing temperature of 96 C, what should we inspect?'; hits = search_manuals(q, 'PX-200', top=5); print(generate_grounded_answer(q, hits))"
```

This performs a live embedding request, a hybrid Azure AI Search query, and a `gpt-5-mini` request. It can consume Azure credits.

Hybrid search combines keyword matching with vector similarity. The `equipment_model` filter prevents `AX-100` sections from being returned for a `PX-200` question. Search scores rank results; they are **not confidence percentages** or failure probabilities.

## Run Quality Checks

```bash
ruff check .
ruff format --check .
mypy src tests
pytest -v
```

At this checkpoint, 15 automated tests pass. They cover configuration, the health endpoint, index structure, manual loading, embedding input checks, and retrieval input checks.

These tests do **not** make live Azure calls. Manual live checks have confirmed document upload, hybrid retrieval, and answer generation. Generation quality and citation accuracy are not yet automatically tested.

## Azure Development Resources

The development environment has been provisioned manually through Azure CLI and the Azure Portal:

| Resource | Name |
|---|---|
| Resource group | `rg-enterprise-ai-platform-dev` |
| Azure Container Registry | `razavisraiplatform` |
| Managed identity | `id-enterprise-ai-platform-dev` |
| Log Analytics workspace | `log-enterprise-ai-platform-dev` |
| Container Apps environment | `cae-enterprise-ai-platform-dev` |
| Container App | `ca-enterprise-ai-api-dev` |
| Foundry resource | `aif-razavisr-platform-dev` |
| Foundry project | `enterprise-ai-platform-dev` |
| Chat deployment | `gpt-5-mini` |
| Embedding deployment | `text-embedding-3-small` |
| Azure AI Search service | `srch-razavisr-platform-dev` |
| Search index | `equipment-manuals` |

Infrastructure as code and automated deployment have not been added. The Container App still runs the health-only API version; pushing this repository to GitHub does **not** deploy the new RAG code.

## Security and Evaluation Boundaries

Current measures include synthetic data, environment-based configuration, Microsoft Entra authentication for local Azure calls, a private container registry, managed identity for container-image pulls, and non-root Docker execution.

Important unfinished work:

- The model is prompted to cite evidence, but citations and factual claims are **not programmatically verified**.
- “Retrieved sources” lists all retrieved sections, including sections the answer may not cite.
- A relevant safety section may be absent from the top search results.
- No human-review gate, API authentication, or production authorization policy is implemented.
- No automated Azure integration or RAG-quality evaluation suite exists.
- The public Container App does not expose a RAG endpoint.

The fictional manuals and generated answers must not be used for real maintenance or safety decisions.

## Next Milestones

1. Build a LangGraph workflow around retrieval and generation, then expose it through a typed FastAPI route.
2. Add evaluation cases, stronger source handling, and a human-review path for consequential recommendations.
3. Engineer synthetic sensor data with Azure Databricks and Delta Lake.
4. Train and track a small failure-risk model with Azure Machine Learning and MLflow.
5. Call that model through Azure Functions and integrate its prediction into the workflow.
6. Add observability, reproducible infrastructure, and CI/CD.

The project is intentionally incremental: each implemented component is kept distinct from planned work.