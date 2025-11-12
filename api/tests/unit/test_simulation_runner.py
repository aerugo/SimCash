"""
Unit tests for SimulationRunner.

Tests the core template method that eliminates 4-way code duplication.
"""

from unittest.mock import Mock
import pytest
from payment_simulator.cli.execution.runner import (
    SimulationRunner,
    SimulationConfig,
    OutputStrategy,
)


class MockOutputStrategy:
    """Mock output strategy for testing."""

    def __init__(self):
        self.calls = []

    def on_simulation_start(self, config):
        self.calls.append(("on_simulation_start", config))

    def on_tick_start(self, tick):
        self.calls.append(("on_tick_start", tick))

    def on_tick_complete(self, result, orch):
        self.calls.append(("on_tick_complete", result.tick))

    def on_day_complete(self, day, day_stats, orch):
        self.calls.append(("on_day_complete", day))

    def on_simulation_complete(self, final_stats):
        self.calls.append(("on_simulation_complete", final_stats))


class TestSimulationRunner:
    """Tests for SimulationRunner template method."""

    def test_runner_calls_lifecycle_hooks_in_order(self):
        """Runner should call output strategy hooks in correct order."""
        orch = Mock()
        orch.tick.return_value = {
            "num_arrivals": 0,
            "num_settlements": 0,
            "num_lsm_releases": 0,
            "total_cost": 0,
        }
        orch.get_tick_events.return_value = []
        orch.get_system_metrics.return_value = {
            "total_arrivals": 0,
            "total_settlements": 0,
            "settlement_rate": 0.0,
        }

        config = SimulationConfig(
            total_ticks=5,
            ticks_per_day=5,
            num_days=1,
            persist=False,
            full_replay=False,
        )

        output = MockOutputStrategy()
        runner = SimulationRunner(orch, config, output, None)

        result = runner.run()

        # Verify call order
        assert output.calls[0][0] == "on_simulation_start"
        assert output.calls[1][0] == "on_tick_start"
        assert output.calls[1][1] == 0  # First tick
        assert output.calls[2][0] == "on_tick_complete"
        # ... more ticks ...
        assert output.calls[-2][0] == "on_day_complete"  # EOD at tick 4
        assert output.calls[-1][0] == "on_simulation_complete"

    def test_runner_detects_eod_correctly(self):
        """Runner should call on_day_complete at correct ticks."""
        orch = Mock()
        orch.tick.return_value = {
            "num_arrivals": 0,
            "num_settlements": 0,
            "num_lsm_releases": 0,
            "total_cost": 0,
        }
        orch.get_tick_events.return_value = []
        orch.get_system_metrics.return_value = {
            "total_arrivals": 0,
            "total_settlements": 0,
            "settlement_rate": 0.0,
        }

        config = SimulationConfig(
            total_ticks=20,
            ticks_per_day=10,
            num_days=2,
            persist=False,
            full_replay=False,
        )

        output = MockOutputStrategy()
        runner = SimulationRunner(orch, config, output, None)

        runner.run()

        # Find all on_day_complete calls
        eod_calls = [c for c in output.calls if c[0] == "on_day_complete"]

        # Should be called exactly 2 times (day 0 and day 1)
        assert len(eod_calls) == 2
        assert eod_calls[0][1] == 0  # Day 0
        assert eod_calls[1][1] == 1  # Day 1

    def test_runner_calls_persistence_hooks(self):
        """Runner should call persistence hooks at correct times."""
        orch = Mock()
        orch.tick.return_value = {
            "num_arrivals": 0,
            "num_settlements": 0,
            "num_lsm_releases": 0,
            "total_cost": 0,
        }
        orch.get_tick_events.return_value = []
        orch.get_agent_policies.return_value = []
        orch.get_system_metrics.return_value = {
            "total_arrivals": 0,
            "total_settlements": 0,
            "settlement_rate": 0.0,
        }

        config = SimulationConfig(
            total_ticks=10,
            ticks_per_day=10,
            num_days=1,
            persist=True,
            full_replay=False,
        )

        output = MockOutputStrategy()
        persistence = Mock()

        runner = SimulationRunner(orch, config, output, persistence)
        runner.run()

        # Verify persistence methods were called
        persistence.persist_initial_snapshots.assert_called_once_with(orch)
        assert persistence.on_tick_complete.call_count == 10
        assert persistence.on_day_complete.call_count == 1

    def test_runner_tracks_statistics_correctly(self):
        """Runner should accumulate statistics correctly."""
        orch = Mock()
        orch.tick.return_value = {
            "num_arrivals": 5,
            "num_settlements": 4,
            "num_lsm_releases": 1,
            "total_cost": 1000,
        }
        orch.get_tick_events.return_value = []
        orch.get_system_metrics.return_value = {
            "total_arrivals": 50,
            "total_settlements": 40,
            "settlement_rate": 0.8,
        }

        config = SimulationConfig(
            total_ticks=10,
            ticks_per_day=10,
            num_days=1,
            persist=False,
            full_replay=False,
        )

        output = MockOutputStrategy()
        runner = SimulationRunner(orch, config, output, None)

        result = runner.run()

        # Verify accumulated statistics
        assert result["total_arrivals"] == 50  # From get_system_metrics (corrected)
        assert result["total_settlements"] == 40  # From get_system_metrics (corrected)
        assert result["total_lsm_releases"] == 0  # From event processing (no LSM events mocked)
        assert result["total_costs"] == 10000  # From tick accumulation
        assert result["settlement_rate"] == 0.8  # From get_system_metrics (corrected)

    def test_runner_applies_event_filter(self):
        """Runner should filter events when event_filter is configured."""
        orch = Mock()
        orch.tick.return_value = {
            "num_arrivals": 2,
            "num_settlements": 1,
            "num_lsm_releases": 0,
            "total_cost": 0,
        }
        orch.get_tick_events.return_value = [
            {"event_type": "Arrival", "tx_id": "tx1"},
            {"event_type": "Settlement", "tx_id": "tx2"},
        ]
        orch.get_system_metrics.return_value = {
            "total_arrivals": 2,
            "total_settlements": 1,
            "settlement_rate": 0.5,
        }

        event_filter = Mock()
        event_filter.matches.side_effect = [True, False]  # Filter out second event

        config = SimulationConfig(
            total_ticks=1,
            ticks_per_day=1,
            num_days=1,
            persist=False,
            full_replay=False,
            event_filter=event_filter,
        )

        output = MockOutputStrategy()
        runner = SimulationRunner(orch, config, output, None)

        runner.run()

        # Find the on_tick_complete call
        tick_complete_calls = [c for c in output.calls if c[0] == "on_tick_complete"]
        assert len(tick_complete_calls) == 1

        # Event filter was applied (checked via mock)
        assert event_filter.matches.call_count == 2
