from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Azure Enterprise AI Platform"
    service_name: str = "azure-enterprise-ai-platform"
    app_version: str = "0.1.0"
    environment: Literal["local", "test", "azure"] = "local"
    log_level: str = "INFO"
    azure_openai_endpoint: str | None = None
    azure_openai_chat_deployment: str = "gpt-5-mini"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_search_endpoint: str | None = None
    azure_search_index_name: str = "equipment-manuals"
    model_path: Path = Path("artifacts/px200-failure-model/px200_failure_model.joblib")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_PLATFORM_",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
