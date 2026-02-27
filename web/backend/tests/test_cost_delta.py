"""Tests for per-day cost accounting.

The engine resets cost accumulators at each day boundary (engine.rs:2973).
Values from get_agent_accumulated_costs() are already per-day, NOT cumulative
across a persistent Orchestrator. Therefore:

1. GameDay.day_total_cost must equal GameDay.total_cost (no delta needed)
2. GameDay.day_per_agent_costs must equal GameDay.per_agent_costs
3. GameDay.day_costs must equal GameDay.costs
4. All costs must be non-negative
5. Serialization (to_dict, to_summary_dict) must use per-day values
6. Checkpoint round-trip must preserve per-day values
7. cost_history in game state must reflect per-day values directly
"""
from __future__ import annotations

import copy
import pytest

import sys
from pathlib import Path
API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

import os
os.environ["SIMCASH_AUTH_DISABLED"] = "true"
os.environ["SIMCASH_STORAGE_MODE"] = "local"

from app.game import Game, GameDay


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_day(day_num: int, total_cost: int,
             per_agent: dict[str, int],
             costs: dict[str, dict] | None = None) -> GameDay:
    """Create a GameDay with known cost values."""
    if costs is None:
        costs = {aid: {"delay_cost": v // 2, "deadline_penalty": v - v // 2, "total": v}
                 for aid, v in per_agent.items()}
    return GameDay(
        day_num=day_num, seed=42 + day_num, policies={},
        costs=costs, events=[], balance_history={},
        total_cost=total_cost, per_agent_costs=per_agent,
    )


def make_game(total_days: int = 5) -> Game:
    from app.scenario_pack import get_scenario_by_id
    scenario = get_scenario_by_id("2bank_2tick")
    return Game(game_id="test-cost", raw_yaml=scenario, total_days=total_days)


# ---------------------------------------------------------------------------
# Test 1: day_* fields equal raw fields (no delta transformation)
# ---------------------------------------------------------------------------

class TestNoDeltaTransformation:
    """Engine costs are per-day. day_* fields must equal raw fields, not deltas."""

    def test_day_total_cost_equals_total_cost(self):
        day = make_day(0, total_cost=5000, per_agent={"A": 3000, "B": 2000})
        assert day.day_total_cost == day.total_cost == 5000

    def test_day_per_agent_costs_equals_per_agent_costs(self):
        day = make_day(0, total_cost=5000, per_agent={"A": 3000, "B": 2000})
        assert day.day_per_agent_costs == day.per_agent_costs

    def test_day_costs_equals_costs(self):
        costs = {"A": {"delay_cost": 100, "total": 300},
                 "B": {"delay_cost": 200, "total": 400}}
        day = make_day(0, total_cost=700, per_agent={"A": 300, "B": 400}, costs=costs)
        assert day.day_costs == day.costs

    def test_second_day_no_delta_subtraction(self):
        """Day 2 costs should NOT be day2 - day1. They're independent per-day values."""
        game = make_game()

        # Day 0: cost 1000
        day0 = make_day(0, total_cost=1000, per_agent={"BANK_A": 600, "BANK_B": 400})
        game.commit_day(day0)

        # Day 1: cost 800 (optimizer reduced costs)
        # Bug: old code would compute delta = 800 - 1000 = -200 (NEGATIVE!)
        day1 = make_day(1, total_cost=800, per_agent={"BANK_A": 400, "BANK_B": 400})

        # day_total_cost must be 800, NOT -200
        assert day1.day_total_cost == 800
        assert day1.day_per_agent_costs == {"BANK_A": 400, "BANK_B": 400}

    def test_decreasing_costs_stay_positive(self):
        """When optimization reduces costs day-over-day, all values stay non-negative."""
        game = make_game()

        costs_sequence = [
            (10000, {"BANK_A": 6000, "BANK_B": 4000}),  # Day 0
            (8000, {"BANK_A": 4000, "BANK_B": 4000}),   # Day 1: reduced
            (5000, {"BANK_A": 2000, "BANK_B": 3000}),   # Day 2: reduced more
            (3000, {"BANK_A": 1000, "BANK_B": 2000}),   # Day 3: even lower
        ]

        for i, (total, per_agent) in enumerate(costs_sequence):
            day = make_day(i, total_cost=total, per_agent=per_agent)
            game.commit_day(day)

            # Every day's cost must be non-negative
            assert day.day_total_cost >= 0, f"Day {i}: day_total_cost={day.day_total_cost}"
            for aid, cost in day.day_per_agent_costs.items():
                assert cost >= 0, f"Day {i}, {aid}: cost={cost}"


# ---------------------------------------------------------------------------
# Test 2: No _compute_cost_deltas or delta logic should exist
# ---------------------------------------------------------------------------

class TestNoDeltaMethodExists:
    """The broken delta computation methods must not exist."""

    def test_no_compute_cost_deltas_method(self):
        game = make_game()
        assert not hasattr(game, '_compute_cost_deltas'), \
            "_compute_cost_deltas should be removed — engine costs are already per-day"

    def test_no_get_previous_day_in_round(self):
        game = make_game()
        assert not hasattr(game, '_get_previous_day_in_round'), \
            "_get_previous_day_in_round should be removed — no cross-day deltas needed"


# ---------------------------------------------------------------------------
# Test 3: Serialization uses per-day values
# ---------------------------------------------------------------------------

class TestSerialization:
    """to_dict and to_summary_dict must output per-day costs directly."""

    def test_to_dict_uses_per_day_values(self):
        day = make_day(0, total_cost=5000, per_agent={"A": 3000, "B": 2000})
        d = day.to_dict()
        assert d["total_cost"] == 5000
        assert d["per_agent_costs"] == {"A": 3000, "B": 2000}

    def test_to_summary_dict_uses_per_day_values(self):
        day = make_day(0, total_cost=5000, per_agent={"A": 3000, "B": 2000})
        d = day.to_summary_dict()
        assert d["total_cost"] == 5000
        assert d["per_agent_costs"] == {"A": 3000, "B": 2000}


# ---------------------------------------------------------------------------
# Test 4: Checkpoint round-trip preserves values
# ---------------------------------------------------------------------------

class TestCheckpointRoundTrip:
    """Checkpoint save/restore must preserve per-day costs."""

    def test_round_trip_preserves_costs(self):
        game = make_game(total_days=3)

        day0 = make_day(0, total_cost=1000, per_agent={"BANK_A": 500, "BANK_B": 500})
        game.commit_day(day0)

        day1 = make_day(1, total_cost=800, per_agent={"BANK_A": 300, "BANK_B": 500})
        game.commit_day(day1)

        cp = game.to_checkpoint()
        restored = Game.from_checkpoint(cp)

        assert restored.days[0].day_total_cost == 1000
        assert restored.days[1].day_total_cost == 800
        assert restored.days[0].day_per_agent_costs == {"BANK_A": 500, "BANK_B": 500}
        assert restored.days[1].day_per_agent_costs == {"BANK_A": 300, "BANK_B": 500}


# ---------------------------------------------------------------------------
# Test 5: cost_history in game state
# ---------------------------------------------------------------------------

class TestCostHistory:
    """Game.get_state() cost_history must use per-day values."""

    def test_cost_history_reflects_per_day(self):
        game = make_game(total_days=3)

        day0 = make_day(0, total_cost=1000, per_agent={"BANK_A": 600, "BANK_B": 400})
        game.commit_day(day0)

        # Day 1 lower than day 0 — the scenario that triggered negative costs
        day1 = make_day(1, total_cost=700, per_agent={"BANK_A": 300, "BANK_B": 400})
        game.commit_day(day1)

        state = game.get_state()
        assert state["cost_history"]["BANK_A"] == [600, 300]
        assert state["cost_history"]["BANK_B"] == [400, 400]

    def test_cost_history_all_non_negative(self):
        """cost_history must never contain negative values."""
        game = make_game(total_days=5)

        # Simulate progressively lower costs (optimization working)
        for i, total in enumerate([10000, 8000, 5000, 3000, 1000]):
            half = total // 2
            day = make_day(i, total_cost=total,
                           per_agent={"BANK_A": half, "BANK_B": total - half})
            game.commit_day(day)

        state = game.get_state()
        for aid, history in state["cost_history"].items():
            for day_idx, cost in enumerate(history):
                assert cost >= 0, f"{aid} day {day_idx}: cost={cost} is negative!"


# ---------------------------------------------------------------------------
# Test 6: simulate_day produces non-negative costs (integration)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test 6b: The actual bug — _compute_cost_deltas on multi-day scenario
# ---------------------------------------------------------------------------

class TestDeltaBugReproduction:
    """Reproduce the exact negative-cost bug from intra-scenario mode.

    When scenario_num_days > 1, _compute_cost_deltas subtracts day N-1's
    per-day costs from day N's per-day costs. Since these are independent
    (engine resets accumulators), when day N < day N-1 the result is negative.
    """

    def test_negative_cost_from_delta_subtraction(self):
        """Simulate the bug: day 2 costs < day 1, delta goes negative."""
        game = make_game(total_days=5)
        # Force multi-day scenario so _get_previous_day_in_round returns a day
        game._scenario_num_days = 5

        day0 = make_day(0, total_cost=10000, per_agent={"BANK_A": 6000, "BANK_B": 4000})
        game.commit_day(day0)

        # Day 1: optimizer reduced costs. Engine returns 8000 (per-day, NOT cumulative).
        day1 = make_day(1, total_cost=8000, per_agent={"BANK_A": 4000, "BANK_B": 4000})

        # With the bug: _compute_cost_deltas would compute 8000 - 10000 = -2000
        # Without the bug: day_total_cost stays 8000
        assert day1.day_total_cost == 8000, \
            f"Expected 8000 but got {day1.day_total_cost} — delta subtraction bug!"
        assert day1.day_total_cost >= 0, "Negative total cost!"

        # Apply _compute_cost_deltas if it exists (to verify it causes the bug)
        if hasattr(game, '_compute_cost_deltas'):
            game._compute_cost_deltas(day1)
            # This is the bug: day_total_cost becomes negative
            if day1.day_total_cost < 0:
                pytest.fail(
                    f"BUG CONFIRMED: _compute_cost_deltas produced negative cost "
                    f"{day1.day_total_cost} (expected 8000). "
                    f"Engine costs are per-day, not cumulative!"
                )


# ---------------------------------------------------------------------------
# Test 7: simulate_day produces non-negative costs (integration)
# ---------------------------------------------------------------------------

class TestSimulateDayIntegration:
    """simulate_day must produce non-negative per-day costs."""

    def test_simulate_day_costs_non_negative(self):
        """Run actual simulation and verify costs are non-negative."""
        game = make_game(total_days=3)

        for _ in range(3):
            day = game.simulate_day()
            assert day.day_total_cost >= 0, f"Day {day.day_num}: negative total cost"
            assert day.day_total_cost == day.total_cost, \
                f"Day {day.day_num}: day_total_cost != total_cost"
            for aid, cost in day.day_per_agent_costs.items():
                assert cost >= 0, f"Day {day.day_num}, {aid}: negative cost {cost}"
            game.commit_day(day)

    def test_simulate_day_cost_fields_equal(self):
        """day_* fields must always equal raw fields — no transformation."""
        game = make_game(total_days=2)

        for _ in range(2):
            day = game.simulate_day()
            assert day.day_total_cost == day.total_cost
            assert day.day_per_agent_costs == day.per_agent_costs
            assert day.day_costs == day.costs
            game.commit_day(day)
