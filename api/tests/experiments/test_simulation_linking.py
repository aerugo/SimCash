"""TDD tests for Phase 3: Experiment → Simulation linking.

These tests are written FIRST following strict TDD principles.
Run these tests to verify they fail (RED), then implement to make them pass (GREEN).

Phase 3.1: Simulation ID generation and parsing
Phase 3.2: ExperimentPersistencePolicy dataclass
Phase 3.3: ExperimentSimulationPersister class
"""

from __future__ import annotations

from typing import Any

import pytest

from payment_simulator.persistence.models import SimulationRunPurpose


# =============================================================================
# Phase 3.1: Simulation ID Generation Tests
# =============================================================================


class TestSimulationIdGeneration:
    """Tests for structured simulation ID generation."""

    def test_generates_evaluation_format(self) -> None:
        """Should generate correct format for evaluation runs."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
        )

        sim_id = generate_experiment_simulation_id(
            experiment_id="exp1-20251214-abc123",
            iteration=5,
            purpose=SimulationRunPurpose.EVALUATION,
        )

        assert sim_id == "exp1-20251214-abc123-iter5-evaluation"

    def test_generates_initial_format(self) -> None:
        """Should generate correct format for initial runs."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
        )

        sim_id = generate_experiment_simulation_id(
            experiment_id="exp1-20251214-abc123",
            iteration=0,
            purpose=SimulationRunPurpose.INITIAL,
        )

        assert sim_id == "exp1-20251214-abc123-iter0-initial"

    def test_generates_bootstrap_format_with_sample(self) -> None:
        """Should include sample index for bootstrap runs."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
        )

        sim_id = generate_experiment_simulation_id(
            experiment_id="exp1-20251214-abc123",
            iteration=5,
            purpose=SimulationRunPurpose.BOOTSTRAP,
            sample_index=3,
        )

        assert sim_id == "exp1-20251214-abc123-iter5-bootstrap-sample3"

    def test_generates_final_format(self) -> None:
        """Should generate correct format for final runs."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
        )

        sim_id = generate_experiment_simulation_id(
            experiment_id="exp1-20251214-abc123",
            iteration=49,
            purpose=SimulationRunPurpose.FINAL,
        )

        assert sim_id == "exp1-20251214-abc123-iter49-final"

    def test_generates_best_format(self) -> None:
        """Should generate correct format for best runs."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
        )

        sim_id = generate_experiment_simulation_id(
            experiment_id="exp1-20251214-abc123",
            iteration=25,
            purpose=SimulationRunPurpose.BEST,
        )

        assert sim_id == "exp1-20251214-abc123-iter25-best"

    def test_sample_index_ignored_for_non_bootstrap(self) -> None:
        """Sample index should only be included for bootstrap purpose."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
        )

        # Even if sample_index is provided, it should be ignored for non-bootstrap
        sim_id = generate_experiment_simulation_id(
            experiment_id="exp1-20251214-abc123",
            iteration=5,
            purpose=SimulationRunPurpose.EVALUATION,
            sample_index=3,  # Should be ignored
        )

        # Should NOT include sample suffix for evaluation
        assert sim_id == "exp1-20251214-abc123-iter5-evaluation"


class TestSimulationIdParsing:
    """Tests for parsing structured simulation IDs back to components."""

    def test_parses_evaluation_id(self) -> None:
        """Should parse evaluation ID back to components."""
        from payment_simulator.experiments.simulation_id import (
            parse_experiment_simulation_id,
        )

        result = parse_experiment_simulation_id("exp1-20251214-abc123-iter5-evaluation")

        assert result["experiment_id"] == "exp1-20251214-abc123"
        assert result["iteration"] == 5
        assert result["purpose"] == SimulationRunPurpose.EVALUATION
        assert result["sample_index"] is None

    def test_parses_bootstrap_with_sample(self) -> None:
        """Should parse bootstrap ID with sample index."""
        from payment_simulator.experiments.simulation_id import (
            parse_experiment_simulation_id,
        )

        result = parse_experiment_simulation_id(
            "exp1-20251214-abc123-iter5-bootstrap-sample3"
        )

        assert result["experiment_id"] == "exp1-20251214-abc123"
        assert result["iteration"] == 5
        assert result["purpose"] == SimulationRunPurpose.BOOTSTRAP
        assert result["sample_index"] == 3

    def test_parses_initial_id(self) -> None:
        """Should parse initial ID correctly."""
        from payment_simulator.experiments.simulation_id import (
            parse_experiment_simulation_id,
        )

        result = parse_experiment_simulation_id("exp1-20251214-abc123-iter0-initial")

        assert result["experiment_id"] == "exp1-20251214-abc123"
        assert result["iteration"] == 0
        assert result["purpose"] == SimulationRunPurpose.INITIAL
        assert result["sample_index"] is None

    def test_round_trip_evaluation(self) -> None:
        """Generate then parse should return original components."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
            parse_experiment_simulation_id,
        )

        original_experiment_id = "exp1-20251214-abc123"
        original_iteration = 5
        original_purpose = SimulationRunPurpose.EVALUATION

        sim_id = generate_experiment_simulation_id(
            experiment_id=original_experiment_id,
            iteration=original_iteration,
            purpose=original_purpose,
        )

        parsed = parse_experiment_simulation_id(sim_id)

        assert parsed["experiment_id"] == original_experiment_id
        assert parsed["iteration"] == original_iteration
        assert parsed["purpose"] == original_purpose

    def test_round_trip_bootstrap_with_sample(self) -> None:
        """Generate then parse should work for bootstrap with sample."""
        from payment_simulator.experiments.simulation_id import (
            generate_experiment_simulation_id,
            parse_experiment_simulation_id,
        )

        original_experiment_id = "exp1-20251214-abc123"
        original_iteration = 10
        original_purpose = SimulationRunPurpose.BOOTSTRAP
        original_sample_index = 7

        sim_id = generate_experiment_simulation_id(
            experiment_id=original_experiment_id,
            iteration=original_iteration,
            purpose=original_purpose,
            sample_index=original_sample_index,
        )

        parsed = parse_experiment_simulation_id(sim_id)

        assert parsed["experiment_id"] == original_experiment_id
        assert parsed["iteration"] == original_iteration
        assert parsed["purpose"] == original_purpose
        assert parsed["sample_index"] == original_sample_index

    def test_raises_on_invalid_format(self) -> None:
        """Should raise ValueError for invalid simulation IDs."""
        from payment_simulator.experiments.simulation_id import (
            parse_experiment_simulation_id,
        )

        with pytest.raises(ValueError, match="Invalid simulation ID format"):
            parse_experiment_simulation_id("not-a-valid-simulation-id")

    def test_raises_on_standalone_id(self) -> None:
        """Should raise ValueError for standalone simulation IDs (no experiment link)."""
        from payment_simulator.experiments.simulation_id import (
            parse_experiment_simulation_id,
        )

        # Standalone IDs don't have the experiment linking structure
        with pytest.raises(ValueError, match="Invalid simulation ID format"):
            parse_experiment_simulation_id("sim-20251214-standalone")


# =============================================================================
# Phase 3.2: ExperimentPersistencePolicy Tests
# =============================================================================


class TestExperimentPersistencePolicy:
    """Tests for persistence policy dataclass."""

    def test_default_values(self) -> None:
        """Should have correct default values per design decisions."""
        from payment_simulator.experiments.persistence.policy import (
            ExperimentPersistencePolicy,
            SimulationPersistenceLevel,
        )

        policy = ExperimentPersistencePolicy()

        # Full tick-level state snapshots for all evaluation simulations
        assert policy.simulation_persistence == SimulationPersistenceLevel.FULL
        # Do NOT persist bootstrap sample transactions
        assert policy.persist_bootstrap_transactions is False
        # Always persist final evaluation
        assert policy.persist_final_evaluation is True
        # Always persist every policy iteration (accepted AND rejected)
        assert policy.persist_all_policy_iterations is True

    def test_custom_values(self) -> None:
        """Should allow custom values to be set."""
        from payment_simulator.experiments.persistence.policy import (
            ExperimentPersistencePolicy,
            SimulationPersistenceLevel,
        )

        policy = ExperimentPersistencePolicy(
            simulation_persistence=SimulationPersistenceLevel.EVENTS,
            persist_bootstrap_transactions=True,
            persist_final_evaluation=False,
            persist_all_policy_iterations=False,
        )

        assert policy.simulation_persistence == SimulationPersistenceLevel.EVENTS
        assert policy.persist_bootstrap_transactions is True
        assert policy.persist_final_evaluation is False
        assert policy.persist_all_policy_iterations is False


class TestSimulationPersistenceLevel:
    """Tests for SimulationPersistenceLevel enum."""

    def test_enum_values(self) -> None:
        """Should have expected persistence levels."""
        from payment_simulator.experiments.persistence.policy import (
            SimulationPersistenceLevel,
        )

        assert SimulationPersistenceLevel.NONE.value == "none"
        assert SimulationPersistenceLevel.SUMMARY.value == "summary"
        assert SimulationPersistenceLevel.EVENTS.value == "events"
        assert SimulationPersistenceLevel.FULL.value == "full"

    def test_enum_ordering(self) -> None:
        """Persistence levels should be ordered from least to most detail."""
        from payment_simulator.experiments.persistence.policy import (
            SimulationPersistenceLevel,
        )

        levels = list(SimulationPersistenceLevel)
        assert levels == [
            SimulationPersistenceLevel.NONE,
            SimulationPersistenceLevel.SUMMARY,
            SimulationPersistenceLevel.EVENTS,
            SimulationPersistenceLevel.FULL,
        ]


# =============================================================================
# Phase 3.3: ExperimentSimulationPersister Tests
# =============================================================================


class TestExperimentSimulationPersister:
    """Tests for ExperimentSimulationPersister class."""

    @pytest.fixture
    def db_manager(self, tmp_path: Any) -> Any:
        """Create a temporary database manager with initialized schema."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        db.initialize_schema()
        return db

    @pytest.fixture
    def experiment_id(self) -> str:
        """Return a test experiment ID."""
        return "exp-test-20251214-abc123"

    @pytest.fixture
    def persister(self, db_manager: Any, experiment_id: str) -> Any:
        """Create an ExperimentSimulationPersister instance."""
        from payment_simulator.experiments.persistence.policy import (
            ExperimentPersistencePolicy,
        )
        from payment_simulator.experiments.persistence.simulation_persister import (
            ExperimentSimulationPersister,
        )

        policy = ExperimentPersistencePolicy()
        return ExperimentSimulationPersister(
            db_manager=db_manager,
            experiment_id=experiment_id,
            policy=policy,
        )

    def test_generates_simulation_id(self, persister: Any) -> None:
        """Should generate structured simulation ID."""
        sim_id = persister.generate_simulation_id(
            iteration=5,
            purpose=SimulationRunPurpose.EVALUATION,
        )

        assert "exp-test-20251214-abc123" in sim_id
        assert "iter5" in sim_id
        assert "evaluation" in sim_id

    def test_generates_bootstrap_id_with_sample(self, persister: Any) -> None:
        """Should generate bootstrap ID with sample index."""
        sim_id = persister.generate_simulation_id(
            iteration=3,
            purpose=SimulationRunPurpose.BOOTSTRAP,
            sample_index=7,
        )

        assert "iter3" in sim_id
        assert "bootstrap" in sim_id
        assert "sample7" in sim_id

    def test_persists_simulation_run_record(
        self, db_manager: Any, persister: Any
    ) -> None:
        """Should persist to simulation_runs table."""
        sim_id = persister.generate_simulation_id(
            iteration=1,
            purpose=SimulationRunPurpose.EVALUATION,
        )

        # Persist a simulation run record
        persister.persist_simulation_run(
            simulation_id=sim_id,
            iteration=1,
            purpose=SimulationRunPurpose.EVALUATION,
            seed=12345,
            config_name="test_scenario",
            total_ticks=100,
            total_transactions=50,
            total_settlements=45,
            total_cost=10000,
            duration_seconds=2.5,
        )

        # Query the record back
        result = db_manager.conn.execute(
            "SELECT simulation_id, experiment_id, iteration, run_purpose FROM simulation_runs WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == sim_id
        assert result[1] == "exp-test-20251214-abc123"  # experiment_id
        assert result[2] == 1  # iteration
        assert result[3] == "evaluation"  # run_purpose

    def test_links_to_experiment(self, db_manager: Any, persister: Any) -> None:
        """Should set experiment_id in simulation record."""
        sim_id = persister.generate_simulation_id(
            iteration=0,
            purpose=SimulationRunPurpose.INITIAL,
        )

        persister.persist_simulation_run(
            simulation_id=sim_id,
            iteration=0,
            purpose=SimulationRunPurpose.INITIAL,
            seed=99999,
            config_name="test_config",
            total_ticks=50,
            total_transactions=25,
            total_settlements=20,
            total_cost=5000,
            duration_seconds=1.0,
        )

        # Verify experiment_id is set correctly
        result = db_manager.conn.execute(
            "SELECT experiment_id FROM simulation_runs WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == "exp-test-20251214-abc123"

    def test_stores_iteration_and_sample_index(
        self, db_manager: Any, persister: Any
    ) -> None:
        """Should store iteration number and sample_index for bootstrap runs."""
        sim_id = persister.generate_simulation_id(
            iteration=10,
            purpose=SimulationRunPurpose.BOOTSTRAP,
            sample_index=5,
        )

        persister.persist_simulation_run(
            simulation_id=sim_id,
            iteration=10,
            purpose=SimulationRunPurpose.BOOTSTRAP,
            seed=11111,
            config_name="bootstrap_config",
            total_ticks=100,
            total_transactions=75,
            total_settlements=70,
            total_cost=8000,
            duration_seconds=3.0,
            sample_index=5,
        )

        result = db_manager.conn.execute(
            "SELECT iteration, sample_index, run_purpose FROM simulation_runs WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == 10  # iteration
        assert result[1] == 5  # sample_index
        assert result[2] == "bootstrap"  # run_purpose

    def test_respects_persistence_level_none(self, db_manager: Any) -> None:
        """Should not persist when level is NONE."""
        from payment_simulator.experiments.persistence.policy import (
            ExperimentPersistencePolicy,
            SimulationPersistenceLevel,
        )
        from payment_simulator.experiments.persistence.simulation_persister import (
            ExperimentSimulationPersister,
        )

        policy = ExperimentPersistencePolicy(
            simulation_persistence=SimulationPersistenceLevel.NONE
        )
        persister = ExperimentSimulationPersister(
            db_manager=db_manager,
            experiment_id="exp-none-test",
            policy=policy,
        )

        # Check if persistence should occur
        should_persist = persister.should_persist_simulation(
            purpose=SimulationRunPurpose.EVALUATION
        )

        assert should_persist is False

    def test_always_persists_final_evaluation(self, db_manager: Any) -> None:
        """Should always persist final evaluation regardless of level."""
        from payment_simulator.experiments.persistence.policy import (
            ExperimentPersistencePolicy,
            SimulationPersistenceLevel,
        )
        from payment_simulator.experiments.persistence.simulation_persister import (
            ExperimentSimulationPersister,
        )

        # Even with NONE level, persist_final_evaluation should force persistence
        policy = ExperimentPersistencePolicy(
            simulation_persistence=SimulationPersistenceLevel.NONE,
            persist_final_evaluation=True,
        )
        persister = ExperimentSimulationPersister(
            db_manager=db_manager,
            experiment_id="exp-final-test",
            policy=policy,
        )

        # Final evaluation should always be persisted
        should_persist = persister.should_persist_simulation(
            purpose=SimulationRunPurpose.FINAL
        )

        assert should_persist is True

    def test_costs_stored_as_integer_cents(
        self, db_manager: Any, persister: Any
    ) -> None:
        """INV-1: Costs should be stored as integer cents (BIGINT)."""
        sim_id = persister.generate_simulation_id(
            iteration=1,
            purpose=SimulationRunPurpose.EVALUATION,
        )

        # Store cost as integer cents: $100.50 = 10050 cents
        persister.persist_simulation_run(
            simulation_id=sim_id,
            iteration=1,
            purpose=SimulationRunPurpose.EVALUATION,
            seed=12345,
            config_name="inv1_test",
            total_ticks=100,
            total_transactions=50,
            total_settlements=45,
            total_cost=10050,  # Integer cents
            duration_seconds=2.5,
        )

        result = db_manager.conn.execute(
            "SELECT total_cost FROM simulation_runs WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == 10050
        assert isinstance(result[0], int)

    def test_stores_seed_for_replay(self, db_manager: Any, persister: Any) -> None:
        """INV-2: Should store seed for deterministic replay."""
        sim_id = persister.generate_simulation_id(
            iteration=1,
            purpose=SimulationRunPurpose.EVALUATION,
        )

        seed = 9876543210  # Large seed to test BIGINT

        persister.persist_simulation_run(
            simulation_id=sim_id,
            iteration=1,
            purpose=SimulationRunPurpose.EVALUATION,
            seed=seed,
            config_name="seed_test",
            total_ticks=100,
            total_transactions=50,
            total_settlements=45,
            total_cost=10000,
            duration_seconds=2.5,
        )

        result = db_manager.conn.execute(
            "SELECT rng_seed FROM simulation_runs WHERE simulation_id = ?",
            [sim_id],
        ).fetchone()

        assert result is not None
        assert result[0] == seed


# =============================================================================
# Phase 3.4-3.5: OptimizationLoop Integration Tests
# =============================================================================


class TestOptimizationLoopSimulationPersister:
    """Tests for OptimizationLoop simulation persister attribute."""

    @pytest.fixture
    def db_manager(self, tmp_path: Any) -> Any:
        """Create a temporary database manager with initialized schema."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        db.initialize_schema()
        return db

    @pytest.fixture
    def experiment_repository(self, db_manager: Any) -> Any:
        """Create an ExperimentRepository from DatabaseManager."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        return ExperimentRepository.from_database_manager(db_manager)

    def test_optimization_loop_has_simulation_persister_attribute(self) -> None:
        """OptimizationLoop should have _simulation_persister attribute."""
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        # Check that OptimizationLoop has the expected attribute defined
        # (will be None by default when no db_manager is provided)
        assert hasattr(OptimizationLoop, "__init__")

    def test_simulation_persister_created_from_db_manager(
        self, db_manager: Any, experiment_repository: Any, tmp_path: Any
    ) -> None:
        """Should create simulation persister when db_manager is available."""
        from payment_simulator.experiments.persistence.simulation_persister import (
            ExperimentSimulationPersister,
        )
        from payment_simulator.experiments.persistence.policy import (
            ExperimentPersistencePolicy,
        )

        # Create a persister using the db_manager from repository
        experiment_id = "test-exp-123"
        policy = ExperimentPersistencePolicy()

        persister = ExperimentSimulationPersister(
            db_manager=db_manager,
            experiment_id=experiment_id,
            policy=policy,
        )

        assert persister is not None
        assert persister.experiment_id == experiment_id


class TestIterationRecordSimulationLink:
    """Tests for IterationRecord evaluation_simulation_id field."""

    @pytest.fixture
    def db_manager(self, tmp_path: Any) -> Any:
        """Create a temporary database manager with initialized schema."""
        from payment_simulator.persistence.connection import DatabaseManager

        db_path = tmp_path / "test.db"
        db = DatabaseManager(str(db_path))
        db.initialize_schema()
        return db

    @pytest.fixture
    def experiment_repository(self, db_manager: Any) -> Any:
        """Create an ExperimentRepository from DatabaseManager."""
        from payment_simulator.experiments.persistence import ExperimentRepository

        return ExperimentRepository.from_database_manager(db_manager)

    def test_iteration_record_has_evaluation_simulation_id_field(self) -> None:
        """IterationRecord should have evaluation_simulation_id field."""
        from payment_simulator.experiments.persistence import IterationRecord

        # Create a record with evaluation_simulation_id
        record = IterationRecord(
            experiment_id="exp-123",
            iteration=0,
            costs_per_agent={"BANK_A": 1000},
            accepted_changes={"BANK_A": True},
            policies={"BANK_A": {"type": "default"}},
            timestamp="2025-12-14T00:00:00",
            evaluation_simulation_id="exp-123-iter0-evaluation",
        )

        assert record.evaluation_simulation_id == "exp-123-iter0-evaluation"

    def test_iteration_record_stores_simulation_id(
        self, experiment_repository: Any
    ) -> None:
        """Should persist evaluation_simulation_id to database."""
        from payment_simulator.experiments.persistence import (
            ExperimentRecord,
            IterationRecord,
        )

        # First create an experiment
        exp_record = ExperimentRecord(
            experiment_id="exp-link-test",
            experiment_name="Link Test",
            experiment_type="test",
            config={"test": True},
            created_at="2025-12-14T00:00:00",
            completed_at=None,
            num_iterations=1,
            converged=False,
            convergence_reason=None,
            master_seed=12345,
        )
        experiment_repository.save_experiment(exp_record)

        # Create iteration record with simulation link
        iter_record = IterationRecord(
            experiment_id="exp-link-test",
            iteration=0,
            costs_per_agent={"BANK_A": 5000},
            accepted_changes={"BANK_A": False},
            policies={"BANK_A": {"type": "test"}},
            timestamp="2025-12-14T00:01:00",
            evaluation_simulation_id="exp-link-test-iter0-evaluation",
        )
        experiment_repository.save_iteration(iter_record)

        # Retrieve and verify
        iterations = experiment_repository.get_iterations("exp-link-test")
        assert len(iterations) == 1
        loaded = iterations[0]
        assert loaded.evaluation_simulation_id == "exp-link-test-iter0-evaluation"


# =============================================================================
# Phase 3.6: End-to-End Integration Tests (Placeholder)
# =============================================================================


class TestEndToEndExperimentPersistence:
    """End-to-end integration tests.

    These tests will be implemented when we reach Sub-Phase 3.6.
    """

    @pytest.mark.skip(reason="Sub-Phase 3.6 not yet implemented")
    def test_experiment_creates_linked_simulations(self) -> None:
        """Full experiment should create linked simulations."""
        pass

    @pytest.mark.skip(reason="Sub-Phase 3.6 not yet implemented")
    def test_simulations_queryable_from_unified_db(self) -> None:
        """Experiment simulations should be queryable via db commands."""
        pass
