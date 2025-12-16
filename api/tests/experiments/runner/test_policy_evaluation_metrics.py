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

        # Verify data extraction
        assert len(data.data_points) == 2
        assert data.data_points[0].cost_dollars == 8.0  # new_cost=800 / 100
        assert data.data_points[0].accepted is True
        assert data.data_points[1].cost_dollars == 8.5  # new_cost=850 / 100
        assert data.data_points[1].accepted is False

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

            # Verify data
            assert len(data.data_points) == 3
            assert data.data_points[0].accepted is True
            assert data.data_points[1].accepted is False
            assert data.data_points[2].accepted is True

            # Costs should be new_cost values
            assert data.data_points[0].cost_dollars == 8.0  # 800 / 100
            assert data.data_points[1].cost_dollars == 7.0  # 700 / 100
            assert data.data_points[2].cost_dollars == 6.0  # 600 / 100
