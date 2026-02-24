"""Tests for the max_days → rounds rename."""
import copy
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import CreateGameRequest
from app.game import Game
from app import serialization as ser

client = TestClient(app)

# Minimal scenario for unit tests
SIMPLE_SCENARIO = {
    "simulation": {
        "num_days": 1,
        "ticks_per_day": 3,
        "rng_seed": 42,
        "cost_params": {
            "liquidity_cost_per_tick_bps": 333,
            "delay_cost_per_tick_per_cent": 0.2,
            "eod_penalty_per_transaction": 100000,
            "deadline_penalty": 50000,
        },
    },
    "agents": [
        {"id": "A", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 100000},
        {"id": "B", "opening_balance": 0, "unsecured_cap": 0, "liquidity_pool": 100000},
    ],
    "payment_schedule": [
        {"sender": "A", "receiver": "B", "amount": 50000, "tick": 0, "deadline": 2},
    ],
}

MULTI_DAY_SCENARIO = {
    **SIMPLE_SCENARIO,
    "simulation": {**SIMPLE_SCENARIO["simulation"], "num_days": 5},
}


class TestCreateGameRequest:
    def test_accepts_rounds(self):
        req = CreateGameRequest(rounds=7)
        assert req.rounds == 7

    def test_default_rounds(self):
        req = CreateGameRequest()
        assert req.rounds == 10

    def test_rounds_validation(self):
        with pytest.raises(Exception):
            CreateGameRequest(rounds=0)
        with pytest.raises(Exception):
            CreateGameRequest(rounds=101)


class TestGameProperties:
    def test_total_days_single_day_scenario(self):
        game = Game(game_id="t1", raw_yaml=SIMPLE_SCENARIO, total_days=5)
        assert game.total_days == 5
        assert game.max_rounds == 5
        assert game.current_round == 0
        assert game.current_day == 0

    def test_total_days_multi_day_scenario(self):
        game = Game(game_id="t2", raw_yaml=MULTI_DAY_SCENARIO, total_days=15)
        # 15 total days / 5 scenario days = 3 rounds
        assert game.total_days == 15
        assert game.max_rounds == 3
        assert game.current_round == 0

    def test_is_complete(self):
        game = Game(game_id="t3", raw_yaml=SIMPLE_SCENARIO, total_days=2)
        assert not game.is_complete
        game.run_day()
        assert not game.is_complete
        game.run_day()
        assert game.is_complete
        assert game.current_day == 2
        assert game.current_round == 2


class TestCheckpointSerialization:
    def test_round_trip(self):
        game = Game(game_id="rt1", raw_yaml=copy.deepcopy(SIMPLE_SCENARIO), total_days=5)
        game.run_day()
        cp = game.to_checkpoint(scenario_id="test", uid="u1")
        assert cp["config"]["total_days"] == 5
        assert cp["config"]["rounds"] == 5

        restored = Game.from_checkpoint(cp)
        assert restored.total_days == 5
        assert restored.max_rounds == 5
        assert restored.current_day == 1

    def test_old_checkpoint_migration(self):
        """Old checkpoints with max_days should still load."""
        game = Game(game_id="old1", raw_yaml=copy.deepcopy(SIMPLE_SCENARIO), total_days=3)
        cp = game.to_checkpoint()
        # Simulate old format
        cp["config"]["max_days"] = cp["config"].pop("total_days")
        del cp["config"]["rounds"]

        restored = Game.from_checkpoint(cp)
        assert restored.total_days == 3
        assert restored.max_rounds == 3


class TestGameState:
    def test_state_has_rounds(self):
        game = Game(game_id="gs1", raw_yaml=SIMPLE_SCENARIO, total_days=5)
        state = game.get_state()
        assert "rounds" in state
        assert state["rounds"] == 5
        assert "current_round" in state
        assert state["current_round"] == 0
        assert "total_days" in state
        assert state["total_days"] == 5

    def test_state_no_max_days(self):
        game = Game(game_id="gs2", raw_yaml=SIMPLE_SCENARIO, total_days=5)
        state = game.get_state()
        assert "max_days" not in state


class TestAPIResponses:
    def test_create_returns_rounds(self):
        resp = client.post("/api/games", json={"rounds": 3, "use_llm": False})
        assert resp.status_code == 200
        data = resp.json()
        state = data["game"]
        assert state["rounds"] == 3
        assert "max_days" not in state

    def test_step_returns_rounds(self):
        resp = client.post("/api/games", json={"rounds": 3, "use_llm": False})
        gid = resp.json()["game_id"]
        resp2 = client.post(f"/api/games/{gid}/step")
        assert resp2.status_code == 200
        state = resp2.json()["game"]
        assert state["rounds"] == 3
        assert state["current_round"] == 1

    def test_list_returns_rounds(self):
        client.post("/api/games", json={"rounds": 5, "use_llm": False})
        resp = client.get("/api/games")
        assert resp.status_code == 200
        games = resp.json()["games"]
        assert len(games) > 0
        # At least one game should have rounds field
        has_rounds = any("rounds" in g for g in games)
        assert has_rounds
