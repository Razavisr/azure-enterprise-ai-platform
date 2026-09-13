import re
from dataclasses import dataclass

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.rag.embeddings import embed_texts


@dataclass(frozen=True)
class ManualHit:
    id: str
    equipment_model: str
    document_title: str
    section_title: str
    content: str
    source: str
    score: float


def search_manuals(
    question: str,
    equipment_model: str,
    top: int = 3,
) -> list[ManualHit]:
    clean_question = question.strip()
    model = equipment_model.strip().upper()

    if not clean_question:
        raise ValueError("Question cannot be empty.")

    if re.fullmatch(r"[A-Z0-9-]+", model) is None:
        raise ValueError("Equipment model must contain only letters, numbers, and hyphens.")

    if not 1 <= top <= 10:
        raise ValueError("top must be between 1 and 10.")

    settings = get_settings()
    search_endpoint = settings.azure_search_endpoint

    if search_endpoint is None:
        raise RuntimeError("AI_PLATFORM_AZURE_SEARCH_ENDPOINT must be configured.")

    question_vector = embed_texts([clean_question])[0]
    vector_query = VectorizedQuery(
        vector=question_vector,
        k_nearest_neighbors=max(top, 5),
        fields="content_vector",
    )

    with DefaultAzureCredential() as credential:
        with SearchClient(
            endpoint=search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        ) as client:
            results = client.search(
                search_text=clean_question,
                vector_queries=[vector_query],
                filter=f"equipment_model eq '{model}'",
                vector_filter_mode="preFilter",
                select=[
                    "id",
                    "equipment_model",
                    "document_title",
                    "section_title",
                    "content",
                    "source",
                ],
                top=top,
            )

            return [
                ManualHit(
                    id=str(result["id"]),
                    equipment_model=str(result["equipment_model"]),
                    document_title=str(result["document_title"]),
                    section_title=str(result["section_title"]),
                    content=str(result["content"]),
                    source=str(result["source"]),
                    score=float(result["@search.score"]),
                )
                for result in results
            ]
