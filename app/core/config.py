from __future__ import annotations
from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DOTENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    app_name: str = "venue-backend"
    environment: Literal["development", "production", "test"] = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000"]

    database_url: str
    db_pool_size: int = 5

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_username: str = ""
    redis_password: SecretStr = SecretStr("")

    # JWT
    jwt_secret_key: SecretStr = SecretStr("dev-only-jwt-secret-DO-NOT-USE-IN-PROD")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expires_minutes: int = 30
    jwt_refresh_token_expires_days: int = 7

    # Argon2 (defaults follow OWASP 2024; tests override to cheap params)
    argon2_time_cost: int = 3
    argon2_memory_cost_kib: int = 12_288
    argon2_parallelism: int = 1

    model_config = SettingsConfigDict(
        env_prefix="BACKEND_",
        env_file=DOTENV_PATH,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
