from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)

INDEX_NAME = "equipment-manuals"
EMBEDDING_DIMENSIONS = 1536
VECTOR_ALGORITHM_NAME = "manual-hnsw"
VECTOR_PROFILE_NAME = "manual-vector-profile"


def build_manual_index(index_name: str = INDEX_NAME) -> SearchIndex:
    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SimpleField(
            name="equipment_model",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SearchableField(
            name="document_title",
            type=SearchFieldDataType.String,
        ),
        SearchableField(
            name="section_title",
            type=SearchFieldDataType.String,
        ),
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
        ),
        SimpleField(
            name="source",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SimpleField(
            name="chunk_order",
            type=SearchFieldDataType.Int32,
            filterable=True,
            sortable=True,
        ),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            hidden=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name=VECTOR_PROFILE_NAME,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name=VECTOR_ALGORITHM_NAME,
                parameters=HnswParameters(
                    metric=VectorSearchAlgorithmMetric.COSINE,
                ),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE_NAME,
                algorithm_configuration_name=VECTOR_ALGORITHM_NAME,
            )
        ],
    )

    return SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search,
    )
