"""Tests for Orchestrator fast-forward replay on resume.

When a container dies mid-round in a multi-day scenario, the Orchestrator
is lost. On resume, we must replay completed days to rebuild engine state
before continuing. Policies must be injected between replayed days to
ensure deterministic identity with the original run.
"""
from __future__ import annotations

import copy
import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[3] / "api"
sys.path.insert(0, str(API_DIR))
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

os.environ["SIMCASH_AUTH_DISABLED"] = "true"
os.environ["SIMCASH_STORAGE_MODE"] = "local"

import pytest
from app.game import Game
from app.scenario_pack import get_scenario_by_id


def _make_multi_day_scenario() -> dict:
    """Create a 2-bank stochastic scenario with multiple scenario days per round."""
    scenario = get_scenario_by_id("2bank_12tick")
    # Make it multi-day: 3 scenario days per round (12 ticks each)
    scenario["simulation"]["num_days"] = 3
    return scenario


class TestFastForwardReplay:
    """Fast-forward replay should produce identical Orchestrator state."""

    def test_continuous_vs_interrupted_mid_round(self):
        """Running 6 days continuously should produce same results as
        running 4, checkpointing mid-round, restoring, and running 2 more."""
        scenario = _make_multi_day_scenario()  # 3 scenario days per round

        # --- Continuous run ---
        game_continuous = Game(
            game_id="continuous", raw_yaml=scenario, total_days=6,
            optimization_schedule="every_scenario_day",
        )
        for _ in range(6):
            day = game_continuous.simulate_day()
            game_continuous.commit_day(day)

        # --- Interrupted mid-round: 4 days (= round 0 complete + round 1 day 0),
        #     checkpoint, restore, run 2 more (round 1 days 1-2) ---
        game_interrupted = Game(
            game_id="interrupted", raw_yaml=scenario, total_days=6,
            optimization_schedule="every_scenario_day",
        )
        for _ in range(4):
            day = game_interrupted.simulate_day()
            game_interrupted.commit_day(day)

        # Checkpoint mid-round (day 3 = first day of round 1)
        cp = game_interrupted.to_checkpoint()
        game_restored = Game.from_checkpoint(cp)

        # Run remaining 2 days
        for _ in range(2):
            day = game_restored.simulate_day()
            game_restored.commit_day(day)

        # Compare all 6 days
        for i in range(6):
            assert game_continuous.days[i].day_total_cost == game_restored.days[i].day_total_cost, \
                f"Day {i} total cost mismatch: {game_continuous.days[i].day_total_cost} vs {game_restored.days[i].day_total_cost}"
            assert game_continuous.days[i].day_per_agent_costs == game_restored.days[i].day_per_agent_costs, \
                f"Day {i} per-agent costs mismatch"

    def test_mid_round_restore_replays_correctly(self):
        """Interrupting mid-round (after day 0 of a 3-day round) should
        replay day 0 before continuing with days 1-2."""
        scenario = _make_multi_day_scenario()  # 3 scenario days per round

        # --- Continuous run ---
        game_continuous = Game(
            game_id="continuous-mid", raw_yaml=scenario, total_days=6,
            optimization_schedule="every_scenario_day",
        )
        for _ in range(6):
            day = game_continuous.simulate_day()
            game_continuous.commit_day(day)

        # --- Interrupted mid-round: run 1 day (day 0), checkpoint, restore ---
        game_interrupted = Game(
            game_id="interrupted-mid", raw_yaml=scenario, total_days=6,
            optimization_schedule="every_scenario_day",
        )
        day = game_interrupted.simulate_day()
        game_interrupted.commit_day(day)

        # Checkpoint after day 0 (mid-round)
        cp = game_interrupted.to_checkpoint()
        game_restored = Game.from_checkpoint(cp)

        # Run remaining 5 days
        for _ in range(5):
            day = game_restored.simulate_day()
            game_restored.commit_day(day)

        # Compare all 6 days
        for i in range(6):
            assert game_continuous.days[i].day_total_cost == game_restored.days[i].day_total_cost, \
                f"Day {i} total cost mismatch: {game_continuous.days[i].day_total_cost} vs {game_restored.days[i].day_total_cost}"

    def test_fast_forward_with_policy_changes(self):
        """Policy changes between days must be respected during replay."""
        scenario = _make_multi_day_scenario()  # 3 scenario days per round

        # --- Run with policy change mid-round ---
        game = Game(
            game_id="policy-change", raw_yaml=scenario, total_days=6,
            optimization_schedule="every_scenario_day",
        )

        # Day 0 — default policy
        day0 = game.simulate_day()
        game.commit_day(day0)

        # Manually change policy before day 1 (simulates optimization)
        for aid in game.agent_ids:
            game.policies[aid] = copy.deepcopy(game.policies[aid])
            game.policies[aid]["parameters"]["initial_liquidity_fraction"] = 0.3
        game._inject_policies_into_orch()

        # Day 1 — with new policy
        day1 = game.simulate_day()
        game.commit_day(day1)

        # Day 2 — still same round
        day2 = game.simulate_day()
        game.commit_day(day2)

        # --- Checkpoint after day 0, restore —
        # Fast-forward should replay day 0 with default policy,
        # then inject 0.3 policy before day 1 replay ---
        game2 = Game(
            game_id="policy-change-2", raw_yaml=scenario, total_days=6,
            optimization_schedule="every_scenario_day",
        )
        d0 = game2.simulate_day()
        game2.commit_day(d0)

        # Apply policy change (just like original)
        for aid in game2.agent_ids:
            game2.policies[aid] = copy.deepcopy(game2.policies[aid])
            game2.policies[aid]["parameters"]["initial_liquidity_fraction"] = 0.3
        game2._inject_policies_into_orch()

        d1 = game2.simulate_day()
        game2.commit_day(d1)

        # Checkpoint after day 1 (mid-round: 2 of 3 days done)
        cp = game2.to_checkpoint()
        game_restored = Game.from_checkpoint(cp)

        # Continue — day 2 should match (fast-forward replays days 0+1 with correct policies)
        d2 = game_restored.simulate_day()
        game_restored.commit_day(d2)

        assert day2.day_total_cost == d2.day_total_cost, \
            f"Day 2 cost mismatch after policy change replay: {day2.day_total_cost} vs {d2.day_total_cost}"

    def test_single_day_round_no_replay_needed(self):
        """Single-day rounds (scenario_num_days=1) don't need replay."""
        scenario = get_scenario_by_id("2bank_2tick")
        assert scenario["simulation"].get("num_days", 1) == 1

        game = Game(game_id="single", raw_yaml=scenario, total_days=3)
        for _ in range(2):
            day = game.simulate_day()
            game.commit_day(day)

        # Checkpoint + restore
        cp = game.to_checkpoint()
        restored = Game.from_checkpoint(cp)

        # Third day should work without replay
        day = restored.simulate_day()
        restored.commit_day(day)

        # Run continuous for comparison
        game2 = Game(game_id="single-2", raw_yaml=scenario, total_days=3)
        for _ in range(3):
            d = game2.simulate_day()
            game2.commit_day(d)

        assert game2.days[2].day_total_cost == restored.days[2].day_total_cost
