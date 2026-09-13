from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.rag.index_schema import EMBEDDING_DIMENSIONS

AZURE_AI_SCOPE = "https://ai.azure.com/.default"


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    if any(not text.strip() for text in texts):
        raise ValueError("Cannot embed empty text.")

    settings = get_settings()
    if settings.azure_openai_endpoint is None:
        raise RuntimeError("AI_PLATFORM_AZURE_OPENAI_ENDPOINT must be configured.")

    base_url = f"{settings.azure_openai_endpoint.rstrip('/')}/openai/v1/"

    with DefaultAzureCredential() as credential:
        token_provider = get_bearer_token_provider(credential, AZURE_AI_SCOPE)

        with OpenAI(base_url=base_url, api_key=token_provider) as client:
            response = client.embeddings.create(
                model=settings.azure_openai_embedding_deployment,
                input=texts,
                dimensions=EMBEDDING_DIMENSIONS,
                encoding_format="float",
            )

    ordered_results = sorted(response.data, key=lambda item: item.index)
    vectors = [item.embedding for item in ordered_results]

    if len(vectors) != len(texts) or any(len(vector) != EMBEDDING_DIMENSIONS for vector in vectors):
        raise RuntimeError("Azure returned an unexpected number or size of embeddings.")

    return vectors
