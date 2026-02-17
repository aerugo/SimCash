"""Tests for game setup API endpoints — Plan 1, Phase 1."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCreateGameValidation:
    """Validate game creation parameters."""

    def test_create_game_with_defaults(self):
        resp = client.post("/api/games", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        state = data["game"]
        assert state["max_days"] == 10
        assert state["use_llm"] is False
        assert state["num_eval_samples"] == 1

    def test_create_game_with_all_params(self):
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "num_eval_samples": 5,
            "max_days": 3,
            "use_llm": False,
            "mock_reasoning": True,
        })
        assert resp.status_code == 200
        state = resp.json()["game"]
        assert state["max_days"] == 3
        assert state["num_eval_samples"] == 5

    def test_create_game_invalid_scenario(self):
        resp = client.post("/api/games", json={"scenario_id": "nonexistent"})
        assert resp.status_code == 400

    def test_create_game_max_days_too_low(self):
        resp = client.post("/api/games", json={"max_days": 0})
        assert resp.status_code == 422

    def test_create_game_max_days_too_high(self):
        resp = client.post("/api/games", json={"max_days": 101})
        assert resp.status_code == 422

    def test_create_game_num_eval_samples_too_low(self):
        resp = client.post("/api/games", json={"num_eval_samples": 0})
        assert resp.status_code == 422

    def test_create_game_num_eval_samples_too_high(self):
        resp = client.post("/api/games", json={"num_eval_samples": 51})
        assert resp.status_code == 422


class TestGameScenariosEndpoint:
    """Test /api/games/scenarios endpoint."""

    def test_list_game_scenarios(self):
        resp = client.get("/api/games/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) >= 7  # We have 7 presets

    def test_scenario_has_required_fields(self):
        resp = client.get("/api/games/scenarios")
        scenarios = resp.json()["scenarios"]
        for s in scenarios:
            assert "id" in s
            assert "name" in s
            assert "description" in s
            assert "num_agents" in s
            assert "ticks_per_day" in s

    def test_scenario_has_cost_rates(self):
        resp = client.get("/api/games/scenarios")
        scenarios = resp.json()["scenarios"]
        for s in scenarios:
            assert "cost_rates" in s
            cr = s["cost_rates"]
            assert "liquidity_cost_per_tick_bps" in cr
            assert "delay_cost_per_tick_per_cent" in cr
