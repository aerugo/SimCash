"""Tests for paired comparison bug fix.

These tests verify that the BootstrapPolicyEvaluator correctly implements
paired comparison for valid statistical policy comparison.

The bug: runner.py was generating NEW bootstrap samples for each evaluation,
breaking the statistical validity of comparing old vs new policies.

The fix: Use compute_paired_deltas() which evaluates BOTH policies on the
SAME samples, enabling valid paired comparison.

References:
- Castro et al. methodology requires paired comparison
- BootstrapPolicyEvaluator.compute_paired_deltas() should be used
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap import (
    BootstrapPolicyEvaluator,
)
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import PairedDelta
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)


def create_test_sample(sample_idx: int, seed: int) -> BootstrapSample:
    """Create a minimal bootstrap sample for testing.

    Args:
        sample_idx: Index of the sample.
        seed: RNG seed for reproducibility.

    Returns:
        BootstrapSample with minimal outgoing transaction.
    """
    tx = RemappedTransaction(
        tx_id=f"tx-{sample_idx}",
        sender_id="TARGET",
        receiver_id="SINK",
        amount=100_00,  # $100.00 in cents
        priority=5,
        arrival_tick=0,
        deadline_tick=10,
        settlement_tick=5,
    )

    return BootstrapSample(
        agent_id="TARGET",
        sample_idx=sample_idx,
        seed=seed,
        outgoing_txns=(tx,),
        incoming_settlements=(),
        total_ticks=12,
    )


class TestPairedComparisonInvariant:
    """Tests that paired comparison uses same samples."""

    def test_compute_paired_deltas_returns_matching_indices(self) -> None:
        """Paired deltas must have matching sample indices.

        When compute_paired_deltas is called, each returned PairedDelta
        should have the same sample_idx as the input sample, proving
        both policies were evaluated on the same sample.
        """
        # Arrange: Create evaluator
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,  # $1M in cents
            credit_limit=500_000_00,  # $500K in cents
        )

        # Create deterministic samples
        samples = [
            create_test_sample(sample_idx=0, seed=42),
            create_test_sample(sample_idx=1, seed=43),
            create_test_sample(sample_idx=2, seed=44),
        ]

        old_policy = _create_seed_policy()
        new_policy = _create_seed_policy()

        # Act: Compute paired deltas
        deltas = evaluator.compute_paired_deltas(
            samples=samples,
            policy_a=old_policy,
            policy_b=new_policy,
        )

        # Assert: Same number of results as samples
        assert len(deltas) == len(samples)

        # Assert: Each delta has matching sample index and seed
        for delta, sample in zip(deltas, samples, strict=True):
            assert delta.sample_idx == sample.sample_idx
            assert delta.seed == sample.seed

    def test_acceptance_based_on_paired_delta_not_absolute(self) -> None:
        """Policy acceptance must use paired delta, not absolute costs.

        Scenario:
        - Sample 0: old=1000, new=900 → delta=100 (A-B, improvement)
        - Sample 1: old=1200, new=1100 → delta=100 (improvement)
        - Sample 2: old=800, new=850 → delta=-50 (regression)

        Mean delta = (100 + 100 - 50) / 3 = 50

        Since delta = cost_a - cost_b, positive delta means B is better.
        """
        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=1000, cost_b=900, delta=100),
            PairedDelta(sample_idx=1, seed=101, cost_a=1200, cost_b=1100, delta=100),
            PairedDelta(sample_idx=2, seed=102, cost_a=800, cost_b=850, delta=-50),
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta is positive → policy_b is cheaper (should accept)
        assert mean_delta == pytest.approx(50.0)
        # Since delta = cost_a - cost_b, positive means B is better
        assert mean_delta > 0

    def test_mean_delta_negative_means_new_policy_is_worse(self) -> None:
        """Negative mean delta means new policy (B) costs MORE.

        Scenario where new policy is worse:
        - Sample 0: old=1000, new=1100 → delta=-100 (B costs more)
        - Sample 1: old=800, new=900 → delta=-100 (B costs more)

        Mean delta = -100, should reject.
        """
        deltas = [
            PairedDelta(sample_idx=0, seed=100, cost_a=1000, cost_b=1100, delta=-100),
            PairedDelta(sample_idx=1, seed=101, cost_a=800, cost_b=900, delta=-100),
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        mean_delta = evaluator.compute_mean_delta(deltas)

        # Mean delta is negative → policy_b is more expensive (reject)
        assert mean_delta == pytest.approx(-100.0)
        assert mean_delta < 0

    def test_paired_delta_structure_is_frozen(self) -> None:
        """PairedDelta is immutable (frozen dataclass)."""
        delta = PairedDelta(
            sample_idx=0,
            seed=42,
            cost_a=1000,
            cost_b=900,
            delta=100,
        )

        with pytest.raises(AttributeError):
            delta.delta = 200  # type: ignore

    def test_compute_mean_delta_handles_empty_list(self) -> None:
        """compute_mean_delta returns 0.0 for empty list."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        mean_delta = evaluator.compute_mean_delta([])

        assert mean_delta == 0.0


class TestEvaluatorConsistency:
    """Tests that evaluator produces consistent results."""

    def test_evaluate_same_sample_twice_returns_identical_results(self) -> None:
        """Evaluating the same sample with same policy is deterministic.

        This proves the evaluator is deterministic, which is a prerequisite
        for paired comparison to be meaningful.
        """
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        sample = create_test_sample(sample_idx=0, seed=42)
        policy = _create_seed_policy()

        # Evaluate twice
        result1 = evaluator.evaluate_sample(sample, policy)
        result2 = evaluator.evaluate_sample(sample, policy)

        # Must be identical
        assert result1.total_cost == result2.total_cost
        assert result1.settlement_rate == result2.settlement_rate
        assert result1.sample_idx == result2.sample_idx
        assert result1.seed == result2.seed

    def test_evaluate_samples_preserves_order(self) -> None:
        """evaluate_samples returns results in same order as input samples."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000_00,
            credit_limit=500_000_00,
        )

        samples = [
            create_test_sample(sample_idx=0, seed=42),
            create_test_sample(sample_idx=1, seed=43),
            create_test_sample(sample_idx=2, seed=44),
        ]

        policy = _create_seed_policy()
        results = evaluator.evaluate_samples(samples, policy)

        # Results must match sample order
        assert len(results) == len(samples)
        for result, sample in zip(results, samples, strict=True):
            assert result.sample_idx == sample.sample_idx
            assert result.seed == sample.seed


def _create_seed_policy() -> dict:
    """Create a minimal valid policy for testing.

    Note: All node_ids MUST be unique across the entire policy.

    Returns:
        Dict representing a simple FIFO-like policy.
    """
    return {
        "version": "2.0",
        "policy_id": "test_policy",
        "parameters": {
            "urgency_threshold": 3.0,
        },
        "payment_tree": {
            "type": "condition",
            "node_id": "urgency_check",
            "condition": {
                "op": "<=",
                "left": {"field": "ticks_to_deadline"},
                "right": {"param": "urgency_threshold"},
            },
            "on_true": {"type": "action", "node_id": "release", "action": "Release"},
            "on_false": {"type": "action", "node_id": "hold_payment", "action": "Hold"},
        },
        "strategic_collateral_tree": {
            "type": "action",
            "node_id": "hold_collateral",
            "action": "HoldCollateral",
        },
    }
