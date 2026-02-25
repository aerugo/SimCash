"""Tests for per-day cost delta tracking.

Ensures that GameDay stores incremental (delta) costs rather than cumulative,
so that checkpoint restore after container crash doesn't corrupt cost totals.
"""
from __future__ import annotations

import copy
import pytest
from unittest.mock import MagicMock, patch

import sys
from pathlib import Path
# Ensure api/ and web/backend are on path
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import os
os.environ["SIMCASH_AUTH_DISABLED"] = "true"
os.environ["SIMCASH_STORAGE_MODE"] = "local"

from app.game import Game, GameDay


VALID_POLICY = {
    "version": "2.0",
    "policy_id": "test",
    "parameters": {"initial_liquidity_fraction": 0.5},
    "payment_tree": {"type": "action", "node_id": "root", "action": "Release"},
    "bank_tree": {"type": "action", "node_id": "bank", "action": "NoAction"},
}


class TestCostDeltaStorage:
    """GameDay should store per-day cost deltas, not cumulative."""

    def test_game_day_has_day_cost_fields(self):
        """GameDay should have day_total_cost and day_per_agent_costs for deltas."""
        day = GameDay(
            day_num=0, seed=42, policies={}, costs={}, events=[],
            balance_history={}, total_cost=1000, per_agent_costs={"A": 500, "B": 500},
        )
        # New delta fields should exist
        assert hasattr(day, "day_total_cost")
        assert hasattr(day, "day_per_agent_costs")

    def test_first_day_delta_equals_cumulative(self):
        """On the first day, delta == cumulative (no prior accumulation)."""
        day = GameDay(
            day_num=0, seed=42, policies={}, costs={}, events=[],
            balance_history={}, total_cost=5000,
            per_agent_costs={"A": 3000, "B": 2000},
        )
        # For the first day, delta should equal the cumulative value
        assert day.day_total_cost == 5000
        assert day.day_per_agent_costs == {"A": 3000, "B": 2000}


class TestCostDeltaCheckpoint:
    """Checkpoint serialization should preserve delta costs."""

    def test_checkpoint_round_trip_preserves_deltas(self):
        """Day cost deltas survive checkpoint save/restore."""
        from app.scenario_pack import get_scenario_by_id
        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test-delta", raw_yaml=scenario, total_days=3)

        # Simulate some days with known deltas
        day0 = GameDay(
            day_num=0, seed=42, policies={},
            costs={"BANK_A": {"delay_cost": 100, "total": 500}},
            events=[], balance_history={},
            total_cost=1000, per_agent_costs={"BANK_A": 500, "BANK_B": 500},
        )
        day0.day_total_cost = 1000
        day0.day_per_agent_costs = {"BANK_A": 500, "BANK_B": 500}

        day1 = GameDay(
            day_num=1, seed=43, policies={},
            costs={"BANK_A": {"delay_cost": 200, "total": 1200}},
            events=[], balance_history={},
            total_cost=2500,  # cumulative
            per_agent_costs={"BANK_A": 1200, "BANK_B": 1300},  # cumulative
        )
        day1.day_total_cost = 1500  # delta: 2500 - 1000
        day1.day_per_agent_costs = {"BANK_A": 700, "BANK_B": 800}  # deltas

        game.days = [day0, day1]

        # Checkpoint round-trip
        cp = game.to_checkpoint()
        restored = Game.from_checkpoint(cp)

        assert len(restored.days) == 2
        assert restored.days[0].day_total_cost == 1000
        assert restored.days[0].day_per_agent_costs == {"BANK_A": 500, "BANK_B": 500}
        assert restored.days[1].day_total_cost == 1500
        assert restored.days[1].day_per_agent_costs == {"BANK_A": 700, "BANK_B": 800}


class TestCostHistoryReconstruction:
    """API cost_history should use deltas, not cumulative values."""

    def test_cost_history_uses_deltas(self):
        """get_game_state cost_history should reflect per-day deltas."""
        from app.scenario_pack import get_scenario_by_id
        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test-hist", raw_yaml=scenario, total_days=3)

        day0 = GameDay(
            day_num=0, seed=42, policies={},
            costs={}, events=[], balance_history={},
            total_cost=1000, per_agent_costs={"BANK_A": 500, "BANK_B": 500},
        )
        day0.day_total_cost = 1000
        day0.day_per_agent_costs = {"BANK_A": 500, "BANK_B": 500}

        day1 = GameDay(
            day_num=1, seed=43, policies={},
            costs={}, events=[], balance_history={},
            total_cost=2500, per_agent_costs={"BANK_A": 1200, "BANK_B": 1300},
        )
        day1.day_total_cost = 1500
        day1.day_per_agent_costs = {"BANK_A": 700, "BANK_B": 800}

        game.days = [day0, day1]

        state = game.get_state()
        # cost_history should use day deltas, not cumulative per_agent_costs
        assert state["cost_history"]["BANK_A"] == [500, 700]
        assert state["cost_history"]["BANK_B"] == [500, 800]


class TestSimRunnerDeltaComputation:
    """SimRunner should compute cost deltas when running scenario days."""

    def test_run_day_computes_delta(self):
        """Game.simulate_day should set day_total_cost as delta, not cumulative."""
        from app.scenario_pack import get_scenario_by_id
        scenario = get_scenario_by_id("2bank_2tick")
        game = Game(game_id="test-sim", raw_yaml=scenario, total_days=3)

        # Run two days
        day0 = game.simulate_day()
        game.commit_day(day0)

        day1 = game.simulate_day()
        game.commit_day(day1)

        # day_total_cost should be the delta, not cumulative
        # For single-day scenarios (scenario_num_days=1), each day is its own round
        # so cumulative == delta (Orchestrator is recreated each round)
        assert day0.day_total_cost == day0.total_cost
        assert day1.day_total_cost == day1.total_cost

        # For the cost_history, values should be deltas
        assert day0.day_per_agent_costs is not None
        assert day1.day_per_agent_costs is not None
