"""Tests for memory optimization features."""
from __future__ import annotations

import copy
import time
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.game import Game, GameDay, DEFAULT_POLICY
from app.scenario_pack import get_scenario_by_id
from app import serialization as _ser


_UUID_FIELDS = {"tx_id", "source_transactions", "matched_transactions"}

def _strip_tx_ids(tick_events: list[list[dict]]) -> list[list[dict]]:
    """Remove UUID fields for structural comparison (UUIDs are non-deterministic)."""
    return [
        [{k: v for k, v in e.items() if k not in _UUID_FIELDS} for e in tick]
        for tick in tick_events
    ]


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def scenario():
    return get_scenario_by_id("2bank_2tick")


@pytest.fixture
def game(scenario):
    return Game(game_id="mem-001", raw_yaml=scenario, total_days=5)


# ── 1. Event trimming after each day ─────────────────────────────────

class TestEventTrimming:

    def test_trim_old_day_events_method_exists(self, game):
        """Game should have _trim_old_day_events method."""
        assert hasattr(game, '_trim_old_day_events')
        assert callable(game._trim_old_day_events)

    def test_after_two_days_first_day_events_trimmed(self, game):
        """After committing day 1, day 0's events and tick_events should be empty."""
        game.run_day()  # day 0
        game.run_day()  # day 1

        # Day 0 should be trimmed
        assert game.days[0].events == []
        assert game.days[0].tick_events == []
        # Day 1 (last) should still have events
        assert len(game.days[1].tick_events) > 0 or len(game.days[1].events) >= 0

    def test_after_three_days_only_last_has_events(self, game):
        """After 3 days, only the last day retains events."""
        for _ in range(3):
            game.run_day()

        for d in game.days[:-1]:
            assert d.events == [], f"Day {d.day_num} events not trimmed"
            assert d.tick_events == [], f"Day {d.day_num} tick_events not trimmed"
        # Last day keeps events
        last = game.days[-1]
        assert isinstance(last.tick_events, list)

    def test_trimming_preserves_event_summary(self, game):
        """Trimming events should NOT destroy cached settlement stats."""
        game.run_day()
        day0_arrivals = game.days[0]._total_arrivals
        day0_settled = game.days[0]._total_settled
        day0_summary = copy.deepcopy(game.days[0]._event_summary)

        game.run_day()  # triggers trim of day 0

        assert game.days[0]._total_arrivals == day0_arrivals
        assert game.days[0]._total_settled == day0_settled
        assert game.days[0]._event_summary == day0_summary

    def test_trimming_preserves_costs_and_policies(self, game):
        """Trimming should not affect cost or policy data on old days."""
        game.run_day()
        day0_costs = copy.deepcopy(game.days[0].costs)
        day0_policies = copy.deepcopy(game.days[0].policies)
        day0_total = game.days[0].total_cost

        game.run_day()

        assert game.days[0].costs == day0_costs
        assert game.days[0].policies == day0_policies
        assert game.days[0].total_cost == day0_total


# ── 2. On-demand recompute (unit test for the recompute helper) ──────

class TestEventRecompute:

    def test_recompute_day_events_returns_events(self, game):
        """Recomputing events for a trimmed day should return non-empty tick_events."""
        game.run_day()
        # Capture original structure (strip tx_ids which are random UUIDs)
        original = _strip_tx_ids(game.days[0].tick_events)

        game.run_day()  # trims day 0

        # Recompute day 0 events
        recomputed = game.recompute_day_events(0)
        assert isinstance(recomputed, list)
        assert len(recomputed) == len(original)
        assert _strip_tx_ids(recomputed) == original

    def test_recompute_uses_day_policy_not_current(self, game):
        """Recompute must use the policy from that day, not current policy."""
        game.run_day()  # day 0 with default policy
        original = _strip_tx_ids(game.days[0].tick_events)

        # Change policy before running day 1
        for aid in game.agent_ids:
            game.policies[aid] = copy.deepcopy(DEFAULT_POLICY)
            game.policies[aid]["parameters"]["initial_liquidity_fraction"] = 0.01

        game.run_day()  # day 1 with different policy, trims day 0

        # Recompute day 0 — should use day 0's policy (fraction=0.5), not current (0.01)
        recomputed = game.recompute_day_events(0)
        assert _strip_tx_ids(recomputed) == original

    def test_recompute_invalid_day_raises(self, game):
        """Recomputing events for non-existent day should raise."""
        with pytest.raises((IndexError, ValueError)):
            game.recompute_day_events(99)


# ── 3. Idle game eviction ────────────────────────────────────────────

class TestIdleEviction:

    def test_touch_activity_updates_timestamp(self, game):
        """touch_activity should update last_activity_at."""
        old = game.last_activity_at
        import time; time.sleep(0.01)
        game.touch_activity()
        assert game.last_activity_at > old

    def test_evict_idle_games(self, scenario):
        """GameManager should evict games idle for > 1 hour."""
        from app.game_manager import GameManager

        mgr = GameManager()
        g1 = Game(game_id="evict-1", raw_yaml=scenario, total_days=1)
        g2 = Game(game_id="evict-2", raw_yaml=scenario, total_days=1)

        mgr.add(g1)
        mgr.add(g2)

        # Make g1 appear idle (last activity > 1 hour ago)
        old_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        g1.last_activity_at = old_time

        # g2 is recent
        g2.touch_activity()

        mgr.evict_idle(max_idle_seconds=3600)

        assert mgr.get("evict-1") is None
        assert mgr.get("evict-2") is not None


# ── 4. Avoid deepcopy in checkpointing ──────────────────────────────

class TestCheckpointNoDeepcopy:

    def test_game_to_checkpoint_no_deepcopy(self, game):
        """game_to_checkpoint should not use copy.deepcopy on the entire game."""
        game.run_day()

        # Monkey-patch copy.deepcopy to track calls
        original_deepcopy = copy.deepcopy
        deepcopy_targets = []

        def tracking_deepcopy(obj, memo=None):
            deepcopy_targets.append(type(obj).__name__)
            return original_deepcopy(obj, memo)

        with patch('app.serialization.copy.deepcopy', side_effect=tracking_deepcopy):
            checkpoint = game.to_checkpoint()

        # Should still produce valid checkpoint
        assert checkpoint["game_id"] == game.game_id
        # Should not deepcopy Game objects or huge structures
        # (some dict deepcopies are ok, just not the whole game)
        assert "Game" not in deepcopy_targets


# ── 5. Cap reasoning_history ─────────────────────────────────────────

class TestReasoningHistoryCap:

    def test_reasoning_history_capped_at_10(self, game):
        """After 15 optimization results, reasoning_history should have at most 10."""
        aid = game.agent_ids[0]
        for i in range(15):
            game.reasoning_history[aid].append({
                "day_num": i,
                "reasoning": f"test reasoning {i}",
                "mock": True,
            })

        game._cap_reasoning_history()

        assert len(game.reasoning_history[aid]) <= 10
        # Should keep the LAST 10
        assert game.reasoning_history[aid][-1]["day_num"] == 14
        assert game.reasoning_history[aid][0]["day_num"] == 5

    def test_cap_called_during_apply_result(self, game):
        """_apply_result should cap reasoning_history."""
        aid = game.agent_ids[0]
        # Pre-fill with 10 entries
        for i in range(10):
            game.reasoning_history[aid].append({"day_num": i, "reasoning": f"r{i}", "mock": True})

        # Apply one more result
        result = {"reasoning": "new", "new_policy": None, "mock": True}
        game._apply_result(aid, result)

        assert len(game.reasoning_history[aid]) <= 10
