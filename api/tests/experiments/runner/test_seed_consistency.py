"""Tests for seed consistency in deterministic evaluation mode.

Verifies INV-9: Policy Evaluation Identity - the seed used for cost display
must equal the seed used for acceptance decision.

Phase 1 of deterministic-evaluation-modes implementation.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.llm.config import LLMConfig


def _create_mock_config(
    mode: str = "deterministic",
    master_seed: int = 42,
    num_samples: int = 1,
    max_iterations: int = 10,
) -> MagicMock:
    """Create a mock ExperimentConfig for testing."""
    mock_config = MagicMock()
    mock_config.name = "test_seed_consistency"
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

    # Agents
    mock_config.optimized_agents = ("BANK_A",)

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints
    mock_config.get_constraints.return_value = None

    return mock_config


class TestSeedConsistencyInDeterministicMode:
    """Tests for seed consistency between _evaluate_policies and _evaluate_policy_pair."""

    @pytest.mark.asyncio
    async def test_evaluate_policies_should_use_iteration_seed_not_master_seed(self) -> None:
        """_evaluate_policies should use iteration seed, not master seed.

        Previously, _evaluate_policies used master_seed directly (line 1398),
        which caused inconsistency with _evaluate_policy_pair which used
        get_iteration_seed (line 1600).

        INV-9: Policy Evaluation Identity requires these to match.
        """
        mock_config = _create_mock_config(mode="deterministic", master_seed=42)
        loop = OptimizationLoop(config=mock_config)

        # Set iteration to non-zero to distinguish from potential edge cases
        loop._current_iteration = 2

        # Get the expected iteration seed
        iteration_idx = loop._current_iteration - 1  # 0-indexed
        agent_id = loop.optimized_agents[0]
        expected_seed = loop._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

        # Track which seed is actually used
        seeds_used: list[int] = []

        def mock_run_simulation_with_events(
            seed: int, sample_idx: int, is_primary: bool = False
        ) -> MagicMock:
            seeds_used.append(seed)
            # Return a mock enriched result
            mock_result = MagicMock()
            mock_result.total_cost = 1000
            mock_result.settlement_rate = 0.95
            mock_result.avg_delay = 1.5
            mock_result.cost_breakdown = MagicMock(
                delay_cost=500,
                overdraft_cost=200,
                deadline_penalty=0,
                eod_penalty=0,
            )
            mock_result.events = []
            return mock_result

        # Patch the simulation method
        with patch.object(
            loop, "_run_simulation_with_events", mock_run_simulation_with_events
        ):
            with patch.object(loop, "_build_agent_contexts", return_value={}):
                await loop._evaluate_policies()

        # CRITICAL ASSERTION: seed used should be iteration seed, NOT master_seed
        assert len(seeds_used) == 1, "Should have called simulation once"
        assert seeds_used[0] == expected_seed, (
            f"Should use iteration seed {expected_seed}, "
            f"not master_seed {mock_config.master_seed}. Got: {seeds_used[0]}"
        )
        assert seeds_used[0] != mock_config.master_seed, (
            "Should NOT use master_seed directly in deterministic mode"
        )

    def test_different_iterations_use_different_seeds(self) -> None:
        """Different iterations should use different seeds for diversity.

        This is important for exploration - each iteration evaluates
        with a different seed to test policy robustness.
        """
        mock_config = _create_mock_config(mode="deterministic", master_seed=42)
        loop = OptimizationLoop(config=mock_config)
        agent_id = loop.optimized_agents[0]

        # Get seeds for different iterations
        seed_iter_0 = loop._seed_matrix.get_iteration_seed(0, agent_id)
        seed_iter_1 = loop._seed_matrix.get_iteration_seed(1, agent_id)
        seed_iter_2 = loop._seed_matrix.get_iteration_seed(2, agent_id)

        # All should be different
        assert seed_iter_0 != seed_iter_1, "Iteration 0 and 1 should have different seeds"
        assert seed_iter_1 != seed_iter_2, "Iteration 1 and 2 should have different seeds"
        assert seed_iter_0 != seed_iter_2, "Iteration 0 and 2 should have different seeds"

    def test_same_iteration_same_agent_always_same_seed(self) -> None:
        """Same iteration + same agent should always produce same seed.

        INV-2: Determinism is Sacred - reproducibility requires consistent seeds.
        """
        mock_config = _create_mock_config(mode="deterministic", master_seed=42)
        loop = OptimizationLoop(config=mock_config)
        agent_id = loop.optimized_agents[0]

        # Get same seed multiple times
        seed_1 = loop._seed_matrix.get_iteration_seed(0, agent_id)
        seed_2 = loop._seed_matrix.get_iteration_seed(0, agent_id)
        seed_3 = loop._seed_matrix.get_iteration_seed(0, agent_id)

        assert seed_1 == seed_2 == seed_3, "Same iteration/agent should always give same seed"

    def test_seed_matrix_initialized_with_correct_params(self) -> None:
        """SeedMatrix should be initialized with correct parameters from config."""
        mock_config = _create_mock_config(
            mode="deterministic",
            master_seed=12345,
            max_iterations=25,
            num_samples=10,
        )
        mock_config.optimized_agents = ("BANK_A", "BANK_B")

        loop = OptimizationLoop(config=mock_config)

        # Verify seed matrix was created with correct params
        assert loop._seed_matrix.master_seed == 12345
        assert loop._seed_matrix.max_iterations == 25
        assert loop._seed_matrix.num_bootstrap_samples == 10
        assert "BANK_A" in loop._seed_matrix._agents_tuple
        assert "BANK_B" in loop._seed_matrix._agents_tuple


class TestSeedDerivationDeterminism:
    """Test that seed derivation is fully deterministic."""

    def test_same_master_seed_produces_same_iteration_seeds(self) -> None:
        """Two loops with same master_seed should produce identical iteration seeds.

        INV-2: Determinism is Sacred.
        """
        mock_config_1 = _create_mock_config(master_seed=42)
        mock_config_2 = _create_mock_config(master_seed=42)

        loop_1 = OptimizationLoop(config=mock_config_1)
        loop_2 = OptimizationLoop(config=mock_config_2)

        agent_id = "BANK_A"
        for iteration in range(5):
            seed_1 = loop_1._seed_matrix.get_iteration_seed(iteration, agent_id)
            seed_2 = loop_2._seed_matrix.get_iteration_seed(iteration, agent_id)
            assert seed_1 == seed_2, f"Seeds should match for iteration {iteration}"

    def test_different_master_seeds_produce_different_iteration_seeds(self) -> None:
        """Different master seeds should produce different iteration seeds."""
        mock_config_1 = _create_mock_config(master_seed=42)
        mock_config_2 = _create_mock_config(master_seed=999)

        loop_1 = OptimizationLoop(config=mock_config_1)
        loop_2 = OptimizationLoop(config=mock_config_2)

        agent_id = "BANK_A"
        seed_1 = loop_1._seed_matrix.get_iteration_seed(0, agent_id)
        seed_2 = loop_2._seed_matrix.get_iteration_seed(0, agent_id)

        assert seed_1 != seed_2, "Different master seeds should produce different iteration seeds"
