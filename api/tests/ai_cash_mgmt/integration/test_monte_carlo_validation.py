"""Comprehensive Monte Carlo validation tests.

These tests mathematically and practically prove that the Monte Carlo
simulations and policy evaluation work correctly, including:

1. Statistical Properties: Law of Large Numbers, CLT, variance estimation
2. Determinism: Same seed produces identical results
3. Sampling Correctness: Bootstrap, permutation, stratified properties
4. Edge Cases: Empty data, single items, extreme distributions
5. Complex Scenarios: Multi-agent, custom events, realistic configs

Mathematical Foundation:
- Bootstrap resampling: E[X*] approx E[X] as n->inf (Law of Large Numbers)
- Central Limit Theorem: (X_bar - mu) / (std/sqrt(n)) -> N(0,1)
- Variance estimation: Var(X_bar) approx std^2/n
"""

from __future__ import annotations

import math
import statistics
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

# =============================================================================
# PART 1: STATISTICAL PROPERTIES OF BOOTSTRAP SAMPLING
# =============================================================================


class TestBootstrapStatisticalProperties:
    """Prove bootstrap sampling has correct statistical properties."""

    def test_bootstrap_mean_converges_to_population_mean(self) -> None:
        """Bootstrap sample mean converges to population mean (LLN).

        Mathematical Proof:
        By the Law of Large Numbers, for i.i.d. samples X₁, X₂, ..., Xₙ:
        X̄ₙ → μ as n → ∞ (almost surely)

        We verify: |E[X*] - μ| < ε for sufficiently many bootstrap samples.
        """
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create population with known mean
        np.random.seed(42)
        population_amounts = [100000 + i * 1000 for i in range(100)]  # Mean = 149500
        population_mean = statistics.mean(population_amounts)

        transactions = [
            {
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": amt,
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            }
            for i, amt in enumerate(population_amounts)
        ]

        sampler = TransactionSampler(seed=12345)
        sampler.collect_transactions(transactions)

        # Take many bootstrap samples and compute means
        num_bootstrap_samples = 1000
        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=num_bootstrap_samples,
            method="bootstrap",
        )

        sample_means = [
            statistics.mean(tx.amount for tx in sample) for sample in samples
        ]
        bootstrap_mean_of_means = statistics.mean(sample_means)

        # Bootstrap mean should be close to population mean
        # Allow 2% tolerance
        relative_error = abs(bootstrap_mean_of_means - population_mean) / population_mean
        assert relative_error < 0.02, (
            f"Bootstrap mean {bootstrap_mean_of_means:.2f} differs from "
            f"population mean {population_mean:.2f} by {relative_error*100:.2f}%"
        )

    def test_bootstrap_variance_estimation_is_unbiased(self) -> None:
        """Bootstrap variance is an unbiased estimator of sampling variance.

        Mathematical Proof:
        For bootstrap, Var*(X̄*) ≈ Var(X̄) = σ²/n

        We verify the bootstrap variance estimate is close to theoretical variance.
        """
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create population with known variance
        population_amounts = list(range(50000, 150001, 1000))  # 101 values
        population_variance = statistics.variance(population_amounts)
        n = len(population_amounts)
        theoretical_se = math.sqrt(population_variance / n)

        transactions = [
            {
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": amt,
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            }
            for i, amt in enumerate(population_amounts)
        ]

        sampler = TransactionSampler(seed=54321)
        sampler.collect_transactions(transactions)

        # Generate bootstrap samples and compute standard error
        num_bootstrap_samples = 500
        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=num_bootstrap_samples,
            method="bootstrap",
        )

        sample_means = [
            statistics.mean(tx.amount for tx in sample) for sample in samples
        ]
        bootstrap_se = statistics.stdev(sample_means)

        # Bootstrap SE should be within 30% of theoretical SE
        relative_error = abs(bootstrap_se - theoretical_se) / theoretical_se
        assert relative_error < 0.3, (
            f"Bootstrap SE {bootstrap_se:.2f} differs from "
            f"theoretical SE {theoretical_se:.2f} by {relative_error*100:.2f}%"
        )

    def test_central_limit_theorem_holds_for_bootstrap_means(self) -> None:
        """Bootstrap sample means follow approximately normal distribution.

        Mathematical Proof:
        By CLT, (X_bar - mu) / (std/sqrt(n)) -> N(0,1)

        We verify: standardized bootstrap means follow standard normal.
        """
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create non-normal population (uniform distribution)
        population_amounts = list(range(100000, 200001, 1000))  # Uniform
        population_mean = statistics.mean(population_amounts)
        population_std = statistics.stdev(population_amounts)

        transactions = [
            {
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": amt,
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            }
            for i, amt in enumerate(population_amounts)
        ]

        sampler = TransactionSampler(seed=99999)
        sampler.collect_transactions(transactions)

        # Generate many bootstrap samples
        num_bootstrap_samples = 500
        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=num_bootstrap_samples,
            method="bootstrap",
        )

        # Compute sample means
        sample_means = [
            statistics.mean(tx.amount for tx in sample) for sample in samples
        ]

        # Standardize: z = (x_bar - mu) / (std/sqrt(n))
        n = len(population_amounts)
        se = population_std / math.sqrt(n)
        z_scores = [(m - population_mean) / se for m in sample_means]

        # For N(0,1), about 68% should be within +/-1, 95% within +/-2
        within_1_std = sum(1 for z in z_scores if -1 <= z <= 1) / len(z_scores)
        within_2_std = sum(1 for z in z_scores if -2 <= z <= 2) / len(z_scores)

        # Allow some tolerance due to finite sample
        assert within_1_std > 0.55, f"Only {within_1_std*100:.1f}% within +/-1 std (expected ~68%)"
        assert within_2_std > 0.90, f"Only {within_2_std*100:.1f}% within +/-2 std (expected ~95%)"


# =============================================================================
# PART 2: STRICT DETERMINISM TESTS
# =============================================================================


class TestStrictDeterminism:
    """Prove same seed always produces identical results."""

    def test_same_seed_produces_identical_samples_across_runs(self) -> None:
        """Same seed must produce byte-for-byte identical samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(50)

        # Run 1
        sampler1 = TransactionSampler(seed=42)
        sampler1.collect_transactions(transactions)
        samples1 = sampler1.create_samples(
            agent_id="BANK_A", num_samples=10, method="bootstrap"
        )

        # Run 2 - MUST be identical
        sampler2 = TransactionSampler(seed=42)
        sampler2.collect_transactions(transactions)
        samples2 = sampler2.create_samples(
            agent_id="BANK_A", num_samples=10, method="bootstrap"
        )

        # Verify EXACT match
        for i in range(10):
            ids1 = [tx.tx_id for tx in samples1[i]]
            ids2 = [tx.tx_id for tx in samples2[i]]
            assert ids1 == ids2, f"Sample {i} differs: {ids1} != {ids2}"

            amounts1 = [tx.amount for tx in samples1[i]]
            amounts2 = [tx.amount for tx in samples2[i]]
            assert amounts1 == amounts2, f"Sample {i} amounts differ"

    def test_different_seeds_produce_different_samples(self) -> None:
        """Different seeds must produce statistically different samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(100)

        sampler1 = TransactionSampler(seed=42)
        sampler1.collect_transactions(transactions)
        samples1 = sampler1.create_samples(
            agent_id="BANK_A", num_samples=10, method="bootstrap"
        )

        sampler2 = TransactionSampler(seed=43)  # Different seed
        sampler2.collect_transactions(transactions)
        samples2 = sampler2.create_samples(
            agent_id="BANK_A", num_samples=10, method="bootstrap"
        )

        # At least some samples should differ
        differences = 0
        for i in range(10):
            ids1 = tuple(tx.tx_id for tx in samples1[i])
            ids2 = tuple(tx.tx_id for tx in samples2[i])
            if ids1 != ids2:
                differences += 1

        assert differences > 5, f"Only {differences}/10 samples differ between seeds"

    def test_seed_isolation_between_agents(self) -> None:
        """Different agents with same base seed should get different samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create transactions where some are exclusive to BANK_A, some to BANK_B
        transactions = []
        # BANK_A only transactions (A sends to C, D sends to A)
        for i in range(20):
            transactions.append({
                "tx_id": f"TXA{i:03d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_C",
                "amount": 100000 + i * 1000,
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            })
        # BANK_B only transactions (B sends to C, D sends to B)
        for i in range(20):
            transactions.append({
                "tx_id": f"TXB{i:03d}",
                "sender_id": "BANK_B",
                "receiver_id": "BANK_D",
                "amount": 200000 + i * 1000,
                "priority": 5,
                "arrival_tick": i + 20,
                "deadline_tick": i + 30,
                "is_divisible": True,
            })
        # Shared transactions (A and B both involved)
        for i in range(10):
            transactions.append({
                "tx_id": f"TXS{i:03d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 300000 + i * 1000,
                "priority": 5,
                "arrival_tick": i + 40,
                "deadline_tick": i + 50,
                "is_divisible": True,
            })

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        # Get samples for BANK_A (should include TXA* and TXS*)
        samples_a = sampler.create_samples(
            agent_id="BANK_A", num_samples=5, method="bootstrap"
        )

        # Reset sampler (same seed)
        sampler2 = TransactionSampler(seed=42)
        sampler2.collect_transactions(transactions)

        # Get samples for BANK_B (should include TXB* and TXS*)
        samples_b = sampler2.create_samples(
            agent_id="BANK_B", num_samples=5, method="bootstrap"
        )

        # Collect all unique tx_ids from samples
        a_tx_ids = {tx.tx_id for sample in samples_a for tx in sample}
        b_tx_ids = {tx.tx_id for sample in samples_b for tx in sample}

        # BANK_A samples should contain TXA* (exclusive to A)
        a_exclusive = {tx_id for tx_id in a_tx_ids if tx_id.startswith("TXA")}
        assert len(a_exclusive) > 0, "BANK_A samples should include A-exclusive txns"

        # BANK_B samples should contain TXB* (exclusive to B)
        b_exclusive = {tx_id for tx_id in b_tx_ids if tx_id.startswith("TXB")}
        assert len(b_exclusive) > 0, "BANK_B samples should include B-exclusive txns"

        # Exclusive transactions should not appear in wrong agent's samples
        b_in_a = {tx_id for tx_id in a_tx_ids if tx_id.startswith("TXB")}
        a_in_b = {tx_id for tx_id in b_tx_ids if tx_id.startswith("TXA")}
        assert len(b_in_a) == 0, "BANK_A samples should not contain B-exclusive txns"
        assert len(a_in_b) == 0, "BANK_B samples should not contain A-exclusive txns"

    def test_seed_manager_derivation_is_collision_free(self) -> None:
        """Derived seeds should be unique for different inputs."""
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager

        manager = SeedManager(master_seed=42)

        # Generate many derived seeds
        seeds = set()
        for iteration in range(100):
            for agent in ["BANK_A", "BANK_B", "BANK_C"]:
                seed = manager.sampling_seed(iteration, agent)
                assert seed not in seeds, f"Collision at iteration={iteration}, agent={agent}"
                seeds.add(seed)

        # Should have 300 unique seeds
        assert len(seeds) == 300


# =============================================================================
# PART 3: SAMPLING METHOD CORRECTNESS
# =============================================================================


class TestBootstrapSamplingCorrectness:
    """Prove bootstrap sampling has correct statistical properties."""

    def test_bootstrap_samples_with_replacement(self) -> None:
        """Bootstrap must sample with replacement (duplicates expected)."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Small population to guarantee duplicates
        transactions = _create_diverse_transactions(10)

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        # With n=10 and sampling n items with replacement,
        # probability of NO duplicates = 10!/10^10 ≈ 0.00036
        # So we should see duplicates in almost all samples
        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=100, method="bootstrap"
        )

        samples_with_duplicates = 0
        for sample in samples:
            tx_ids = [tx.tx_id for tx in sample]
            if len(tx_ids) != len(set(tx_ids)):
                samples_with_duplicates += 1

        # Should see duplicates in at least 90% of samples
        assert samples_with_duplicates >= 90, (
            f"Only {samples_with_duplicates}/100 samples had duplicates; "
            "bootstrap should sample with replacement"
        )

    def test_bootstrap_preserves_sample_size(self) -> None:
        """Bootstrap samples should have same size as original."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(47)  # Odd number

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=20, method="bootstrap"
        )

        for i, sample in enumerate(samples):
            assert len(sample) == 47, f"Sample {i} has {len(sample)} items, expected 47"


class TestPermutationSamplingCorrectness:
    """Prove permutation sampling correctly shuffles without replacement."""

    def test_permutation_preserves_all_elements(self) -> None:
        """Permutation must contain all original elements exactly once."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(50)
        original_ids = {f"TX{i:04d}" for i in range(50)}

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=20, method="permutation"
        )

        for i, sample in enumerate(samples):
            sample_ids = {tx.tx_id for tx in sample}
            assert sample_ids == original_ids, f"Sample {i} missing or extra elements"

            # No duplicates allowed
            tx_ids_list = [tx.tx_id for tx in sample]
            assert len(tx_ids_list) == len(set(tx_ids_list)), f"Sample {i} has duplicates"

    def test_permutation_produces_different_orderings(self) -> None:
        """Permutation should produce genuinely different orderings."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(20)

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=50, method="permutation"
        )

        # Convert to tuples for hashing
        orderings = [tuple(tx.tx_id for tx in sample) for sample in samples]
        unique_orderings = set(orderings)

        # With 20! possible orderings, 50 samples should all be unique
        assert len(unique_orderings) == 50, (
            f"Only {len(unique_orderings)}/50 unique orderings; "
            "permutation should produce different orders"
        )


class TestStratifiedSamplingCorrectness:
    """Prove stratified sampling maintains distribution."""

    def test_stratified_maintains_quartile_distribution(self) -> None:
        """Stratified sampling should maintain amount distribution."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create transactions with clear quartile boundaries
        # Q1: 10k-30k, Q2: 30k-50k, Q3: 50k-70k, Q4: 70k-90k
        transactions = []
        amounts = (
            list(range(10000, 30001, 2000)) +  # Q1: 11 values
            list(range(30000, 50001, 2000)) +  # Q2: 11 values
            list(range(50000, 70001, 2000)) +  # Q3: 11 values
            list(range(70000, 90001, 2000))    # Q4: 11 values
        )
        for i, amt in enumerate(amounts):
            transactions.append({
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": amt,
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            })

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=50, method="stratified"
        )

        # Check that each sample has transactions from all quartiles
        for i, sample in enumerate(samples):
            amounts = [tx.amount for tx in sample]
            q1_count = sum(1 for a in amounts if a < 30000)
            q2_count = sum(1 for a in amounts if 30000 <= a < 50000)
            q3_count = sum(1 for a in amounts if 50000 <= a < 70000)
            q4_count = sum(1 for a in amounts if a >= 70000)

            # Each quartile should be represented
            assert q1_count > 0, f"Sample {i} missing Q1 transactions"
            assert q2_count > 0, f"Sample {i} missing Q2 transactions"
            assert q3_count > 0, f"Sample {i} missing Q3 transactions"
            assert q4_count > 0, f"Sample {i} missing Q4 transactions"


# =============================================================================
# PART 4: EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_single_transaction_bootstrap(self) -> None:
        """Bootstrap with single transaction should replicate it."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = [{
            "tx_id": "TX0001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "priority": 5,
            "arrival_tick": 0,
            "deadline_tick": 10,
            "is_divisible": True,
        }]

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=10, method="bootstrap"
        )

        # Each sample should have exactly 1 transaction (the same one)
        for sample in samples:
            assert len(sample) == 1
            assert sample[0].tx_id == "TX0001"

    def test_single_transaction_permutation(self) -> None:
        """Permutation with single transaction should return it unchanged."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = [{
            "tx_id": "TX0001",
            "sender_id": "BANK_A",
            "receiver_id": "BANK_B",
            "amount": 100000,
            "priority": 5,
            "arrival_tick": 0,
            "deadline_tick": 10,
            "is_divisible": True,
        }]

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A", num_samples=10, method="permutation"
        )

        for sample in samples:
            assert len(sample) == 1
            assert sample[0].tx_id == "TX0001"

    def test_empty_after_filtering(self) -> None:
        """Filtering that removes all transactions returns empty samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Transactions not involving BANK_X
        transactions = _create_diverse_transactions(50)

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_X",  # Not in any transaction
            num_samples=5,
            method="bootstrap",
        )

        for sample in samples:
            assert len(sample) == 0

    def test_max_tick_zero_returns_empty(self) -> None:
        """max_tick=0 should filter out transactions arriving after tick 0."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = [
            {
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 5,
                "arrival_tick": i + 1,  # All arrive after tick 0
                "deadline_tick": i + 11,
                "is_divisible": True,
            }
            for i in range(10)
        ]

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=3,
            max_tick=0,
            method="bootstrap",
        )

        for sample in samples:
            assert len(sample) == 0

    def test_large_sample_count(self) -> None:
        """Should handle large number of samples efficiently."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(100)

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        # Request many samples
        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=1000,
            method="bootstrap",
        )

        assert len(samples) == 1000
        # Verify they're valid
        for sample in samples[:10]:  # Spot check
            assert len(sample) == 100

    def test_extreme_amount_distribution(self) -> None:
        """Handle extreme amount distributions (high variance)."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create bimodal distribution: 1 cent and 1 billion
        transactions = []
        for i in range(50):
            transactions.append({
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 1 if i < 25 else 100000000000,  # 1 cent or $1B
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            })

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=20,
            method="stratified",
        )

        # Should still work without numerical issues
        for sample in samples:
            assert len(sample) > 0
            amounts = [tx.amount for tx in sample]
            assert all(a > 0 for a in amounts)


# =============================================================================
# PART 5: POLICY EVALUATOR INTEGRATION TESTS
# =============================================================================


class TestPolicyEvaluatorStatistics:
    """Test statistical correctness of PolicyEvaluator."""

    def test_evaluator_mean_calculation_is_correct(self) -> None:
        """Evaluator mean should be arithmetic mean of sample costs."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(num_samples=5, evaluation_ticks=10)

        samples = [_create_mock_samples(3) for _ in range(5)]
        costs = [100.0, 200.0, 300.0, 400.0, 500.0]
        mock_runner = _create_mock_runner_with_costs(costs)

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        expected_mean = statistics.mean(costs)
        assert result.mean_cost == pytest.approx(expected_mean)

    def test_evaluator_std_calculation_is_correct(self) -> None:
        """Evaluator std should be sample standard deviation."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        evaluator = PolicyEvaluator(num_samples=10, evaluation_ticks=10)

        samples = [_create_mock_samples(3) for _ in range(10)]
        costs = [100.0, 110.0, 90.0, 105.0, 95.0, 102.0, 98.0, 108.0, 92.0, 100.0]
        mock_runner = _create_mock_runner_with_costs(costs)

        result = evaluator.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner,
        )

        expected_std = statistics.stdev(costs)
        assert result.std_cost == pytest.approx(expected_std)

    def test_evaluator_confidence_interval_coverage(self) -> None:
        """95% confidence interval should cover true mean ~95% of time.

        Using: CI = X_bar +/- 1.96 * (std/sqrt(n))
        """
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )

        true_mean = 1000.0
        true_std = 100.0

        # Run many evaluations and check CI coverage
        np.random.seed(42)
        coverage_count = 0
        num_trials = 100

        for _trial in range(num_trials):
            evaluator = PolicyEvaluator(num_samples=30, evaluation_ticks=10)
            samples = [_create_mock_samples(3) for _ in range(30)]

            # Generate costs from known distribution
            costs = list(np.random.normal(true_mean, true_std, 30))
            mock_runner = _create_mock_runner_with_costs(costs)

            result = evaluator.evaluate(
                agent_id="BANK_A",
                policy={},
                samples=samples,
                scenario_config={},
                simulation_runner=mock_runner,
            )

            # Compute 95% CI
            se = result.std_cost / math.sqrt(result.num_samples)
            ci_lower = result.mean_cost - 1.96 * se
            ci_upper = result.mean_cost + 1.96 * se

            if ci_lower <= true_mean <= ci_upper:
                coverage_count += 1

        coverage_rate = coverage_count / num_trials
        # Should be close to 95% (allow some slack due to finite samples)
        assert coverage_rate >= 0.85, f"CI coverage {coverage_rate*100:.1f}% < 85%"


class TestPolicyEvaluatorComparison:
    """Test policy comparison correctness."""

    def test_better_policy_has_lower_cost(self) -> None:
        """is_better_than should correctly identify lower-cost policy."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )

        result_a = EvaluationResult(
            agent_id="BANK_A",
            policy={"name": "policy_a"},
            mean_cost=1000.0,
            std_cost=50.0,
            min_cost=900.0,
            max_cost=1100.0,
            sample_costs=[1000.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        result_b = EvaluationResult(
            agent_id="BANK_A",
            policy={"name": "policy_b"},
            mean_cost=800.0,  # Better (lower)
            std_cost=50.0,
            min_cost=700.0,
            max_cost=900.0,
            sample_costs=[800.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        assert result_b.is_better_than(result_a)
        assert not result_a.is_better_than(result_b)

    def test_improvement_calculation(self) -> None:
        """improvement_over should calculate correct percentage."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            EvaluationResult,
        )

        baseline = EvaluationResult(
            agent_id="BANK_A",
            policy={},
            mean_cost=1000.0,
            std_cost=0.0,
            min_cost=1000.0,
            max_cost=1000.0,
            sample_costs=[1000.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        improved = EvaluationResult(
            agent_id="BANK_A",
            policy={},
            mean_cost=750.0,  # 25% improvement
            std_cost=0.0,
            min_cost=750.0,
            max_cost=750.0,
            sample_costs=[750.0],
            num_samples=1,
            settlement_rate=0.95,
        )

        assert improved.improvement_over(baseline) == pytest.approx(0.25)


# =============================================================================
# PART 6: COMPLEX SCENARIO TESTS
# =============================================================================


class TestComplexScenarios:
    """Test with complex, realistic scenario configurations."""

    def test_multi_agent_network_sampling(self) -> None:
        """Test sampling in a multi-agent network with varying activity."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create network: A is high-volume, B is medium, C is low
        transactions = []
        tx_id = 0

        # A sends many transactions
        for i in range(100):
            transactions.append({
                "tx_id": f"TX{tx_id:04d}",
                "sender_id": "BANK_A",
                "receiver_id": ["BANK_B", "BANK_C", "BANK_D"][i % 3],
                "amount": 100000 + i * 100,
                "priority": 5,
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            })
            tx_id += 1

        # B sends fewer
        for i in range(30):
            transactions.append({
                "tx_id": f"TX{tx_id:04d}",
                "sender_id": "BANK_B",
                "receiver_id": ["BANK_A", "BANK_C"][i % 2],
                "amount": 500000 + i * 1000,
                "priority": 7,
                "arrival_tick": i * 3,
                "deadline_tick": i * 3 + 15,
                "is_divisible": False,
            })
            tx_id += 1

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        # Sample for each agent
        samples_a = sampler.create_samples("BANK_A", num_samples=10, method="bootstrap")
        samples_b = sampler.create_samples("BANK_B", num_samples=10, method="bootstrap")

        # A should have more transactions per sample
        avg_a = statistics.mean(len(s) for s in samples_a)
        avg_b = statistics.mean(len(s) for s in samples_b)

        assert avg_a > avg_b, "High-volume agent should have more transactions"

    def test_time_windowed_sampling(self) -> None:
        """Test sampling with time windows (intra-simulation optimization)."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Create transactions across time
        transactions = [
            {
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000 + i * 1000,
                "priority": 5,
                "arrival_tick": i * 10,  # 0, 10, 20, ..., 990
                "deadline_tick": i * 10 + 50,
                "is_divisible": True,
            }
            for i in range(100)
        ]

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        # Sample at tick 250 (should include ~25 transactions)
        samples_early = sampler.create_samples(
            "BANK_A", num_samples=10, max_tick=250, method="bootstrap"
        )

        # Sample at tick 500 (should include ~50 transactions)
        sampler2 = TransactionSampler(seed=42)  # Reset
        sampler2.collect_transactions(transactions)
        samples_mid = sampler2.create_samples(
            "BANK_A", num_samples=10, max_tick=500, method="bootstrap"
        )

        avg_early = statistics.mean(len(s) for s in samples_early)
        avg_mid = statistics.mean(len(s) for s in samples_mid)

        assert avg_mid > avg_early, "Later window should have more transactions"
        assert avg_early == pytest.approx(26, abs=2)  # ~26 transactions by tick 250
        assert avg_mid == pytest.approx(51, abs=2)  # ~51 transactions by tick 500

    def test_priority_weighted_transactions(self) -> None:
        """Test that high-priority transactions are preserved in samples."""
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Mix of priorities
        transactions = []
        for i in range(100):
            transactions.append({
                "tx_id": f"TX{i:04d}",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 10 if i < 10 else 1,  # 10% high priority
                "arrival_tick": i,
                "deadline_tick": i + 10,
                "is_divisible": True,
            })

        sampler = TransactionSampler(seed=42)
        sampler.collect_transactions(transactions)

        # Bootstrap preserves relative frequency
        samples = sampler.create_samples(
            "BANK_A", num_samples=100, method="bootstrap"
        )

        high_priority_fractions = []
        for sample in samples:
            high_count = sum(1 for tx in sample if tx.priority == 10)
            high_priority_fractions.append(high_count / len(sample))

        avg_fraction = statistics.mean(high_priority_fractions)
        # Should be close to 10%
        assert 0.07 < avg_fraction < 0.13, (
            f"High priority fraction {avg_fraction:.2%} should be ~10%"
        )


class TestMonteCarloEndToEnd:
    """End-to-end Monte Carlo evaluation tests."""

    def test_full_evaluation_pipeline(self) -> None:
        """Test complete pipeline: sample → evaluate → compare."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )
        from payment_simulator.ai_cash_mgmt.sampling.seed_manager import SeedManager
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        # Setup
        seed_manager = SeedManager(master_seed=42)
        transactions = _create_diverse_transactions(50)

        # Create sampler with derived seed
        sampling_seed = seed_manager.sampling_seed(iteration=0, agent_id="BANK_A")
        sampler = TransactionSampler(seed=sampling_seed)
        sampler.collect_transactions(transactions)

        # Create samples
        samples = sampler.create_samples(
            agent_id="BANK_A",
            num_samples=20,
            method="bootstrap",
        )

        # Evaluate two policies
        evaluator = PolicyEvaluator(num_samples=20, evaluation_ticks=100)

        # Policy A: higher costs
        mock_runner_a = _create_mock_runner_with_costs([1000.0] * 20)
        result_a = evaluator.evaluate(
            agent_id="BANK_A",
            policy={"name": "policy_a"},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner_a,
        )

        # Policy B: lower costs
        mock_runner_b = _create_mock_runner_with_costs([800.0] * 20)
        result_b = evaluator.evaluate(
            agent_id="BANK_A",
            policy={"name": "policy_b"},
            samples=samples,
            scenario_config={},
            simulation_runner=mock_runner_b,
        )

        # Policy B should be better
        assert result_b.is_better_than(result_a)
        assert result_b.improvement_over(result_a) == pytest.approx(0.2)

    def test_deterministic_evaluation_across_runs(self) -> None:
        """Same inputs must produce identical evaluation results."""
        from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
            PolicyEvaluator,
        )
        from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
            TransactionSampler,
        )

        transactions = _create_diverse_transactions(30)

        # Run 1
        sampler1 = TransactionSampler(seed=12345)
        sampler1.collect_transactions(transactions)
        samples1 = sampler1.create_samples("BANK_A", num_samples=10, method="bootstrap")

        evaluator1 = PolicyEvaluator(num_samples=10, evaluation_ticks=100)
        np.random.seed(42)
        costs1 = list(np.random.uniform(900, 1100, 10))
        mock_runner1 = _create_mock_runner_with_costs(costs1)

        result1 = evaluator1.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples1,
            scenario_config={},
            simulation_runner=mock_runner1,
        )

        # Run 2 - identical setup
        sampler2 = TransactionSampler(seed=12345)
        sampler2.collect_transactions(transactions)
        samples2 = sampler2.create_samples("BANK_A", num_samples=10, method="bootstrap")

        evaluator2 = PolicyEvaluator(num_samples=10, evaluation_ticks=100)
        np.random.seed(42)
        costs2 = list(np.random.uniform(900, 1100, 10))
        mock_runner2 = _create_mock_runner_with_costs(costs2)

        result2 = evaluator2.evaluate(
            agent_id="BANK_A",
            policy={},
            samples=samples2,
            scenario_config={},
            simulation_runner=mock_runner2,
        )

        # Results must be identical
        assert result1.mean_cost == result2.mean_cost
        assert result1.std_cost == result2.std_cost
        assert result1.sample_costs == result2.sample_costs


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _create_diverse_transactions(count: int) -> list[dict[str, Any]]:
    """Create diverse test transactions."""
    return [
        {
            "tx_id": f"TX{i:04d}",
            "sender_id": "BANK_A" if i % 2 == 0 else "BANK_B",
            "receiver_id": "BANK_B" if i % 2 == 0 else "BANK_A",
            "amount": 100000 + (i * 1234) % 500000,  # Varied amounts
            "priority": 1 + (i % 10),
            "arrival_tick": i,
            "deadline_tick": i + 10 + (i % 5),
            "is_divisible": i % 3 != 0,
        }
        for i in range(count)
    ]


def _create_mock_samples(count: int) -> list[Any]:
    """Create mock transaction samples."""
    from payment_simulator.ai_cash_mgmt.sampling.transaction_sampler import (
        HistoricalTransaction,
    )

    return [
        HistoricalTransaction(
            tx_id=f"TX{i:04d}",
            sender_id="BANK_A",
            receiver_id="BANK_B",
            amount=100000,
            priority=5,
            arrival_tick=i,
            deadline_tick=i + 10,
            is_divisible=True,
        )
        for i in range(count)
    ]


def _create_mock_runner_with_costs(costs: list[float]) -> MagicMock:
    """Create mock runner returning specified costs."""
    from payment_simulator.ai_cash_mgmt.optimization.policy_evaluator import (
        SimulationResult,
    )

    mock = MagicMock()
    results = [
        SimulationResult(total_cost=cost, settlement_rate=0.95)
        for cost in costs
    ]
    mock.run_ephemeral.side_effect = results
    return mock
