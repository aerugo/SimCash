"""Tests for intra-scenario settlement counting & cost accounting.

Covers _run_scenario_day() behavior: cumulative settlement stats,
direct cost usage (no delta), orchestrator lifecycle, and GameDay
receiving cumulative stats via simulate_day().
"""
from __future__ import annotations

import copy
import json
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.game import Game, GameDay, DEFAULT_POLICY


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scenario(num_days: int = 3, ticks_per_day: int = 4) -> dict:
    """Minimal scenario YAML dict for testing."""
    return {
        "agents": [
            {"id": "BANK_A", "initial_balance": 1000},
            {"id": "BANK_B", "initial_balance": 1000},
        ],
        "simulation": {
            "rng_seed": 42,
            "num_days": num_days,
            "ticks_per_day": ticks_per_day,
        },
    }


def _mock_orchestrator(events_by_tick: dict[int, list[dict]] | None = None,
                       costs: dict[str, dict] | None = None,
                       balances: dict[str, int] | None = None):
    """Create a mock Orchestrator with configurable per-tick events and costs."""
    orch = MagicMock()
    _events_by_tick = events_by_tick or {}
    _costs = costs or {}
    _balances = balances or {"BANK_A": 500, "BANK_B": 500}

    orch.tick.return_value = None
    orch.get_tick_events.side_effect = lambda tick: [
        MagicMock(**{k: v for k, v in e.items()}, **{"get": e.get, "keys": e.keys, "values": e.values, "__iter__": e.__iter__})
        for e in _events_by_tick.get(tick, [])
    ]
    # Make mock events behave like dicts when dict() is called
    def _make_dict_event(e):
        m = MagicMock()
        m.__iter__ = lambda self: iter(e)
        m.__getitem__ = lambda self, k: e[k]
        m.keys = lambda: e.keys()
        m.items = lambda: e.items()
        m.get = lambda k, d=None: e.get(k, d)
        return m

    orch.get_tick_events.side_effect = lambda tick: [
        _make_dict_event(e) for e in _events_by_tick.get(tick, [])
    ]
    orch.get_agent_balance.side_effect = lambda aid: _balances.get(aid, 0)
    orch.get_agent_accumulated_costs.side_effect = lambda aid: _costs.get(aid, {
        "total_cost": 0, "delay_cost": 0, "deadline_penalty": 0,
        "liquidity_cost": 0, "collateral_cost": 0, "split_friction_cost": 0,
    })
    return orch


# ---------------------------------------------------------------------------
# Tests: Cumulative settlement stats
# ---------------------------------------------------------------------------

class TestCumulativeSettlementStats:
    """When a transaction arrives on Day 1 and settles on Day 2,
    the cumulative event_summary should count both."""

    @patch("app.sim_runner.SimulationConfig")
    @patch("app.sim_runner.Orchestrator")
    def test_arrival_day1_settlement_day2(self, mock_orch_cls, mock_sim_cfg):
        """Arrival on day 0, settlement on day 1 → cumulative counts both."""
        mock_sim_cfg.from_dict.return_value.to_ffi_dict.return_value = {
            "ticks_per_day": 2, "num_days": 2,
        }

        # Day 0: 1 arrival on tick 0
        # Day 1: 1 settlement on tick 2
        events_by_tick = {
            0: [{"event_type": "Arrival", "sender_id": "BANK_A"}],
            1: [],
            2: [{"event_type": "Settlement", "sender_id": "BANK_A"}],
            3: [],
        }
        orch = _mock_orchestrator(events_by_tick=events_by_tick)
        mock_orch_cls.new.return_value = orch

        scenario = _make_scenario(num_days=2, ticks_per_day=2)
        game = Game(
            game_id="test-cum",
            raw_yaml=scenario,
            total_days=2,
            optimization_schedule="every_scenario_day",
        )

        # Day 0
        ev0, _, _, _, _, _, cum_summary0, cum_arr0, cum_set0 = game.sim.run_scenario_day(game.current_day)
        assert cum_arr0 == 1
        assert cum_set0 == 0
        assert cum_summary0["BANK_A"]["arrivals"] == 1
        assert cum_summary0["BANK_A"]["settled"] == 0
        game.days.append(GameDay(0, 42, {}, {}, ev0, {}, 0, {}, event_summary=cum_summary0, total_arrivals=cum_arr0, total_settled=cum_set0))

        # Day 1
        ev1, _, _, _, _, _, cum_summary1, cum_arr1, cum_set1 = game.sim.run_scenario_day(game.current_day)
        assert cum_arr1 == 1, "Cumulative arrivals should still be 1"
        assert cum_set1 == 1, "Cumulative settlements should be 1"
        assert cum_summary1["BANK_A"]["arrivals"] == 1
        assert cum_summary1["BANK_A"]["settled"] == 1

    @patch("app.sim_runner.SimulationConfig")
    @patch("app.sim_runner.Orchestrator")
    def test_settlement_rate_never_exceeds_100_pct(self, mock_orch_cls, mock_sim_cfg):
        """Settlement rate (settled/arrivals) should never exceed 100%."""
        mock_sim_cfg.from_dict.return_value.to_ffi_dict.return_value = {
            "ticks_per_day": 2, "num_days": 2,
        }

        # 1 arrival, 1 settlement same day
        events_by_tick = {
            0: [{"event_type": "Arrival", "sender_id": "BANK_A"}],
            1: [{"event_type": "Settlement", "sender_id": "BANK_A"}],
            2: [],
            3: [],
        }
        orch = _mock_orchestrator(events_by_tick=events_by_tick)
        mock_orch_cls.new.return_value = orch

        scenario = _make_scenario(num_days=2, ticks_per_day=2)
        game = Game(
            game_id="test-rate",
            raw_yaml=scenario,
            total_days=2,
            optimization_schedule="every_scenario_day",
        )

        _, _, _, _, _, _, cum_summary, cum_arr, cum_set = game.sim.run_scenario_day(game.current_day)
        assert cum_arr >= cum_set, "Settled should never exceed arrivals"
        if cum_arr > 0:
            assert cum_set / cum_arr <= 1.0


# ---------------------------------------------------------------------------
# Tests: Direct cost usage (no delta)
# ---------------------------------------------------------------------------

class TestDirectCostUsage:
    """Engine resets cost accumulators per day. _run_scenario_day() should
    return the day's costs directly from get_agent_accumulated_costs()."""

    @patch("app.sim_runner.SimulationConfig")
    @patch("app.sim_runner.Orchestrator")
    def test_costs_are_direct_not_delta(self, mock_orch_cls, mock_sim_cfg):
        """Costs returned are direct from FFI, not subtracted from previous."""
        mock_sim_cfg.from_dict.return_value.to_ffi_dict.return_value = {
            "ticks_per_day": 2, "num_days": 2,
        }

        day_costs = {
            "BANK_A": {"total_cost": 100, "delay_cost": 30, "deadline_penalty": 10,
                        "liquidity_cost": 5, "collateral_cost": 0, "split_friction_cost": 0},
            "BANK_B": {"total_cost": 50, "delay_cost": 20, "deadline_penalty": 0,
                        "liquidity_cost": 0, "collateral_cost": 0, "split_friction_cost": 0},
        }
        orch = _mock_orchestrator(costs=day_costs)
        mock_orch_cls.new.return_value = orch

        scenario = _make_scenario(num_days=2, ticks_per_day=2)
        game = Game(
            game_id="test-cost",
            raw_yaml=scenario,
            total_days=2,
            optimization_schedule="every_scenario_day",
        )

        # Day 0
        _, _, costs0, per_agent0, total0, _, _, _, _ = game.sim.run_scenario_day(game.current_day)
        assert per_agent0["BANK_A"] == 100
        assert per_agent0["BANK_B"] == 50
        assert costs0["BANK_A"]["delay_cost"] == 30
        assert costs0["BANK_A"]["penalty_cost"] == 10
        assert total0 == 150
        game.days.append(GameDay(0, 42, {}, costs0, [], {}, total0, per_agent0))

        # Day 1: same costs returned by FFI (engine reset accumulators)
        # The code should NOT subtract day 0 costs
        _, _, costs1, per_agent1, total1, _, _, _, _ = game.sim.run_scenario_day(game.current_day)
        assert per_agent1["BANK_A"] == 100, "Should be direct, not delta"
        assert per_agent1["BANK_B"] == 50
        assert total1 == 150


# ---------------------------------------------------------------------------
# Tests: Orchestrator lifecycle
# ---------------------------------------------------------------------------

class TestOrchestratorLifecycle:
    """Orchestrator created on first day of round, persisted across days,
    destroyed at end of last scenario day."""

    @patch("app.sim_runner.SimulationConfig")
    @patch("app.sim_runner.Orchestrator")
    def test_orch_created_once_per_round(self, mock_orch_cls, mock_sim_cfg):
        mock_sim_cfg.from_dict.return_value.to_ffi_dict.return_value = {
            "ticks_per_day": 2, "num_days": 3,
        }
        orch = _mock_orchestrator()
        mock_orch_cls.new.return_value = orch

        scenario = _make_scenario(num_days=3, ticks_per_day=2)
        game = Game(
            game_id="test-lifecycle",
            raw_yaml=scenario,
            total_days=6,  # 2 rounds of 3 days
            optimization_schedule="every_scenario_day",
        )

        assert game.sim._live_orch is None

        # Day 0: orchestrator created
        game.sim.run_scenario_day(game.current_day)
        game.days.append(GameDay(0, 42, {}, {}, [], {}, 0, {}))
        assert mock_orch_cls.new.call_count == 1
        assert game.sim._live_orch is not None  # still alive

        # Day 1: same orchestrator
        game.sim.run_scenario_day(game.current_day)
        game.days.append(GameDay(1, 42, {}, {}, [], {}, 0, {}))
        assert mock_orch_cls.new.call_count == 1  # NOT called again
        assert game.sim._live_orch is not None

        # Day 2: last day of round → destroyed
        game.sim.run_scenario_day(game.current_day)
        game.days.append(GameDay(2, 42, {}, {}, [], {}, 0, {}))
        assert game.sim._live_orch is None, "Should be destroyed after last scenario day"

        # Day 3: new round → new orchestrator
        game.sim.run_scenario_day(game.current_day)
        game.days.append(GameDay(3, 42, {}, {}, [], {}, 0, {}))
        assert mock_orch_cls.new.call_count == 2
        assert game.sim._live_orch is not None


# ---------------------------------------------------------------------------
# Tests: GameDay receives cumulative stats via simulate_day()
# ---------------------------------------------------------------------------

class TestSimulateDayCumulativeStats:
    """When optimization_schedule == 'every_scenario_day', simulate_day()
    should set cumulative stats on the GameDay."""

    @patch("app.sim_runner.SimulationConfig")
    @patch("app.sim_runner.Orchestrator")
    def test_simulate_day_sets_cumulative_stats(self, mock_orch_cls, mock_sim_cfg):
        mock_sim_cfg.from_dict.return_value.to_ffi_dict.return_value = {
            "ticks_per_day": 2, "num_days": 2,
        }

        events_by_tick = {
            0: [{"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B", "tx_id": "tx1", "tick": 0, "amount": 100, "priority": 1, "deadline_tick": 10},
                {"event_type": "Arrival", "sender_id": "BANK_B", "receiver_id": "BANK_A", "tx_id": "tx2", "tick": 0, "amount": 200, "priority": 1, "deadline_tick": 10}],
            1: [{"event_type": "Settlement", "sender_id": "BANK_A", "tx_id": "tx1", "tick": 1}],
            2: [{"event_type": "Settlement", "sender_id": "BANK_B", "tx_id": "tx2", "tick": 2}],
            3: [],
        }
        orch = _mock_orchestrator(events_by_tick=events_by_tick)
        mock_orch_cls.new.return_value = orch

        scenario = _make_scenario(num_days=2, ticks_per_day=2)
        game = Game(
            game_id="test-simday",
            raw_yaml=scenario,
            total_days=2,
            optimization_schedule="every_scenario_day",
        )

        # Day 0
        day0 = game.simulate_day()
        assert day0._event_summary is not None, "Should have cumulative event_summary"
        assert day0._total_arrivals == 2
        assert day0._total_settled == 1
        assert day0._event_summary["BANK_A"]["arrivals"] == 1
        assert day0._event_summary["BANK_A"]["settled"] == 1
        game.commit_day(day0)

        # Day 1
        day1 = game.simulate_day()
        assert day1._total_arrivals == 2, "Cumulative arrivals across round"
        assert day1._total_settled == 2, "Cumulative settlements across round"

    @patch("app.sim_runner.SimulationConfig")
    @patch("app.sim_runner.Orchestrator")
    def test_every_round_mode_computes_from_events(self, mock_orch_cls, mock_sim_cfg):
        """In every_round mode, GameDay computes stats from events (not cumulative)."""
        mock_sim_cfg.from_dict.return_value.to_ffi_dict.return_value = {
            "ticks_per_day": 2, "num_days": 1,
        }

        events_by_tick = {
            0: [{"event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B", "tx_id": "tx1", "tick": 0, "amount": 100, "priority": 1, "deadline_tick": 10}],
            1: [{"event_type": "Settlement", "sender_id": "BANK_A", "tx_id": "tx1", "tick": 1}],
        }
        orch = _mock_orchestrator(events_by_tick=events_by_tick)
        mock_orch_cls.new.return_value = orch

        scenario = _make_scenario(num_days=1, ticks_per_day=2)
        game = Game(
            game_id="test-evround",
            raw_yaml=scenario,
            total_days=3,
            optimization_schedule="every_round",
        )

        day = game.simulate_day()
        # Should compute from events directly
        assert day._total_arrivals == 1
        assert day._total_settled == 1
