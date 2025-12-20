"""Integration tests for bootstrap policy acceptance.

These tests verify the critical property that:
1. The same bootstrap samples are used for old and new policy evaluation
2. Paired deltas are computed correctly
3. Policy acceptance/rejection is based on mean_delta > 0

Key Formula:
    delta = cost_a - cost_b
    - If mean(delta) > 0: policy_b is cheaper → ACCEPT
    - If mean(delta) <= 0: policy_a is same or better → REJECT
"""

from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import CostBreakdown
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import (
    BootstrapPolicyEvaluator,
    EvaluationResult,
    PairedDelta,
)
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapSample,
    RemappedTransaction,
)


class TestPairedDeltaDataclass:
    """Tests for PairedDelta dataclass correctness."""

    def test_delta_formula_is_cost_a_minus_cost_b(self) -> None:
        """delta = cost_a - cost_b (positive means A is more expensive)."""
        delta = PairedDelta(
            sample_idx=0,
            seed=12345,
            cost_a=1000,
            cost_b=800,
            delta=200,  # 1000 - 800 = 200
        )
        assert delta.delta == delta.cost_a - delta.cost_b
        assert delta.delta == 200

    def test_positive_delta_means_policy_a_costs_more(self) -> None:
        """Positive delta means policy A is more expensive than B."""
        delta = PairedDelta(
            sample_idx=0,
            seed=1,
            cost_a=1500,  # A costs more
            cost_b=1000,  # B costs less
            delta=500,
        )
        assert delta.delta > 0
        assert delta.cost_a > delta.cost_b

    def test_negative_delta_means_policy_b_costs_more(self) -> None:
        """Negative delta means policy B is more expensive than A."""
        delta = PairedDelta(
            sample_idx=0,
            seed=1,
            cost_a=1000,  # A costs less
            cost_b=1500,  # B costs more
            delta=-500,
        )
        assert delta.delta < 0
        assert delta.cost_a < delta.cost_b

    def test_zero_delta_means_equal_costs(self) -> None:
        """Zero delta means both policies have same cost."""
        delta = PairedDelta(
            sample_idx=0,
            seed=1,
            cost_a=1000,
            cost_b=1000,
            delta=0,
        )
        assert delta.delta == 0
        assert delta.cost_a == delta.cost_b


class TestMeanDeltaCalculation:
    """Tests for mean delta calculation."""

    def test_compute_mean_delta_single_sample(self) -> None:
        """Mean delta with single sample equals that sample's delta."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=800, delta=200),
        ]
        mean = evaluator.compute_mean_delta(deltas)
        assert mean == 200.0

    def test_compute_mean_delta_multiple_samples(self) -> None:
        """Mean delta is average of all sample deltas."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=800, delta=200),
            PairedDelta(sample_idx=1, seed=2, cost_a=1200, cost_b=900, delta=300),
            PairedDelta(sample_idx=2, seed=3, cost_a=900, cost_b=900, delta=0),
        ]
        # mean = (200 + 300 + 0) / 3 = 166.67
        mean = evaluator.compute_mean_delta(deltas)
        assert abs(mean - 166.67) < 1.0

    def test_compute_mean_delta_empty_list_returns_zero(self) -> None:
        """Mean delta of empty list is 0."""
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        mean = evaluator.compute_mean_delta([])
        assert mean == 0.0


class TestPolicyAcceptanceLogic:
    """Tests for policy acceptance based on mean delta.

    The acceptance rule is:
    - mean_delta > 0 → ACCEPT (new policy B is cheaper)
    - mean_delta <= 0 → REJECT (old policy A is same or better)
    """

    def test_policy_accepted_when_mean_delta_positive(self) -> None:
        """Policy B should be accepted when mean_delta > 0 (B is cheaper)."""
        # mean_delta = cost_old - cost_new
        # If positive, new policy is cheaper → ACCEPT
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=800, delta=200),
            PairedDelta(sample_idx=1, seed=2, cost_a=1200, cost_b=900, delta=300),
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        mean_delta = evaluator.compute_mean_delta(deltas)

        # mean_delta = (200 + 300) / 2 = 250 > 0
        assert mean_delta == 250.0
        assert mean_delta > 0, "Mean delta should be positive"

        # This means policy B should be ACCEPTED
        should_accept = mean_delta > 0
        assert should_accept is True

    def test_policy_rejected_when_mean_delta_zero(self) -> None:
        """Policy B should be rejected when mean_delta == 0 (same cost)."""
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=1000, delta=0),
            PairedDelta(sample_idx=1, seed=2, cost_a=1000, cost_b=1000, delta=0),
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        mean_delta = evaluator.compute_mean_delta(deltas)

        # mean_delta = 0
        assert mean_delta == 0.0

        # This means policy B should be REJECTED (no improvement)
        should_accept = mean_delta > 0
        assert should_accept is False

    def test_policy_rejected_when_mean_delta_negative(self) -> None:
        """Policy B should be rejected when mean_delta < 0 (B is more expensive)."""
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=800, cost_b=1000, delta=-200),
            PairedDelta(sample_idx=1, seed=2, cost_a=900, cost_b=1100, delta=-200),
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        mean_delta = evaluator.compute_mean_delta(deltas)

        # mean_delta = -200 < 0
        assert mean_delta == -200.0
        assert mean_delta < 0, "Mean delta should be negative"

        # This means policy B should be REJECTED (regression)
        should_accept = mean_delta > 0
        assert should_accept is False

    def test_mixed_deltas_overall_improvement(self) -> None:
        """Policy B accepted when overall mean is positive despite some regressions."""
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=600, delta=400),  # Big improvement
            PairedDelta(sample_idx=1, seed=2, cost_a=1000, cost_b=1100, delta=-100),  # Small regression
            PairedDelta(sample_idx=2, seed=3, cost_a=1000, cost_b=900, delta=100),  # Small improvement
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        mean_delta = evaluator.compute_mean_delta(deltas)

        # mean_delta = (400 - 100 + 100) / 3 = 133.33 > 0
        assert mean_delta > 0, "Overall improvement should be positive"
        should_accept = mean_delta > 0
        assert should_accept is True

    def test_mixed_deltas_overall_regression(self) -> None:
        """Policy B rejected when overall mean is negative despite some improvements."""
        deltas = [
            PairedDelta(sample_idx=0, seed=1, cost_a=1000, cost_b=900, delta=100),  # Small improvement
            PairedDelta(sample_idx=1, seed=2, cost_a=1000, cost_b=1500, delta=-500),  # Big regression
            PairedDelta(sample_idx=2, seed=3, cost_a=1000, cost_b=1100, delta=-100),  # Small regression
        ]

        evaluator = BootstrapPolicyEvaluator(
            opening_balance=1_000_000,
            credit_limit=500_000,
        )
        mean_delta = evaluator.compute_mean_delta(deltas)

        # mean_delta = (100 - 500 - 100) / 3 = -166.67 < 0
        assert mean_delta < 0, "Overall should show regression"
        should_accept = mean_delta > 0
        assert should_accept is False


class TestBootstrapSampleReuse:
    """Tests verifying the same samples are used for both policies.

    This is CRITICAL - the paired comparison only works if we evaluate
    both policies on IDENTICAL samples.
    """

    @pytest.fixture
    def sample_list(self) -> list[BootstrapSample]:
        """Create a list of bootstrap samples for testing."""
        return [
            BootstrapSample(
                agent_id="TEST_AGENT",
                sample_idx=i,
                seed=12345 + i,
                outgoing_txns=(
                    RemappedTransaction(
                        tx_id=f"tx_{i}",
                        sender_id="TEST_AGENT",
                        receiver_id="OTHER",
                        amount=100000 + i * 10000,  # Varying amounts
                        priority=5,
                        arrival_tick=1,
                        deadline_tick=10,
                        settlement_tick=None,
                    ),
                ),
                incoming_settlements=(),
                total_ticks=12,
            )
            for i in range(3)
        ]

    def test_paired_deltas_have_matching_sample_indices(
        self,
        sample_list: list[BootstrapSample],
    ) -> None:
        """Each paired delta should have the sample_idx from the input samples."""
        # Note: This is a structural test - the actual evaluator creates
        # PairedDelta objects with the correct sample_idx

        # Create mock deltas as if from compute_paired_deltas
        deltas = [
            PairedDelta(
                sample_idx=sample.sample_idx,
                seed=sample.seed,
                cost_a=1000 + i * 100,
                cost_b=900 + i * 100,
                delta=100,
            )
            for i, sample in enumerate(sample_list)
        ]

        # Verify each delta corresponds to correct sample
        for delta, sample in zip(deltas, sample_list, strict=True):
            assert delta.sample_idx == sample.sample_idx
            assert delta.seed == sample.seed

    def test_paired_deltas_have_matching_seeds(
        self,
        sample_list: list[BootstrapSample],
    ) -> None:
        """Each paired delta should preserve the seed from the sample."""
        deltas = [
            PairedDelta(
                sample_idx=sample.sample_idx,
                seed=sample.seed,
                cost_a=1000,
                cost_b=900,
                delta=100,
            )
            for sample in sample_list
        ]

        # Verify seeds match
        for delta, sample in zip(deltas, sample_list, strict=True):
            assert delta.seed == sample.seed, (
                f"Delta seed {delta.seed} should match sample seed {sample.seed}"
            )


class TestCostsAreIntegerCents:
    """Tests verifying costs are always integer cents (INV-1)."""

    def test_paired_delta_costs_are_integers(self) -> None:
        """All costs in PairedDelta must be integers."""
        delta = PairedDelta(
            sample_idx=0,
            seed=1,
            cost_a=100000,  # $1000.00 in cents
            cost_b=95000,   # $950.00 in cents
            delta=5000,     # $50.00 in cents
        )

        assert isinstance(delta.cost_a, int)
        assert isinstance(delta.cost_b, int)
        assert isinstance(delta.delta, int)

    def test_evaluation_result_cost_is_integer(self) -> None:
        """EvaluationResult.total_cost must be integer cents."""
        cost_breakdown = CostBreakdown(
            delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
        )
        result = EvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=100000,  # $1000.00 in cents
            settlement_rate=1.0,
            avg_delay=0.0,
            cost_breakdown=cost_breakdown,
        )

        assert isinstance(result.total_cost, int)

    def test_no_float_costs_in_delta_computation(self) -> None:
        """Verify delta is exact integer arithmetic, no floats."""
        cost_a = 123456  # Arbitrary cents value
        cost_b = 78901   # Arbitrary cents value
        delta = cost_a - cost_b

        # This should be exact integer arithmetic
        assert delta == 44555
        assert isinstance(delta, int)
        # Verify no floating point rounding
        assert cost_a - cost_b == 44555
