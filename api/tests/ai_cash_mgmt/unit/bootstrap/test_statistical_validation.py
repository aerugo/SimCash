"""Statistical validation tests for bootstrap sampling.

Phase 3B: Statistical Validation - Verify Bootstrap Properties

Tests that verify the bootstrap sampler preserves statistical properties:
- Mean amount preservation
- Transaction frequency preservation
- Arrival time uniform distribution
- Coverage: bootstrap captures original data characteristics
"""

from __future__ import annotations

import math
import statistics

import pytest

from payment_simulator.ai_cash_mgmt.bootstrap.models import TransactionRecord
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler


class TestMeanAmountPreservation:
    """Test that bootstrap preserves mean transaction amount."""

    def test_mean_amount_converges_to_original(self) -> None:
        """Mean amount across many samples converges to original mean."""
        # Create records with known mean
        amounts = [100000, 200000, 300000, 400000, 500000]  # Mean = 300000
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=amounts[i],
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(len(amounts))
        )

        original_mean = statistics.mean(amounts)

        # Generate many samples and compute mean of means
        sampler = BootstrapSampler(seed=42)
        sample_means: list[float] = []

        for sample_idx in range(100):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )
            sample_mean = statistics.mean(tx.amount for tx in sample.outgoing_txns)
            sample_means.append(sample_mean)

        # Mean of sample means should be close to original mean
        bootstrap_mean = statistics.mean(sample_means)
        # Allow 10% tolerance
        assert abs(bootstrap_mean - original_mean) / original_mean < 0.10

    def test_amount_variance_reasonable(self) -> None:
        """Bootstrap sample means have reasonable variance."""
        amounts = [100000, 200000, 300000, 400000, 500000]
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=amounts[i],
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(len(amounts))
        )

        sampler = BootstrapSampler(seed=12345)
        sample_means: list[float] = []

        for sample_idx in range(100):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )
            sample_mean = statistics.mean(tx.amount for tx in sample.outgoing_txns)
            sample_means.append(sample_mean)

        # Variance should be positive (samples differ)
        variance = statistics.variance(sample_means)
        assert variance > 0

        # Standard error should be reasonable (not zero, not huge)
        std_err = math.sqrt(variance)
        original_mean = statistics.mean(amounts)
        # Coefficient of variation for sample means should be < 50%
        cv = std_err / original_mean
        assert cv < 0.5


class TestTransactionFrequencyPreservation:
    """Test that bootstrap maintains expected transaction frequency."""

    def test_sample_size_equals_original(self) -> None:
        """Bootstrap sample has same size as original."""
        n_records = 25
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 + i * 1000,
                priority=5,
                original_arrival_tick=i * 4,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(n_records)
        )

        sampler = BootstrapSampler(seed=42)

        for sample_idx in range(10):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )
            assert len(sample.outgoing_txns) == n_records

    def test_incoming_sample_size_equals_settled_count(self) -> None:
        """Bootstrap incoming sample has same size as settled transactions."""
        # Mix of settled and unsettled
        incoming_records = tuple(
            TransactionRecord(
                tx_id=f"tx-in-{i:03d}",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=100000,
                priority=5,
                original_arrival_tick=i * 5,
                deadline_offset=20,
                settlement_offset=10 if i % 2 == 0 else None,  # Half settled
            )
            for i in range(20)
        )

        settled_count = sum(1 for r in incoming_records if r.was_settled)

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=(),
            incoming_records=incoming_records,
            total_ticks=100,
        )

        assert len(sample.incoming_settlements) == settled_count


class TestArrivalTimeDistribution:
    """Test that remapped arrival times are uniformly distributed."""

    def test_arrivals_uniform_across_ticks(self) -> None:
        """Arrival ticks should be approximately uniform across time range."""
        n_records = 50
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,  # All originally at tick 0
                deadline_offset=100,
                settlement_offset=50,
            )
            for i in range(n_records)
        )

        total_ticks = 100
        sampler = BootstrapSampler(seed=42)

        # Aggregate arrivals across many samples
        arrival_ticks: list[int] = []
        for sample_idx in range(100):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=total_ticks,
            )
            arrival_ticks.extend(tx.arrival_tick for tx in sample.outgoing_txns)

        # Check distribution is approximately uniform
        # Divide into 10 bins
        n_bins = 10
        bin_size = total_ticks // n_bins
        bin_counts = [0] * n_bins

        for tick in arrival_ticks:
            bin_idx = min(tick // bin_size, n_bins - 1)
            bin_counts[bin_idx] += 1

        # Each bin should have roughly 10% of arrivals
        expected_per_bin = len(arrival_ticks) // n_bins
        for count in bin_counts:
            # Allow 50% tolerance for each bin
            assert count > expected_per_bin * 0.5
            assert count < expected_per_bin * 1.5

    def test_mean_arrival_tick_near_midpoint(self) -> None:
        """Mean arrival tick should be approximately at midpoint of range."""
        n_records = 20
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=5,
                original_arrival_tick=0,
                deadline_offset=100,
                settlement_offset=50,
            )
            for i in range(n_records)
        )

        total_ticks = 100
        sampler = BootstrapSampler(seed=12345)

        # Aggregate mean arrivals across many samples
        mean_arrivals: list[float] = []
        for sample_idx in range(200):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=total_ticks,
            )
            mean_arrival = statistics.mean(tx.arrival_tick for tx in sample.outgoing_txns)
            mean_arrivals.append(mean_arrival)

        # Grand mean should be near midpoint (49.5 for range [0, 100))
        grand_mean = statistics.mean(mean_arrivals)
        expected_midpoint = (total_ticks - 1) / 2
        # Within 10% of midpoint
        assert abs(grand_mean - expected_midpoint) / total_ticks < 0.10


class TestBootstrapCoverage:
    """Test bootstrap coverage - samples cover original data characteristics."""

    def test_all_original_records_appear_in_samples(self) -> None:
        """With enough samples, all original records should appear at least once."""
        n_records = 10
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 + i * 1000,  # Unique amounts
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(n_records)
        )

        original_amounts = {r.amount for r in records}

        sampler = BootstrapSampler(seed=42)
        seen_amounts: set[int] = set()

        # Generate many samples
        for sample_idx in range(200):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )
            seen_amounts.update(tx.amount for tx in sample.outgoing_txns)

        # Should have seen all original amounts
        assert seen_amounts == original_amounts

    def test_priority_distribution_preserved(self) -> None:
        """Bootstrap preserves the distribution of transaction priorities."""
        # Create records with varied priorities
        priorities = [1, 2, 3, 5, 5, 5, 7, 8, 9, 10]  # Known distribution
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000,
                priority=priorities[i],
                original_arrival_tick=i * 10,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(len(priorities))
        )

        original_mean_priority = statistics.mean(priorities)

        sampler = BootstrapSampler(seed=42)
        sample_mean_priorities: list[float] = []

        for sample_idx in range(100):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )
            sample_mean = statistics.mean(tx.priority for tx in sample.outgoing_txns)
            sample_mean_priorities.append(sample_mean)

        # Mean of sample means should be close to original mean
        bootstrap_mean = statistics.mean(sample_mean_priorities)
        # Within 10% tolerance
        assert abs(bootstrap_mean - original_mean_priority) / original_mean_priority < 0.10


class TestDeterminismInvariant:
    """Test the determinism invariant (project critical)."""

    def test_same_seed_identical_statistical_properties(self) -> None:
        """Same seed produces identical statistical properties."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 + i * 10000,
                priority=i % 10,
                original_arrival_tick=i * 5,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(20)
        )

        def compute_stats(seed: int) -> tuple[float, float, float]:
            """Compute statistics for samples with given seed."""
            sampler = BootstrapSampler(seed=seed)
            all_amounts: list[int] = []
            all_arrivals: list[int] = []
            all_priorities: list[int] = []

            for sample_idx in range(10):
                sample = sampler.generate_sample(
                    agent_id="BANK_A",
                    sample_idx=sample_idx,
                    outgoing_records=records,
                    incoming_records=(),
                    total_ticks=100,
                )
                all_amounts.extend(tx.amount for tx in sample.outgoing_txns)
                all_arrivals.extend(tx.arrival_tick for tx in sample.outgoing_txns)
                all_priorities.extend(tx.priority for tx in sample.outgoing_txns)

            return (
                statistics.mean(all_amounts),
                statistics.mean(all_arrivals),
                statistics.mean(all_priorities),
            )

        # Same seed should produce identical results
        stats1 = compute_stats(seed=12345)
        stats2 = compute_stats(seed=12345)
        assert stats1 == stats2

        # Different seed should produce different results
        stats3 = compute_stats(seed=54321)
        assert stats1 != stats3


class TestMoneyIntegerInvariant:
    """Test that money invariant (integer cents) is preserved."""

    def test_all_amounts_are_integers(self) -> None:
        """All amounts in bootstrap samples must be integers."""
        records = tuple(
            TransactionRecord(
                tx_id=f"tx-{i:03d}",
                sender_id="BANK_A",
                receiver_id="BANK_B",
                amount=100000 + i * 1000,
                priority=5,
                original_arrival_tick=i * 10,
                deadline_offset=20,
                settlement_offset=10,
            )
            for i in range(10)
        )

        sampler = BootstrapSampler(seed=42)

        for sample_idx in range(10):
            sample = sampler.generate_sample(
                agent_id="BANK_A",
                sample_idx=sample_idx,
                outgoing_records=records,
                incoming_records=(),
                total_ticks=100,
            )

            for tx in sample.outgoing_txns:
                assert isinstance(tx.amount, int), f"Amount must be int, got {type(tx.amount)}"

    def test_liquidity_calculations_are_integers(self) -> None:
        """Liquidity calculations from bootstrap samples are integers."""
        incoming_records = tuple(
            TransactionRecord(
                tx_id=f"tx-in-{i:03d}",
                sender_id="BANK_B",
                receiver_id="BANK_A",
                amount=50000 + i * 5000,
                priority=5,
                original_arrival_tick=i * 5,
                deadline_offset=20,
                settlement_offset=3,  # All settle at offset 3
            )
            for i in range(10)
        )

        sampler = BootstrapSampler(seed=42)
        sample = sampler.generate_sample(
            agent_id="BANK_A",
            sample_idx=0,
            outgoing_records=(),
            incoming_records=incoming_records,
            total_ticks=100,
        )

        # Test liquidity at various ticks
        for tick in range(100):
            liquidity = sample.get_incoming_liquidity_at_tick(tick)
            assert isinstance(liquidity, int), f"Liquidity must be int, got {type(liquidity)}"
