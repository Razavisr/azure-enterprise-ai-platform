from typing import cast

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import SearchIndex

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.rag.index_schema import build_manual_index


def create_or_update_manual_index() -> SearchIndex:
    settings = get_settings()
    search_endpoint = settings.azure_search_endpoint

    if search_endpoint is None:
        raise RuntimeError("AI_PLATFORM_AZURE_SEARCH_ENDPOINT must be configured.")

    index_schema = build_manual_index(settings.azure_search_index_name)

    with DefaultAzureCredential() as credential:
        with SearchIndexClient(
            endpoint=search_endpoint,
            credential=credential,
        ) as client:
            created_index = client.create_or_update_index(index_schema)
            return cast(SearchIndex, created_index)


def main() -> None:
    index = create_or_update_manual_index()
    print(f"Azure AI Search index '{index.name}' is ready with {len(index.fields)} fields.")


if __name__ == "__main__":
    main()
