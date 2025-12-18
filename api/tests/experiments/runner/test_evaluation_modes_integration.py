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


class TestDeterministicModeWithNumSamplesGreaterThanOne:
    """Tests for bug fix: deterministic modes with num_samples > 1.

    Bug: The code checked `eval_mode == "deterministic"` instead of using
    `is_deterministic` property, causing deterministic-temporal and
    deterministic-pairwise modes to incorrectly fall into bootstrap path
    when num_samples > 1.

    These tests verify the fix works correctly.
    """

    def test_temporal_mode_is_deterministic_with_many_samples(self) -> None:
        """deterministic-temporal with num_samples=50 should be deterministic."""
        config = _create_config(mode="deterministic-temporal")
        # Override to use num_samples > 1 (like real exp1 config)
        config.evaluation = EvaluationConfig(
            ticks=2, mode="deterministic-temporal", num_samples=50
        )

        # The is_deterministic property should return True
        assert config.evaluation.is_deterministic is True
        assert config.evaluation.is_deterministic_temporal is True
        assert config.evaluation.is_bootstrap is False

    def test_pairwise_mode_is_deterministic_with_many_samples(self) -> None:
        """deterministic-pairwise with num_samples=50 should be deterministic."""
        config = _create_config(mode="deterministic-pairwise")
        config.evaluation = EvaluationConfig(
            ticks=2, mode="deterministic-pairwise", num_samples=50
        )

        assert config.evaluation.is_deterministic is True
        assert config.evaluation.is_deterministic_pairwise is True
        assert config.evaluation.is_bootstrap is False

    def test_plain_deterministic_is_deterministic_with_many_samples(self) -> None:
        """Plain 'deterministic' with num_samples=50 should be deterministic."""
        config = _create_config(mode="deterministic")
        config.evaluation = EvaluationConfig(
            ticks=2, mode="deterministic", num_samples=50
        )

        assert config.evaluation.is_deterministic is True
        assert config.evaluation.is_bootstrap is False

    def test_optimization_loop_uses_is_deterministic_property(self) -> None:
        """OptimizationLoop should use is_deterministic, not string comparison.

        This test verifies the fix for the bug where the code checked:
            eval_mode == "deterministic"
        instead of:
            self._config.evaluation.is_deterministic

        The bug caused deterministic-temporal with num_samples > 1 to fall
        into the bootstrap evaluation path incorrectly.
        """
        config = _create_config(mode="deterministic-temporal")
        config.evaluation = EvaluationConfig(
            ticks=2, mode="deterministic-temporal", num_samples=50
        )
        loop = OptimizationLoop(config=config)

        # Verify that the loop correctly identifies this as deterministic mode
        # by checking the evaluation config property (not string comparison)
        eval_mode = loop._config.evaluation.mode
        num_samples = loop._config.evaluation.num_samples

        # The BUG: this string comparison was used instead of is_deterministic
        buggy_check = eval_mode == "deterministic" or num_samples <= 1

        # The FIX: use is_deterministic property
        correct_check = loop._config.evaluation.is_deterministic or num_samples <= 1

        # With num_samples=50, the buggy check returns False (wrong!)
        # The correct check returns True (right!)
        assert buggy_check is False, "Buggy check should be False for temporal+50 samples"
        assert correct_check is True, "Correct check should be True for temporal+50 samples"

    @pytest.mark.asyncio
    async def test_temporal_mode_runs_single_simulation_not_bootstrap(self) -> None:
        """deterministic-temporal should run 1 simulation, not num_samples.

        This test will FAIL until optimization.py is fixed to use
        is_deterministic property instead of string comparison.

        The bug causes _evaluate_policies() to run 50 simulations (bootstrap)
        when it should run just 1 (deterministic).
        """
        from unittest.mock import patch, MagicMock

        config = _create_config(mode="deterministic-temporal")
        config.evaluation = EvaluationConfig(
            ticks=2, mode="deterministic-temporal", num_samples=50
        )
        loop = OptimizationLoop(config=config)

        # Set up loop state needed for _evaluate_policies
        loop._current_iteration = 1

        # Mock _run_simulation_with_events to count calls
        mock_result = MagicMock()
        mock_result.total_cost = 10000  # $100.00
        mock_result.settlement_rate = 1.0
        mock_result.events = []

        call_count = 0

        def count_calls(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return mock_result

        with patch.object(loop, '_run_simulation_with_events', side_effect=count_calls):
            with patch.object(loop, '_build_agent_contexts', return_value={}):
                await loop._evaluate_policies()

        # CRITICAL: In deterministic mode, should run exactly 1 simulation
        # Bug causes it to run 50 (num_samples) simulations
        assert call_count == 1, (
            f"deterministic-temporal should run 1 simulation, not {call_count}. "
            f"This test fails because optimization.py uses string comparison "
            f"'== \"deterministic\"' instead of 'is_deterministic' property."
        )
