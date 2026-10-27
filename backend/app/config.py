from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_prefix="AIVANTA_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://aivanta:aivanta@localhost:5432/aivanta"
    jwt_secret: str = Field(default="dev-only-insecure-secret-change-me-000000", min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 8 * 60
    cors_origins: str = "http://localhost:3000"
    demo_password: str = "aivanta-demo"
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
