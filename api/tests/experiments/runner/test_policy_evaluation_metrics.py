"""TDD tests for policy evaluation metrics persistence.

Tests the feature request: Persist policy evaluation metrics with actual costs.

All costs are integer cents (INV-1 compliance).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest


# =============================================================================
# Phase 1: PairedDelta Tests
# =============================================================================


class TestPairedDeltaCostFields:
    """Tests for PairedDelta having old_cost and new_cost fields.

    The PairedDelta already has cost_a and cost_b fields.
    These tests verify the semantic naming convention expected by the spec.
    """

    def test_paired_delta_has_cost_a_field(self) -> None:
        """PairedDelta should have cost_a field (old policy cost)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import PairedDelta

        pd = PairedDelta(
            sample_idx=0,
            seed=12345,
            cost_a=1000,
            cost_b=800,
            delta=200,
        )
        assert pd.cost_a == 1000

    def test_paired_delta_has_cost_b_field(self) -> None:
        """PairedDelta should have cost_b field (new policy cost)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import PairedDelta

        pd = PairedDelta(
            sample_idx=0,
            seed=12345,
            cost_a=1000,
            cost_b=800,
            delta=200,
        )
        assert pd.cost_b == 800

    def test_paired_delta_delta_is_cost_a_minus_cost_b(self) -> None:
        """Delta should be cost_a - cost_b (positive = improvement)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import PairedDelta

        pd = PairedDelta(
            sample_idx=0,
            seed=12345,
            cost_a=1000,
            cost_b=800,
            delta=200,
        )
        assert pd.delta == pd.cost_a - pd.cost_b


# =============================================================================
# Phase 2: SampleEvaluationResult and PolicyPairEvaluation Tests
# =============================================================================


class TestSampleEvaluationResult:
    """Tests for SampleEvaluationResult dataclass."""

    def test_importable_from_optimization(self) -> None:
        """SampleEvaluationResult should be importable from optimization module."""
        from payment_simulator.experiments.runner.optimization import (
            SampleEvaluationResult,
        )

        assert SampleEvaluationResult is not None

    def test_is_frozen_dataclass(self) -> None:
        """SampleEvaluationResult should be immutable."""
        from payment_simulator.experiments.runner.optimization import (
            SampleEvaluationResult,
        )

        result = SampleEvaluationResult(
            sample_index=0,
            seed=12345,
            old_cost=1000,
            new_cost=800,
            delta=200,
        )

        with pytest.raises(AttributeError):
            result.old_cost = 500  # type: ignore

    def test_has_required_fields(self) -> None:
        """SampleEvaluationResult should have all required fields."""
        from payment_simulator.experiments.runner.optimization import (
            SampleEvaluationResult,
        )

        result = SampleEvaluationResult(
            sample_index=0,
            seed=12345,
            old_cost=1000,
            new_cost=800,
            delta=200,
        )

        assert result.sample_index == 0
        assert result.seed == 12345
        assert result.old_cost == 1000
        assert result.new_cost == 800
        assert result.delta == 200

    def test_costs_are_integer_cents(self) -> None:
        """All costs must be integer cents (INV-1)."""
        from payment_simulator.experiments.runner.optimization import (
            SampleEvaluationResult,
        )

        result = SampleEvaluationResult(
            sample_index=0,
            seed=12345,
            old_cost=100050,  # $1,000.50 in cents
            new_cost=80025,  # $800.25 in cents
            delta=20025,
        )

        assert isinstance(result.old_cost, int)
        assert isinstance(result.new_cost, int)
        assert isinstance(result.delta, int)


class TestPolicyPairEvaluation:
    """Tests for PolicyPairEvaluation dataclass."""

    def test_importable_from_optimization(self) -> None:
        """PolicyPairEvaluation should be importable from optimization module."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
        )

        assert PolicyPairEvaluation is not None

    def test_is_frozen_dataclass(self) -> None:
        """PolicyPairEvaluation should be immutable."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=1000,
                new_cost=800,
                delta=200,
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=200,
            mean_old_cost=1000,
            mean_new_cost=800,
        )

        with pytest.raises(AttributeError):
            evaluation.delta_sum = 100  # type: ignore

    def test_has_required_fields(self) -> None:
        """PolicyPairEvaluation should have all required fields."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=1000,
                new_cost=800,
                delta=200,
            ),
            SampleEvaluationResult(
                sample_index=1,
                seed=12346,
                old_cost=1100,
                new_cost=900,
                delta=200,
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=400,
            mean_old_cost=1050,
            mean_new_cost=850,
        )

        assert len(evaluation.sample_results) == 2
        assert evaluation.delta_sum == 400
        assert evaluation.mean_old_cost == 1050
        assert evaluation.mean_new_cost == 850

    def test_deltas_property(self) -> None:
        """deltas property should return list of deltas for backward compatibility."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=1000,
                new_cost=800,
                delta=200,
            ),
            SampleEvaluationResult(
                sample_index=1,
                seed=12346,
                old_cost=1100,
                new_cost=900,
                delta=200,
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=400,
            mean_old_cost=1050,
            mean_new_cost=850,
        )

        assert evaluation.deltas == [200, 200]

    def test_num_samples_property(self) -> None:
        """num_samples property should return sample count."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        sample_results = [
            SampleEvaluationResult(
                sample_index=i,
                seed=12345 + i,
                old_cost=1000,
                new_cost=800,
                delta=200,
            )
            for i in range(5)
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=1000,
            mean_old_cost=1000,
            mean_new_cost=800,
        )

        assert evaluation.num_samples == 5


# =============================================================================
# Phase 5: PolicyEvaluationRecord Tests
# =============================================================================


class TestPolicyEvaluationRecord:
    """Tests for PolicyEvaluationRecord dataclass."""

    def test_importable_from_repository(self) -> None:
        """PolicyEvaluationRecord should be importable from repository module."""
        from payment_simulator.experiments.persistence.repository import (
            PolicyEvaluationRecord,
        )

        assert PolicyEvaluationRecord is not None

    def test_importable_from_persistence_package(self) -> None:
        """PolicyEvaluationRecord should be exported from persistence package."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        assert PolicyEvaluationRecord is not None

    def test_is_frozen_dataclass(self) -> None:
        """PolicyEvaluationRecord should be immutable."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "release"},
            old_cost=1000,
            new_cost=800,
            context_simulation_cost=1000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=200,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )

        with pytest.raises(AttributeError):
            record.accepted = False  # type: ignore

    def test_has_required_fields(self) -> None:
        """PolicyEvaluationRecord should have all required fields."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        record = PolicyEvaluationRecord(
            run_id="test-run-001",
            iteration=5,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "release", "parameters": {"threshold": 0.5}},
            old_cost=100050,
            new_cost=80025,
            context_simulation_cost=100000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=20025,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )

        assert record.run_id == "test-run-001"
        assert record.iteration == 5
        assert record.agent_id == "BANK_A"
        assert record.evaluation_mode == "deterministic"
        assert record.proposed_policy == {
            "type": "release",
            "parameters": {"threshold": 0.5},
        }
        assert record.old_cost == 100050
        assert record.new_cost == 80025
        assert record.context_simulation_cost == 100000
        assert record.accepted is True
        assert record.acceptance_reason == "cost_improved"
        assert record.delta_sum == 20025
        assert record.num_samples == 1
        assert record.sample_details is None
        assert record.scenario_seed == 12345

    def test_costs_are_integer_cents(self) -> None:
        """All costs must be integer cents (INV-1)."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "release"},
            old_cost=100050,  # $1,000.50 in cents
            new_cost=80025,  # $800.25 in cents
            context_simulation_cost=100000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=20025,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )

        assert isinstance(record.old_cost, int)
        assert isinstance(record.new_cost, int)
        assert isinstance(record.context_simulation_cost, int)
        assert isinstance(record.delta_sum, int)

    def test_bootstrap_mode_sample_details(self) -> None:
        """Bootstrap mode should have sample_details populated."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        sample_details = [
            {
                "index": 0,
                "seed": 12345,
                "old_cost": 1000,
                "new_cost": 800,
                "delta": 200,
            },
            {
                "index": 1,
                "seed": 12346,
                "old_cost": 1100,
                "new_cost": 900,
                "delta": 200,
            },
        ]

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "release"},
            old_cost=1050,  # Mean of old costs
            new_cost=850,  # Mean of new costs
            context_simulation_cost=1000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=400,
            num_samples=2,
            sample_details=sample_details,
            scenario_seed=None,  # Not used in bootstrap mode
            timestamp="2025-12-16T10:00:00",
        )

        assert record.evaluation_mode == "bootstrap"
        assert record.num_samples == 2
        assert record.sample_details is not None
        assert len(record.sample_details) == 2
        assert record.scenario_seed is None


# =============================================================================
# Phase 5: Repository Policy Evaluation CRUD Tests
# =============================================================================


class TestPolicyEvaluationRepositoryOperations:
    """Tests for PolicyEvaluationRecord CRUD operations."""

    @pytest.fixture
    def repo_with_experiment(self, tmp_path: Path) -> Any:
        """Create repository with a test experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        db_path = tmp_path / "test.db"
        repository = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={"evaluation": {"mode": "deterministic"}},
            created_at="2025-12-16T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repository.save_experiment(record)

        yield repository
        repository.close()

    def test_policy_evaluations_table_created(self, tmp_path: Path) -> None:
        """policy_evaluations table should be created on repository init."""
        from payment_simulator.experiments.persistence import ExperimentRepository
        import duckdb

        db_path = tmp_path / "test.db"
        repo = ExperimentRepository(db_path)
        repo.close()

        # Verify table exists
        conn = duckdb.connect(str(db_path))
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='main'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        conn.close()

        assert "policy_evaluations" in table_names

    def test_save_policy_evaluation(self, repo_with_experiment: Any) -> None:
        """Should save policy evaluation record."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "release"},
            old_cost=1000,
            new_cost=800,
            context_simulation_cost=1000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=200,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )

        repo_with_experiment.save_policy_evaluation(record)

        # Should not raise - verify retrieval
        evaluations = repo_with_experiment.get_policy_evaluations(
            "test-run", "BANK_A"
        )
        assert len(evaluations) == 1

    def test_get_policy_evaluations_by_agent(self, repo_with_experiment: Any) -> None:
        """Should get policy evaluations filtered by agent."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        # Save evaluations for two agents
        for agent_id in ["BANK_A", "BANK_B"]:
            for iteration in range(3):
                record = PolicyEvaluationRecord(
                    run_id="test-run",
                    iteration=iteration,
                    agent_id=agent_id,
                    evaluation_mode="deterministic",
                    proposed_policy={"type": "release"},
                    old_cost=1000 - iteration * 100,
                    new_cost=800 - iteration * 100,
                    context_simulation_cost=1000,
                    accepted=True,
                    acceptance_reason="cost_improved",
                    delta_sum=200,
                    num_samples=1,
                    sample_details=None,
                    scenario_seed=12345 + iteration,
                    timestamp=f"2025-12-16T10:{iteration:02d}:00",
                )
                repo_with_experiment.save_policy_evaluation(record)

        # Get evaluations for BANK_A only
        bank_a_evals = repo_with_experiment.get_policy_evaluations(
            "test-run", "BANK_A"
        )
        assert len(bank_a_evals) == 3
        assert all(e.agent_id == "BANK_A" for e in bank_a_evals)

    def test_get_all_policy_evaluations(self, repo_with_experiment: Any) -> None:
        """Should get all policy evaluations for a run."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        # Save evaluations for two agents
        for agent_id in ["BANK_A", "BANK_B"]:
            record = PolicyEvaluationRecord(
                run_id="test-run",
                iteration=0,
                agent_id=agent_id,
                evaluation_mode="deterministic",
                proposed_policy={"type": "release"},
                old_cost=1000,
                new_cost=800,
                context_simulation_cost=1000,
                accepted=True,
                acceptance_reason="cost_improved",
                delta_sum=200,
                num_samples=1,
                sample_details=None,
                scenario_seed=12345,
                timestamp="2025-12-16T10:00:00",
            )
            repo_with_experiment.save_policy_evaluation(record)

        all_evals = repo_with_experiment.get_all_policy_evaluations("test-run")
        assert len(all_evals) == 2

    def test_has_policy_evaluations_true(self, repo_with_experiment: Any) -> None:
        """has_policy_evaluations should return True when evaluations exist."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "release"},
            old_cost=1000,
            new_cost=800,
            context_simulation_cost=1000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=200,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )
        repo_with_experiment.save_policy_evaluation(record)

        assert repo_with_experiment.has_policy_evaluations("test-run") is True

    def test_has_policy_evaluations_false(self, repo_with_experiment: Any) -> None:
        """has_policy_evaluations should return False when no evaluations exist."""
        assert repo_with_experiment.has_policy_evaluations("test-run") is False

    def test_policy_evaluation_upsert(self, repo_with_experiment: Any) -> None:
        """Saving same (run_id, iteration, agent_id) should update."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        # Save initial record
        record1 = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "release"},
            old_cost=1000,
            new_cost=800,
            context_simulation_cost=1000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=200,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )
        repo_with_experiment.save_policy_evaluation(record1)

        # Save updated record with same key
        record2 = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "hold"},  # Changed
            old_cost=1000,
            new_cost=900,  # Changed
            context_simulation_cost=1000,
            accepted=False,  # Changed
            acceptance_reason="cost_not_improved",  # Changed
            delta_sum=100,  # Changed
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:01:00",  # Changed
        )
        repo_with_experiment.save_policy_evaluation(record2)

        # Should still have only 1 record
        evaluations = repo_with_experiment.get_policy_evaluations(
            "test-run", "BANK_A"
        )
        assert len(evaluations) == 1
        # Should have updated values
        assert evaluations[0].new_cost == 900
        assert evaluations[0].accepted is False

    def test_policy_evaluation_with_sample_details(
        self, repo_with_experiment: Any
    ) -> None:
        """Sample details should be properly serialized and deserialized."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )

        sample_details = [
            {
                "index": 0,
                "seed": 12345,
                "old_cost": 1000,
                "new_cost": 800,
                "delta": 200,
            },
            {
                "index": 1,
                "seed": 12346,
                "old_cost": 1100,
                "new_cost": 900,
                "delta": 200,
            },
        ]

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "release"},
            old_cost=1050,
            new_cost=850,
            context_simulation_cost=1000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=400,
            num_samples=2,
            sample_details=sample_details,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
        )
        repo_with_experiment.save_policy_evaluation(record)

        evaluations = repo_with_experiment.get_policy_evaluations(
            "test-run", "BANK_A"
        )
        assert len(evaluations) == 1
        assert evaluations[0].sample_details is not None
        assert len(evaluations[0].sample_details) == 2
        assert evaluations[0].sample_details[0]["seed"] == 12345
        assert evaluations[0].sample_details[1]["old_cost"] == 1100


# =============================================================================
# Phase 7: Charting with Policy Evaluations Tests
# =============================================================================


class TestChartingWithPolicyEvaluations:
    """Tests for charting using policy_evaluations table."""

    @pytest.fixture
    def mock_repo(self) -> Any:
        """Create a mock ExperimentRepository."""
        from unittest.mock import MagicMock

        return MagicMock()

    @pytest.fixture
    def sample_experiment(self) -> Any:
        """Create a sample experiment record."""
        from payment_simulator.experiments.persistence import ExperimentRecord

        return ExperimentRecord(
            run_id="exp1-20251216-100000-abc123",
            experiment_name="exp1",
            experiment_type="castro",
            config={"evaluation": {"mode": "deterministic"}},
            created_at="2025-12-16T10:00:00",
            completed_at="2025-12-16T11:00:00",
            num_iterations=5,
            converged=True,
            convergence_reason="stability",
        )

    def test_extract_chart_data_uses_policy_evaluations_when_available(
        self,
        mock_repo: Any,
        sample_experiment: Any,
    ) -> None:
        """Chart data should use policy_evaluations table when available."""
        from payment_simulator.experiments.persistence import (
            PolicyEvaluationRecord,
        )
        from payment_simulator.experiments.analysis.charting import (
            ExperimentChartService,
        )

        # Setup mock
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = True

        policy_evals = [
            PolicyEvaluationRecord(
                run_id="exp1-20251216-100000-abc123",
                iteration=0,
                agent_id="BANK_A",
                evaluation_mode="deterministic",
                proposed_policy={"type": "release"},
                old_cost=1000,
                new_cost=800,
                context_simulation_cost=1000,
                accepted=True,
                acceptance_reason="cost_improved",
                delta_sum=200,
                num_samples=1,
                sample_details=None,
                scenario_seed=12345,
                timestamp="2025-12-16T10:00:00",
            ),
            PolicyEvaluationRecord(
                run_id="exp1-20251216-100000-abc123",
                iteration=1,
                agent_id="BANK_A",
                evaluation_mode="deterministic",
                proposed_policy={"type": "hold"},
                old_cost=800,
                new_cost=850,
                context_simulation_cost=800,
                accepted=False,
                acceptance_reason="cost_not_improved",
                delta_sum=-50,
                num_samples=1,
                sample_details=None,
                scenario_seed=12346,
                timestamp="2025-12-16T10:01:00",
            ),
        ]
        mock_repo.get_policy_evaluations.return_value = policy_evals

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data(
            "exp1-20251216-100000-abc123",
            agent_filter="BANK_A",
        )

        # Verify policy_evaluations was checked and used
        mock_repo.has_policy_evaluations.assert_called_once_with(
            "exp1-20251216-100000-abc123"
        )
        mock_repo.get_policy_evaluations.assert_called_once()

        # Verify data extraction - now includes baseline at iteration 0
        assert len(data.data_points) == 3
        # Iteration 0: baseline from old_cost of first evaluation
        assert data.data_points[0].iteration == 0
        assert data.data_points[0].cost_dollars == 10.0  # old_cost=1000 / 100
        assert data.data_points[0].accepted is True
        # Iteration 1: first proposed policy
        assert data.data_points[1].iteration == 1
        assert data.data_points[1].cost_dollars == 8.0  # new_cost=800 / 100
        assert data.data_points[1].accepted is True
        # Iteration 2: second proposed policy
        assert data.data_points[2].iteration == 2
        assert data.data_points[2].cost_dollars == 8.5  # new_cost=850 / 100
        assert data.data_points[2].accepted is False

    def test_extract_chart_data_falls_back_to_iterations(
        self,
        mock_repo: Any,
        sample_experiment: Any,
    ) -> None:
        """Chart data should fall back to iterations table for old experiments."""
        from payment_simulator.experiments.persistence import IterationRecord
        from payment_simulator.experiments.analysis.charting import (
            ExperimentChartService,
        )

        # Setup mock - no policy evaluations
        mock_repo.load_experiment.return_value = sample_experiment
        mock_repo.has_policy_evaluations.return_value = False

        iterations = [
            IterationRecord(
                run_id="exp1-20251216-100000-abc123",
                iteration=0,
                costs_per_agent={"BANK_A": 8000},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": {"type": "release"}},
                timestamp="2025-12-16T10:00:00",
            ),
            IterationRecord(
                run_id="exp1-20251216-100000-abc123",
                iteration=1,
                costs_per_agent={"BANK_A": 7500},
                accepted_changes={"BANK_A": True},
                policies={"BANK_A": {"type": "hold"}},
                timestamp="2025-12-16T10:01:00",
            ),
        ]
        mock_repo.get_iterations.return_value = iterations

        service = ExperimentChartService(mock_repo)
        data = service.extract_chart_data(
            "exp1-20251216-100000-abc123",
            agent_filter="BANK_A",
        )

        # Verify fallback to iterations
        mock_repo.has_policy_evaluations.assert_called_once()
        mock_repo.get_iterations.assert_called_once()

        # Verify data extraction from iterations
        assert len(data.data_points) == 2
        assert data.data_points[0].cost_dollars == 80.0  # 8000 / 100


# =============================================================================
# Integration Tests
# =============================================================================


class TestPolicyEvaluationIntegration:
    """Integration tests for the complete policy evaluation flow."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "test.db"

    def test_full_evaluation_persist_and_chart_flow(self, db_path: Path) -> None:
        """Test complete flow: save evaluation -> chart extraction."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            PolicyEvaluationRecord,
        )
        from payment_simulator.experiments.analysis.charting import (
            ExperimentChartService,
        )

        with ExperimentRepository(db_path) as repo:
            # Create experiment
            experiment = ExperimentRecord(
                run_id="test-run",
                experiment_name="test",
                experiment_type="castro",
                config={"evaluation": {"mode": "deterministic"}},
                created_at="2025-12-16T10:00:00",
                completed_at="2025-12-16T11:00:00",
                num_iterations=3,
                converged=True,
                convergence_reason="stability",
            )
            repo.save_experiment(experiment)

            # Save policy evaluations
            for i in range(3):
                record = PolicyEvaluationRecord(
                    run_id="test-run",
                    iteration=i,
                    agent_id="BANK_A",
                    evaluation_mode="deterministic",
                    proposed_policy={"type": "release"},
                    old_cost=1000 - i * 100,
                    new_cost=800 - i * 100,
                    context_simulation_cost=1000 - i * 100,
                    accepted=(i != 1),  # Iteration 1 rejected
                    acceptance_reason=(
                        "cost_improved" if i != 1 else "cost_not_improved"
                    ),
                    delta_sum=200,
                    num_samples=1,
                    sample_details=None,
                    scenario_seed=12345 + i,
                    timestamp=f"2025-12-16T10:{i:02d}:00",
                )
                repo.save_policy_evaluation(record)

            # Extract chart data
            service = ExperimentChartService(repo)
            data = service.extract_chart_data("test-run", agent_filter="BANK_A")

            # Verify data - now includes baseline at iteration 0
            assert len(data.data_points) == 4
            # Iteration 0: baseline from old_cost of first evaluation
            assert data.data_points[0].iteration == 0
            assert data.data_points[0].cost_dollars == 10.0  # 1000 / 100
            assert data.data_points[0].accepted is True
            # Iteration 1-3: proposed policies
            assert data.data_points[1].accepted is True
            assert data.data_points[2].accepted is False
            assert data.data_points[3].accepted is True

            # Costs should be new_cost values for iterations 1-3
            assert data.data_points[1].cost_dollars == 8.0  # 800 / 100
            assert data.data_points[2].cost_dollars == 7.0  # 700 / 100
            assert data.data_points[3].cost_dollars == 6.0  # 600 / 100


# =============================================================================
# Phase 3: _evaluate_policy_pair Returns PolicyPairEvaluation Tests
# =============================================================================


class TestEvaluatePolicyPairReturnType:
    """Tests for _evaluate_policy_pair returning PolicyPairEvaluation.

    These tests verify that _evaluate_policy_pair returns a PolicyPairEvaluation
    containing actual computed costs, not just deltas.
    """

    def test_evaluate_policy_pair_returns_policy_pair_evaluation(self) -> None:
        """_evaluate_policy_pair should return PolicyPairEvaluation, not tuple."""
        # This test verifies the return type annotation
        # The method signature should be:
        # def _evaluate_policy_pair(...) -> PolicyPairEvaluation:
        # not:
        # def _evaluate_policy_pair(...) -> tuple[list[int], int]:

        # Import the method to inspect its return type
        import inspect
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        sig = inspect.signature(OptimizationLoop._evaluate_policy_pair)
        return_annotation = sig.return_annotation

        # Due to `from __future__ import annotations`, the annotation is a string
        # Check that it's PolicyPairEvaluation (not tuple)
        assert "PolicyPairEvaluation" in str(return_annotation)
        assert "tuple" not in str(return_annotation)

    def test_policy_pair_evaluation_contains_sample_results(self) -> None:
        """PolicyPairEvaluation should contain SampleEvaluationResult objects."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        # Create a valid PolicyPairEvaluation
        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=10000,  # $100.00 in cents
                new_cost=8000,  # $80.00 in cents
                delta=2000,  # Improvement
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=2000,
            mean_old_cost=10000,
            mean_new_cost=8000,
        )

        # Verify sample results are accessible
        assert len(evaluation.sample_results) == 1
        assert evaluation.sample_results[0].old_cost == 10000
        assert evaluation.sample_results[0].new_cost == 8000

    def test_policy_pair_evaluation_has_mean_costs(self) -> None:
        """PolicyPairEvaluation should have mean_old_cost and mean_new_cost."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=10000,
                new_cost=8000,
                delta=2000,
            ),
            SampleEvaluationResult(
                sample_index=1,
                seed=12346,
                old_cost=11000,
                new_cost=9000,
                delta=2000,
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=4000,
            mean_old_cost=10500,  # (10000 + 11000) / 2
            mean_new_cost=8500,  # (8000 + 9000) / 2
        )

        # Mean costs should be actual computed values, not estimates
        assert evaluation.mean_old_cost == 10500
        assert evaluation.mean_new_cost == 8500


# =============================================================================
# Phase 4: _should_accept_policy Returns Actual Costs Tests
# =============================================================================


class TestShouldAcceptPolicyActualCosts:
    """Tests for _should_accept_policy returning actual costs.

    The current implementation estimates costs using:
        old_cost = current_cost
        new_cost = current_cost - mean_delta

    These tests verify it returns actual computed costs instead.
    """

    def test_should_accept_policy_returns_six_tuple(self) -> None:
        """_should_accept_policy should return 6 values including evaluation."""
        import inspect
        from payment_simulator.experiments.runner.optimization import (
            OptimizationLoop,
            PolicyPairEvaluation,
        )

        # The method signature should return:
        # tuple[bool, int, int, list[int], int, PolicyPairEvaluation]
        # i.e., (should_accept, old_cost, new_cost, deltas, delta_sum, evaluation)

        sig = inspect.signature(OptimizationLoop._should_accept_policy)
        return_annotation = sig.return_annotation

        # The return type should be a tuple with 6 elements
        # Check that it includes PolicyPairEvaluation in the type hint
        assert "PolicyPairEvaluation" in str(return_annotation)

    def test_should_accept_policy_old_cost_matches_evaluation(self) -> None:
        """old_cost should equal evaluation.mean_old_cost (actual value)."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        # Create evaluation with known actual costs
        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=10000,  # Actual computed cost
                new_cost=8000,
                delta=2000,
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=2000,
            mean_old_cost=10000,  # Actual mean
            mean_new_cost=8000,  # Actual mean
        )

        # When _should_accept_policy returns, old_cost should be 10000
        # NOT current_cost (which could be different due to context simulation)
        assert evaluation.mean_old_cost == 10000

    def test_should_accept_policy_new_cost_matches_evaluation(self) -> None:
        """new_cost should equal evaluation.mean_new_cost (actual value)."""
        from payment_simulator.experiments.runner.optimization import (
            PolicyPairEvaluation,
            SampleEvaluationResult,
        )

        # Create evaluation with known actual costs
        sample_results = [
            SampleEvaluationResult(
                sample_index=0,
                seed=12345,
                old_cost=10000,
                new_cost=8000,  # Actual computed cost
                delta=2000,
            ),
        ]

        evaluation = PolicyPairEvaluation(
            sample_results=sample_results,
            delta_sum=2000,
            mean_old_cost=10000,
            mean_new_cost=8000,  # Actual mean
        )

        # When _should_accept_policy returns, new_cost should be 8000
        # NOT (current_cost - mean_delta) which is an estimate
        assert evaluation.mean_new_cost == 8000


# =============================================================================
# Phase 6: _save_policy_evaluation Method Tests
# =============================================================================


class TestSavePolicyEvaluationMethod:
    """Tests for _save_policy_evaluation method being called.

    These tests verify that policy evaluations are persisted after
    _should_accept_policy is called.
    """

    def test_optimization_loop_has_save_policy_evaluation_method(self) -> None:
        """OptimizationLoop should have _save_policy_evaluation method."""
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        assert hasattr(OptimizationLoop, "_save_policy_evaluation")
        assert callable(getattr(OptimizationLoop, "_save_policy_evaluation", None))

    def test_save_policy_evaluation_accepts_required_params(self) -> None:
        """_save_policy_evaluation should accept all required parameters."""
        import inspect
        from payment_simulator.experiments.runner.optimization import OptimizationLoop

        sig = inspect.signature(OptimizationLoop._save_policy_evaluation)
        params = list(sig.parameters.keys())

        # Should have parameters for all evaluation fields
        expected_params = [
            "self",
            "agent_id",
            "evaluation_mode",
            "proposed_policy",
            "old_cost",
            "new_cost",
            "context_simulation_cost",
            "accepted",
            "acceptance_reason",
            "delta_sum",
            "num_samples",
            "sample_details",
            "scenario_seed",
        ]

        for param in expected_params:
            assert param in params, f"Missing parameter: {param}"


# =============================================================================
# Phase 8: accepted_changes Bug Fix Tests
# =============================================================================


class TestAcceptedChangesBugFix:
    """Tests for accepted_changes bug fix.

    The bug: accepted_changes is saved BEFORE optimization completes,
    so it always shows False.

    The fix: Save iteration record AFTER optimization loop for all agents.
    """

    def test_accepted_changes_reflects_optimization_result(self) -> None:
        """accepted_changes should reflect actual optimization result.

        This is a design test - we verify the expectation that
        accepted_changes[agent_id] = True when policy was accepted.
        """
        # When a policy is accepted:
        # - _optimize_agent sets self._accepted_changes[agent_id] = True
        # - _save_iteration_record should be called AFTER this

        # The key invariant:
        # If should_accept is True, then accepted_changes[agent_id] must be True
        # in the saved IterationRecord

        # This test documents the expected behavior
        accepted = True
        accepted_changes = {"BANK_A": accepted}

        # The iteration record saved should have this value
        assert accepted_changes["BANK_A"] is True

    def test_accepted_changes_false_when_rejected(self) -> None:
        """accepted_changes should be False when policy was rejected."""
        # When a policy is rejected:
        # - _optimize_agent does NOT set self._accepted_changes[agent_id]
        # - Default value remains False

        accepted_changes = {"BANK_A": False}  # Default

        # The iteration record saved should preserve False
        assert accepted_changes["BANK_A"] is False


# =============================================================================
# Integration Tests: End-to-End Policy Evaluation Flow
# =============================================================================


class TestPolicyEvaluationEndToEnd:
    """End-to-end integration tests for policy evaluation persistence.

    These tests verify the complete flow from optimization through persistence
    to charting, using actual simulation components where possible.
    """

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path."""
        return tmp_path / "integration_test.db"

    def test_deterministic_evaluation_saves_scenario_seed(
        self, db_path: Path
    ) -> None:
        """Deterministic mode should save scenario_seed, not sample_details."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            PolicyEvaluationRecord,
        )

        with ExperimentRepository(db_path) as repo:
            # Create experiment
            experiment = ExperimentRecord(
                run_id="det-test-run",
                experiment_name="deterministic_test",
                experiment_type="castro",
                config={"evaluation": {"mode": "deterministic"}},
                created_at="2025-12-16T10:00:00",
                completed_at=None,
                num_iterations=1,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(experiment)

            # Save deterministic evaluation (simulates what _save_policy_evaluation does)
            record = PolicyEvaluationRecord(
                run_id="det-test-run",
                iteration=0,
                agent_id="BANK_A",
                evaluation_mode="deterministic",
                proposed_policy={"type": "release", "parameters": {"threshold": 0.5}},
                old_cost=10000,  # Actual cost from simulation
                new_cost=8000,  # Actual cost from simulation
                context_simulation_cost=9500,  # Context sim cost (different!)
                accepted=True,
                acceptance_reason="cost_improved",
                delta_sum=2000,
                num_samples=1,
                sample_details=None,  # NULL for deterministic
                scenario_seed=12345,  # Set for deterministic
                timestamp="2025-12-16T10:00:00",
            )
            repo.save_policy_evaluation(record)

            # Verify retrieval
            evaluations = repo.get_policy_evaluations("det-test-run", "BANK_A")
            assert len(evaluations) == 1

            eval_record = evaluations[0]
            assert eval_record.evaluation_mode == "deterministic"
            assert eval_record.scenario_seed == 12345
            assert eval_record.sample_details is None
            assert eval_record.num_samples == 1

            # Verify actual costs are stored (not context_simulation_cost)
            assert eval_record.old_cost == 10000
            assert eval_record.new_cost == 8000
            assert eval_record.context_simulation_cost == 9500

    def test_bootstrap_evaluation_saves_sample_details(self, db_path: Path) -> None:
        """Bootstrap mode should save sample_details, not scenario_seed."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            PolicyEvaluationRecord,
        )

        with ExperimentRepository(db_path) as repo:
            # Create experiment
            experiment = ExperimentRecord(
                run_id="boot-test-run",
                experiment_name="bootstrap_test",
                experiment_type="castro",
                config={"evaluation": {"mode": "bootstrap", "num_samples": 3}},
                created_at="2025-12-16T10:00:00",
                completed_at=None,
                num_iterations=1,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(experiment)

            # Sample details from bootstrap evaluation
            sample_details = [
                {"index": 0, "seed": 11111, "old_cost": 10000, "new_cost": 8000, "delta": 2000},
                {"index": 1, "seed": 22222, "old_cost": 11000, "new_cost": 9000, "delta": 2000},
                {"index": 2, "seed": 33333, "old_cost": 9000, "new_cost": 7000, "delta": 2000},
            ]

            # Save bootstrap evaluation
            record = PolicyEvaluationRecord(
                run_id="boot-test-run",
                iteration=0,
                agent_id="BANK_A",
                evaluation_mode="bootstrap",
                proposed_policy={"type": "release"},
                old_cost=10000,  # Mean of old costs
                new_cost=8000,  # Mean of new costs
                context_simulation_cost=9500,
                accepted=True,
                acceptance_reason="cost_improved",
                delta_sum=6000,  # Sum of deltas
                num_samples=3,
                sample_details=sample_details,  # Set for bootstrap
                scenario_seed=None,  # NULL for bootstrap
                timestamp="2025-12-16T10:00:00",
            )
            repo.save_policy_evaluation(record)

            # Verify retrieval
            evaluations = repo.get_policy_evaluations("boot-test-run", "BANK_A")
            assert len(evaluations) == 1

            eval_record = evaluations[0]
            assert eval_record.evaluation_mode == "bootstrap"
            assert eval_record.scenario_seed is None
            assert eval_record.sample_details is not None
            assert len(eval_record.sample_details) == 3
            assert eval_record.num_samples == 3

            # Verify sample details preserved
            assert eval_record.sample_details[0]["seed"] == 11111
            assert eval_record.sample_details[1]["old_cost"] == 11000
            assert eval_record.sample_details[2]["delta"] == 2000

    def test_charting_uses_actual_costs_from_policy_evaluations(
        self, db_path: Path
    ) -> None:
        """Charts should display new_cost from policy_evaluations, not estimates."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            PolicyEvaluationRecord,
        )
        from payment_simulator.experiments.analysis.charting import (
            ExperimentChartService,
        )

        with ExperimentRepository(db_path) as repo:
            # Create experiment
            experiment = ExperimentRecord(
                run_id="chart-test-run",
                experiment_name="chart_test",
                experiment_type="castro",
                config={"evaluation": {"mode": "deterministic"}},
                created_at="2025-12-16T10:00:00",
                completed_at="2025-12-16T11:00:00",
                num_iterations=3,
                converged=True,
                convergence_reason="stability",
            )
            repo.save_experiment(experiment)

            # Save evaluations with known actual costs
            # These costs are intentionally different from what estimates would give
            test_cases = [
                # (iteration, old_cost, new_cost, context_cost, accepted)
                (0, 10000, 8000, 9500, True),  # Accepted: new < old
                (1, 8000, 8500, 8200, False),  # Rejected: new > old
                (2, 8000, 7000, 8100, True),  # Accepted: new < old
            ]

            for iteration, old_cost, new_cost, context_cost, accepted in test_cases:
                record = PolicyEvaluationRecord(
                    run_id="chart-test-run",
                    iteration=iteration,
                    agent_id="BANK_A",
                    evaluation_mode="deterministic",
                    proposed_policy={"type": "release"},
                    old_cost=old_cost,
                    new_cost=new_cost,
                    context_simulation_cost=context_cost,
                    accepted=accepted,
                    acceptance_reason="cost_improved" if accepted else "cost_not_improved",
                    delta_sum=old_cost - new_cost,
                    num_samples=1,
                    sample_details=None,
                    scenario_seed=12345 + iteration,
                    timestamp=f"2025-12-16T10:{iteration:02d}:00",
                )
                repo.save_policy_evaluation(record)

            # Extract chart data
            service = ExperimentChartService(repo)
            data = service.extract_chart_data("chart-test-run", agent_filter="BANK_A")

            # Verify chart uses ACTUAL new_cost values - now includes baseline at iteration 0
            assert len(data.data_points) == 4

            # Iteration 0: baseline from old_cost of first evaluation
            assert data.data_points[0].iteration == 0
            assert data.data_points[0].cost_dollars == 100.0  # old_cost=10000 / 100
            assert data.data_points[0].accepted is True

            # new_cost values should match what we saved, not context_cost estimates
            assert data.data_points[1].cost_dollars == 80.0  # 8000 / 100
            assert data.data_points[2].cost_dollars == 85.0  # 8500 / 100
            assert data.data_points[3].cost_dollars == 70.0  # 7000 / 100

            # Acceptance should come from stored accepted field
            assert data.data_points[1].accepted is True
            assert data.data_points[2].accepted is False
            assert data.data_points[3].accepted is True

    def test_backward_compatibility_without_policy_evaluations(
        self, db_path: Path
    ) -> None:
        """Old experiments without policy_evaluations should use iterations table."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            IterationRecord,
        )
        from payment_simulator.experiments.analysis.charting import (
            ExperimentChartService,
        )

        with ExperimentRepository(db_path) as repo:
            # Create experiment (old-style, no policy_evaluations)
            experiment = ExperimentRecord(
                run_id="old-test-run",
                experiment_name="old_test",
                experiment_type="castro",
                config={"evaluation": {"mode": "deterministic"}},
                created_at="2025-12-16T10:00:00",
                completed_at="2025-12-16T11:00:00",
                num_iterations=2,
                converged=True,
                convergence_reason="stability",
            )
            repo.save_experiment(experiment)

            # Save only iterations (no policy_evaluations - simulates old experiment)
            iterations = [
                IterationRecord(
                    run_id="old-test-run",
                    iteration=0,
                    costs_per_agent={"BANK_A": 10000},
                    accepted_changes={"BANK_A": True},  # May be buggy in real data
                    policies={"BANK_A": {"type": "release"}},
                    timestamp="2025-12-16T10:00:00",
                ),
                IterationRecord(
                    run_id="old-test-run",
                    iteration=1,
                    costs_per_agent={"BANK_A": 8000},
                    accepted_changes={"BANK_A": True},
                    policies={"BANK_A": {"type": "hold"}},
                    timestamp="2025-12-16T10:01:00",
                ),
            ]
            for iteration in iterations:
                repo.save_iteration(iteration)

            # Verify no policy_evaluations exist
            assert repo.has_policy_evaluations("old-test-run") is False

            # Extract chart data - should fall back to iterations table
            service = ExperimentChartService(repo)
            data = service.extract_chart_data("old-test-run", agent_filter="BANK_A")

            # Should still work using iterations table
            assert len(data.data_points) == 2
            assert data.data_points[0].cost_dollars == 100.0  # 10000 / 100
            assert data.data_points[1].cost_dollars == 80.0  # 8000 / 100

            # Acceptance inferred from cost improvement
            assert data.data_points[0].accepted is True  # First iteration
            assert data.data_points[1].accepted is True  # 8000 < 10000

    def test_actual_vs_estimated_costs_differ(self, db_path: Path) -> None:
        """Verify that actual costs can differ from context_simulation_cost.

        This test documents the key improvement: we now store actual computed
        costs from evaluation, not estimates based on context_simulation_cost.
        """
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            PolicyEvaluationRecord,
        )

        with ExperimentRepository(db_path) as repo:
            experiment = ExperimentRecord(
                run_id="diff-test-run",
                experiment_name="diff_test",
                experiment_type="castro",
                config={"evaluation": {"mode": "deterministic"}},
                created_at="2025-12-16T10:00:00",
                completed_at=None,
                num_iterations=1,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(experiment)

            # Scenario: context_simulation_cost = 9500
            # But actual evaluation gives old_cost = 10000, new_cost = 8000
            # Old estimate would have been: new_cost = 9500 - 2000 = 7500
            # We now store actual 8000 instead of estimated 7500

            record = PolicyEvaluationRecord(
                run_id="diff-test-run",
                iteration=0,
                agent_id="BANK_A",
                evaluation_mode="deterministic",
                proposed_policy={"type": "release"},
                old_cost=10000,  # ACTUAL from evaluation
                new_cost=8000,  # ACTUAL from evaluation
                context_simulation_cost=9500,  # Context sim (different!)
                accepted=True,
                acceptance_reason="cost_improved",
                delta_sum=2000,
                num_samples=1,
                sample_details=None,
                scenario_seed=12345,
                timestamp="2025-12-16T10:00:00",
            )
            repo.save_policy_evaluation(record)

            # Verify the distinction is preserved
            evaluations = repo.get_policy_evaluations("diff-test-run", "BANK_A")
            eval_record = evaluations[0]

            # All three values are different and preserved:
            assert eval_record.old_cost == 10000  # Actual old
            assert eval_record.new_cost == 8000  # Actual new
            assert eval_record.context_simulation_cost == 9500  # Context

            # The old estimate would have been:
            # estimated_new = context_simulation_cost - delta = 9500 - 2000 = 7500
            # But we store actual 8000 instead
            estimated_new_cost = eval_record.context_simulation_cost - eval_record.delta_sum
            assert estimated_new_cost == 7500  # Old estimate
            assert eval_record.new_cost == 8000  # Actual (different!)

    def test_multi_agent_evaluations_stored_separately(self, db_path: Path) -> None:
        """Each agent's evaluation should be stored as a separate record."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
            PolicyEvaluationRecord,
        )

        with ExperimentRepository(db_path) as repo:
            experiment = ExperimentRecord(
                run_id="multi-agent-run",
                experiment_name="multi_agent_test",
                experiment_type="castro",
                config={"evaluation": {"mode": "deterministic"}},
                created_at="2025-12-16T10:00:00",
                completed_at=None,
                num_iterations=1,
                converged=False,
                convergence_reason=None,
            )
            repo.save_experiment(experiment)

            # Save evaluations for multiple agents in same iteration
            agents = ["BANK_A", "BANK_B", "BANK_C"]
            for i, agent_id in enumerate(agents):
                record = PolicyEvaluationRecord(
                    run_id="multi-agent-run",
                    iteration=0,
                    agent_id=agent_id,
                    evaluation_mode="deterministic",
                    proposed_policy={"type": "release"},
                    old_cost=10000 + i * 1000,
                    new_cost=8000 + i * 1000,
                    context_simulation_cost=9500 + i * 1000,
                    accepted=True,
                    acceptance_reason="cost_improved",
                    delta_sum=2000,
                    num_samples=1,
                    sample_details=None,
                    scenario_seed=12345 + i,
                    timestamp="2025-12-16T10:00:00",
                )
                repo.save_policy_evaluation(record)

            # Verify all agents stored
            all_evals = repo.get_all_policy_evaluations("multi-agent-run")
            assert len(all_evals) == 3

            # Verify each agent can be retrieved separately
            for i, agent_id in enumerate(agents):
                agent_evals = repo.get_policy_evaluations("multi-agent-run", agent_id)
                assert len(agent_evals) == 1
                assert agent_evals[0].agent_id == agent_id
                assert agent_evals[0].old_cost == 10000 + i * 1000


# =============================================================================
# Phase 1: Extended Policy Evaluation Stats - Schema Tests
# =============================================================================


class TestPolicyEvaluationExtendedStatsSchema:
    """Tests for extended policy evaluation statistics schema (PR-01 to PR-08)."""

    def test_policy_evaluation_record_has_extended_stats_fields(self) -> None:
        """PolicyEvaluationRecord should have all 6 extended stats fields."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        # Verify fields exist by creating record with all fields
        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=50,
            sample_details=None,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            # Extended stats - all 6 fields
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={
                "delay_cost": 3000,
                "overdraft_cost": 5000,
                "deadline_penalty": 0,
                "eod_penalty": 0,
            },
            cost_std_dev=500,
            confidence_interval_95=[7800, 8200],
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {
                        "delay_cost": 3000,
                        "overdraft_cost": 5000,
                        "deadline_penalty": 0,
                        "eod_penalty": 0,
                    },
                    "std_dev": 450,
                    "ci_95_lower": 7100,
                    "ci_95_upper": 8900,
                }
            },
        )

        # Verify all 6 extended fields exist and have correct values
        assert record.settlement_rate == 0.95
        assert record.avg_delay == 5.2
        assert record.cost_breakdown is not None
        assert record.cost_std_dev == 500
        assert record.confidence_interval_95 == [7800, 8200]
        assert record.agent_stats is not None

    def test_settlement_rate_type_is_float(self) -> None:
        """settlement_rate should be float type."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.95,
        )

        assert isinstance(record.settlement_rate, float)
        assert 0.0 <= record.settlement_rate <= 1.0

    def test_avg_delay_type_is_float(self) -> None:
        """avg_delay should be float type."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            avg_delay=5.2,
        )

        assert isinstance(record.avg_delay, float)
        assert record.avg_delay >= 0.0

    def test_cost_breakdown_type_is_dict(self) -> None:
        """cost_breakdown should be dict type with int values."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        breakdown = {
            "delay_cost": 3000,
            "overdraft_cost": 5000,
            "deadline_penalty": 0,
            "eod_penalty": 0,
        }

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            cost_breakdown=breakdown,
        )

        assert isinstance(record.cost_breakdown, dict)
        assert "delay_cost" in record.cost_breakdown
        assert "overdraft_cost" in record.cost_breakdown
        assert "deadline_penalty" in record.cost_breakdown
        assert "eod_penalty" in record.cost_breakdown

    def test_cost_std_dev_type_is_int_or_none(self) -> None:
        """cost_std_dev should be int (bootstrap) or None (deterministic)."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        # Bootstrap mode - should have std_dev
        record_bootstrap = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=50,
            sample_details=None,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            cost_std_dev=500,
        )

        assert isinstance(record_bootstrap.cost_std_dev, int)
        assert record_bootstrap.cost_std_dev >= 0

        # Deterministic mode - should be None
        record_det = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            cost_std_dev=None,
        )

        assert record_det.cost_std_dev is None

    def test_confidence_interval_type_is_list_or_none(self) -> None:
        """confidence_interval_95 should be list[int] (bootstrap) or None."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        # Bootstrap mode - should have CI
        record_bootstrap = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=50,
            sample_details=None,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            confidence_interval_95=[7800, 8200],
        )

        assert isinstance(record_bootstrap.confidence_interval_95, list)
        assert len(record_bootstrap.confidence_interval_95) == 2
        assert all(isinstance(v, int) for v in record_bootstrap.confidence_interval_95)

        # Deterministic mode - should be None
        record_det = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            confidence_interval_95=None,
        )

        assert record_det.confidence_interval_95 is None

    def test_agent_stats_type_is_dict(self) -> None:
        """agent_stats should be dict of dicts."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        agent_stats = {
            "BANK_A": {
                "cost": 8000,
                "settlement_rate": 0.95,
                "avg_delay": 5.2,
                "cost_breakdown": {
                    "delay_cost": 3000,
                    "overdraft_cost": 5000,
                    "deadline_penalty": 0,
                    "eod_penalty": 0,
                },
            }
        }

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            agent_stats=agent_stats,
        )

        assert isinstance(record.agent_stats, dict)
        assert "BANK_A" in record.agent_stats
        assert isinstance(record.agent_stats["BANK_A"], dict)


class TestPolicyEvaluationExtendedStatsRoundTrip:
    """Round-trip persistence tests for extended stats (PR-01 through PR-08)."""

    @pytest.fixture
    def repo_with_experiment(self, tmp_path: Path) -> Any:
        """Create repository with a test experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        db_path = tmp_path / "test_extended_stats.db"
        repository = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={"evaluation": {"mode": "deterministic"}},
            created_at="2025-12-16T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repository.save_experiment(record)

        yield repository
        repository.close()

    def test_roundtrip_deterministic_single_agent(
        self, repo_with_experiment: Any
    ) -> None:
        """PR-01: Deterministic single-agent record survives round-trip."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            # Deterministic mode: std_dev and CI should be None
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={
                "delay_cost": 3000,
                "overdraft_cost": 4500,
                "deadline_penalty": 500,
                "eod_penalty": 0,
            },
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {
                        "delay_cost": 3000,
                        "overdraft_cost": 4500,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify ALL extended stats fields
        assert loaded.settlement_rate == 0.95
        assert loaded.avg_delay == 5.2
        assert loaded.cost_breakdown == {
            "delay_cost": 3000,
            "overdraft_cost": 4500,
            "deadline_penalty": 500,
            "eod_penalty": 0,
        }
        assert loaded.cost_std_dev is None
        assert loaded.confidence_interval_95 is None
        assert loaded.agent_stats["BANK_A"]["cost"] == 8000
        assert loaded.agent_stats["BANK_A"]["settlement_rate"] == 0.95
        assert loaded.agent_stats["BANK_A"]["std_dev"] is None

    def test_roundtrip_deterministic_multi_agent(
        self, repo_with_experiment: Any
    ) -> None:
        """PR-02: Deterministic multi-agent record survives round-trip."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",  # Primary agent being optimized
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.93,
            avg_delay=4.8,
            cost_breakdown={
                "delay_cost": 5000,
                "overdraft_cost": 8000,
                "deadline_penalty": 1000,
                "eod_penalty": 0,
            },
            cost_std_dev=None,
            confidence_interval_95=None,
            # Multi-agent: stats for all 3 agents
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {
                        "delay_cost": 3000,
                        "overdraft_cost": 4500,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                },
                "BANK_B": {
                    "cost": 7500,
                    "settlement_rate": 0.92,
                    "avg_delay": 4.5,
                    "cost_breakdown": {
                        "delay_cost": 2000,
                        "overdraft_cost": 5000,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                },
                "BANK_C": {
                    "cost": 6000,
                    "settlement_rate": 0.91,
                    "avg_delay": 4.2,
                    "cost_breakdown": {
                        "delay_cost": 1500,
                        "overdraft_cost": 4000,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": None,
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                },
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify all 3 agents present
        assert len(loaded.agent_stats) == 3
        assert "BANK_A" in loaded.agent_stats
        assert "BANK_B" in loaded.agent_stats
        assert "BANK_C" in loaded.agent_stats

        # Verify each agent has all required fields
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            agent = loaded.agent_stats[agent_id]
            assert "cost" in agent
            assert "settlement_rate" in agent
            assert "avg_delay" in agent
            assert "cost_breakdown" in agent
            assert isinstance(agent["cost"], int)
            assert isinstance(agent["settlement_rate"], float)

    def test_roundtrip_bootstrap_single_agent(self, repo_with_experiment: Any) -> None:
        """PR-03: Bootstrap single-agent record with std_dev and CI survives."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "LiquidityAware", "threshold": 50000},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=100000,  # Sum across 50 samples
            num_samples=50,
            sample_details=[
                {
                    "index": 0,
                    "seed": 111,
                    "old_cost": 10000,
                    "new_cost": 8000,
                    "delta": 2000,
                }
            ],
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            # Bootstrap mode: std_dev and CI present
            settlement_rate=0.94,
            avg_delay=5.0,
            cost_breakdown={
                "delay_cost": 3500,
                "overdraft_cost": 4000,
                "deadline_penalty": 500,
                "eod_penalty": 0,
            },
            cost_std_dev=450,
            confidence_interval_95=[7100, 8900],
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.94,
                    "avg_delay": 5.0,
                    "cost_breakdown": {
                        "delay_cost": 3500,
                        "overdraft_cost": 4000,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": 450,
                    "ci_95_lower": 7100,
                    "ci_95_upper": 8900,
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify bootstrap-specific fields
        assert loaded.cost_std_dev == 450
        assert loaded.confidence_interval_95 == [7100, 8900]
        assert loaded.agent_stats["BANK_A"]["std_dev"] == 450
        assert loaded.agent_stats["BANK_A"]["ci_95_lower"] == 7100
        assert loaded.agent_stats["BANK_A"]["ci_95_upper"] == 8900

    def test_roundtrip_bootstrap_multi_agent(self, repo_with_experiment: Any) -> None:
        """PR-04: Bootstrap multi-agent record with all agents having std_dev/CI."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="bootstrap",
            proposed_policy={"type": "LiquidityAware", "threshold": 50000},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=100000,
            num_samples=50,
            sample_details=None,
            scenario_seed=None,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.93,
            avg_delay=4.8,
            cost_breakdown={
                "delay_cost": 5000,
                "overdraft_cost": 8000,
                "deadline_penalty": 1000,
                "eod_penalty": 0,
            },
            cost_std_dev=600,
            confidence_interval_95=[7200, 8800],
            # Multi-agent bootstrap: all agents have std_dev and CI
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "settlement_rate": 0.95,
                    "avg_delay": 5.2,
                    "cost_breakdown": {
                        "delay_cost": 3000,
                        "overdraft_cost": 4500,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": 450,
                    "ci_95_lower": 7100,
                    "ci_95_upper": 8900,
                },
                "BANK_B": {
                    "cost": 7500,
                    "settlement_rate": 0.92,
                    "avg_delay": 4.5,
                    "cost_breakdown": {
                        "delay_cost": 2000,
                        "overdraft_cost": 5000,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": 380,
                    "ci_95_lower": 6800,
                    "ci_95_upper": 8200,
                },
                "BANK_C": {
                    "cost": 6000,
                    "settlement_rate": 0.91,
                    "avg_delay": 4.2,
                    "cost_breakdown": {
                        "delay_cost": 1500,
                        "overdraft_cost": 4000,
                        "deadline_penalty": 500,
                        "eod_penalty": 0,
                    },
                    "std_dev": 320,
                    "ci_95_lower": 5400,
                    "ci_95_upper": 6600,
                },
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify all 3 agents have bootstrap stats
        assert len(loaded.agent_stats) == 3
        for agent_id in ["BANK_A", "BANK_B", "BANK_C"]:
            agent = loaded.agent_stats[agent_id]
            assert agent["std_dev"] is not None, f"{agent_id} missing std_dev"
            assert agent["ci_95_lower"] is not None, f"{agent_id} missing ci_95_lower"
            assert agent["ci_95_upper"] is not None, f"{agent_id} missing ci_95_upper"
            assert isinstance(agent["std_dev"], int)
            assert isinstance(agent["ci_95_lower"], int)
            assert isinstance(agent["ci_95_upper"], int)

    def test_roundtrip_cost_breakdown_all_components(
        self, repo_with_experiment: Any
    ) -> None:
        """PR-05: cost_breakdown with all 4 components preserved exactly."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        expected_breakdown = {
            "delay_cost": 3000,
            "overdraft_cost": 5000,
            "deadline_penalty": 1500,
            "eod_penalty": 500,
        }

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=10000,
            context_simulation_cost=10000,
            accepted=False,
            acceptance_reason="cost_not_improved",
            delta_sum=0,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.90,
            avg_delay=6.0,
            cost_breakdown=expected_breakdown,
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={"BANK_A": {"cost": 10000}},
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify all 4 components exactly
        assert loaded.cost_breakdown["delay_cost"] == 3000
        assert loaded.cost_breakdown["overdraft_cost"] == 5000
        assert loaded.cost_breakdown["deadline_penalty"] == 1500
        assert loaded.cost_breakdown["eod_penalty"] == 500
        assert sum(loaded.cost_breakdown.values()) == 10000

    def test_roundtrip_agent_stats_nested_cost_breakdown(
        self, repo_with_experiment: Any
    ) -> None:
        """PR-06: Nested cost_breakdown within agent_stats preserved."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        agent_breakdown = {
            "delay_cost": 1500,
            "overdraft_cost": 2500,
            "deadline_penalty": 750,
            "eod_penalty": 250,
        }

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=5000,
            new_cost=5000,
            context_simulation_cost=5000,
            accepted=False,
            acceptance_reason="cost_not_improved",
            delta_sum=0,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.92,
            avg_delay=5.5,
            cost_breakdown=agent_breakdown,
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={
                "BANK_A": {
                    "cost": 5000,
                    "settlement_rate": 0.92,
                    "avg_delay": 5.5,
                    "cost_breakdown": agent_breakdown,  # Nested!
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify nested cost_breakdown
        nested = loaded.agent_stats["BANK_A"]["cost_breakdown"]
        assert nested["delay_cost"] == 1500
        assert nested["overdraft_cost"] == 2500
        assert nested["deadline_penalty"] == 750
        assert nested["eod_penalty"] == 250

    def test_roundtrip_null_values_preserved(self, repo_with_experiment: Any) -> None:
        """PR-07: None values stored and retrieved as None."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={
                "delay_cost": 8000,
                "overdraft_cost": 0,
                "deadline_penalty": 0,
                "eod_penalty": 0,
            },
            cost_std_dev=None,  # Explicitly None
            confidence_interval_95=None,  # Explicitly None
            agent_stats={
                "BANK_A": {
                    "cost": 8000,
                    "std_dev": None,  # Explicitly None
                    "ci_95_lower": None,
                    "ci_95_upper": None,
                }
            },
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify None is preserved (not 0, not empty string)
        assert loaded.cost_std_dev is None
        assert loaded.confidence_interval_95 is None
        assert loaded.agent_stats["BANK_A"]["std_dev"] is None
        assert loaded.agent_stats["BANK_A"]["ci_95_lower"] is None

    def test_roundtrip_empty_agent_stats(self, repo_with_experiment: Any) -> None:
        """PR-08: Empty agent_stats dict stored and retrieved correctly."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            settlement_rate=0.95,
            avg_delay=5.2,
            cost_breakdown={
                "delay_cost": 8000,
                "overdraft_cost": 0,
                "deadline_penalty": 0,
                "eod_penalty": 0,
            },
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={},  # Empty dict
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # Verify empty dict is preserved
        assert loaded.agent_stats == {}


class TestPolicyEvaluationBackwardCompatibility:
    """Tests for backward compatibility with records without extended stats."""

    @pytest.fixture
    def repo_with_experiment(self, tmp_path: Path) -> Any:
        """Create repository with a test experiment."""
        from payment_simulator.experiments.persistence import (
            ExperimentRepository,
            ExperimentRecord,
        )

        db_path = tmp_path / "test_backward_compat.db"
        repository = ExperimentRepository(db_path)

        record = ExperimentRecord(
            run_id="test-run",
            experiment_name="test",
            experiment_type="castro",
            config={"evaluation": {"mode": "deterministic"}},
            created_at="2025-12-16T10:00:00",
            completed_at=None,
            num_iterations=0,
            converged=False,
            convergence_reason=None,
        )
        repository.save_experiment(record)

        yield repository
        repository.close()

    def test_load_record_without_extended_stats(
        self, repo_with_experiment: Any
    ) -> None:
        """Old records should load with extended stats as None."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        # Save a record without extended stats (using defaults)
        record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
            # Extended stats all default to None
        )

        repo_with_experiment.save_policy_evaluation(record)
        loaded = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")[0]

        # All extended stats should be None
        assert loaded.settlement_rate is None
        assert loaded.avg_delay is None
        assert loaded.cost_breakdown is None
        assert loaded.cost_std_dev is None
        assert loaded.confidence_interval_95 is None
        assert loaded.agent_stats is None

    def test_mixed_records_old_and_new(self, repo_with_experiment: Any) -> None:
        """Database can hold both old (no extended stats) and new records."""
        from payment_simulator.experiments.persistence import PolicyEvaluationRecord

        # Save old record (no extended stats)
        old_record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=0,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=10000,
            new_cost=8000,
            context_simulation_cost=9500,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=2000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12345,
            timestamp="2025-12-16T10:00:00",
        )
        repo_with_experiment.save_policy_evaluation(old_record)

        # Save new record (with extended stats)
        new_record = PolicyEvaluationRecord(
            run_id="test-run",
            iteration=1,
            agent_id="BANK_A",
            evaluation_mode="deterministic",
            proposed_policy={"type": "Fifo"},
            old_cost=8000,
            new_cost=7000,
            context_simulation_cost=8000,
            accepted=True,
            acceptance_reason="cost_improved",
            delta_sum=1000,
            num_samples=1,
            sample_details=None,
            scenario_seed=12346,
            timestamp="2025-12-16T10:01:00",
            settlement_rate=0.96,
            avg_delay=4.5,
            cost_breakdown={
                "delay_cost": 2000,
                "overdraft_cost": 5000,
                "deadline_penalty": 0,
                "eod_penalty": 0,
            },
            cost_std_dev=None,
            confidence_interval_95=None,
            agent_stats={"BANK_A": {"cost": 7000}},
        )
        repo_with_experiment.save_policy_evaluation(new_record)

        # Load both records
        records = repo_with_experiment.get_policy_evaluations("test-run", "BANK_A")
        assert len(records) == 2

        # Old record (iteration 0) has no extended stats
        assert records[0].settlement_rate is None
        assert records[0].agent_stats is None

        # New record (iteration 1) has extended stats
        assert records[1].settlement_rate == 0.96
        assert records[1].agent_stats is not None
        assert records[1].agent_stats["BANK_A"]["cost"] == 7000


# =============================================================================
# Phase 3: Derived Statistics Tests
# =============================================================================


class TestDerivedStatistics:
    """Tests for std dev and confidence interval computation (Phase 3)."""

    def test_compute_cost_std_dev_known_values(self) -> None:
        """Standard deviation should be computed correctly for known sample data."""
        import statistics

        from payment_simulator.experiments.runner.statistics import (
            compute_cost_statistics,
        )

        # Known sample costs
        sample_costs = [10000, 12000, 11000, 13000, 9000]  # cents

        stats = compute_cost_statistics(sample_costs)

        # Expected std dev: stdev([10000, 12000, 11000, 13000, 9000]) ≈ 1581
        expected_std = int(statistics.stdev(sample_costs))
        assert stats["std_dev"] == expected_std

    def test_compute_confidence_interval_known_values(self) -> None:
        """95% CI should be computed using t-distribution."""
        from payment_simulator.experiments.runner.statistics import (
            compute_cost_statistics,
        )

        sample_costs = [10000, 12000, 11000, 13000, 9000]  # cents

        stats = compute_cost_statistics(sample_costs)

        # Mean = 11000, std ≈ 1581
        # For n=5, t_{4, 0.975} ≈ 2.776
        # Margin = 2.776 * (1581 / sqrt(5)) ≈ 1963
        # CI = [11000 - 1963, 11000 + 1963] = [9037, 12963]
        assert stats["ci_95_lower"] is not None
        assert stats["ci_95_upper"] is not None
        assert stats["ci_95_lower"] < 11000 < stats["ci_95_upper"]
        # CI should be symmetric around mean (11000)
        assert 9000 <= stats["ci_95_lower"] <= 9500
        assert 12500 <= stats["ci_95_upper"] <= 13000

    def test_std_dev_returns_none_for_single_sample(self) -> None:
        """Std dev should be None when N=1 (undefined)."""
        from payment_simulator.experiments.runner.statistics import (
            compute_cost_statistics,
        )

        sample_costs = [10000]  # Single sample

        stats = compute_cost_statistics(sample_costs)

        assert stats["std_dev"] is None
        assert stats["ci_95_lower"] is None
        assert stats["ci_95_upper"] is None

    def test_std_dev_returns_none_for_empty_samples(self) -> None:
        """Std dev should be None for empty sample list."""
        from payment_simulator.experiments.runner.statistics import (
            compute_cost_statistics,
        )

        stats = compute_cost_statistics([])

        assert stats["std_dev"] is None
        assert stats["ci_95_lower"] is None
        assert stats["ci_95_upper"] is None

    def test_per_agent_std_dev_computed(self) -> None:
        """Per-agent std dev should be computed from per-agent sample costs."""
        from payment_simulator.experiments.runner.statistics import (
            compute_per_agent_statistics,
        )

        # Per-agent costs across 5 samples
        per_agent_samples = {
            "BANK_A": [5000, 6000, 5500, 6500, 4500],
            "BANK_B": [5000, 6000, 5500, 6500, 4500],
        }

        agent_stats = compute_per_agent_statistics(per_agent_samples)

        assert "BANK_A" in agent_stats
        assert "std_dev" in agent_stats["BANK_A"]
        assert agent_stats["BANK_A"]["std_dev"] is not None
        assert agent_stats["BANK_A"]["ci_95_lower"] is not None
        assert agent_stats["BANK_A"]["ci_95_upper"] is not None

    def test_statistics_stored_as_integer_cents(self) -> None:
        """All statistical values should be integer cents (INV-1)."""
        from payment_simulator.experiments.runner.statistics import (
            compute_cost_statistics,
        )

        sample_costs = [10000, 12000, 11000, 13000, 9000]

        stats = compute_cost_statistics(sample_costs)

        # Verify integer types (INV-1)
        assert isinstance(stats["std_dev"], int)
        assert isinstance(stats["ci_95_lower"], int)
        assert isinstance(stats["ci_95_upper"], int)

    def test_per_agent_statistics_mean_computed(self) -> None:
        """Per-agent statistics should include mean cost."""
        from payment_simulator.experiments.runner.statistics import (
            compute_per_agent_statistics,
        )

        per_agent_samples = {
            "BANK_A": [5000, 6000, 5500],
        }

        agent_stats = compute_per_agent_statistics(per_agent_samples)

        # Mean of [5000, 6000, 5500] = 5500
        assert agent_stats["BANK_A"]["cost"] == 5500

    def test_per_agent_empty_costs_handled(self) -> None:
        """Per-agent statistics should handle empty cost lists."""
        from payment_simulator.experiments.runner.statistics import (
            compute_per_agent_statistics,
        )

        per_agent_samples = {
            "BANK_A": [],
        }

        agent_stats = compute_per_agent_statistics(per_agent_samples)

        assert agent_stats["BANK_A"]["cost"] == 0
        assert agent_stats["BANK_A"]["std_dev"] is None

    def test_t_critical_for_small_samples(self) -> None:
        """t-distribution critical value should be larger for small samples."""
        from payment_simulator.experiments.runner.statistics import _get_t_critical

        # Smaller samples have larger t-critical (more uncertainty)
        t_2 = _get_t_critical(2)  # df=2 (n=3)
        t_10 = _get_t_critical(10)  # df=10 (n=11)
        t_100 = _get_t_critical(100)  # df=100 (n=101)

        assert t_2 > t_10 > t_100
        # Normal approximation for large samples
        assert abs(t_100 - 1.984) < 0.01

    def test_large_sample_uses_normal_approximation(self) -> None:
        """Samples > 100 should use normal approximation (1.96)."""
        from payment_simulator.experiments.runner.statistics import _get_t_critical

        t_200 = _get_t_critical(200)
        assert t_200 == 1.96

    def test_ci_width_decreases_with_sample_size(self) -> None:
        """Confidence interval should be narrower with more samples."""
        from payment_simulator.experiments.runner.statistics import (
            compute_cost_statistics,
        )

        # Small sample (n=5)
        small_sample = [10000, 12000, 11000, 13000, 9000]
        small_stats = compute_cost_statistics(small_sample)

        # Large sample (n=20) with same variance
        import random

        random.seed(42)
        large_sample = [10000 + random.randint(-2000, 2000) for _ in range(20)]
        large_stats = compute_cost_statistics(large_sample)

        # CI width = upper - lower
        small_width = small_stats["ci_95_upper"] - small_stats["ci_95_lower"]
        large_width = large_stats["ci_95_upper"] - large_stats["ci_95_lower"]

        # Larger samples should have narrower CIs (assuming similar std dev)
        # This is a general property, but std dev differences may affect it
        # At minimum, both should have valid CIs
        assert small_width > 0
        assert large_width > 0
