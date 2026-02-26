"""Tests for optimization threads and prompts API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client():
    """TestClient for the FastAPI app."""
    from app.main import app
    return TestClient(app)


@pytest.fixture
def game_with_optimization(simple_scenario):
    """Create a game with fake optimization data on days."""
    from app.game import Game
    game = Game(game_id="opt-threads-test", raw_yaml=simple_scenario, total_days=3)
    # Run day 0
    game.run_day()

    day0 = game.days[0]
    # Simulate optimization prompts + results for two agents
    day0.optimization_prompts["bank_a"] = {
        "system_prompt": "You are an optimizer.",
        "user_prompt": "Optimize bank_a.",
        "blocks": [{"id": "b1", "name": "context", "category": "core", "source": "system", "enabled": True, "options": {}, "token_estimate": 100}],
        "total_tokens": 500,
        "profile_hash": "abc123",
    }
    day0.optimization_results["bank_a"] = {
        "structured_prompt": day0.optimization_prompts["bank_a"],
        "raw_response": "I suggest lowering fraction.",
        "thinking": "Costs are high...",
        "reasoning": "Lower fraction reduces delay costs.",
        "usage": {"prompt_tokens": 400, "completion_tokens": 100},
        "latency_seconds": 3.5,
        "model": "openai:gpt-5.2",
        "validation_attempts": 1,
        "old_policy": {"policy_id": "old"},
        "new_policy": {"policy_id": "new"},
        "old_fraction": 0.5,
        "new_fraction": 0.45,
        "accepted": True,
        "mock": False,
    }
    return game


def _register_game(game):
    """Register a game in the game_manager."""
    from app.main import game_manager
    game_manager._games[game.game_id] = game


# ---- optimization_results on GameDay ----

class TestGameDayOptimizationResults:
    def test_gameday_has_optimization_results(self, game):
        """GameDay should have optimization_results dict."""
        game.run_day()
        assert hasattr(game.days[0], "optimization_results")
        assert isinstance(game.days[0].optimization_results, dict)

    def test_store_prompt_stores_results(self, game):
        """_store_prompt should store full result in optimization_results."""
        game.run_day()
        day = game.days[0]
        result = {
            "structured_prompt": {"system_prompt": "test", "user_prompt": "test"},
            "raw_response": "response",
            "old_policy": {},
            "new_policy": {},
            "accepted": True,
        }
        game._store_prompt(day, "bank_a", result)
        assert "bank_a" in day.optimization_results
        assert day.optimization_results["bank_a"]["raw_response"] == "response"
        assert "bank_a" in day.optimization_prompts


# ---- Serialization ----

class TestOptimizationResultsSerialization:
    def test_checkpoint_roundtrip(self, game):
        """optimization_results should survive checkpoint serialization."""
        from app.serialization import day_to_checkpoint, game_to_checkpoint, game_from_checkpoint
        game.run_day()
        day = game.days[0]
        day.optimization_results["bank_a"] = {"raw_response": "test", "accepted": True}

        # Day checkpoint
        cp = day_to_checkpoint(day)
        assert "optimization_results" in cp
        assert cp["optimization_results"]["bank_a"]["raw_response"] == "test"

        # Full game roundtrip
        game_cp = game_to_checkpoint(game)
        restored = game_from_checkpoint(game_cp)
        assert restored.days[0].optimization_results["bank_a"]["raw_response"] == "test"


# ---- API: /optimization-threads ----

class TestOptimizationThreadsEndpoint:
    def test_returns_threads(self, app_client, game_with_optimization):
        _register_game(game_with_optimization)
        resp = app_client.get(f"/api/v1/experiments/{game_with_optimization.game_id}/optimization-threads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["experiment_id"] == game_with_optimization.game_id
        threads = data["threads"]
        assert len(threads) == 1
        t = threads[0]
        assert t["day"] == 0
        assert t["agent_id"] == "bank_a"
        assert t["prompt"]["system_prompt"] == "You are an optimizer."
        assert t["response"]["raw_response"] == "I suggest lowering fraction."
        assert t["result"]["accepted"] is True
        assert t["result"]["old_fraction"] == 0.5

    def test_filter_by_agent(self, app_client, game_with_optimization):
        _register_game(game_with_optimization)
        resp = app_client.get(
            f"/api/v1/experiments/{game_with_optimization.game_id}/optimization-threads?agent_id=bank_b"
        )
        assert resp.status_code == 200
        assert len(resp.json()["threads"]) == 0

    def test_filter_by_day_range(self, app_client, game_with_optimization):
        _register_game(game_with_optimization)
        resp = app_client.get(
            f"/api/v1/experiments/{game_with_optimization.game_id}/optimization-threads?day_start=1&day_end=5"
        )
        assert resp.status_code == 200
        assert len(resp.json()["threads"]) == 0

    def test_404_unknown_experiment(self, app_client):
        resp = app_client.get("/api/v1/experiments/nonexistent/optimization-threads")
        assert resp.status_code == 404

    def test_prompt_only_fallback(self, app_client, simple_scenario):
        """When optimization_results missing, fall back to prompt-only data."""
        from app.game import Game
        game = Game(game_id="prompt-only-test", raw_yaml=simple_scenario, total_days=2)
        game.run_day()
        game.days[0].optimization_prompts["bank_a"] = {
            "system_prompt": "sys",
            "user_prompt": "usr",
            "blocks": [],
            "total_tokens": 100,
            "profile_hash": "h",
        }
        # No optimization_results set
        _register_game(game)
        resp = app_client.get(f"/api/v1/experiments/{game.game_id}/optimization-threads")
        assert resp.status_code == 200
        threads = resp.json()["threads"]
        assert len(threads) == 1
        assert threads[0]["prompt"]["system_prompt"] == "sys"
        assert threads[0]["response"] is None
        assert threads[0]["result"] is None


# ---- API: /prompts ----

class TestPromptsEndpoint:
    def test_returns_prompts(self, app_client, game_with_optimization):
        _register_game(game_with_optimization)
        resp = app_client.get(f"/api/v1/experiments/{game_with_optimization.game_id}/prompts")
        assert resp.status_code == 200
        data = resp.json()
        assert data["experiment_id"] == game_with_optimization.game_id
        assert "manifest" in data
        assert len(data["days"]) >= 1
        day0 = data["days"][0]
        assert "bank_a" in day0["prompts"]
        assert "raw_response" not in str(day0)  # no response data

    def test_404_unknown(self, app_client):
        resp = app_client.get("/api/v1/experiments/nonexistent/prompts")
        assert resp.status_code == 404
