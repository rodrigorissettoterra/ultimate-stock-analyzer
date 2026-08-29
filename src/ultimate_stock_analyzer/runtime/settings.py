from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="USA_",
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )

    env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    database_url: str = ""
    data_dir: Path = Path("./data")
    worker_heartbeat_seconds: int = Field(default=300, ge=30, le=86400)
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = ""
    llm_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    http_user_agent: str = "ultimate-stock-analyzer/0.1"

    @model_validator(mode="after")
    def require_database_in_production(self) -> RuntimeSettings:
        if self.env == "production" and not self.database_url.strip():
            raise ValueError("USA_DATABASE_URL is required in production")
        return self
