"""Platform settings — Firestore-backed, cached, admin-only writes.

Stores optimization model selection and available models list.
Falls back to env vars / defaults when Firestore is unavailable (local dev).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from . import config

logger = logging.getLogger(__name__)

# Default model if nothing configured
DEFAULT_MODEL = os.environ.get("SIMCASH_DEFAULT_MODEL", "google-vertex:glm-4.7-maas")

# Built-in available models
# Gemini 3.x = preview (latest features), Gemini 2.5 = stable/GA (production)
AVAILABLE_MODELS: list[dict[str, str]] = [
    {
        "id": "google-vertex:gemini-2.5-flash",
        "label": "Gemini 2.5 Flash (Stable)",
        "provider": "google-vertex",
    },
    {
        "id": "google-vertex:gemini-2.5-pro",
        "label": "Gemini 2.5 Pro (Stable)",
        "provider": "google-vertex",
    },
    {
        "id": "google-vertex:gemini-3-flash-preview",
        "label": "Gemini 3 Flash (Preview)",
        "provider": "google-vertex",
    },
    {
        "id": "google-vertex:gemini-3-pro-preview",
        "label": "Gemini 3 Pro (Preview)",
        "provider": "google-vertex",
    },
    {
        "id": "google-vertex:gemini-2.5-flash-lite",
        "label": "Gemini 2.5 Flash Lite (Budget)",
        "provider": "google-vertex",
    },
    {
        "id": "google-vertex:glm-4.7-maas",
        "label": "GLM-4.7 (Vertex AI MaaS)",
        "provider": "google-vertex",
    },
    {
        "id": "google-vertex:glm-5-maas",
        "label": "GLM-5 (Vertex AI MaaS)",
        "provider": "google-vertex",
    },
    {
        "id": "openai:gpt-5.2",
        "label": "GPT-5.2 (OpenAI)",
        "provider": "openai",
    },
    {
        "id": "anthropic:claude-sonnet-4-5",
        "label": "Claude Sonnet 4.5 (Anthropic)",
        "provider": "anthropic",
    },
]

# Provider-specific default settings
PROVIDER_DEFAULTS: dict[str, dict[str, Any]] = {
    "openai": {
        "reasoning_effort": "high",
        "reasoning_summary": "detailed",
    },
    "google-vertex": {
        "thinking_config": {"thinking_budget": 8192},
    },
    "anthropic": {
        "thinking_budget": 8192,
    },
}


# Models that need special provider config (non-default publisher or global region)
MAAS_MODEL_CONFIG: dict[str, dict[str, Any]] = {
    "glm-4.7-maas": {
        "publisher": "zai-org",
        "region": "global",
    },
    "glm-5-maas": {
        "publisher": "zai-org",
        "region": "global",
    },
    # Gemini 3 preview models require global region
    "gemini-3-flash-preview": {
        "publisher": "google",
        "region": "global",
    },
    "gemini-3-pro-preview": {
        "publisher": "google",
        "region": "global",
    },
}


@dataclass
class PlatformSettings:
    """Current platform configuration."""

    optimization_model: str = ""
    model_settings: dict[str, Any] = field(default_factory=dict)
    available_models: list[dict[str, str]] = field(default_factory=list)
    updated_by: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        if not self.optimization_model:
            self.optimization_model = DEFAULT_MODEL
        if not self.available_models:
            self.available_models = list(AVAILABLE_MODELS)


class SettingsManager:
    """Read/write platform settings with Firestore + caching."""

    CACHE_TTL = 60  # seconds
    COLLECTION = "platform_settings"
    DOC_ID = "config"

    def __init__(self) -> None:
        self._cache: PlatformSettings | None = None
        self._cache_time: float = 0

    def _get_db(self) -> Any:
        """Get Firestore client (lazy)."""
        from firebase_admin import firestore  # type: ignore[import-untyped]

        db_id = getattr(config, "FIRESTORE_DATABASE", "(default)")
        return firestore.client(database_id=db_id)

    def _is_firestore_available(self) -> bool:
        """Check if Firestore is configured and reachable."""
        if config.is_auth_disabled() and os.environ.get("SIMCASH_STORAGE", "local") == "local":
            return False
        try:
            self._get_db()
            return True
        except Exception:
            return False

    def get_settings(self) -> PlatformSettings:
        """Get current settings (cached for CACHE_TTL seconds)."""
        now = time.time()
        if self._cache and (now - self._cache_time) < self.CACHE_TTL:
            return self._cache

        settings = self._load_from_firestore()
        # If Firestore unavailable and we have a cached copy (e.g. from
        # update_settings), keep using it instead of resetting to defaults.
        if not self._is_firestore_available() and self._cache is not None:
            self._cache_time = now  # refresh TTL
            return self._cache
        self._cache = settings
        self._cache_time = now
        return settings

    def _load_from_firestore(self) -> PlatformSettings:
        """Load settings from Firestore, falling back to defaults."""
        if not self._is_firestore_available():
            return PlatformSettings()

        try:
            db = self._get_db()
            doc = db.collection(self.COLLECTION).document(self.DOC_ID).get()
            if doc.exists:
                data = doc.to_dict()
                return PlatformSettings(
                    optimization_model=data.get("optimization_model", DEFAULT_MODEL),
                    model_settings=data.get("model_settings", {}),
                    available_models=data.get("available_models", list(AVAILABLE_MODELS)),
                    updated_by=data.get("updated_by", ""),
                    updated_at=data.get("updated_at", ""),
                )
        except Exception as e:
            logger.warning("Failed to load settings from Firestore: %s", e)

        return PlatformSettings()

    def update_settings(self, updates: dict[str, Any], admin_email: str) -> PlatformSettings:
        """Update settings in Firestore. Returns updated settings."""
        from datetime import datetime, timezone

        current = self.get_settings()

        # Apply updates (available_models first so model validation uses new list)
        if "available_models" in updates:
            current.available_models = updates["available_models"]

        if "optimization_model" in updates:
            model_id = updates["optimization_model"]
            valid_ids = {m["id"] for m in current.available_models}
            if model_id not in valid_ids:
                raise ValueError(f"Unknown model: {model_id}. Valid: {sorted(valid_ids)}")
            current.optimization_model = model_id

        if "model_settings" in updates:
            current.model_settings = updates["model_settings"]

        current.updated_by = admin_email
        current.updated_at = datetime.now(timezone.utc).isoformat()

        # Write to Firestore
        if self._is_firestore_available():
            try:
                db = self._get_db()
                db.collection(self.COLLECTION).document(self.DOC_ID).set({
                    "optimization_model": current.optimization_model,
                    "model_settings": current.model_settings,
                    "available_models": current.available_models,
                    "updated_by": current.updated_by,
                    "updated_at": current.updated_at,
                })
            except Exception as e:
                logger.error("Failed to write settings to Firestore: %s", e)
                raise

        # Invalidate cache
        self._cache = current
        self._cache_time = time.time()
        return current

    def get_llm_config(self) -> Any:
        """Build an LLMConfig from current settings.

        Returns:
            LLMConfig instance ready for pydantic-ai Agent.
        """
        from payment_simulator.llm.config import LLMConfig  # type: ignore[import-untyped]

        settings = self.get_settings()
        model = settings.optimization_model
        provider = model.split(":")[0]

        # Start with provider defaults, overlay any saved model_settings
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        merged = {**defaults, **settings.model_settings}

        return LLMConfig(
            model=model,
            temperature=merged.get("temperature", 0.0),
            max_tokens=merged.get("max_tokens", 35000),
            reasoning_effort=merged.get("reasoning_effort"),
            reasoning_summary=merged.get("reasoning_summary"),
            thinking_budget=merged.get("thinking_budget"),
            thinking_config=merged.get("thinking_config"),
        )

    def get_model_metadata(self) -> dict[str, Any]:
        """Get extra metadata for the current model (publisher, region, etc).

        MaaS models like GLM-5 need special handling:
        - Different publisher (zai-org instead of google)
        - Global region instead of project region
        """
        settings = self.get_settings()
        model = settings.optimization_model
        model_name = model.split(":", 1)[1] if ":" in model else model
        return MAAS_MODEL_CONFIG.get(model_name, {})

    def get_available_models(self) -> list[dict[str, Any]]:
        """Get available models with current selection marked."""
        settings = self.get_settings()
        result = []
        for m in settings.available_models:
            result.append({
                **m,
                "active": m["id"] == settings.optimization_model,
            })
        return result


# Singleton
settings_manager = SettingsManager()
