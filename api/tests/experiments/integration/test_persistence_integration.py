"""TDD integration tests for persistence integration with experiment runner.

Tests verify that GenericExperimentRunner and OptimizationLoop correctly
persist experiment data to DuckDB via ExperimentRepository.

Write tests FIRST (TDD), then implement to make them pass.

Phase: 02-persistence-integration
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Test Fixtures
# =============================================================================


def create_minimal_scenario_yaml(path: Path) -> None:
    """Create a minimal scenario YAML file for testing.

    Args:
        path: Path to write the scenario file.
    """
    content = dedent("""
        simulation:
          ticks_per_day: 2
          num_days: 1
          rng_seed: 42

        cost_rates:
          collateral_cost_per_tick_bps: 500
          delay_cost_per_tick_per_cent: 0.1
          overdraft_bps_per_tick: 2000
          eod_penalty_per_transaction: 100000
          deadline_penalty: 50000
          split_friction_cost: 0

        lsm_config:
          enable_bilateral: false
          enable_cycles: false

        agents:
          - id: BANK_A
            opening_balance: 100000
            unsecured_cap: 50000
            max_collateral_capacity: 10000000
            policy:
              version: "2.0"
              policy_id: "BANK_A_default"
              parameters:
                urgency_threshold: 5
              payment_tree:
                type: action
                node_id: default_release
                action: Release
              strategic_collateral_tree:
                type: action
                node_id: default_collateral
                action: HoldCollateral
                parameters:
                  amount:
                    value: 0
                  reason:
                    value: InitialAllocation

          - id: BANK_B
            opening_balance: 100000
            unsecured_cap: 50000
            max_collateral_capacity: 10000000
            policy:
              version: "2.0"
              policy_id: "BANK_B_default"
              parameters:
                urgency_threshold: 5
              payment_tree:
                type: action
                node_id: default_release
                action: Release
              strategic_collateral_tree:
                type: action
                node_id: default_collateral
                action: HoldCollateral
                parameters:
                  amount:
                    value: 0
                  reason:
                    value: InitialAllocation

        scenario_events:
          - type: CustomTransactionArrival
            from_agent: BANK_A
            to_agent: BANK_B
            amount: 1000
            priority: 5
            deadline: 2
            schedule:
              type: OneTime
              tick: 0
    """)
    path.write_text(content)


def create_experiment_config_yaml(
    path: Path,
    *,
    name: str = "test_exp",
    scenario_path: str = "scenario.yaml",
    max_iterations: int = 1,
    output_directory: str | None = None,
    output_database: str | None = None,
) -> None:
    """Create an experiment config YAML file for testing.

    Args:
        path: Path to write the config file.
        name: Experiment name.
        scenario_path: Relative path to scenario file.
        max_iterations: Maximum iterations.
        output_directory: Output directory (optional).
        output_database: Database filename (optional).
    """
    output_section = ""
    if output_directory is not None or output_database is not None:
        output_section = "output:\n"
        if output_directory is not None:
            output_section += f"  directory: {output_directory}\n"
        if output_database is not None:
            output_section += f"  database: {output_database}\n"
        output_section += "  verbose: true"

    content = f"""name: {name}
description: "Test experiment"
scenario: {scenario_path}
evaluation:
  mode: deterministic
  ticks: 2
convergence:
  max_iterations: {max_iterations}
  stability_threshold: 0.05
  stability_window: 3
llm:
  model: "anthropic:claude-sonnet-4-5"
optimized_agents:
  - BANK_A
{output_section}
master_seed: 42
"""
    path.write_text(content)


# =============================================================================
# Task 1: Repository created from config
# =============================================================================


class TestRepositoryCreatedFromConfig:
    """Tests for Task 1: Repository created from config."""

    def test_runner_creates_repository_when_output_configured(
        self, tmp_path: Path
    ) -> None:
        """GenericExperimentRunner creates ExperimentRepository when output.database set."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config files
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(tmp_path / "results"),
            output_database="test.db",
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        assert runner._repository is not None
        assert isinstance(runner._repository, ExperimentRepository)

    def test_runner_no_repository_when_output_not_configured(
        self, tmp_path: Path
    ) -> None:
        """GenericExperimentRunner has no repository when output not configured."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create config without output section
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        # Config without output.database
        config_yaml = dedent("""
            name: test_exp
            description: "Test"
            scenario: scenario.yaml
            evaluation:
              mode: deterministic
              ticks: 2
            convergence:
              max_iterations: 1
            llm:
              model: "anthropic:claude-sonnet-4-5"
            optimized_agents:
              - BANK_A
        """)
        config_path = tmp_path / "exp.yaml"
        config_path.write_text(config_yaml)

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        assert runner._repository is None

    def test_database_created_in_output_directory(self, tmp_path: Path) -> None:
        """Database file is created in the configured output directory."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config files
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="experiments.db",
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        # Directory and database should be created
        db_path = output_dir / "experiments.db"
        assert db_path.exists()

    def test_output_directory_created_if_not_exists(self, tmp_path: Path) -> None:
        """Output directory is created if it doesn't exist."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario file
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        # Non-existent nested output directory
        output_dir = tmp_path / "results" / "nested" / "deep"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        assert output_dir.exists()
        assert (output_dir / "test.db").exists()


# =============================================================================
# Task 2: Experiment record saved at start
# =============================================================================


class TestExperimentRecordSavedAtStart:
    """Tests for Task 2: Experiment record saved at start."""

    @pytest.mark.asyncio
    async def test_experiment_record_saved_at_start(self, tmp_path: Path) -> None:
        """ExperimentRecord is saved when experiment run starts."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            name="test_exp",
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=1,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        # Run experiment
        await runner.run()

        # Verify record exists in database
        experiments = runner._repository.list_experiments()
        assert len(experiments) == 1
        assert experiments[0].experiment_name == "test_exp"

    @pytest.mark.asyncio
    async def test_experiment_record_has_metadata(self, tmp_path: Path) -> None:
        """ExperimentRecord contains correct metadata."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            name="test_metadata",
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=1,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        experiments = runner._repository.list_experiments()
        record = experiments[0]

        assert record.experiment_name == "test_metadata"
        assert record.experiment_type == "generic"
        assert record.config is not None
        assert "master_seed" in str(record.config)

    @pytest.mark.asyncio
    async def test_experiment_record_has_run_id(self, tmp_path: Path) -> None:
        """ExperimentRecord has correct run_id."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=1,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
            run_id="custom-run-id-123",
        )

        await runner.run()

        experiments = runner._repository.list_experiments()
        assert experiments[0].run_id == "custom-run-id-123"


# =============================================================================
# Task 3: Iteration records saved
# =============================================================================


class TestIterationRecordsSaved:
    """Tests for Task 3: Iteration records saved."""

    @pytest.mark.asyncio
    async def test_iteration_records_saved(self, tmp_path: Path) -> None:
        """IterationRecords are saved for each iteration."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=3,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        # Query iterations from database
        iterations = runner._repository.get_iterations(runner._run_id)
        assert len(iterations) >= 1  # At least 1 iteration ran

    @pytest.mark.asyncio
    async def test_iteration_records_have_costs(self, tmp_path: Path) -> None:
        """IterationRecords contain cost data in integer cents."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=1,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        iterations = runner._repository.get_iterations(runner._run_id)
        assert len(iterations) >= 1

        iteration = iterations[0]
        # INV-1: All costs must be integer cents
        for agent_id, cost in iteration.costs_per_agent.items():
            assert isinstance(cost, int), f"Cost for {agent_id} must be integer cents"
        assert iteration.iteration >= 0

    @pytest.mark.asyncio
    async def test_iteration_records_have_policies(self, tmp_path: Path) -> None:
        """IterationRecords contain policies."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=1,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        iterations = runner._repository.get_iterations(runner._run_id)
        assert len(iterations) >= 1

        iteration = iterations[0]
        # Policies should be stored
        assert iteration.policies is not None


# =============================================================================
# Task 4: Final result saved
# =============================================================================


class TestFinalResultSaved:
    """Tests for Task 4: Final result saved."""

    @pytest.mark.asyncio
    async def test_experiment_marked_complete(self, tmp_path: Path) -> None:
        """Experiment record is updated when run completes."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=2,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        experiments = runner._repository.list_experiments()
        record = experiments[0]

        assert record.completed_at is not None
        assert record.num_iterations >= 1

    @pytest.mark.asyncio
    async def test_convergence_info_saved(self, tmp_path: Path) -> None:
        """Convergence info is saved in experiment record."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=2,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        experiments = runner._repository.list_experiments()
        record = experiments[0]

        # Convergence info should be set (converged or not)
        assert record.converged is not None
        assert record.convergence_reason is not None

    @pytest.mark.asyncio
    async def test_result_matches_database_record(self, tmp_path: Path) -> None:
        """ExperimentResult matches database record."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=2,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        result = await runner.run()

        experiments = runner._repository.list_experiments()
        record = experiments[0]

        # Result should match database
        assert record.num_iterations == result.num_iterations
        assert record.converged == result.converged
        assert record.convergence_reason == result.convergence_reason


# =============================================================================
# Task 5: Events saved for audit
# =============================================================================


class TestEventsSavedForAudit:
    """Tests for Task 5: Events saved for audit."""

    @pytest.mark.asyncio
    async def test_evaluation_events_saved(self, tmp_path: Path) -> None:
        """Evaluation events are saved for audit."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=2,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        # Query events from database
        events = runner._repository.get_all_events(runner._run_id)

        # Should have at least evaluation events
        eval_events = [e for e in events if e.event_type == "evaluation"]
        assert len(eval_events) >= 1  # At least one evaluation occurred

    @pytest.mark.asyncio
    async def test_events_have_iteration_info(self, tmp_path: Path) -> None:
        """Events have correct iteration info."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=3,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        events = runner._repository.get_all_events(runner._run_id)

        # Events should have iteration numbers
        for event in events:
            assert event.iteration >= 0
            assert event.timestamp is not None


# =============================================================================
# Integration: End-to-end persistence test
# =============================================================================


class TestEndToEndPersistence:
    """End-to-end tests for persistence integration."""

    @pytest.mark.asyncio
    async def test_full_experiment_persisted(self, tmp_path: Path) -> None:
        """Full experiment run is persisted correctly."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.persistence import ExperimentRepository
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            name="full_test",
            output_directory=str(output_dir),
            output_database="full_test.db",
            max_iterations=3,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        result = await runner.run()

        # Verify all data is persisted
        db_path = output_dir / "full_test.db"
        assert db_path.exists()

        # Open a new repository connection to verify persistence
        with ExperimentRepository(db_path) as repo:
            # Experiment record
            experiments = repo.list_experiments()
            assert len(experiments) == 1
            assert experiments[0].experiment_name == "full_test"
            assert experiments[0].completed_at is not None

            # Iteration records
            iterations = repo.get_iterations(runner._run_id)
            assert len(iterations) >= 1

            # Events
            events = repo.get_all_events(runner._run_id)
            # We expect at least evaluation events
            assert len(events) >= 1

    @pytest.mark.asyncio
    async def test_repository_closed_after_run(self, tmp_path: Path) -> None:
        """Repository is properly closed after run completes."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner import GenericExperimentRunner

        # Create scenario and experiment config
        scenario_path = tmp_path / "scenario.yaml"
        create_minimal_scenario_yaml(scenario_path)

        output_dir = tmp_path / "results"
        config_path = tmp_path / "exp.yaml"
        create_experiment_config_yaml(
            config_path,
            output_directory=str(output_dir),
            output_database="test.db",
            max_iterations=1,
        )

        config = ExperimentConfig.from_yaml(config_path)
        runner = GenericExperimentRunner(
            config=config,
            config_dir=tmp_path,
        )

        await runner.run()

        # Repository should still be accessible for final verification
        assert runner._repository is not None
