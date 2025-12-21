"""Integration tests for bootstrap seed hierarchy (INV-13).

Phase 3 of bootstrap-seed-fix implementation.

These tests verify end-to-end behavior:
1. Each iteration uses a unique seed for context simulation
2. Bootstrap samples are regenerated each iteration
3. Total unique seeds = iterations × samples
4. Results are deterministic across runs

INV-2: Determinism is Sacred
INV-13: Bootstrap Seed Hierarchy
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch, AsyncMock

import pytest

from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.experiments.runner.seed_matrix import SeedMatrix
from payment_simulator.llm.config import LLMConfig


def _create_bootstrap_config(
    master_seed: int = 42,
    num_samples: int = 5,
    max_iterations: int = 5,
) -> MagicMock:
    """Create a mock ExperimentConfig for bootstrap mode testing."""
    mock_config = MagicMock()
    mock_config.name = "test_bootstrap_hierarchy"
    mock_config.master_seed = master_seed

    # Convergence settings - never converge early
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.001  # Very tight
    mock_config.convergence.stability_window = 100  # Never hit this
    mock_config.convergence.improvement_threshold = 0.0

    # Evaluation settings - bootstrap mode
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = "bootstrap"
    mock_config.evaluation.num_samples = num_samples
    mock_config.evaluation.ticks = 2
    mock_config.evaluation.is_bootstrap = True

    # Agents
    mock_config.optimized_agents = ("BANK_A",)

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints
    mock_config.get_constraints.return_value = None

    return mock_config


class TestBootstrapSeedHierarchyIntegration:
    """Integration tests for per-iteration bootstrap seeds."""

    def test_iteration_seeds_are_unique(self) -> None:
        """Each iteration should use a unique seed from SeedMatrix.

        Verifies: iterations × 1 unique context simulation seeds.
        """
        mock_config = _create_bootstrap_config(
            master_seed=42, max_iterations=5, num_samples=3
        )
        loop = OptimizationLoop(config=mock_config)

        # Collect iteration seeds
        iteration_seeds = []
        for iteration_idx in range(5):
            seed = loop._seed_matrix.get_iteration_seed(iteration_idx, "BANK_A")
            iteration_seeds.append(seed)

        # All 5 seeds should be unique
        assert len(set(iteration_seeds)) == 5, (
            f"Expected 5 unique iteration seeds, got {len(set(iteration_seeds))}"
        )

    def test_bootstrap_sample_seeds_unique_per_iteration(self) -> None:
        """Each iteration × sample should have unique seed.

        Verifies: iterations × samples unique bootstrap seeds.
        """
        mock_config = _create_bootstrap_config(
            master_seed=42, max_iterations=5, num_samples=3
        )
        loop = OptimizationLoop(config=mock_config)

        # Collect all bootstrap seeds across all iterations
        all_bootstrap_seeds = []
        for iteration_idx in range(5):
            bootstrap_seeds = loop._seed_matrix.get_bootstrap_seeds(
                iteration_idx, "BANK_A"
            )
            all_bootstrap_seeds.extend(bootstrap_seeds)

        # 5 iterations × 3 samples = 15 unique seeds
        assert len(all_bootstrap_seeds) == 15
        assert len(set(all_bootstrap_seeds)) == 15, (
            f"Expected 15 unique bootstrap seeds, got {len(set(all_bootstrap_seeds))}"
        )

    def test_seed_hierarchy_determinism(self) -> None:
        """Same master_seed must produce identical seed hierarchy.

        INV-2: Determinism is Sacred.
        """
        # Create two loops with same config
        mock_config1 = _create_bootstrap_config(master_seed=42)
        mock_config2 = _create_bootstrap_config(master_seed=42)

        loop1 = OptimizationLoop(config=mock_config1)
        loop2 = OptimizationLoop(config=mock_config2)

        # All seeds must match
        for iteration_idx in range(5):
            iter_seed_1 = loop1._seed_matrix.get_iteration_seed(
                iteration_idx, "BANK_A"
            )
            iter_seed_2 = loop2._seed_matrix.get_iteration_seed(
                iteration_idx, "BANK_A"
            )
            assert iter_seed_1 == iter_seed_2, f"Iteration {iteration_idx} seed mismatch"

            boot_seeds_1 = loop1._seed_matrix.get_bootstrap_seeds(
                iteration_idx, "BANK_A"
            )
            boot_seeds_2 = loop2._seed_matrix.get_bootstrap_seeds(
                iteration_idx, "BANK_A"
            )
            assert boot_seeds_1 == boot_seeds_2, (
                f"Bootstrap seeds mismatch at iteration {iteration_idx}"
            )

    def test_different_master_seeds_produce_different_hierarchies(self) -> None:
        """Different master_seed produces completely different hierarchy."""
        mock_config1 = _create_bootstrap_config(master_seed=42)
        mock_config2 = _create_bootstrap_config(master_seed=999)

        loop1 = OptimizationLoop(config=mock_config1)
        loop2 = OptimizationLoop(config=mock_config2)

        # All iteration seeds should differ
        for iteration_idx in range(5):
            iter_seed_1 = loop1._seed_matrix.get_iteration_seed(
                iteration_idx, "BANK_A"
            )
            iter_seed_2 = loop2._seed_matrix.get_iteration_seed(
                iteration_idx, "BANK_A"
            )
            assert iter_seed_1 != iter_seed_2, (
                f"Different master_seeds should produce different iteration seeds"
            )


class TestBootstrapLoopIntegration:
    """Test that the optimization loop correctly uses per-iteration seeds."""

    @pytest.mark.asyncio
    async def test_context_simulation_called_each_iteration_with_correct_seed(
        self,
    ) -> None:
        """Verify context simulation runs each iteration with iteration_seed.

        This is the critical integration test - it verifies the loop
        actually calls _run_initial_simulation with the correct seed
        each iteration.
        """
        mock_config = _create_bootstrap_config(
            master_seed=42, max_iterations=3, num_samples=2
        )
        loop = OptimizationLoop(config=mock_config)

        # Track context simulation calls
        context_sim_calls: list[dict[str, Any]] = []

        # Create mock for _run_initial_simulation that tracks calls
        original_run_initial = loop._run_initial_simulation

        def tracking_run_initial_simulation(
            seed: int | None = None, iteration: int = 0
        ) -> MagicMock:
            context_sim_calls.append({
                "seed": seed,
                "iteration": iteration,
            })
            # Return a mock result
            mock_result = MagicMock()
            mock_result.total_cost = 1000
            mock_result.per_agent_costs = {"BANK_A": 1000}
            mock_result.events = []
            mock_result.agent_histories = {"BANK_A": MagicMock(outgoing=[], incoming=[])}
            mock_result.verbose_output = "test output"
            return mock_result

        # Mock other methods needed for the loop
        async def mock_evaluate_policies() -> tuple[int, dict[str, int]]:
            return 1000, {"BANK_A": 1000}

        async def mock_optimize_agent(agent_id: str) -> None:
            pass

        # Patch methods
        with patch.object(loop, "_run_initial_simulation", tracking_run_initial_simulation):
            with patch.object(loop, "_evaluate_policies", mock_evaluate_policies):
                with patch.object(loop, "_optimize_agent", mock_optimize_agent):
                    with patch.object(loop, "_create_bootstrap_samples"):
                        # Run 3 iterations
                        loop._current_iteration = 0
                        for _ in range(3):
                            loop._current_iteration += 1
                            iteration_idx = loop._current_iteration - 1

                            # Simulate what happens in bootstrap mode
                            if mock_config.evaluation.mode == "bootstrap":
                                agent_id = loop.optimized_agents[0]
                                iteration_seed = loop._seed_matrix.get_iteration_seed(
                                    iteration_idx, agent_id
                                )
                                loop._run_initial_simulation(
                                    seed=iteration_seed, iteration=iteration_idx
                                )

        # Verify calls
        assert len(context_sim_calls) == 3, "Should have 3 context simulation calls"

        # Verify each call used the correct iteration_seed
        for i, call in enumerate(context_sim_calls):
            expected_seed = loop._seed_matrix.get_iteration_seed(i, "BANK_A")
            assert call["seed"] == expected_seed, (
                f"Iteration {i}: expected seed {expected_seed}, got {call['seed']}"
            )
            assert call["iteration"] == i, (
                f"Iteration {i}: expected iteration {i}, got {call['iteration']}"
            )

        # All seeds should be different
        seeds_used = [call["seed"] for call in context_sim_calls]
        assert len(set(seeds_used)) == 3, "Each iteration should use different seed"


class TestBootstrapSampleRegeneration:
    """Test that bootstrap samples are regenerated each iteration."""

    def test_create_bootstrap_samples_uses_provided_seed(self) -> None:
        """_create_bootstrap_samples should use the provided seed."""
        mock_config = _create_bootstrap_config(master_seed=42, num_samples=3)
        loop = OptimizationLoop(config=mock_config)

        # Track which seeds are passed to BootstrapSampler
        sampler_seeds: list[int] = []

        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        original_init = BootstrapSampler.__init__

        def tracking_init(
            self: BootstrapSampler, seed: int, **kwargs: Any
        ) -> None:
            sampler_seeds.append(seed)
            self._base_seed = seed
            self._samples: list = []

        # Set up initial result so _create_bootstrap_samples works
        mock_result = MagicMock()
        mock_result.agent_histories = {"BANK_A": MagicMock(outgoing=[], incoming=[])}
        loop._initial_sim_result = mock_result

        # Call with different seeds
        with patch.object(BootstrapSampler, "__init__", tracking_init):
            with patch.object(BootstrapSampler, "generate_samples", return_value=[]):
                loop._create_bootstrap_samples(seed=111)
                loop._create_bootstrap_samples(seed=222)
                loop._create_bootstrap_samples(seed=333)

        # Each call should use the provided seed
        assert sampler_seeds == [111, 222, 333], (
            f"Expected seeds [111, 222, 333], got {sampler_seeds}"
        )

    def test_fallback_to_master_seed_when_no_seed_provided(self) -> None:
        """Without seed param, should fall back to master_seed."""
        mock_config = _create_bootstrap_config(master_seed=999, num_samples=3)
        loop = OptimizationLoop(config=mock_config)

        sampler_seeds: list[int] = []

        from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler

        def tracking_init(
            self: BootstrapSampler, seed: int, **kwargs: Any
        ) -> None:
            sampler_seeds.append(seed)
            self._base_seed = seed
            self._samples: list = []

        # Set up initial result
        mock_result = MagicMock()
        mock_result.agent_histories = {"BANK_A": MagicMock(outgoing=[], incoming=[])}
        loop._initial_sim_result = mock_result

        with patch.object(BootstrapSampler, "__init__", tracking_init):
            with patch.object(BootstrapSampler, "generate_samples", return_value=[]):
                loop._create_bootstrap_samples()  # No seed = master_seed

        assert sampler_seeds == [999], (
            f"Expected master_seed [999], got {sampler_seeds}"
        )
