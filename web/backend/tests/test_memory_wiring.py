"""Tests for memory optimization wiring into API endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import sys
from pathlib import Path
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.main import app, game_manager
from app.game import Game
from app.scenario_pack import get_scenario_by_id


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def game_with_trimmed_day(client):
    """Create a game with 2 days run (day 0 trimmed), registered in game_manager."""
    scenario = get_scenario_by_id("2bank_2tick")
    game = Game(game_id="trim-test-001", raw_yaml=scenario, total_days=5, use_llm=False)
    game.run_day()  # day 0
    game.run_day()  # day 1 — trims day 0

    game_manager.add(game)

    assert game.days[0].tick_events == [], "Day 0 should be trimmed"
    assert game.days[0].events == [], "Day 0 events should be trimmed"

    yield game.game_id

    game_manager.remove(game.game_id)


class TestReplayFallback:
    """Task 1: Replay endpoint recomputes events for trimmed days."""

    def test_replay_trimmed_day_returns_ticks(self, client, game_with_trimmed_day):
        game_id = game_with_trimmed_day
        resp = client.get(f"/api/games/{game_id}/days/0/replay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["num_ticks"] > 0
        assert len(data["ticks"]) > 0

    def test_replay_trimmed_day_does_not_store_events(self, client, game_with_trimmed_day):
        game_id = game_with_trimmed_day
        client.get(f"/api/games/{game_id}/days/0/replay")
        game = game_manager.get(game_id)
        assert game.days[0].tick_events == [], "Should not store recomputed events"

    def test_replay_untrimmed_day_works(self, client, game_with_trimmed_day):
        game_id = game_with_trimmed_day
        resp = client.get(f"/api/games/{game_id}/days/1/replay")
        assert resp.status_code == 200
        assert resp.json()["num_ticks"] > 0


class TestPaymentsFallback:
    """Task 1: Payments endpoint recomputes events for trimmed days."""

    def test_payments_trimmed_day_returns_data(self, client, game_with_trimmed_day):
        game_id = game_with_trimmed_day
        resp = client.get(f"/api/games/{game_id}/days/0/payments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["day"] == 0
        assert data["total_payments"] >= 0

    def test_payments_trimmed_day_does_not_store(self, client, game_with_trimmed_day):
        game_id = game_with_trimmed_day
        client.get(f"/api/games/{game_id}/days/0/payments")
        game = game_manager.get(game_id)
        assert game.days[0].events == [], "Should not store recomputed events"


class TestGameManagerIntegration:
    """Task 2: game_manager is a GameManager instance."""

    def test_game_manager_is_game_manager_class(self):
        from app.game_manager import GameManager
        assert isinstance(game_manager, GameManager)

    def test_create_game_uses_game_manager(self, client):
        resp = client.post("/api/games", json={})
        game_id = resp.json()["game_id"]
        assert game_manager.get(game_id) is not None
        game_manager.remove(game_id)

    def test_delete_game_uses_game_manager(self, client):
        resp = client.post("/api/games", json={})
        game_id = resp.json()["game_id"]
        client.delete(f"/api/games/{game_id}")
        assert game_manager.get(game_id) is None


class TestEvictionTask:
    """Task 3: Background eviction task is registered."""

    def test_eviction_loop_function_exists(self):
        from app.main import _eviction_loop
        assert callable(_eviction_loop)
