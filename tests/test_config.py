from pathlib import Path

import pytest
from pydantic import ValidationError

from enterprise_ai_platform.config import Settings


def test_settings_use_safe_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AI_PLATFORM_ENVIRONMENT", raising=False)
    monkeypatch.delenv("AI_PLATFORM_LOG_LEVEL", raising=False)

    settings = Settings()

    assert settings.environment == "local"
    assert settings.log_level == "INFO"


def test_settings_read_environment_variables(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLATFORM_ENVIRONMENT", "azure")
    monkeypatch.setenv("AI_PLATFORM_LOG_LEVEL", "DEBUG")

    settings = Settings()

    assert settings.environment == "azure"
    assert settings.log_level == "DEBUG"


def test_settings_reject_invalid_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AI_PLATFORM_ENVIRONMENT", "incorrect")

    with pytest.raises(ValidationError):
        Settings()


def test_settings_read_azure_service_configuration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "AI_PLATFORM_AZURE_OPENAI_ENDPOINT",
        "https://example-openai.openai.azure.com",
    )
    monkeypatch.setenv(
        "AI_PLATFORM_AZURE_SEARCH_ENDPOINT",
        "https://example-search.search.windows.net",
    )
    monkeypatch.setenv(
        "AI_PLATFORM_AZURE_SEARCH_INDEX_NAME",
        "test-manuals",
    )

    settings = Settings()

    assert settings.azure_openai_endpoint == "https://example-openai.openai.azure.com"
    assert settings.azure_search_endpoint == "https://example-search.search.windows.net"
    assert settings.azure_search_index_name == "test-manuals"
