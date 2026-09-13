import pytest

from enterprise_ai_platform import workflow
from enterprise_ai_platform.rag.retrieval import ManualHit


def test_graph_retrieves_before_generating(monkeypatch: pytest.MonkeyPatch) -> None:
    hit = ManualHit(
        id="example-1",
        equipment_model="PX-200",
        document_title="Example manual",
        section_title="Abnormal vibration",
        content="Synthetic example guidance.",
        source="px-200/example.md",
        score=0.03,
    )
    calls: list[str] = []

    def fake_search(question: str, equipment_model: str, top: int) -> list[ManualHit]:
        assert question == "What should we inspect?"
        assert equipment_model == "PX-200"
        assert top == 5
        calls.append("retrieve")
        return [hit]

    def fake_generate(question: str, hits: list[ManualHit]) -> str:
        assert question == "What should we inspect?"
        assert hits == [hit]
        calls.append("generate")
        return "See the abnormal vibration section [1]."

    monkeypatch.setattr(workflow, "search_manuals", fake_search)
    monkeypatch.setattr(workflow, "generate_grounded_answer", fake_generate)

    result = workflow.rag_graph.invoke(
        {"question": "What should we inspect?", "equipment_model": "PX-200"}
    )

    assert calls == ["retrieve", "generate"]
    assert result["hits"] == [hit]
    assert result["answer"] == "See the abnormal vibration section [1]."


def test_generation_requires_retrieved_hits() -> None:
    with pytest.raises(RuntimeError, match="retrieval step"):
        workflow.write_answer({"question": "What should we inspect?", "equipment_model": "PX-200"})
