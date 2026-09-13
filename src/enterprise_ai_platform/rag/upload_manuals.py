from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.rag.embeddings import embed_texts
from enterprise_ai_platform.rag.index_schema import EMBEDDING_DIMENSIONS
from enterprise_ai_platform.rag.manual_loader import ManualChunk, load_manual_chunks


def build_search_documents(
    chunks: list[ManualChunk],
    vectors: list[list[float]],
) -> list[dict[str, object]]:
    if not chunks:
        raise ValueError("No manual chunks to upload.")

    if len(chunks) != len(vectors):
        raise ValueError("The number of chunks and vectors must match.")

    if len({chunk.id for chunk in chunks}) != len(chunks):
        raise ValueError("Manual chunk IDs must be unique.")

    documents: list[dict[str, object]] = []

    for chunk, vector in zip(chunks, vectors, strict=True):
        if len(vector) != EMBEDDING_DIMENSIONS:
            raise ValueError(
                f"Chunk {chunk.id} has {len(vector)} vector values; "
                f"expected {EMBEDDING_DIMENSIONS}."
            )

        documents.append(
            {
                "id": chunk.id,
                "equipment_model": chunk.equipment_model,
                "document_title": chunk.document_title,
                "section_title": chunk.section_title,
                "content": chunk.content,
                "source": chunk.source,
                "chunk_order": chunk.chunk_order,
                "content_vector": vector,
            }
        )

    return documents


def upload_manuals(manuals_dir: Path) -> int:
    settings = get_settings()
    search_endpoint = settings.azure_search_endpoint

    if search_endpoint is None:
        raise RuntimeError("AI_PLATFORM_AZURE_SEARCH_ENDPOINT must be configured.")

    chunks = load_manual_chunks(manuals_dir)

    with DefaultAzureCredential() as credential:
        with SearchClient(
            endpoint=search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        ) as client:
            client.get_document_count()

            vectors = embed_texts([chunk.content for chunk in chunks])
            documents = build_search_documents(chunks, vectors)
            results = client.upload_documents(documents=documents)

    failures = [
        f"{result.key}: HTTP {result.status_code} — {result.error_message}"
        for result in results
        if result.succeeded is not True
    ]
    if failures:
        raise RuntimeError("Some documents failed to upload: " + "; ".join(failures))

    if len(results) != len(documents) or {result.key for result in results} != {
        chunk.id for chunk in chunks
    }:
        raise RuntimeError("Azure AI Search did not confirm every uploaded chunk.")

    return len(results)


def main() -> None:
    count = upload_manuals(Path("data/manuals"))
    print(f"Azure AI Search accepted {count} manual chunks.")


if __name__ == "__main__":
    main()
