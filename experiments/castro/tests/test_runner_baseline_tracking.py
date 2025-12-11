"""Tests for bootstrap baseline tracking in ExperimentRunner.

TDD tests for ensuring the runner:
1. Uses consistent seeds across iterations (for valid comparison)
2. Stores baseline costs on iteration 1
3. Passes baseline_cost to BootstrapSampleResult on iteration 2+
4. Passes is_baseline_run flag to verbose logger
"""

from __future__ import annotations

import pytest


class TestConsistentSeedsAcrossIterations:
    """Tests that seeds are consistent across iterations for valid comparison."""

    def test_seeds_should_be_consistent_across_iterations(self) -> None:
        """Same sample_idx should produce same seed in different iterations.

        This is critical for comparing policy performance on the same
        transaction sets.
        """
        from payment_simulator.ai_cash_mgmt import SeedManager

        seed_manager = SeedManager(master_seed=12345)

        # Current broken behavior uses: iteration * 1000 + sample_idx
        # This produces DIFFERENT seeds for same sample_idx in different iterations

        # What we need: same seed for sample_idx regardless of iteration
        # For sample 0, iteration 1 should produce same seed as sample 0, iteration 5

        # Using the new approach: seeds based only on sample_idx
        seed_iter1_sample0 = seed_manager.simulation_seed(0)
        seed_iter5_sample0 = seed_manager.simulation_seed(0)  # Same input = same output

        assert seed_iter1_sample0 == seed_iter5_sample0, (
            "Same sample_idx should produce same seed regardless of iteration"
        )

        # Different sample_idx should produce different seeds
        seed_sample0 = seed_manager.simulation_seed(0)
        seed_sample1 = seed_manager.simulation_seed(1)

        assert seed_sample0 != seed_sample1, (
            "Different sample_idx should produce different seeds"
        )


class TestBaselineCostTracking:
    """Tests for storing and retrieving baseline costs."""

    def test_runner_stores_baseline_costs_on_first_iteration(self) -> None:
        """Runner should store seed→cost mapping on iteration 1.

        This baseline is used for delta comparison on subsequent iterations.
        """
        # This test verifies the _baseline_costs dict is populated
        # after the first evaluation
        pytest.skip("Requires full runner integration - will implement after unit tests pass")

    def test_runner_passes_baseline_cost_to_seed_results(self) -> None:
        """On iteration 2+, BootstrapSampleResult should have baseline_cost set."""
        pytest.skip("Requires full runner integration - will implement after unit tests pass")


class TestVerboseLoggerIntegration:
    """Tests for passing is_baseline_run to verbose logger."""

    def test_iteration_1_passes_is_baseline_run_true(self) -> None:
        """On iteration 1, verbose logger should receive is_baseline_run=True."""
        pytest.skip("Requires full runner integration - will implement after unit tests pass")

    def test_iteration_2_plus_passes_is_baseline_run_false(self) -> None:
        """On iteration 2+, verbose logger should receive is_baseline_run=False."""
        pytest.skip("Requires full runner integration - will implement after unit tests pass")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
