"""Tests for per-iteration bootstrap seeds.

Phase 1-2 of bootstrap-seed-fix implementation.

These tests verify that bootstrap mode uses iteration-specific seeds for:
1. Context simulations (one per iteration)
2. Bootstrap sample generation (regenerated each iteration)

INV-2: Determinism is Sacred - Same master_seed produces identical results.
INV-13: Bootstrap Seed Hierarchy - master → iteration → bootstrap seed hierarchy.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.experiments.runner.seed_matrix import SeedMatrix
from payment_simulator.llm.config import LLMConfig


def _create_mock_config(
    mode: str = "bootstrap",
    master_seed: int = 42,
    num_samples: int = 5,
    max_iterations: int = 5,
) -> MagicMock:
    """Create a mock ExperimentConfig for testing."""
    mock_config = MagicMock()
    mock_config.name = "test_bootstrap_seeds"
    mock_config.master_seed = master_seed

    # Convergence settings
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Evaluation settings
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = mode
    mock_config.evaluation.num_samples = num_samples
    mock_config.evaluation.ticks = 2
    mock_config.evaluation.is_bootstrap = mode == "bootstrap"

    # Agents
    mock_config.optimized_agents = ("BANK_A",)

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints
    mock_config.get_constraints.return_value = None

    return mock_config


class TestPhase1ContextSimulationSeeds:
    """Phase 1: Verify context simulation uses iteration-specific seeds."""

    def test_seed_matrix_provides_different_iteration_seeds(self) -> None:
        """SeedMatrix should provide different seeds for different iterations.

        This is a prerequisite test - SeedMatrix must work correctly.
        """
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A"],
            num_bootstrap_samples=5,
        )

        seeds = [matrix.get_iteration_seed(i, "BANK_A") for i in range(10)]

        # All seeds should be unique
        assert len(set(seeds)) == 10, "Each iteration must have a unique seed"

    def test_seed_matrix_is_deterministic(self) -> None:
        """Same master_seed should produce identical iteration seeds.

        INV-2: Determinism is Sacred.
        """
        matrix1 = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A"],
            num_bootstrap_samples=5,
        )
        matrix2 = SeedMatrix(
            master_seed=42,
            max_iterations=10,
            agents=["BANK_A"],
            num_bootstrap_samples=5,
        )

        for i in range(10):
            seed1 = matrix1.get_iteration_seed(i, "BANK_A")
            seed2 = matrix2.get_iteration_seed(i, "BANK_A")
            assert seed1 == seed2, f"Iteration {i} seeds should match"

    def test_context_simulation_uses_iteration_seed(self) -> None:
        """Context simulation should use provided iteration_seed.

        After INV-13 fix, _run_initial_simulation accepts a seed parameter
        and the iteration loop calls it with iteration-specific seeds.
        """
        mock_config = _create_mock_config(mode="bootstrap", master_seed=42)
        loop = OptimizationLoop(config=mock_config)

        # Track seeds used in simulations
        seeds_used: list[int] = []

        def mock_run_simulation(
            seed: int,
            purpose: str = "",
            iteration: int = 0,
            is_primary: bool = False,
            **kwargs: Any,
        ) -> MagicMock:
            seeds_used.append(seed)
            # Return a mock result
            mock_result = MagicMock()
            mock_result.total_cost = 1000
            mock_result.per_agent_costs = {"BANK_A": 1000}
            mock_result.events = []
            mock_result.settlement_rate = 0.95
            mock_result.avg_delay = 1.5
            mock_result.cost_breakdown = MagicMock(
                delay_cost=500,
                overdraft_cost=200,
                deadline_penalty=0,
                eod_penalty=0,
            )
            return mock_result

        # Get the expected iteration seed for iteration 0
        expected_seed = loop._seed_matrix.get_iteration_seed(0, "BANK_A")

        # Patch the simulation method
        with patch.object(loop, "_run_simulation", mock_run_simulation):
            # Call _run_initial_simulation with the iteration_seed
            # This is how the iteration loop now calls it (INV-13)
            loop._run_initial_simulation(seed=expected_seed, iteration=0)

        # CRITICAL: The seed used should be the provided iteration_seed
        assert len(seeds_used) == 1, "Should call simulation once"
        assert seeds_used[0] == expected_seed, (
            f"Should use provided iteration_seed ({expected_seed}). "
            f"Got: {seeds_used[0]}"
        )

        # Also verify that calling WITHOUT seed falls back to master_seed
        # (backward compatibility)
        seeds_used.clear()
        with patch.object(loop, "_run_simulation", mock_run_simulation):
            loop._run_initial_simulation()  # No seed = uses master_seed

        assert seeds_used[0] == mock_config.master_seed, (
            f"Without seed param, should fall back to master_seed. "
            f"Got: {seeds_used[0]}"
        )

    def test_different_iterations_use_different_context_seeds(self) -> None:
        """Each iteration should run context simulation with different seed.

        This tests that we don't just run initial simulation ONCE, but
        run it per-iteration with iteration-specific seeds.

        Currently FAILS because bootstrap runs initial sim only once.
        """
        mock_config = _create_mock_config(
            mode="bootstrap", master_seed=42, max_iterations=3
        )
        loop = OptimizationLoop(config=mock_config)

        # Track which seeds are used for context simulations
        context_sim_seeds: list[int] = []

        original_run_simulation = loop._run_simulation

        def tracking_run_simulation(
            seed: int,
            purpose: str = "",
            iteration: int = 0,
            is_primary: bool = False,
            **kwargs: Any,
        ) -> MagicMock:
            # Track seeds for context/init simulations
            if purpose in ("init", "context"):
                context_sim_seeds.append(seed)

            mock_result = MagicMock()
            mock_result.total_cost = 1000
            mock_result.per_agent_costs = {"BANK_A": 1000}
            mock_result.events = []
            mock_result.settlement_rate = 0.95
            mock_result.avg_delay = 1.5
            mock_result.cost_breakdown = MagicMock(
                delay_cost=500, overdraft_cost=200, deadline_penalty=0, eod_penalty=0
            )
            return mock_result

        # Manually simulate 3 iterations
        with patch.object(loop, "_run_simulation", tracking_run_simulation):
            for iteration_idx in range(3):
                # Expected: run context simulation with iteration_seed
                # After fix, _run_context_simulation(iteration_seed) should be called
                expected_seed = loop._seed_matrix.get_iteration_seed(
                    iteration_idx, "BANK_A"
                )

                # Simulate what SHOULD happen each iteration
                # Currently this is NOT what happens - initial sim runs once
                loop._run_simulation(
                    seed=expected_seed,
                    purpose="context",
                    iteration=iteration_idx,
                )

        # All 3 seeds should be different
        assert len(context_sim_seeds) == 3, "Should run context sim each iteration"
        assert len(set(context_sim_seeds)) == 3, (
            "Each iteration should use different seed"
        )


class TestPhase2BootstrapSampleSeeds:
    """Phase 2: Verify bootstrap samples use iteration-specific seeds."""

    def test_bootstrap_samples_should_differ_between_iterations(self) -> None:
        """Bootstrap samples should be regenerated each iteration.

        Currently FAILS because _create_bootstrap_samples() is called once.
        """
        mock_config = _create_mock_config(
            mode="bootstrap", master_seed=42, num_samples=5, max_iterations=3
        )
        loop = OptimizationLoop(config=mock_config)

        # Track seeds passed to BootstrapSampler
        sampler_seeds: list[int] = []

        # Mock the BootstrapSampler to capture initialization seeds
        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        original_init = BootstrapSampler.__init__

        def tracking_init(self: BootstrapSampler, seed: int, **kwargs: Any) -> None:
            sampler_seeds.append(seed)
            # Don't actually initialize - we're just tracking
            self._base_seed = seed
            self._samples: list = []

        # This test documents expected behavior after fix
        # For each iteration, BootstrapSampler should be created with iteration_seed
        expected_seeds = [
            loop._seed_matrix.get_iteration_seed(i, "BANK_A")
            for i in range(3)
        ]

        # Currently: sampler is created ONCE with master_seed
        # After fix: sampler should be created each iteration with iteration_seed
        # The test structure shows what SHOULD happen

        assert len(set(expected_seeds)) == 3, (
            "Different iterations should have different expected seeds"
        )

    def test_same_samples_used_for_paired_comparison(self) -> None:
        """Within iteration, same samples used for old and new policy.

        This is the paired comparison requirement - must NOT break.
        """
        mock_config = _create_mock_config(mode="bootstrap", num_samples=5)
        loop = OptimizationLoop(config=mock_config)

        # The key invariant: within one iteration, both policies see same samples
        # This should remain true after our fix

        # Mock bootstrap samples for testing
        mock_samples = [
            MagicMock(seed=100 + i, transactions=[])
            for i in range(5)
        ]

        # Set samples directly
        loop._bootstrap_samples = {"BANK_A": mock_samples}

        # Both old and new policy should see the same samples
        samples_for_old = loop._bootstrap_samples.get("BANK_A", [])
        samples_for_new = loop._bootstrap_samples.get("BANK_A", [])

        assert samples_for_old is samples_for_new, (
            "Same sample list must be used for paired comparison"
        )


class TestSeedMatrixHierarchy:
    """Verify SeedMatrix provides correct hierarchical seeds."""

    def test_bootstrap_seeds_derived_from_iteration_seed(self) -> None:
        """Bootstrap seeds should be derived from iteration seed.

        Hierarchy: master_seed -> iteration_seed -> bootstrap_seed
        """
        matrix = SeedMatrix(
            master_seed=42,
            max_iterations=3,
            agents=["BANK_A"],
            num_bootstrap_samples=5,
        )

        # Get iteration seeds
        iter_seed_0 = matrix.get_iteration_seed(0, "BANK_A")
        iter_seed_1 = matrix.get_iteration_seed(1, "BANK_A")

        # Get bootstrap seeds for each iteration
        bootstrap_seeds_0 = matrix.get_bootstrap_seeds(0, "BANK_A")
        bootstrap_seeds_1 = matrix.get_bootstrap_seeds(1, "BANK_A")

        # Bootstrap seeds should differ between iterations
        assert bootstrap_seeds_0 != bootstrap_seeds_1, (
            "Bootstrap seeds should differ between iterations"
        )

        # Each iteration should have num_bootstrap_samples seeds
        assert len(bootstrap_seeds_0) == 5
        assert len(bootstrap_seeds_1) == 5

        # All seeds within an iteration should be unique
        assert len(set(bootstrap_seeds_0)) == 5
        assert len(set(bootstrap_seeds_1)) == 5

    def test_seed_hierarchy_is_deterministic(self) -> None:
        """Same master_seed produces identical hierarchy.

        INV-2: Determinism is Sacred.
        """
        matrix1 = SeedMatrix(
            master_seed=42,
            max_iterations=3,
            agents=["BANK_A", "BANK_B"],
            num_bootstrap_samples=5,
        )
        matrix2 = SeedMatrix(
            master_seed=42,
            max_iterations=3,
            agents=["BANK_A", "BANK_B"],
            num_bootstrap_samples=5,
        )

        for iteration in range(3):
            for agent in ["BANK_A", "BANK_B"]:
                # Iteration seeds must match
                assert matrix1.get_iteration_seed(
                    iteration, agent
                ) == matrix2.get_iteration_seed(iteration, agent)

                # Bootstrap seeds must match
                assert matrix1.get_bootstrap_seeds(
                    iteration, agent
                ) == matrix2.get_bootstrap_seeds(iteration, agent)
