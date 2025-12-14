"""Integration tests for _run_simulation() method.

Tests for the unified simulation execution method that captures all output.
Following TDD - tests written before implementation.

All cost values must be integers (INV-1: Money is ALWAYS i64).
Determinism must be maintained (INV-2: same seed = same output).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

if TYPE_CHECKING:
    from payment_simulator.experiments.config import ExperimentConfig
    from payment_simulator.experiments.runner.optimization import OptimizationLoop


def create_mock_config() -> MagicMock:
    """Create a mock experiment configuration for testing.

    Returns:
        MagicMock with ExperimentConfig interface.
    """
    from payment_simulator.experiments.config import ExperimentConfig
    from payment_simulator.llm import LLMConfig

    mock_config = MagicMock(spec=ExperimentConfig)
    mock_config.name = "test-experiment"
    mock_config.master_seed = 12345

    # Convergence settings
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = 10
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Evaluation settings
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = "deterministic"
    mock_config.evaluation.num_samples = 1
    mock_config.evaluation.ticks = 10

    # Optimized agents
    mock_config.optimized_agents = ("BANK_A",)
    mock_config.get_constraints.return_value = None

    # LLM config
    mock_config.llm = LLMConfig(model="anthropic:claude-sonnet-4-5")

    return mock_config


def get_test_scenario_dict() -> dict:
    """Get a minimal valid scenario dict for testing.

    Returns:
        Scenario dict that can be processed by SimulationConfig.from_dict().
    """
    return {
        "simulation": {
            "num_days": 1,
            "ticks_per_day": 10,
            "rng_seed": 12345,
        },
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
                "arrival": {
                    "rate_per_tick": 1.0,
                    "amount_distribution": {"type": "Fixed", "value": 10000},
                },
            },
            {
                "id": "BANK_B",
                "opening_balance": 1000000,
                "unsecured_cap": 0,
            },
        ],
    }


def create_loop_with_scenario(run_id: str = "test-run") -> "OptimizationLoop":
    """Create an OptimizationLoop with injected scenario dict for testing.

    This bypasses file loading by setting _scenario_dict directly.

    Args:
        run_id: Run ID for the loop.

    Returns:
        OptimizationLoop ready for testing.
    """
    from payment_simulator.experiments.runner.optimization import OptimizationLoop

    config = create_mock_config()
    loop = OptimizationLoop(config, run_id=run_id)

    # Inject scenario dict directly to bypass file loading
    loop._scenario_dict = get_test_scenario_dict()

    return loop


class TestRunSimulationIntegration:
    """Integration tests for _run_simulation() method."""

    def test_run_simulation_returns_simulation_result(self) -> None:
        """_run_simulation() returns SimulationResult dataclass."""
        from payment_simulator.experiments.runner.bootstrap_support import (
            SimulationResult,
        )

        loop = create_loop_with_scenario()
        result = loop._run_simulation(seed=12345, purpose="test")

        assert isinstance(result, SimulationResult)
        assert result.seed == 12345
        assert result.simulation_id is not None
        assert "-sim-" in result.simulation_id

    def test_run_simulation_generates_unique_id(self) -> None:
        """Each call generates a unique simulation ID."""
        loop = create_loop_with_scenario()

        result1 = loop._run_simulation(seed=1, purpose="test")
        result2 = loop._run_simulation(seed=2, purpose="test")

        assert result1.simulation_id != result2.simulation_id
        assert "test-run" in result1.simulation_id
        assert "test-run" in result2.simulation_id

    def test_run_simulation_captures_events(self) -> None:
        """Events are captured for all ticks."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # Should have some events from the simulation
        assert isinstance(result.events, tuple)
        # Each event should be a dict with at least event_type
        for event in result.events:
            assert isinstance(event, dict)
            assert "event_type" in event

    def test_run_simulation_extracts_cost_breakdown(self) -> None:
        """Cost breakdown includes delay, overdraft, deadline, eod."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )

        loop = create_loop_with_scenario()
        result = loop._run_simulation(seed=42, purpose="test")

        # Cost breakdown should be a CostBreakdown instance
        assert isinstance(result.cost_breakdown, CostBreakdown)
        # All cost fields should be integers (INV-1)
        assert isinstance(result.cost_breakdown.delay_cost, int)
        assert isinstance(result.cost_breakdown.overdraft_cost, int)
        assert isinstance(result.cost_breakdown.deadline_penalty, int)
        assert isinstance(result.cost_breakdown.eod_penalty, int)

    def test_run_simulation_calculates_settlement_rate(self) -> None:
        """Settlement rate is calculated correctly."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # Settlement rate should be between 0.0 and 1.0
        assert 0.0 <= result.settlement_rate <= 1.0
        # avg_delay should be non-negative
        assert result.avg_delay >= 0.0

    def test_run_simulation_deterministic_with_same_seed(self) -> None:
        """Same seed produces identical results (INV-2)."""
        seed = 12345

        loop1 = create_loop_with_scenario(run_id="test-run-1")
        result1 = loop1._run_simulation(seed=seed, purpose="test")

        loop2 = create_loop_with_scenario(run_id="test-run-2")
        result2 = loop2._run_simulation(seed=seed, purpose="test")

        # Costs should be identical
        assert result1.total_cost == result2.total_cost
        assert result1.per_agent_costs == result2.per_agent_costs
        assert result1.settlement_rate == result2.settlement_rate
        # Event count should be identical (though IDs may differ due to simulation ID)
        assert len(result1.events) == len(result2.events)

    def test_run_simulation_per_agent_costs_integer_cents(self) -> None:
        """Per-agent costs are integer cents (INV-1)."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # All per-agent costs should be integers
        for agent_id, cost in result.per_agent_costs.items():
            assert isinstance(cost, int), f"Cost for {agent_id} should be int"

    def test_run_simulation_total_cost_integer_cents(self) -> None:
        """Total cost is integer cents (INV-1)."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        assert isinstance(result.total_cost, int)

    def test_run_simulation_purpose_in_id(self) -> None:
        """Purpose is included in simulation ID."""
        loop = create_loop_with_scenario()

        result_init = loop._run_simulation(seed=1, purpose="init")
        result_eval = loop._run_simulation(seed=2, purpose="eval")
        result_bootstrap = loop._run_simulation(seed=3, purpose="bootstrap")

        assert "-init" in result_init.simulation_id
        assert "-eval" in result_eval.simulation_id
        assert "-bootstrap" in result_bootstrap.simulation_id


class TestRunSimulationVerboseLogging:
    """Tests for verbose logging in _run_simulation()."""

    def test_run_simulation_logs_id_when_verbose(self) -> None:
        """Simulation ID is logged to terminal when verbose logger is set."""
        from payment_simulator.experiments.runner.verbose import (
            VerboseConfig,
            VerboseLogger,
        )

        loop = create_loop_with_scenario()

        # Create a mock verbose logger
        mock_console = MagicMock()
        verbose_config = VerboseConfig(simulations=True)
        verbose_logger = VerboseLogger(verbose_config, console=mock_console)
        loop._verbose_logger = verbose_logger

        result = loop._run_simulation(seed=42, purpose="test")

        # Verify log_simulation_start was called
        # The logger should have printed something about the simulation ID
        assert mock_console.print.called

    def test_run_simulation_no_log_when_no_verbose(self) -> None:
        """No logging when verbose logger is not set."""
        loop = create_loop_with_scenario()
        loop._verbose_logger = None

        # Should not raise even without verbose logger
        result = loop._run_simulation(seed=42, purpose="test")

        assert result is not None


class TestRunSimulationPersistence:
    """Tests for persistence in _run_simulation()."""

    def test_run_simulation_persists_when_flag_set(self, tmp_path: Path) -> None:
        """Events are persisted to database when persist=True."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = create_mock_config()
        db_path = tmp_path / "test.db"

        with ExperimentRepository(db_path) as repo:
            loop = OptimizationLoop(
                config,
                run_id="test-run",
                repository=repo,
            )
            # Inject scenario dict to bypass file loading
            loop._scenario_dict = get_test_scenario_dict()
            loop._persist_bootstrap = True

            result = loop._run_simulation(seed=42, purpose="test", persist=True)

            # Check that events were persisted
            # The simulation_run event should be in the database
            # get_events(run_id, iteration) - iteration defaults to 0 in _run_simulation
            events = repo.get_events("test-run", iteration=0)
            assert len(events) > 0

            # Find the simulation_run event
            sim_events = [e for e in events if e.event_type == "simulation_run"]
            assert len(sim_events) == 1
            assert sim_events[0].event_data["simulation_id"] == result.simulation_id

    def test_run_simulation_no_persist_when_flag_false(self, tmp_path: Path) -> None:
        """Events are not persisted when persist=False."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = create_mock_config()
        db_path = tmp_path / "test.db"

        with ExperimentRepository(db_path) as repo:
            loop = OptimizationLoop(
                config,
                run_id="test-run",
                repository=repo,
            )
            # Inject scenario dict to bypass file loading
            loop._scenario_dict = get_test_scenario_dict()
            loop._persist_bootstrap = False

            result = loop._run_simulation(seed=42, purpose="test", persist=False)

            # Check that no events were persisted
            events = repo.get_events("test-run", iteration=0)
            sim_events = [e for e in events if e.event_type == "simulation_run"]
            assert len(sim_events) == 0

    def test_run_simulation_persist_override(self, tmp_path: Path) -> None:
        """Persist parameter overrides class default."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = create_mock_config()
        db_path = tmp_path / "test.db"

        with ExperimentRepository(db_path) as repo:
            loop = OptimizationLoop(
                config,
                run_id="test-run",
                repository=repo,
            )
            # Inject scenario dict to bypass file loading
            loop._scenario_dict = get_test_scenario_dict()
            # Class default is False
            loop._persist_bootstrap = False

            # But we explicitly pass persist=True
            result = loop._run_simulation(seed=42, purpose="test", persist=True)

            # Should persist because explicit parameter overrides default
            events = repo.get_events("test-run", iteration=0)
            sim_events = [e for e in events if e.event_type == "simulation_run"]
            assert len(sim_events) == 1


class TestRunSimulationIterationTracking:
    """Tests for iteration and sample tracking in _run_simulation()."""

    def test_run_simulation_with_iteration(self) -> None:
        """Iteration parameter is used for tracking."""
        loop = create_loop_with_scenario()

        # Run with iteration specified
        result = loop._run_simulation(seed=42, purpose="test", iteration=5)

        # Should succeed (iteration is used for logging/persistence)
        assert result is not None

    def test_run_simulation_with_sample_idx(self) -> None:
        """Sample index parameter is used for tracking."""
        loop = create_loop_with_scenario()

        # Run with sample_idx specified
        result = loop._run_simulation(seed=42, purpose="test", sample_idx=3)

        # Should succeed
        assert result is not None


class TestRunSimulationReplayIdentity:
    """Tests for replay identity invariant (INV-3).

    Events captured by _run_simulation() must be complete and self-contained
    for replay without reconstruction.
    """

    def test_run_simulation_events_have_tick_field(self) -> None:
        """All events have a tick field for chronological ordering."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # All events should have a tick field
        for event in result.events:
            assert "tick" in event, f"Event missing tick field: {event.get('event_type')}"
            assert isinstance(event["tick"], int), "tick must be an integer"

    def test_run_simulation_events_have_event_type(self) -> None:
        """All events have event_type for dispatch/filtering."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # All events should have event_type
        for event in result.events:
            assert "event_type" in event, f"Event missing event_type: {event}"
            assert isinstance(event["event_type"], str)

    def test_run_simulation_events_immutable(self) -> None:
        """Events are returned as immutable tuple for safety."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # Events should be a tuple (immutable)
        assert isinstance(result.events, tuple)

    def test_run_simulation_deterministic_events(self) -> None:
        """Same seed produces identical event sequence (INV-2 + INV-3)."""
        seed = 54321

        loop1 = create_loop_with_scenario(run_id="test-1")
        result1 = loop1._run_simulation(seed=seed, purpose="test")

        loop2 = create_loop_with_scenario(run_id="test-2")
        result2 = loop2._run_simulation(seed=seed, purpose="test")

        # Event count must be identical
        assert len(result1.events) == len(result2.events)

        # Event types and ticks must be identical
        for e1, e2 in zip(result1.events, result2.events):
            assert e1["event_type"] == e2["event_type"]
            assert e1["tick"] == e2["tick"]

    def test_run_simulation_cost_breakdown_complete(self) -> None:
        """CostBreakdown contains all cost components for analysis."""
        loop = create_loop_with_scenario()

        result = loop._run_simulation(seed=42, purpose="test")

        # Cost breakdown should have all components
        cb = result.cost_breakdown
        assert hasattr(cb, "delay_cost")
        assert hasattr(cb, "overdraft_cost")
        assert hasattr(cb, "deadline_penalty")
        assert hasattr(cb, "eod_penalty")

        # All should be integers (INV-1)
        assert isinstance(cb.delay_cost, int)
        assert isinstance(cb.overdraft_cost, int)
        assert isinstance(cb.deadline_penalty, int)
        assert isinstance(cb.eod_penalty, int)


class TestRunSimulationPersistBootstrapE2E:
    """E2E tests for --persist-bootstrap flag with unified _run_simulation()."""

    def test_initial_simulation_persists_with_flag(self, tmp_path: Path) -> None:
        """Initial simulation events are persisted when --persist-bootstrap is set."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = create_mock_config()
        db_path = tmp_path / "persist_test.db"

        with ExperimentRepository(db_path) as repo:
            loop = OptimizationLoop(
                config,
                run_id="persist-e2e-test",
                repository=repo,
            )
            loop._scenario_dict = get_test_scenario_dict()
            loop._persist_bootstrap = True  # Enable --persist-bootstrap

            # Run initial simulation (uses _run_simulation internally)
            result = loop._run_initial_simulation()

            # Verify events were persisted
            events = repo.get_events("persist-e2e-test", iteration=0)
            assert len(events) > 0, "Events should be persisted with --persist-bootstrap"

            # Verify simulation_run event exists
            sim_events = [e for e in events if e.event_type == "simulation_run"]
            assert len(sim_events) == 1, "simulation_run event should be persisted"

    def test_bootstrap_samples_not_persisted_by_default(self, tmp_path: Path) -> None:
        """Bootstrap sample simulations are NOT persisted by default."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        config = create_mock_config()
        db_path = tmp_path / "no_persist_test.db"

        with ExperimentRepository(db_path) as repo:
            loop = OptimizationLoop(
                config,
                run_id="no-persist-test",
                repository=repo,
            )
            loop._scenario_dict = get_test_scenario_dict()
            loop._persist_bootstrap = False  # Default: no persistence

            # Run a bootstrap sample (uses _run_simulation with persist=False)
            result = loop._run_simulation_with_events(seed=42, sample_idx=0)

            # Verify NO events were persisted (bootstrap samples don't persist by default)
            events = repo.get_events("no-persist-test", iteration=0)
            sim_events = [e for e in events if e.event_type == "simulation_run"]
            assert len(sim_events) == 0, "Bootstrap samples should NOT persist by default"
