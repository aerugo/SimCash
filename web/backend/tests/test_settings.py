"""Tests for platform settings (model selection)."""
import os
import pytest
from unittest.mock import patch, MagicMock

# Force auth disabled for tests
os.environ.setdefault("SIMCASH_AUTH_DISABLED", "true")
os.environ.setdefault("SIMCASH_STORAGE", "local")

from app.settings import (
    SettingsManager,
    PlatformSettings,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
    PROVIDER_DEFAULTS,
    MAAS_MODEL_CONFIG,
)


class TestPlatformSettings:
    """Test PlatformSettings dataclass."""

    def test_defaults(self):
        s = PlatformSettings()
        assert s.optimization_model == DEFAULT_MODEL
        assert len(s.available_models) == len(AVAILABLE_MODELS)

    def test_custom_model(self):
        s = PlatformSettings(optimization_model="google-vertex:gemini-2.5-pro")
        assert s.optimization_model == "google-vertex:gemini-2.5-pro"

    def test_empty_model_falls_back(self):
        s = PlatformSettings(optimization_model="")
        assert s.optimization_model == DEFAULT_MODEL


class TestSettingsManager:
    """Test SettingsManager without Firestore."""

    def test_get_settings_returns_defaults(self):
        mgr = SettingsManager()
        s = mgr.get_settings()
        assert s.optimization_model == DEFAULT_MODEL
        assert "glm-4.7-maas" in DEFAULT_MODEL  # GLM 4.7 MaaS is default
        assert len(s.available_models) == len(AVAILABLE_MODELS)

    def test_get_settings_cached(self):
        mgr = SettingsManager()
        s1 = mgr.get_settings()
        s2 = mgr.get_settings()
        assert s1 is s2  # Same object = cached

    def test_get_llm_config_openai(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="openai:gpt-5.2")
        mgr._cache_time = float("inf")  # Never expire

        config = mgr.get_llm_config()
        assert config.model == "openai:gpt-5.2"
        assert config.provider == "openai"
        assert config.reasoning_effort == "high"
        assert config.reasoning_summary == "detailed"

    def test_get_llm_config_vertex(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="google-vertex:gemini-2.5-pro")
        mgr._cache_time = float("inf")

        config = mgr.get_llm_config()
        assert config.model == "google-vertex:gemini-2.5-pro"
        assert config.provider == "google-vertex"
        assert config.thinking_config is not None
        assert config.thinking_config["thinking_budget"] == 8192

    def test_get_llm_config_anthropic(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="anthropic:claude-sonnet-4-5")
        mgr._cache_time = float("inf")

        config = mgr.get_llm_config()
        assert config.model == "anthropic:claude-sonnet-4-5"
        assert config.thinking_budget == 8192

    def test_get_llm_config_with_custom_settings(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(
            optimization_model="openai:gpt-5.2",
            model_settings={"temperature": 0.5, "max_tokens": 10000},
        )
        mgr._cache_time = float("inf")

        config = mgr.get_llm_config()
        assert config.temperature == 0.5
        assert config.max_tokens == 10000

    def test_get_available_models(self):
        mgr = SettingsManager()
        models = mgr.get_available_models()
        assert len(models) == len(AVAILABLE_MODELS)
        # Default model should be marked active
        active = [m for m in models if m.get("active")]
        assert len(active) == 1
        assert active[0]["id"] == DEFAULT_MODEL

    def test_get_available_models_marks_correct_active(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="google-vertex:gemini-2.5-pro")
        mgr._cache_time = float("inf")

        models = mgr.get_available_models()
        active = [m for m in models if m.get("active")]
        assert active[0]["id"] == "google-vertex:gemini-2.5-pro"

    def test_get_llm_config_glm5(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="google-vertex:glm-5-maas")
        mgr._cache_time = float("inf")

        config = mgr.get_llm_config()
        assert config.model == "google-vertex:glm-5-maas"
        assert config.model_name == "glm-5-maas"
        assert config.provider == "google-vertex"

    def test_glm5_maas_metadata(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="google-vertex:glm-5-maas")
        mgr._cache_time = float("inf")

        meta = mgr.get_model_metadata()
        assert meta["publisher"] == "zai-org"
        assert meta["region"] == "global"

    def test_non_maas_no_metadata(self):
        mgr = SettingsManager()
        mgr._cache = PlatformSettings(optimization_model="google-vertex:gemini-2.5-flash")
        mgr._cache_time = float("inf")

        meta = mgr.get_model_metadata()
        assert meta == {}

    def test_update_validates_model(self):
        mgr = SettingsManager()
        with pytest.raises(ValueError, match="Unknown model"):
            mgr.update_settings({"optimization_model": "fake:model"}, "admin@test.com")


class TestSettingsAPI:
    """Test settings API endpoints."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_get_models_list(self, client):
        resp = client.get("/api/settings/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) >= 4
        # Each model has id, label, provider, active
        for m in data["models"]:
            assert "id" in m
            assert "label" in m
            assert "provider" in m
            assert "active" in m

    def test_get_settings_admin_only(self, client):
        # With auth disabled, all users are "admin"
        resp = client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "optimization_model" in data
        assert "available_models" in data

    def test_patch_settings(self, client):
        resp = client.patch(
            "/api/settings",
            json={"optimization_model": "google-vertex:gemini-2.5-pro"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["optimization_model"] == "google-vertex:gemini-2.5-pro"

    def test_patch_settings_invalid_model(self, client):
        resp = client.patch(
            "/api/settings",
            json={"optimization_model": "invalid:model"},
        )
        assert resp.status_code == 400
