from unittest.mock import Mock

import pytest
import structlog
from fastapi.testclient import TestClient

from enterprise_ai_platform import main, observability

client = TestClient(main.app)


def test_request_log_omits_private_input(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_logger = Mock()
    fake_graph = Mock()
    fake_graph.invoke.return_value = {"answer": "See the manual [1]."}
    monkeypatch.setattr(main, "request_logger", fake_logger)
    monkeypatch.setattr(main, "rag_graph", fake_graph)

    question = "private-canary-pump-question"
    response = client.post(
        "/ask?private_query=private-canary-query",
        json={"question": question, "equipment_model": "PX-200"},
    )

    assert response.status_code == 200
    fake_logger.info.assert_called_once()
    log_call = fake_logger.info.call_args
    assert log_call.args == ("http_request",)

    fields = log_call.kwargs
    assert fields["method"] == "POST"
    assert fields["route"] == "/ask"
    assert fields["status_code"] == 200
    assert fields["duration_ms"] >= 0
    assert fields["request_id"] == response.headers["X-Request-ID"]
    assert question not in repr(fields)
    assert "private-canary-query" not in repr(fields)


def test_stage_timer_logs_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_logger = Mock()
    monkeypatch.setattr(structlog, "get_logger", Mock(return_value=fake_logger))

    with observability.measure_stage("diagnose.predict"):
        pass

    success = fake_logger.info.call_args
    assert success.args == ("workflow_stage",)
    assert success.kwargs["stage"] == "diagnose.predict"
    assert success.kwargs["outcome"] == "ok"
    assert success.kwargs["duration_ms"] >= 0

    with pytest.raises(ValueError, match="private-canary"):
        with observability.measure_stage("diagnose.retrieve"):
            raise ValueError("private-canary")

    failure = fake_logger.error.call_args
    assert failure.kwargs["stage"] == "diagnose.retrieve"
    assert failure.kwargs["outcome"] == "error"
    assert failure.kwargs["error_type"] == "ValueError"
    assert "private-canary" not in repr(failure)
