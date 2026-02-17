"""Centralized configuration from environment variables."""
from __future__ import annotations

import os


def _bool_env(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def is_auth_disabled() -> bool:
    """Check at call time whether auth is disabled."""
    return _bool_env("SIMCASH_AUTH_DISABLED")


AUTH_DISABLED: bool = _bool_env("SIMCASH_AUTH_DISABLED")
STORAGE_MODE: str = os.getenv("SIMCASH_STORAGE_MODE", "memory")  # memory | gcs
MOCK_DEFAULT: bool = _bool_env("SIMCASH_MOCK_DEFAULT", True)
GCS_BUCKET: str = os.getenv("SIMCASH_GCS_BUCKET", "simcash-487714-games")
CONFIGS_DIR: str = os.getenv("SIMCASH_CONFIGS_DIR", "configs")
PORT: int = int(os.getenv("PORT", "8080"))
ALLOWED_EMAILS: list[str] = [
    e.strip()
    for e in os.getenv("SIMCASH_ALLOWED_EMAILS", "").split(",")
    if e.strip()
]
