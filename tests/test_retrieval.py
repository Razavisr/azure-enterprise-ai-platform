import pytest

from enterprise_ai_platform.rag.retrieval import search_manuals


@pytest.mark.parametrize(
    ("question", "equipment_model", "top", "expected_message"),
    [
        ("   ", "PX-200", 3, "Question cannot be empty"),
        ("What happened?", "PX-200' OR 1", 3, "Equipment model"),
        ("What happened?", "PX-200", 0, "top must be"),
        ("What happened?", "PX-200", 11, "top must be"),
    ],
)
def test_search_rejects_invalid_inputs(
    question: str,
    equipment_model: str,
    top: int,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        search_manuals(question, equipment_model, top)
