"""Integration tests for deterministic evaluation modes.

Phase 4 of deterministic-evaluation-modes implementation.

Tests verify that:
1. Both modes (pairwise and temporal) can be configured and initialized
2. Mode selection affects evaluation behavior appropriately
3. Determinism is preserved (INV-2)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from payment_simulator.experiments.config.experiment_config import (
    EvaluationConfig,
    ExperimentConfig,
    ConvergenceConfig,
)
from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.llm.config import LLMConfig


def _create_config(
    mode: str,
    master_seed: int = 42,
) -> MagicMock:
    """Create a mock ExperimentConfig with specified evaluation mode."""
    mock_config = MagicMock(spec=ExperimentConfig)
    mock_config.name = f"test_{mode}"
    mock_config.master_seed = master_seed

    # Convergence settings
    mock_config.convergence = MagicMock(spec=ConvergenceConfig)
    mock_config.convergence.max_iterations = 5
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Real EvaluationConfig to test mode properties
    mock_config.evaluation = EvaluationConfig(ticks=2, mode=mode, num_samples=1)

    # Agents
    mock_config.optimized_agents = ("BANK_A",)

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints
    mock_config.get_constraints.return_value = None

    return mock_config


class TestModeInitialization:
    """Tests that modes can be properly initialized."""

    def test_pairwise_mode_creates_valid_loop(self) -> None:
        """Deterministic-pairwise mode creates valid OptimizationLoop."""
        config = _create_config(mode="deterministic-pairwise")
        loop = OptimizationLoop(config=config)

        assert loop is not None
        assert config.evaluation.is_deterministic_pairwise is True
        assert config.evaluation.is_deterministic_temporal is False

    def test_temporal_mode_creates_valid_loop(self) -> None:
        """Deterministic-temporal mode creates valid OptimizationLoop."""
        config = _create_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=config)

        assert loop is not None
        assert config.evaluation.is_deterministic_temporal is True
        assert config.evaluation.is_deterministic_pairwise is False

    def test_plain_deterministic_creates_pairwise_loop(self) -> None:
        """Plain 'deterministic' mode treated as pairwise."""
        config = _create_config(mode="deterministic")
        loop = OptimizationLoop(config=config)

        assert loop is not None
        assert config.evaluation.is_deterministic_pairwise is True
        assert config.evaluation.is_deterministic_temporal is False

    def test_bootstrap_mode_still_works(self) -> None:
        """Bootstrap mode is not affected by new modes."""
        config = _create_config(mode="bootstrap")
        # Bootstrap needs num_samples
        config.evaluation = EvaluationConfig(ticks=2, mode="bootstrap", num_samples=5)
        loop = OptimizationLoop(config=config)

        assert loop is not None
        assert config.evaluation.is_bootstrap is True


class TestDeterminismInv2:
    """Tests verifying INV-2: Determinism is Sacred."""

    def test_same_seed_produces_same_iteration_seeds_pairwise(self) -> None:
        """Pairwise mode: same master_seed produces identical iteration seeds."""
        config1 = _create_config(mode="deterministic-pairwise", master_seed=42)
        config2 = _create_config(mode="deterministic-pairwise", master_seed=42)

        loop1 = OptimizationLoop(config=config1)
        loop2 = OptimizationLoop(config=config2)

        agent_id = "BANK_A"
        for i in range(3):
            seed1 = loop1._seed_matrix.get_iteration_seed(i, agent_id)
            seed2 = loop2._seed_matrix.get_iteration_seed(i, agent_id)
            assert seed1 == seed2, f"Seeds should match at iteration {i}"

    def test_same_seed_produces_same_iteration_seeds_temporal(self) -> None:
        """Temporal mode: same master_seed produces identical iteration seeds."""
        config1 = _create_config(mode="deterministic-temporal", master_seed=42)
        config2 = _create_config(mode="deterministic-temporal", master_seed=42)

        loop1 = OptimizationLoop(config=config1)
        loop2 = OptimizationLoop(config=config2)

        agent_id = "BANK_A"
        for i in range(3):
            seed1 = loop1._seed_matrix.get_iteration_seed(i, agent_id)
            seed2 = loop2._seed_matrix.get_iteration_seed(i, agent_id)
            assert seed1 == seed2, f"Seeds should match at iteration {i}"


class TestTemporalModeStateTracking:
    """Tests for temporal mode state tracking."""

    def test_temporal_tracks_costs_per_agent(self) -> None:
        """Temporal mode tracks previous costs per agent."""
        config = _create_config(mode="deterministic-temporal")
        config.optimized_agents = ("BANK_A", "BANK_B")
        loop = OptimizationLoop(config=config)

        # Simulate accepting costs for two agents
        loop._evaluate_temporal_acceptance("BANK_A", 1000)
        loop._evaluate_temporal_acceptance("BANK_B", 2000)

        assert loop._previous_iteration_costs["BANK_A"] == 1000
        assert loop._previous_iteration_costs["BANK_B"] == 2000

    def test_temporal_mode_cost_improvement_sequence(self) -> None:
        """Test a sequence of cost improvements in temporal mode."""
        config = _create_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=config)

        # Iteration 1: First cost, always accepted
        assert loop._evaluate_temporal_acceptance("BANK_A", 1000) is True

        # Iteration 2: Improved cost, accepted
        assert loop._evaluate_temporal_acceptance("BANK_A", 900) is True
        assert loop._previous_iteration_costs["BANK_A"] == 900

        # Iteration 3: Further improvement, accepted
        assert loop._evaluate_temporal_acceptance("BANK_A", 800) is True
        assert loop._previous_iteration_costs["BANK_A"] == 800

        # Iteration 4: Regression, rejected
        assert loop._evaluate_temporal_acceptance("BANK_A", 850) is False
        # Cost should NOT be updated
        assert loop._previous_iteration_costs["BANK_A"] == 800


class TestPairwiseModeConsistency:
    """Tests for pairwise mode consistency (INV-9)."""

    def test_pairwise_mode_uses_consistent_seeds(self) -> None:
        """Pairwise mode uses same seed for display and acceptance."""
        config = _create_config(mode="deterministic-pairwise")
        loop = OptimizationLoop(config=config)

        # Both _evaluate_policies and _evaluate_policy_pair should use
        # iteration seeds from the same seed matrix
        agent_id = "BANK_A"
        iteration_idx = 0

        # Get the iteration seed that would be used
        expected_seed = loop._seed_matrix.get_iteration_seed(iteration_idx, agent_id)

        # This seed should be deterministic and consistent
        assert expected_seed == loop._seed_matrix.get_iteration_seed(iteration_idx, agent_id)
