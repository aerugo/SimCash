"""TDD tests for LiveStateProvider integration with OptimizationLoop.

These tests verify that the OptimizationLoop correctly creates and uses
the LiveStateProvider to capture events during experiment execution.

Write tests FIRST, then implement to make them pass.

Phase 03: LiveStateProvider Integration
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from payment_simulator.experiments.config import (
    ConvergenceConfig,
    EvaluationConfig,
    ExperimentConfig,
    OutputConfig,
)
from payment_simulator.experiments.runner.state_provider import LiveStateProvider
from payment_simulator.experiments.runner.verbose import VerboseConfig
from payment_simulator.llm.config import LLMConfig

# =============================================================================
# Test Fixtures
# =============================================================================


def get_test_config_dir() -> Path:
    """Get directory containing test scenario configs."""
    return Path(__file__).parent.parent.parent.parent.parent / "experiments" / "castro"


def create_test_experiment_config(
    name: str = "test_experiment",
    max_iterations: int = 2,
    evaluation_mode: str = "deterministic",
    num_samples: int = 1,
    ticks: int = 2,
    master_seed: int = 42,
) -> ExperimentConfig:
    """Create a minimal experiment config for testing.

    Args:
        name: Experiment name.
        max_iterations: Max iterations for convergence.
        evaluation_mode: 'deterministic' or 'bootstrap'.
        num_samples: Number of bootstrap samples.
        ticks: Simulation ticks per evaluation.
        master_seed: RNG seed.

    Returns:
        ExperimentConfig suitable for testing.
    """
    return ExperimentConfig(
        name=name,
        description="Test experiment",
        scenario_path=Path("configs/exp1_2period.yaml"),  # Relative to config_dir
        evaluation=EvaluationConfig(
            ticks=ticks,
            mode=evaluation_mode,
            num_samples=num_samples,
        ),
        convergence=ConvergenceConfig(
            max_iterations=max_iterations,
            stability_threshold=0.05,
            stability_window=3,
            improvement_threshold=0.01,
        ),
        llm=LLMConfig(model="anthropic:claude-sonnet-4-5"),
        optimized_agents=("BANK_A", "BANK_B"),  # All agents in the scenario
        constraints_module="",
        output=OutputConfig(
            directory=Path("results"),
            database="test.db",
            verbose=True,
        ),
        master_seed=master_seed,
    )


# =============================================================================
# Task 1: LiveStateProvider created for each run
# =============================================================================


class TestOptimizationLoopCreatesStateProvider:
    """Tests for OptimizationLoop._state_provider initialization."""

    def test_optimization_loop_creates_state_provider(self) -> None:
        """OptimizationLoop creates LiveStateProvider for event capture."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config()

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        assert loop._state_provider is not None
        assert isinstance(loop._state_provider, LiveStateProvider)

    def test_state_provider_has_experiment_metadata(self) -> None:
        """LiveStateProvider is initialized with experiment metadata."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(name="test_exp")

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        info = loop._state_provider.get_experiment_info()
        assert info["experiment_name"] == "test_exp"
        assert info["experiment_type"] == "generic"
        assert info["run_id"] is not None

    def test_state_provider_has_run_id(self) -> None:
        """LiveStateProvider has a run_id set."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config()

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        assert loop._state_provider.run_id is not None
        assert len(loop._state_provider.run_id) > 0

    def test_custom_run_id_passed_to_provider(self) -> None:
        """Custom run_id is passed to LiveStateProvider."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config()

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
            run_id="custom-run-id-123",
        )

        assert loop._state_provider.run_id == "custom-run-id-123"


# =============================================================================
# Task 2: Iteration events recorded
# =============================================================================


class TestIterationEventsRecorded:
    """Tests for iteration event recording during run()."""

    @pytest.mark.asyncio
    async def test_iteration_start_events_recorded(self) -> None:
        """OptimizationLoop records iteration_start events."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=2)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        # Check events were recorded
        events = list(loop._state_provider.get_all_events())
        iteration_starts = [e for e in events if e["event_type"] == "iteration_start"]

        assert len(iteration_starts) >= 1
        assert "iteration" in iteration_starts[0]
        assert "total_cost" in iteration_starts[0]

    @pytest.mark.asyncio
    async def test_iteration_costs_recorded(self) -> None:
        """OptimizationLoop records per-agent costs for each iteration."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=2)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        costs = loop._state_provider.get_iteration_costs(0)
        assert len(costs) > 0  # At least one agent
        assert all(isinstance(v, int) for v in costs.values())  # INV-1: integer cents

    @pytest.mark.asyncio
    async def test_experiment_start_event_recorded(self) -> None:
        """OptimizationLoop records experiment_start event at beginning."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=1, name="start_test")

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        start_events = [e for e in events if e["event_type"] == "experiment_start"]

        assert len(start_events) == 1
        assert start_events[0]["experiment_name"] == "start_test"
        assert "max_iterations" in start_events[0]


# =============================================================================
# Task 3: Bootstrap evaluation events
# =============================================================================


class TestBootstrapEventsRecorded:
    """Tests for bootstrap evaluation event recording."""

    @pytest.mark.asyncio
    async def test_bootstrap_events_recorded(self) -> None:
        """OptimizationLoop records bootstrap_evaluation events in bootstrap mode."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(
            evaluation_mode="bootstrap",
            num_samples=3,
            max_iterations=1,
        )

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        bootstrap_events = [e for e in events if e["event_type"] == "bootstrap_evaluation"]

        assert len(bootstrap_events) >= 1
        assert "seed_results" in bootstrap_events[0]
        assert "mean_cost" in bootstrap_events[0]

    @pytest.mark.asyncio
    async def test_bootstrap_event_structure(self) -> None:
        """Bootstrap events contain all required fields for display."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(
            evaluation_mode="bootstrap",
            num_samples=3,
            max_iterations=1,
        )

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        bootstrap_events = [e for e in events if e["event_type"] == "bootstrap_evaluation"]

        event = bootstrap_events[0]
        assert "seed_results" in event
        assert len(event["seed_results"]) == 3  # num_samples
        assert "seed" in event["seed_results"][0]
        assert "cost" in event["seed_results"][0]

    @pytest.mark.asyncio
    async def test_bootstrap_mean_cost_is_integer(self) -> None:
        """Bootstrap mean_cost must be integer cents (INV-1)."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(
            evaluation_mode="bootstrap",
            num_samples=3,
            max_iterations=1,
        )

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        bootstrap_events = [e for e in events if e["event_type"] == "bootstrap_evaluation"]

        if bootstrap_events:
            assert isinstance(bootstrap_events[0]["mean_cost"], int)


# =============================================================================
# Task 5: Final result recorded
# =============================================================================


class TestExperimentEndEventRecorded:
    """Tests for experiment end event recording."""

    @pytest.mark.asyncio
    async def test_experiment_end_event_recorded(self) -> None:
        """OptimizationLoop records experiment_end event on completion."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=2)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        end_events = [e for e in events if e["event_type"] == "experiment_end"]

        assert len(end_events) == 1
        assert "final_cost" in end_events[0]
        assert "converged" in end_events[0]

    @pytest.mark.asyncio
    async def test_final_result_accessible(self) -> None:
        """LiveStateProvider.get_final_result() returns correct data."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=2)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        result = loop._state_provider.get_final_result()
        assert result is not None
        assert "final_cost" in result
        assert "best_cost" in result
        assert "converged" in result
        assert isinstance(result["final_cost"], int)  # INV-1

    @pytest.mark.asyncio
    async def test_experiment_end_event_has_convergence_reason(self) -> None:
        """experiment_end event includes convergence_reason."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=2)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        end_events = [e for e in events if e["event_type"] == "experiment_end"]

        assert len(end_events) == 1
        assert "convergence_reason" in end_events[0]


# =============================================================================
# Task 6: StateProvider exposed for display
# =============================================================================


class TestRunnerExposesStateProvider:
    """Tests for GenericExperimentRunner.state_provider property."""

    def test_runner_has_state_provider_attribute(self) -> None:
        """GenericExperimentRunner has state_provider attribute."""
        from payment_simulator.experiments.runner import GenericExperimentRunner

        config = create_test_experiment_config()

        runner = GenericExperimentRunner(
            config=config,
            config_dir=get_test_config_dir(),
        )

        assert hasattr(runner, "state_provider")

    @pytest.mark.asyncio
    async def test_runner_exposes_state_provider_after_run(self) -> None:
        """GenericExperimentRunner exposes state_provider after run."""
        from payment_simulator.experiments.runner import GenericExperimentRunner

        config = create_test_experiment_config(max_iterations=1)

        runner = GenericExperimentRunner(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await runner.run()

        # Provider should exist and have data after run
        assert runner.state_provider is not None
        assert runner.state_provider.get_total_iterations() >= 1

    @pytest.mark.asyncio
    async def test_display_with_live_provider(self) -> None:
        """display_experiment_output() works with LiveStateProvider."""
        from rich.console import Console

        from payment_simulator.experiments.runner import OptimizationLoop
        from payment_simulator.experiments.runner.display import display_experiment_output

        config = create_test_experiment_config(max_iterations=1, name="display_test")
        verbose_config = VerboseConfig.all_enabled()

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        # Display using provider
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        display_experiment_output(loop._state_provider, console, verbose_config)

        output_text = output.getvalue()
        assert "display_test" in output_text or "Experiment" in output_text


# =============================================================================
# Task 7: Replay identity verification (integration with persistence)
# =============================================================================


class TestReplayIdentity:
    """Tests for replay identity - run output should match replay output.

    Note: These tests require the persistence layer to be wired up.
    """

    @pytest.mark.asyncio
    async def test_state_provider_has_all_events_for_display(self) -> None:
        """LiveStateProvider contains all event types needed for display."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(
            max_iterations=2,
            evaluation_mode="bootstrap",
            num_samples=3,
        )

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        event_types = {e["event_type"] for e in events}

        # Must have these core event types for replay identity
        assert "experiment_start" in event_types
        assert "iteration_start" in event_types
        assert "experiment_end" in event_types
        # Bootstrap events should be present if in bootstrap mode
        assert "bootstrap_evaluation" in event_types


# =============================================================================
# INV-1 Compliance Tests
# =============================================================================


class TestInv1Compliance:
    """Tests ensuring all costs are integer cents (INV-1)."""

    @pytest.mark.asyncio
    async def test_iteration_costs_are_integer_cents(self) -> None:
        """All iteration costs must be integer cents."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=2)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        for i in range(loop._state_provider.get_total_iterations()):
            costs = loop._state_provider.get_iteration_costs(i)
            for agent_id, cost in costs.items():
                msg = f"Cost for {agent_id} iter {i} must be integer cents"
                assert isinstance(cost, int), msg

    @pytest.mark.asyncio
    async def test_event_costs_are_integer_cents(self) -> None:
        """All cost fields in events must be integer cents."""
        from payment_simulator.experiments.runner import OptimizationLoop

        config = create_test_experiment_config(max_iterations=1)

        loop = OptimizationLoop(
            config=config,
            config_dir=get_test_config_dir(),
        )

        await loop.run()

        events = list(loop._state_provider.get_all_events())
        for event in events:
            for key, value in event.items():
                if "cost" in key.lower() and value is not None:
                    assert isinstance(value, int), f"Event cost field {key} must be integer cents"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
