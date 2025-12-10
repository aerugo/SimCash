"""Unit tests for BootstrapPolicyEvaluator.

Phase 5: Policy Evaluator - TDD Tests

Tests for:
- Evaluating policy on a single bootstrap sample
- Evaluating policy across multiple samples (Monte Carlo)
- Computing paired deltas between policies
- Integration with SandboxConfigBuilder
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import (
    BootstrapPolicyEvaluator,
    EvaluationResult,
    PairedDelta,
)
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)


class TestEvaluationResultDataclass:
    """Test EvaluationResult data structure."""

    def test_evaluation_result_creation(self) -> None:
        """EvaluationResult stores cost and metadata."""
        result = EvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=50000,
            settlement_rate=0.95,
            avg_delay=2.5,
        )

        assert result.sample_idx == 0
        assert result.seed == 12345
        assert result.total_cost == 50000
        assert result.settlement_rate == 0.95
        assert result.avg_delay == 2.5

    def test_evaluation_result_immutable(self) -> None:
        """EvaluationResult is immutable."""
        result = EvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=50000,
            settlement_rate=0.95,
            avg_delay=2.5,
        )

        with pytest.raises(AttributeError):
            result.total_cost = 999  # type: ignore[misc]


class TestPairedDeltaDataclass:
    """Test PairedDelta data structure."""

    def test_paired_delta_creation(self) -> None:
        """PairedDelta stores comparison between two policies."""
        delta = PairedDelta(
            sample_idx=0,
            seed=12345,
            cost_a=50000,
            cost_b=45000,
            delta=-5000,  # B is better (lower cost)
        )

        assert delta.sample_idx == 0
        assert delta.delta == -5000

    def test_paired_delta_calculation(self) -> None:
        """Delta is cost_a - cost_b."""
        delta = PairedDelta(
            sample_idx=0,
            seed=12345,
            cost_a=100000,
            cost_b=80000,
            delta=20000,  # A costs 20000 more than B
        )

        assert delta.delta == delta.cost_a - delta.cost_b


class TestEvaluateSingleSample:
    """Test evaluating a single sample."""

    def test_evaluate_empty_sample(self) -> None:
        """Evaluating empty sample returns minimal cost."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        result = evaluator.evaluate_sample(
            sample=sample,
            policy={"type": "Fifo"},
        )

        assert isinstance(result, EvaluationResult)
        assert result.sample_idx == 0
        assert result.seed == 12345
        # Empty sample should have zero or minimal cost
        assert result.total_cost >= 0

    def test_evaluate_with_transactions(self) -> None:
        """Evaluating sample with transactions returns cost."""
        outgoing = (
            RemappedTransaction(
                tx_id="tx-001",
                sender_id="BANK_A",
                receiver_id="SINK",
                amount=100000,
                priority=5,
                arrival_tick=5,
                deadline_tick=20,
                settlement_tick=None,
            ),
        )

        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=outgoing,
            incoming_settlements=(),
            total_ticks=100,
        )

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        result = evaluator.evaluate_sample(
            sample=sample,
            policy={"type": "Fifo"},
        )

        assert isinstance(result, EvaluationResult)
        # With sufficient balance, transaction should settle
        assert result.settlement_rate > 0


class TestEvaluateMultipleSamples:
    """Test Monte Carlo evaluation across multiple samples."""

    def test_evaluate_samples_returns_list(self) -> None:
        """evaluate_samples returns list of EvaluationResults."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(3)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        results = evaluator.evaluate_samples(
            samples=samples,
            policy={"type": "Fifo"},
        )

        assert len(results) == 3
        assert all(isinstance(r, EvaluationResult) for r in results)

    def test_each_sample_gets_unique_index(self) -> None:
        """Each result has correct sample_idx."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(5)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        results = evaluator.evaluate_samples(
            samples=samples,
            policy={"type": "Fifo"},
        )

        indices = [r.sample_idx for r in results]
        assert indices == [0, 1, 2, 3, 4]


class TestPairedComparison:
    """Test paired comparison between two policies."""

    def test_compute_paired_deltas(self) -> None:
        """compute_paired_deltas compares two policies on same samples."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(3)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},  # Same policy
        )

        assert len(deltas) == 3
        assert all(isinstance(d, PairedDelta) for d in deltas)

    def test_paired_deltas_same_policy_zero_delta(self) -> None:
        """Same policy compared to itself should have zero delta."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(3)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},
        )

        # Same policy should produce same cost -> zero delta
        for delta in deltas:
            assert delta.delta == 0


class TestAggregateStatistics:
    """Test aggregate statistics computation."""

    def test_compute_mean_cost(self) -> None:
        """compute_mean_cost calculates average across samples."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(5)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        results = evaluator.evaluate_samples(
            samples=samples,
            policy={"type": "Fifo"},
        )

        mean_cost = evaluator.compute_mean_cost(results)
        assert isinstance(mean_cost, float)
        assert mean_cost >= 0

    def test_compute_mean_delta(self) -> None:
        """compute_mean_delta calculates average delta."""
        samples = [
            BootstrapSample(
                agent_id="BANK_A",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(),
                incoming_settlements=(),
                total_ticks=100,
            )
            for i in range(5)
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a={"type": "Fifo"},
            policy_b={"type": "Fifo"},
        )

        mean_delta = evaluator.compute_mean_delta(deltas)
        assert isinstance(mean_delta, float)
        # Same policy should have zero mean delta
        assert mean_delta == 0.0


class TestCustomCostRates:
    """Test evaluation with custom cost rates."""

    def test_custom_cost_rates(self) -> None:
        """Evaluator accepts custom cost rates."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
            cost_rates={
                "overdraft_bps_per_tick": 0.01,
                "delay_cost_per_tick_per_cent": 0.001,
            },
        )

        result = evaluator.evaluate_sample(
            sample=sample,
            policy={"type": "Fifo"},
        )

        # Should succeed with custom rates
        assert isinstance(result, EvaluationResult)


class TestDeterminism:
    """Test determinism invariant."""

    def test_same_sample_same_result(self) -> None:
        """Same sample produces identical result each time."""
        sample = BootstrapSample(
            agent_id="BANK_A",
            sample_idx=0,
            seed=12345,
            outgoing_txns=(),
            incoming_settlements=(),
            total_ticks=100,
        )

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )

        result1 = evaluator.evaluate_sample(sample=sample, policy={"type": "Fifo"})
        result2 = evaluator.evaluate_sample(sample=sample, policy={"type": "Fifo"})

        assert result1.total_cost == result2.total_cost
        assert result1.settlement_rate == result2.settlement_rate
