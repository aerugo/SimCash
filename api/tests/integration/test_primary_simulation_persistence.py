"""Phase 5: Primary Simulation Persistence Tests.

Tests that verify primary simulations persist by default while bootstrap
samples only persist with --persist-bootstrap flag.

Per user specification:
- Primary simulations (main scenario run each iteration) should persist BY DEFAULT
- Bootstrap sample simulations should ONLY persist with --persist-bootstrap flag
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from payment_simulator.experiments.persistence import ExperimentRepository


@pytest.fixture
def deterministic_scenario_config(tmp_path: Path) -> Path:
    """Create a minimal deterministic scenario config."""
    scenario_content = """
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 12345
  costs:
    delay_per_tick: 1
    delay_overdue_multiplier: 5
    liquidity_per_tick: 1
    deadline_penalty: 100
    eod_penalty: 1000
    split_fee: 10

agents:
  - id: BANK_A
    opening_balance: 100000
    credit_limit: 0
  - id: BANK_B
    opening_balance: 100000
    credit_limit: 0

transactions: []
"""
    scenario_path = tmp_path / "deterministic_scenario.yaml"
    scenario_path.write_text(scenario_content)
    return scenario_path


@pytest.fixture
def deterministic_experiment_config(
    tmp_path: Path, deterministic_scenario_config: Path
) -> Path:
    """Create a minimal deterministic experiment config."""
    experiment_content = f"""
name: test-deterministic-persistence
description: Test primary simulation persistence in deterministic mode
scenario: {deterministic_scenario_config}

evaluation:
  mode: deterministic
  num_samples: 1
  ticks: 2

convergence:
  max_iterations: 1
  stability_threshold: 0.1
  stability_window: 1

llm:
  model: "test:mock"
  temperature: 0.0
  max_retries: 1
  timeout_seconds: 10

optimized_agents:
  - BANK_A

output:
  directory: {tmp_path / "results"}
  database: test.db
  verbose: false

master_seed: 42
"""
    exp_config_path = tmp_path / "experiment.yaml"
    exp_config_path.write_text(experiment_content)
    return exp_config_path


@pytest.fixture
def experiment_repository(tmp_path: Path) -> ExperimentRepository:
    """Create a fresh experiment repository."""
    from payment_simulator.experiments.persistence import ExperimentRepository

    db_path = tmp_path / "test_persistence.db"
    return ExperimentRepository(db_path)


class TestPrimarySimulationPersistsByDefault:
    """Tests for primary simulation persistence behavior.

    Primary simulations should persist by default when a repository is present,
    WITHOUT requiring any special flag.
    """

    def test_deterministic_mode_primary_simulation_persists_by_default(
        self,
        experiment_repository: ExperimentRepository,
        deterministic_experiment_config: Path,
        tmp_path: Path,
    ) -> None:
        """Primary simulation in deterministic mode should persist without any flag.

        This is the key test for Phase 5: when running an experiment with a
        repository but persist_bootstrap=False, the PRIMARY simulation
        (main scenario run) should still be persisted.
        """
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        # Load experiment config
        exp_config = ExperimentConfig.from_yaml(deterministic_experiment_config)

        # Create OptimizationLoop with repository but persist_bootstrap=False
        loop = OptimizationLoop(
            config=exp_config,
            config_dir=tmp_path,
            repository=experiment_repository,
            run_id="test-primary-persistence",
            persist_bootstrap=False,  # Explicitly False - but primary should still persist!
        )

        # Run _evaluate_policies which runs the primary simulation
        # This is what happens each iteration
        import asyncio

        total_cost, per_agent_costs = asyncio.get_event_loop().run_until_complete(
            loop._evaluate_policies()
        )

        # Query database - should find the primary simulation
        result = experiment_repository._conn.execute(
            "SELECT simulation_id, status, config_json FROM simulations"
        ).fetchall()

        # PRIMARY simulation should be persisted even with persist_bootstrap=False
        assert len(result) >= 1, (
            "Primary simulation should persist by default when repository is present. "
            f"Found {len(result)} simulations, expected at least 1."
        )

        # Verify it has correct format for replay (YAML format, not FFI)
        sim_id, status, config_json = result[0]
        assert status == "completed", f"Simulation should be completed, got {status}"

        config = json.loads(config_json)
        assert "agents" in config, (
            f"Config should have 'agents' key (YAML format), got keys: {list(config.keys())}"
        )
        assert "simulation" in config, (
            f"Config should have 'simulation' key (YAML format), got keys: {list(config.keys())}"
        )

    def test_primary_simulation_has_events_for_replay(
        self,
        experiment_repository: ExperimentRepository,
        deterministic_experiment_config: Path,
        tmp_path: Path,
    ) -> None:
        """Primary simulation should have events persisted for replay."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        exp_config = ExperimentConfig.from_yaml(deterministic_experiment_config)

        loop = OptimizationLoop(
            config=exp_config,
            config_dir=tmp_path,
            repository=experiment_repository,
            run_id="test-events-persistence",
            persist_bootstrap=False,
        )

        import asyncio

        asyncio.get_event_loop().run_until_complete(loop._evaluate_policies())

        # Query simulation_events table
        events_result = experiment_repository._conn.execute(
            "SELECT COUNT(*) FROM simulation_events"
        ).fetchone()

        assert events_result[0] > 0, (
            "Primary simulation should have events persisted for replay. "
            f"Found {events_result[0]} events, expected > 0."
        )

    def test_multiple_iterations_each_persist_primary(
        self,
        experiment_repository: ExperimentRepository,
        deterministic_experiment_config: Path,
        tmp_path: Path,
    ) -> None:
        """Each iteration should persist its primary simulation."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        exp_config = ExperimentConfig.from_yaml(deterministic_experiment_config)

        loop = OptimizationLoop(
            config=exp_config,
            config_dir=tmp_path,
            repository=experiment_repository,
            run_id="test-multi-iteration",
            persist_bootstrap=False,
        )

        import asyncio

        # Run _evaluate_policies twice (simulating 2 iterations)
        asyncio.get_event_loop().run_until_complete(loop._evaluate_policies())
        asyncio.get_event_loop().run_until_complete(loop._evaluate_policies())

        # Should have 2 primary simulations persisted
        result = experiment_repository._conn.execute(
            "SELECT COUNT(*) FROM simulations"
        ).fetchone()

        assert result[0] >= 2, (
            f"Each iteration should persist primary simulation. "
            f"Found {result[0]} simulations after 2 iterations, expected >= 2."
        )


class TestBootstrapSamplesPersistOnlyWithFlag:
    """Tests verifying bootstrap samples only persist with --persist-bootstrap."""

    @pytest.fixture
    def bootstrap_scenario_config(self, tmp_path: Path) -> Path:
        """Create a scenario with stochastic arrivals for bootstrap mode."""
        scenario_content = """
simulation:
  ticks_per_day: 2
  num_days: 1
  rng_seed: 12345
  costs:
    delay_per_tick: 1
    delay_overdue_multiplier: 5
    liquidity_per_tick: 1
    deadline_penalty: 100
    eod_penalty: 1000
    split_fee: 10

agents:
  - id: BANK_A
    opening_balance: 100000
    credit_limit: 0
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: Normal
        mean: 1000
        std_dev: 200
      counterparty_weights:
        BANK_B: 1.0
      deadline_range: [1, 2]
  - id: BANK_B
    opening_balance: 100000
    credit_limit: 0
    arrival_config:
      rate_per_tick: 2.0
      amount_distribution:
        type: Normal
        mean: 1000
        std_dev: 200
      counterparty_weights:
        BANK_A: 1.0
      deadline_range: [1, 2]

transactions: []
"""
        scenario_path = tmp_path / "bootstrap_scenario.yaml"
        scenario_path.write_text(scenario_content)
        return scenario_path

    @pytest.fixture
    def bootstrap_experiment_config(
        self, tmp_path: Path, bootstrap_scenario_config: Path
    ) -> Path:
        """Create a bootstrap mode experiment config."""
        experiment_content = f"""
name: test-bootstrap-persistence
description: Test bootstrap sample persistence
scenario: {bootstrap_scenario_config}

evaluation:
  mode: bootstrap
  num_samples: 5
  ticks: 2

convergence:
  max_iterations: 1
  stability_threshold: 0.1
  stability_window: 1

llm:
  model: "test:mock"
  temperature: 0.0
  max_retries: 1
  timeout_seconds: 10

optimized_agents:
  - BANK_A

output:
  directory: {tmp_path / "results"}
  database: test.db
  verbose: false

master_seed: 42
"""
        exp_config_path = tmp_path / "bootstrap_experiment.yaml"
        exp_config_path.write_text(experiment_content)
        return exp_config_path

    def test_bootstrap_samples_dont_persist_without_flag(
        self,
        experiment_repository: ExperimentRepository,
        bootstrap_experiment_config: Path,
        tmp_path: Path,
    ) -> None:
        """Bootstrap sample simulations should NOT persist without --persist-bootstrap.

        When persist_bootstrap=False, only the PRIMARY simulation should persist,
        not the N bootstrap sample simulations used for policy comparison.
        """
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        exp_config = ExperimentConfig.from_yaml(bootstrap_experiment_config)
        num_samples = exp_config.evaluation.num_samples  # 5 samples

        loop = OptimizationLoop(
            config=exp_config,
            config_dir=tmp_path,
            repository=experiment_repository,
            run_id="test-no-bootstrap-persist",
            persist_bootstrap=False,  # Bootstrap samples should NOT persist
        )

        import asyncio

        # Set iteration state to simulate being in iteration 1
        # (required for state provider to record events properly)
        loop._current_iteration = 1

        # Run evaluation which triggers bootstrap samples
        asyncio.get_event_loop().run_until_complete(loop._evaluate_policies())

        # Count simulations
        result = experiment_repository._conn.execute(
            "SELECT COUNT(*) FROM simulations"
        ).fetchone()

        # Should have only primary simulation(s), NOT the bootstrap samples
        # With num_samples=5, if bootstrap samples persisted we'd have 5+ simulations
        assert result[0] < num_samples, (
            f"Bootstrap samples should NOT persist without flag. "
            f"Found {result[0]} simulations, but num_samples={num_samples}. "
            "Only primary simulations should be persisted."
        )

    def test_bootstrap_samples_persist_with_flag(
        self,
        experiment_repository: ExperimentRepository,
        bootstrap_experiment_config: Path,
        tmp_path: Path,
    ) -> None:
        """Bootstrap sample simulations SHOULD persist with --persist-bootstrap."""
        from payment_simulator.experiments.config import ExperimentConfig
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        exp_config = ExperimentConfig.from_yaml(bootstrap_experiment_config)
        num_samples = exp_config.evaluation.num_samples  # 5 samples

        loop = OptimizationLoop(
            config=exp_config,
            config_dir=tmp_path,
            repository=experiment_repository,
            run_id="test-with-bootstrap-persist",
            persist_bootstrap=True,  # Bootstrap samples SHOULD persist
        )

        import asyncio

        # Set iteration state to simulate being in iteration 1
        loop._current_iteration = 1

        asyncio.get_event_loop().run_until_complete(loop._evaluate_policies())

        # Count simulations
        result = experiment_repository._conn.execute(
            "SELECT COUNT(*) FROM simulations"
        ).fetchone()

        # Should have primary + bootstrap samples
        assert result[0] >= num_samples, (
            f"Bootstrap samples should persist with flag. "
            f"Found {result[0]} simulations, expected >= {num_samples}."
        )
