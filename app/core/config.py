from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    secret_key: str
    access_token_expire_minutes: int
    bootstrap_superadmin_username: str | None
    bootstrap_superadmin_password: str | None


def _read_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"Invalid integer env var {name}={raw!r}") from exc


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Centralized configuration.

    Uses env vars (optionally loaded from a local .env via python-dotenv).
    """
    # Local dev convenience. In Docker Compose, env vars are provided explicitly.
    load_dotenv(override=False)

    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is required. Example: "
            "postgresql+psycopg2://postgres:postgres@localhost:5432/municipio"
        )

    secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

    return Settings(
        database_url=database_url,
        secret_key=secret_key,
        access_token_expire_minutes=_read_int("ACCESS_TOKEN_EXPIRE_MINUTES", 60),
        bootstrap_superadmin_username=os.getenv("BOOTSTRAP_SUPERADMIN_USERNAME") or None,
        bootstrap_superadmin_password=os.getenv("BOOTSTRAP_SUPERADMIN_PASSWORD") or None,
    )
