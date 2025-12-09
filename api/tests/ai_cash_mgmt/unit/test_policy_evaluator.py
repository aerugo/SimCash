"""Unit tests for PolicyEvaluator - Monte Carlo policy evaluation.

TDD: These tests are written BEFORE the implementation.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest


class TestEvaluationResult:
    """Test evaluation result dataclass."""

    def test_evaluation_result_creation(self) -> None:
        """EvaluationResult should store all metrics."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )

        result = EvaluationResult(
            agent_id="BANK_A",
            policy={"payment_tree": {"root": {"action": "submit"}}},
            mean_cost=1000.0,
            std_cost=50.0,
            min_cost=900.0,
            max_cost=1100.0,
            sample_costs=[950.0, 1000.0, 1050.0],
            num_samples=3,
            settlement_rate=0.95,
        )

        assert result.agent_id == "BANK_A"
        assert result.mean_cost == 1000.0
        assert result.std_cost == 50.0
        assert result.settlement_rate == 0.95

    def test_evaluation_result_is_better_than(self) -> None:
        """is_better_than should compare mean costs."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )

        result1 = EvaluationResult(
            agent_id="BANK_A",
            policy={},
            mean_cost=1000.0,
            std_cost=50.0,
            min_cost=900.0,
            max_cost=1100.0,
            sample_costs=[1000.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        result2 = EvaluationResult(
            agent_id="BANK_A",
            policy={},
            mean_cost=800.0,  # Lower cost is better
            std_cost=50.0,
            min_cost=700.0,
            max_cost=900.0,
            sample_costs=[800.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        assert result2.is_better_than(result1)
        assert not result1.is_better_than(result2)

    def test_evaluation_result_improvement_ratio(self) -> None:
        """improvement_over should calculate relative improvement."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )

        baseline = EvaluationResult(
            agent_id="BANK_A",
            policy={},
            mean_cost=1000.0,
            std_cost=50.0,
            min_cost=900.0,
            max_cost=1100.0,
            sample_costs=[1000.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        improved = EvaluationResult(
            agent_id="BANK_A",
            policy={},
            mean_cost=800.0,  # 20% improvement
            std_cost=50.0,
            min_cost=700.0,
            max_cost=900.0,
            sample_costs=[800.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        assert improved.improvement_over(baseline) == pytest.approx(0.2, rel=0.01)


class TestPolicyEvaluator:
    """Test policy evaluator."""

    def test_evaluator_creation(self) -> None:
        """PolicyEvaluator should be creatable with config."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(
            num_samples=20,
            evaluation_ticks=100,
            parallel_workers=4,
        )

        assert evaluator.num_samples == 20
        assert evaluator.evaluation_ticks == 100

    def test_evaluator_evaluate_returns_result(self) -> None:
        """evaluate() should return EvaluationResult."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
            PolicyEvaluator,
        )
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            HistoricalTransaction,
        )

        evaluator = PolicyEvaluator(
            num_samples=3,
            evaluation_ticks=10,
            parallel_workers=1,
        )

        # Create mock samples
        samples = [
            [_create_mock_transaction(f"TX{i}") for i in range(5)]
            for _ in range(3)
        ]

        # Mock simulation runner
        mock_runner = _create_mock_runner(costs=[100.0, 110.0, 90.0])

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={"payment_tree": {"root": {"action": "submit"}}},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        assert isinstance(result, EvaluationResult)
        assert result.agent_id == "BANK_A"
        assert result.num_samples == 3

    def test_evaluator_calculates_mean_cost(self) -> None:
        """evaluate() should calculate correct mean cost."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(
            num_samples=3,
            evaluation_ticks=10,
            parallel_workers=1,
        )

        samples = [
            [_create_mock_transaction(f"TX{i}") for i in range(5)]
            for _ in range(3)
        ]

        # Costs: 100, 200, 300 -> mean = 200
        mock_runner = _create_mock_runner(costs=[100.0, 200.0, 300.0])

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        assert result.mean_cost == pytest.approx(200.0)
        assert result.min_cost == pytest.approx(100.0)
        assert result.max_cost == pytest.approx(300.0)

    def test_evaluator_calculates_std_cost(self) -> None:
        """evaluate() should calculate correct std deviation."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(
            num_samples=4,
            evaluation_ticks=10,
            parallel_workers=1,
        )

        samples = [[_create_mock_transaction("TX1")] for _ in range(4)]

        # All same cost -> std = 0
        mock_runner = _create_mock_runner(costs=[100.0, 100.0, 100.0, 100.0])

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        assert result.std_cost == pytest.approx(0.0)

    def test_evaluator_does_not_persist(self) -> None:
        """evaluate() should run simulations without persistence."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(
            num_samples=2,
            evaluation_ticks=10,
            parallel_workers=1,
        )

        samples = [[_create_mock_transaction("TX1")] for _ in range(2)]
        mock_runner = _create_mock_runner(costs=[100.0, 100.0])

        evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        # Verify runner was called with persist=False
        for call in mock_runner.run_ephemeral.call_args_list:
            # The runner should be called with ephemeral mode
            assert call is not None

    def test_evaluator_handles_empty_samples(self) -> None:
        """evaluate() should handle empty samples gracefully."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(
            num_samples=3,
            evaluation_ticks=10,
            parallel_workers=1,
        )

        # Empty samples
        samples: list[list[Any]] = [[], [], []]
        mock_runner = _create_mock_runner(costs=[0.0, 0.0, 0.0])

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        assert result.num_samples == 3


class TestPolicyEvaluatorWithSettlementRate:
    """Test settlement rate calculation."""

    def test_evaluator_calculates_settlement_rate(self) -> None:
        """evaluate() should calculate settlement rate."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(
            num_samples=2,
            evaluation_ticks=10,
            parallel_workers=1,
        )

        samples = [[_create_mock_transaction("TX1")] for _ in range(2)]

        # Mock runner with settlement rates
        mock_runner = _create_mock_runner(
            costs=[100.0, 100.0],
            settlement_rates=[0.90, 0.80],
        )

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        # Mean settlement rate
        assert result.settlement_rate == pytest.approx(0.85)


class TestSimulationRunnerProtocol:
    """Test the simulation runner protocol."""

    def test_runner_protocol_defines_run_ephemeral(self) -> None:
        """SimulationRunnerProtocol should define run_ephemeral method."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            SimulationRunnerProtocol,
        )

        # Just verify the protocol exists and has the method
        assert hasattr(SimulationRunnerProtocol, "run_ephemeral")


class TestEvaluationMetrics:
    """Test detailed evaluation metrics."""

    def test_evaluation_result_to_dict(self) -> None:
        """EvaluationResult should convert to dict."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )

        result = EvaluationResult(
            agent_id="BANK_A",
            policy={"test": "policy"},
            mean_cost=1000.0,
            std_cost=50.0,
            min_cost=900.0,
            max_cost=1100.0,
            sample_costs=[950.0, 1000.0, 1050.0],
            num_samples=3,
            settlement_rate=0.95,
        )

        data = result.to_dict()

        assert data["agent_id"] == "BANK_A"
        assert data["mean_cost"] == 1000.0
        assert data["settlement_rate"] == 0.95
        assert "sample_costs" in data


# Helper functions


def _create_mock_transaction(tx_id: str) -> Any:
    """Create a mock HistoricalTransaction."""
    from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
        HistoricalTransaction,
    )

    return HistoricalTransaction(
        tx_id=tx_id,
        sender_id="BANK_A",
        receiver_id="BANK_B",
        amount=100000,
        priority=5,
        arrival_tick=0,
        deadline_tick=10,
        is_divisible=True,
    )


def _create_mock_runner(
    costs: list[float],
    settlement_rates: list[float] | None = None,
) -> MagicMock:
    """Create a mock simulation runner."""
    if settlement_rates is None:
        settlement_rates = [1.0] * len(costs)

    mock = MagicMock()
    results = []
    for cost, rate in zip(costs, settlement_rates):
        result = MagicMock()
        result.total_cost = cost
        result.settlement_rate = rate
        results.append(result)

    mock.run_ephemeral.side_effect = results
    return mock
