from enterprise_ai_platform.rag.index_schema import (
    EMBEDDING_DIMENSIONS,
    INDEX_NAME,
    VECTOR_ALGORITHM_NAME,
    VECTOR_PROFILE_NAME,
    build_manual_index,
)


def test_manual_index_supports_hybrid_search() -> None:
    index = build_manual_index()
    fields = {field.name: field for field in index.fields}

    assert index.name == INDEX_NAME
    assert set(fields) == {
        "id",
        "equipment_model",
        "document_title",
        "section_title",
        "content",
        "source",
        "chunk_order",
        "content_vector",
    }

    assert fields["id"].key is True
    assert fields["equipment_model"].filterable is True
    assert fields["content"].searchable is True

    vector_field = fields["content_vector"]
    assert vector_field.searchable is True
    assert vector_field.hidden is True
    assert vector_field.vector_search_dimensions == EMBEDDING_DIMENSIONS
    assert vector_field.vector_search_profile_name == VECTOR_PROFILE_NAME

    vector_search = index.vector_search
    assert vector_search is not None

    algorithms = vector_search.algorithms
    profiles = vector_search.profiles

    assert algorithms is not None
    assert profiles is not None
    assert len(algorithms) == 1
    assert len(profiles) == 1

    assert algorithms[0].name == VECTOR_ALGORITHM_NAME
    assert profiles[0].name == VECTOR_PROFILE_NAME
