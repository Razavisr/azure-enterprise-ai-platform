import pytest
from fastapi.testclient import TestClient

from enterprise_ai_platform import main

client = TestClient(main.app)


def test_ask_returns_workflow_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeGraph:
        def invoke(self, state: dict[str, str]) -> dict[str, str]:
            assert state == {
                "question": "What should we inspect?",
                "equipment_model": "PX-200",
            }
            return {"answer": "Inspect the bearings [1]."}

    monkeypatch.setattr(main, "rag_graph", FakeGraph())

    response = client.post(
        "/ask",
        json={
            "question": "What should we inspect?",
            "equipment_model": "PX-200",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"answer": "Inspect the bearings [1]."}


@pytest.mark.parametrize(
    "payload",
    [
        {"question": "   ", "equipment_model": "PX-200"},
        {"question": "What happened?", "equipment_model": "PX-200' OR 1=1"},
    ],
)
def test_ask_rejects_invalid_input(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, str]
) -> None:
    class FailGraph:
        def invoke(self, state: dict[str, str]) -> dict[str, str]:
            raise AssertionError("The graph must not run for invalid input.")

    monkeypatch.setattr(main, "rag_graph", FailGraph())

    response = client.post("/ask", json=payload)

    assert response.status_code == 422
