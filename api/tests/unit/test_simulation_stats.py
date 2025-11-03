"""
Unit tests for SimulationStats.

Tests the centralized statistics tracking class that eliminates
duplication across execution modes.
"""

import pytest
from payment_simulator.cli.execution.stats import SimulationStats, TickResult


class TestTickResult:
    """Tests for TickResult dataclass."""

    def test_tick_result_creation(self):
        """TickResult should be created with all required fields."""
        result = TickResult(
            tick=5,
            day=0,
            num_arrivals=10,
            num_settlements=8,
            num_lsm_releases=2,
            total_cost=5000,
            events=[],
        )

        assert result.tick == 5
        assert result.day == 0
        assert result.num_arrivals == 10
        assert result.num_settlements == 8
        assert result.num_lsm_releases == 2
        assert result.total_cost == 5000
        assert result.events == []

    def test_tick_result_with_events(self):
        """TickResult should store events list."""
        events = [
            {"event_type": "Arrival", "tx_id": "tx1"},
            {"event_type": "Settlement", "tx_id": "tx2"},
        ]
        result = TickResult(
            tick=0,
            day=0,
            num_arrivals=1,
            num_settlements=1,
            num_lsm_releases=0,
            total_cost=0,
            events=events,
        )

        assert len(result.events) == 2
        assert result.events[0]["event_type"] == "Arrival"


class TestSimulationStatsInitialization:
    """Tests for SimulationStats initialization."""

    def test_initialization_zeros_all_totals(self):
        """New SimulationStats should initialize all counters to zero."""
        stats = SimulationStats()

        assert stats.total_arrivals == 0
        assert stats.total_settlements == 0
        assert stats.total_lsm_releases == 0
        assert stats.total_costs == 0

    def test_initialization_zeros_day_stats(self):
        """New SimulationStats should initialize day counters to zero."""
        stats = SimulationStats()

        assert stats.day_arrivals == 0
        assert stats.day_settlements == 0
        assert stats.day_lsm_releases == 0
        assert stats.day_costs == 0


class TestSimulationStatsUpdate:
    """Tests for updating statistics with tick results."""

    def test_update_increments_totals(self):
        """Update should increment total counters."""
        stats = SimulationStats()

        result = TickResult(
            tick=0,
            day=0,
            num_arrivals=5,
            num_settlements=3,
            num_lsm_releases=1,
            total_cost=1000,
            events=[],
        )

        stats.update(result)

        assert stats.total_arrivals == 5
        assert stats.total_settlements == 3
        assert stats.total_lsm_releases == 1
        assert stats.total_costs == 1000

    def test_update_increments_day_stats(self):
        """Update should increment day counters."""
        stats = SimulationStats()

        result = TickResult(
            tick=0,
            day=0,
            num_arrivals=5,
            num_settlements=3,
            num_lsm_releases=1,
            total_cost=1000,
            events=[],
        )

        stats.update(result)

        assert stats.day_arrivals == 5
        assert stats.day_settlements == 3
        assert stats.day_lsm_releases == 1
        assert stats.day_costs == 1000

    def test_update_accumulates_multiple_ticks(self):
        """Multiple updates should accumulate correctly."""
        stats = SimulationStats()

        # Tick 0
        stats.update(
            TickResult(
                tick=0,
                day=0,
                num_arrivals=5,
                num_settlements=4,
                num_lsm_releases=1,
                total_cost=1000,
                events=[],
            )
        )

        # Tick 1
        stats.update(
            TickResult(
                tick=1,
                day=0,
                num_arrivals=3,
                num_settlements=2,
                num_lsm_releases=0,
                total_cost=500,
                events=[],
            )
        )

        assert stats.total_arrivals == 8
        assert stats.total_settlements == 6
        assert stats.total_lsm_releases == 1
        assert stats.total_costs == 1500

        assert stats.day_arrivals == 8
        assert stats.day_settlements == 6

    def test_update_handles_zero_values(self):
        """Update should handle zero values correctly."""
        stats = SimulationStats()

        stats.update(
            TickResult(
                tick=0,
                day=0,
                num_arrivals=0,
                num_settlements=0,
                num_lsm_releases=0,
                total_cost=0,
                events=[],
            )
        )

        assert stats.total_arrivals == 0
        assert stats.total_settlements == 0
        assert stats.total_lsm_releases == 0
        assert stats.total_costs == 0


class TestSimulationStatsDayStats:
    """Tests for day statistics retrieval."""

    def test_get_day_stats_returns_current_values(self):
        """get_day_stats should return current day counters."""
        stats = SimulationStats()

        stats.update(
            TickResult(
                tick=0,
                day=0,
                num_arrivals=10,
                num_settlements=8,
                num_lsm_releases=2,
                total_cost=5000,
                events=[],
            )
        )

        day_stats = stats.get_day_stats(0)

        assert day_stats["day"] == 0
        assert day_stats["arrivals"] == 10
        assert day_stats["settlements"] == 8
        assert day_stats["lsm_releases"] == 2
        assert day_stats["costs"] == 5000

    def test_get_day_stats_includes_accumulated_day_values(self):
        """get_day_stats should include all ticks from current day."""
        stats = SimulationStats()

        # Multiple ticks in day 0
        stats.update(
            TickResult(tick=0, day=0, num_arrivals=5, num_settlements=4, num_lsm_releases=1, total_cost=1000, events=[])
        )
        stats.update(
            TickResult(tick=1, day=0, num_arrivals=3, num_settlements=2, num_lsm_releases=0, total_cost=500, events=[])
        )

        day_stats = stats.get_day_stats(0)

        assert day_stats["arrivals"] == 8
        assert day_stats["settlements"] == 6
        assert day_stats["lsm_releases"] == 1
        assert day_stats["costs"] == 1500


class TestSimulationStatsReset:
    """Tests for resetting day statistics."""

    def test_reset_day_stats_zeros_day_counters(self):
        """reset_day_stats should zero day counters."""
        stats = SimulationStats()

        stats.update(
            TickResult(tick=0, day=0, num_arrivals=10, num_settlements=8, num_lsm_releases=2, total_cost=5000, events=[])
        )

        assert stats.day_arrivals == 10
        assert stats.day_settlements == 8

        stats.reset_day_stats()

        assert stats.day_arrivals == 0
        assert stats.day_settlements == 0
        assert stats.day_lsm_releases == 0
        assert stats.day_costs == 0

    def test_reset_day_stats_preserves_totals(self):
        """reset_day_stats should NOT reset total counters."""
        stats = SimulationStats()

        stats.update(
            TickResult(tick=0, day=0, num_arrivals=10, num_settlements=8, num_lsm_releases=2, total_cost=5000, events=[])
        )

        assert stats.total_arrivals == 10
        assert stats.total_settlements == 8

        stats.reset_day_stats()

        # Totals should remain unchanged
        assert stats.total_arrivals == 10
        assert stats.total_settlements == 8
        assert stats.total_lsm_releases == 2
        assert stats.total_costs == 5000

    def test_reset_day_stats_allows_new_day_tracking(self):
        """After reset, day stats should track new day correctly."""
        stats = SimulationStats()

        # Day 0
        stats.update(
            TickResult(tick=0, day=0, num_arrivals=10, num_settlements=8, num_lsm_releases=0, total_cost=1000, events=[])
        )

        assert stats.day_arrivals == 10
        assert stats.total_arrivals == 10

        stats.reset_day_stats()

        # Day 1
        stats.update(
            TickResult(tick=10, day=1, num_arrivals=5, num_settlements=4, num_lsm_releases=0, total_cost=500, events=[])
        )

        assert stats.day_arrivals == 5  # Reset for day 1
        assert stats.total_arrivals == 15  # Accumulated across days


class TestSimulationStatsToDictionary:
    """Tests for converting stats to dictionary."""

    def test_to_dict_returns_all_totals(self):
        """to_dict should return all total counters."""
        stats = SimulationStats()

        stats.update(
            TickResult(tick=0, day=0, num_arrivals=100, num_settlements=95, num_lsm_releases=10, total_cost=50000, events=[])
        )

        result = stats.to_dict()

        assert result["total_arrivals"] == 100
        assert result["total_settlements"] == 95
        assert result["total_lsm_releases"] == 10
        assert result["total_costs"] == 50000

    def test_to_dict_calculates_settlement_rate(self):
        """to_dict should calculate settlement rate."""
        stats = SimulationStats()

        stats.update(
            TickResult(tick=0, day=0, num_arrivals=100, num_settlements=95, num_lsm_releases=0, total_cost=0, events=[])
        )

        result = stats.to_dict()

        assert result["settlement_rate"] == 0.95  # 95/100

    def test_to_dict_handles_zero_arrivals(self):
        """to_dict should handle zero arrivals (avoid division by zero)."""
        stats = SimulationStats()

        # No transactions
        result = stats.to_dict()

        assert result["settlement_rate"] == 0  # Should not raise error

    def test_to_dict_settlement_rate_precision(self):
        """to_dict settlement rate should be floating point."""
        stats = SimulationStats()

        stats.update(
            TickResult(tick=0, day=0, num_arrivals=3, num_settlements=2, num_lsm_releases=0, total_cost=0, events=[])
        )

        result = stats.to_dict()

        assert result["settlement_rate"] == pytest.approx(0.6666666, rel=1e-5)
