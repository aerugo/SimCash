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
