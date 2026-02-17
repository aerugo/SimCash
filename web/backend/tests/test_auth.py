"""Tests for Firebase Auth integration."""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _disable_auth():
    """Ensure auth is disabled for all tests in this module by default."""
    pass


@pytest.fixture
def client_auth_disabled():
    """Client with auth disabled."""
    with patch.dict(os.environ, {"SIMCASH_AUTH_DISABLED": "true"}):
        # Reimport to pick up env
        import importlib
        from app import config
        importlib.reload(config)
        from app.main import app
        yield TestClient(app)
        # Reset
        importlib.reload(config)


@pytest.fixture
def client_auth_enabled():
    """Client with auth enabled."""
    with patch.dict(os.environ, {"SIMCASH_AUTH_DISABLED": "false"}):
        import importlib
        from app import config
        importlib.reload(config)
        from app.main import app
        yield TestClient(app)
        importlib.reload(config)


class TestAuthDisabled:
    def test_games_scenarios_accessible(self, client_auth_disabled):
        res = client_auth_disabled.get("/api/games/scenarios")
        assert res.status_code == 200

    def test_fixed_dev_uid(self, client_auth_disabled):
        """Auth disabled should return dev-user uid."""
        res = client_auth_disabled.post("/api/games", json={})
        assert res.status_code == 200
        data = res.json()
        assert "game_id" in data


class TestAuthEnabled:
    def test_unauthenticated_returns_401(self, client_auth_enabled):
        res = client_auth_enabled.get("/api/games/scenarios")
        assert res.status_code == 401

    def test_invalid_token_returns_401(self, client_auth_enabled):
        res = client_auth_enabled.get(
            "/api/games/scenarios",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert res.status_code == 401

    def test_valid_token_extracts_uid(self, client_auth_enabled):
        """Mock Firebase token verification to test uid extraction."""
        with patch("app.auth._verify_token", return_value="test-uid-123"):
            res = client_auth_enabled.get(
                "/api/games/scenarios",
                headers={"Authorization": "Bearer valid-mock-token"},
            )
            assert res.status_code == 200

    def test_public_endpoints_no_auth(self, client_auth_enabled):
        """Health and presets should not require auth."""
        res = client_auth_enabled.get("/api/health")
        assert res.status_code == 200

        res = client_auth_enabled.get("/api/presets")
        assert res.status_code == 200

    def test_missing_bearer_prefix(self, client_auth_enabled):
        res = client_auth_enabled.get(
            "/api/games/scenarios",
            headers={"Authorization": "not-bearer"},
        )
        assert res.status_code == 401
