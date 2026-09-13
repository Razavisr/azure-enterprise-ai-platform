from pathlib import Path

import pytest

from enterprise_ai_platform.config import get_settings
from enterprise_ai_platform.rag.embeddings import embed_texts


def test_empty_batch_returns_no_embeddings() -> None:
    assert embed_texts([]) == []


def test_blank_text_is_rejected() -> None:
    with pytest.raises(ValueError, match="Cannot embed empty text"):
        embed_texts(["valid text", "  "])


def test_missing_endpoint_has_a_clear_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_PLATFORM_AZURE_OPENAI_ENDPOINT", raising=False)
    get_settings.cache_clear()

    try:
        with pytest.raises(
            RuntimeError,
            match="AI_PLATFORM_AZURE_OPENAI_ENDPOINT must be configured",
        ):
            embed_texts(["Example text"])
    finally:
        get_settings.cache_clear()
