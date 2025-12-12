"""Unit tests for SeedMatrix deterministic seed generation.

Tests ensure:
- Reproducibility: same master_seed produces identical seeds
- Agent isolation: different agents get different seeds
- Iteration isolation: different iterations get different seeds
- Bootstrap isolation: different samples get different seeds
- Range validity: seeds fit within FFI-safe range
"""

from __future__ import annotations

import pytest

from payment_simulator.experiments.runner.seed_matrix import SeedMatrix


class TestSeedMatrixReproducibility:
    """Test that SeedMatrix produces reproducible seeds."""

    def test_same_master_seed_produces_identical_seeds(self) -> None:
        """Same master_seed produces identical seeds."""
        matrix1 = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A", "BANK_B"],
            num_bootstrap_samples=10,
        )
        matrix2 = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A", "BANK_B"],
            num_bootstrap_samples=10,
        )

        for iteration in range(10):
            for agent in ["BANK_A", "BANK_B"]:
                assert matrix1.get_iteration_seed(iteration, agent) == matrix2.get_iteration_seed(
                    iteration, agent
                ), f"Iteration seeds differ at iter={iteration}, agent={agent}"

                for sample in range(10):
                    assert matrix1.get_bootstrap_seed(
                        iteration, agent, sample
                    ) == matrix2.get_bootstrap_seed(
                        iteration, agent, sample
                    ), f"Bootstrap seeds differ at iter={iteration}, agent={agent}, sample={sample}"

    def test_different_master_seeds_produce_different_matrices(self) -> None:
        """Different master seeds produce completely different matrices."""
        matrix1 = SeedMatrix(
            master_seed=42, max_iterations=5, agents=["A"], num_bootstrap_samples=5
        )
        matrix2 = SeedMatrix(
            master_seed=43, max_iterations=5, agents=["A"], num_bootstrap_samples=5
        )

        # All iteration seeds should differ
        for i in range(5):
            assert (
                matrix1.get_iteration_seed(i, "A") != matrix2.get_iteration_seed(i, "A")
            ), f"Master seed 42 and 43 produced same iteration seed at iter={i}"


class TestSeedMatrixIsolation:
    """Test that SeedMatrix provides proper isolation."""

    def test_agent_isolation(self) -> None:
        """Different agents get different seeds for same iteration."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A", "BANK_B"],
            num_bootstrap_samples=10,
        )

        for iteration in range(10):
            seed_a = matrix.get_iteration_seed(iteration, "BANK_A")
            seed_b = matrix.get_iteration_seed(iteration, "BANK_B")
            assert (
                seed_a != seed_b
            ), f"Iteration {iteration}: agents should have different seeds"

    def test_iteration_isolation(self) -> None:
        """Different iterations get different seeds for same agent."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A"],
            num_bootstrap_samples=10,
        )

        seeds = [matrix.get_iteration_seed(i, "BANK_A") for i in range(10)]
        assert len(set(seeds)) == 10, "Each iteration should have unique seed"

    def test_bootstrap_sample_isolation(self) -> None:
        """Different bootstrap samples get different seeds."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=1,
            agents=["BANK_A"],
            num_bootstrap_samples=10,
        )

        seeds = [matrix.get_bootstrap_seed(0, "BANK_A", sample) for sample in range(10)]
        assert len(set(seeds)) == 10, "Each sample should have unique seed"


class TestSeedMatrixRangeValidity:
    """Test that seeds are within valid range for Rust FFI."""

    def test_seeds_within_i32_range(self) -> None:
        """Seeds are within valid i32 range for Rust FFI."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=100,
            agents=["BANK_A", "BANK_B", "BANK_C"],
            num_bootstrap_samples=50,
        )

        max_seed = 2**31 - 1  # i32 max for compatibility

        for iteration in range(100):
            for agent in ["BANK_A", "BANK_B", "BANK_C"]:
                seed = matrix.get_iteration_seed(iteration, agent)
                assert 0 <= seed <= max_seed, f"Iteration seed {seed} out of range"

                for sample in range(50):
                    bootstrap_seed = matrix.get_bootstrap_seed(iteration, agent, sample)
                    assert (
                        0 <= bootstrap_seed <= max_seed
                    ), f"Bootstrap seed {bootstrap_seed} out of range"

    def test_extreme_master_seeds(self) -> None:
        """Test with extreme master seed values."""
        for master_seed in [0, 1, 2**31 - 1, 2**32 - 1]:
            matrix = SeedMatrix(
                master_seed=master_seed,
                max_iterations=5,
                agents=["A"],
                num_bootstrap_samples=5,
            )

            # Should not raise, and all seeds should be valid
            max_seed = 2**31 - 1
            for i in range(5):
                seed = matrix.get_iteration_seed(i, "A")
                assert 0 <= seed <= max_seed


class TestSeedMatrixAPI:
    """Test SeedMatrix API behavior."""

    def test_get_bootstrap_seeds_returns_list(self) -> None:
        """get_bootstrap_seeds returns list of all sample seeds."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=1,
            agents=["BANK_A"],
            num_bootstrap_samples=10,
        )

        seeds = matrix.get_bootstrap_seeds(0, "BANK_A")
        assert len(seeds) == 10
        assert all(isinstance(s, int) for s in seeds)

        # Should match individual calls
        for i, seed in enumerate(seeds):
            assert seed == matrix.get_bootstrap_seed(0, "BANK_A", i)

    def test_agents_as_list_or_tuple(self) -> None:
        """SeedMatrix accepts agents as list or tuple."""
        # List input
        matrix1 = SeedMatrix(
            master_seed=42,
            max_iterations=5,
            agents=["A", "B"],
            num_bootstrap_samples=5,
        )

        # Tuple input
        matrix2 = SeedMatrix(
            master_seed=42,
            max_iterations=5,
            agents=("A", "B"),
            num_bootstrap_samples=5,
        )

        # Should produce same seeds
        for i in range(5):
            for agent in ["A", "B"]:
                assert matrix1.get_iteration_seed(i, agent) == matrix2.get_iteration_seed(
                    i, agent
                )

    def test_invalid_iteration_raises_key_error(self) -> None:
        """Accessing invalid iteration raises KeyError."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=5,
            agents=["A"],
            num_bootstrap_samples=5,
        )

        with pytest.raises(KeyError):
            matrix.get_iteration_seed(10, "A")  # Only 0-4 valid

    def test_invalid_agent_raises_key_error(self) -> None:
        """Accessing invalid agent raises KeyError."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=5,
            agents=["A"],
            num_bootstrap_samples=5,
        )

        with pytest.raises(KeyError):
            matrix.get_iteration_seed(0, "B")  # Only "A" valid

    def test_invalid_sample_raises_key_error(self) -> None:
        """Accessing invalid sample raises KeyError."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=5,
            agents=["A"],
            num_bootstrap_samples=5,
        )

        with pytest.raises(KeyError):
            matrix.get_bootstrap_seed(0, "A", 10)  # Only 0-4 valid


class TestSeedMatrixStatisticalProperties:
    """Test statistical properties of generated seeds."""

    def test_seed_distribution_is_spread(self) -> None:
        """Seeds should be reasonably spread across the range."""
        matrix = SeedMatrix(
            master_seed=12345,
            max_iterations=100,
            agents=["A", "B", "C"],
            num_bootstrap_samples=100,
        )

        # Collect all iteration seeds
        seeds = []
        for i in range(100):
            for agent in ["A", "B", "C"]:
                seeds.append(matrix.get_iteration_seed(i, agent))

        # Check they're spread (not all in one range)
        max_seed = 2**31
        quartiles = [0] * 4
        for seed in seeds:
            quartile = min(3, seed * 4 // max_seed)
            quartiles[quartile] += 1

        # Each quartile should have some seeds (rough check)
        for q, count in enumerate(quartiles):
            assert count > 0, f"Quartile {q} has no seeds - distribution may be biased"

    def test_no_obvious_patterns(self) -> None:
        """Sequential iteration seeds shouldn't have obvious patterns."""
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=100,
            agents=["A"],
            num_bootstrap_samples=10,
        )

        # Get sequential seeds
        seeds = [matrix.get_iteration_seed(i, "A") for i in range(100)]

        # Check that differences aren't constant (would indicate arithmetic progression)
        diffs = [seeds[i + 1] - seeds[i] for i in range(len(seeds) - 1)]
        unique_diffs = set(diffs)

        # Should have many unique differences (hash output looks random)
        assert len(unique_diffs) > 50, "Seed differences are too regular"
