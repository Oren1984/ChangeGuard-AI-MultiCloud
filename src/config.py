from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CHANGEGUARD_", env_file=".env", extra="ignore")

    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "postgresql+psycopg://changeguard:changeguard@localhost:5432/changeguard"

    ai_provider: Literal["mock", "external"] = "mock"
    ai_external_base_url: str | None = None
    ai_external_api_key: str | None = None

    confidence_approval_threshold: float = 0.70
    confidence_hard_floor: float = 0.35

    allow_critical_cab_exception: bool = False
    kill_switch_default_active: bool = False

    max_payload_bytes: int = Field(default=1_000_000, description="Max inbound JSON payload size in bytes.")

    cors_allow_origins: list[str] = Field(default_factory=list)


@lru_cache
def get_settings() -> Settings:
    return Settings()
