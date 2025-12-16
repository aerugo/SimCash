"""Tests for deterministic-temporal evaluation mode.

Phase 3 of deterministic-evaluation-modes implementation.

Temporal mode compares cost across iterations rather than
old vs new policy within the same iteration.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.llm.config import LLMConfig


def _create_mock_config(
    mode: str = "deterministic-temporal",
    master_seed: int = 42,
    max_iterations: int = 10,
) -> MagicMock:
    """Create a mock ExperimentConfig for temporal mode testing."""
    mock_config = MagicMock()
    mock_config.name = "test_temporal"
    mock_config.master_seed = master_seed

    # Convergence settings
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = 3
    mock_config.convergence.improvement_threshold = 0.01

    # Evaluation settings with temporal mode
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = mode
    mock_config.evaluation.num_samples = 1
    mock_config.evaluation.ticks = 2
    mock_config.evaluation.is_deterministic_temporal = mode == "deterministic-temporal"
    mock_config.evaluation.is_deterministic_pairwise = mode in ("deterministic", "deterministic-pairwise")
    mock_config.evaluation.is_bootstrap = mode == "bootstrap"

    # Agents
    mock_config.optimized_agents = ("BANK_A",)

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints
    mock_config.get_constraints.return_value = None

    return mock_config


class TestTemporalAcceptanceLogic:
    """Tests for temporal acceptance decision logic."""

    def test_first_iteration_always_accepts(self) -> None:
        """First iteration has no previous cost, should always accept."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # First iteration - no previous cost stored
        loop._current_iteration = 1
        # Initialize empty tracking (simulating first iteration state)
        loop._previous_iteration_costs = {}

        # Should accept regardless of cost (no baseline)
        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1000,
        )

        assert accepted is True
        # Should store cost for next iteration
        assert loop._previous_iteration_costs.get("BANK_A") == 1000

    def test_cost_decrease_accepts_policy(self) -> None:
        """If current cost < previous cost, accept the policy."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=800,  # Less than 1000
        )

        assert accepted is True
        # Should update stored cost
        assert loop._previous_iteration_costs.get("BANK_A") == 800

    def test_cost_increase_rejects_policy(self) -> None:
        """If current cost > previous cost, reject (don't accept)."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1200,  # Greater than 1000
        )

        assert accepted is False
        # Should NOT update stored cost (keep baseline for next attempt)
        assert loop._previous_iteration_costs.get("BANK_A") == 1000

    def test_cost_equal_accepts_policy(self) -> None:
        """If current cost == previous cost, accept (allow exploration)."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        # Equal cost - accept to allow exploration
        accepted = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=1000,
        )

        assert accepted is True
        # Should still store (same value)
        assert loop._previous_iteration_costs.get("BANK_A") == 1000

    def test_multi_agent_independent_tracking(self) -> None:
        """Each agent's cost should be tracked independently."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        mock_config.optimized_agents = ("BANK_A", "BANK_B")
        loop = OptimizationLoop(config=mock_config)

        loop._current_iteration = 2
        loop._previous_iteration_costs = {
            "BANK_A": 1000,
            "BANK_B": 2000,
        }

        # BANK_A improves
        accepted_a = loop._evaluate_temporal_acceptance(
            agent_id="BANK_A",
            current_cost=800,
        )
        # BANK_B gets worse
        accepted_b = loop._evaluate_temporal_acceptance(
            agent_id="BANK_B",
            current_cost=2500,
        )

        assert accepted_a is True
        assert accepted_b is False
        assert loop._previous_iteration_costs["BANK_A"] == 800
        assert loop._previous_iteration_costs["BANK_B"] == 2000  # Unchanged


class TestTemporalModeInitialization:
    """Tests for temporal mode initialization."""

    def test_previous_iteration_costs_initialized_empty(self) -> None:
        """_previous_iteration_costs should be initialized as empty dict."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "_previous_iteration_costs")
        assert loop._previous_iteration_costs == {}

    def test_previous_policies_initialized_empty(self) -> None:
        """_previous_policies should be initialized for revert capability."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "_previous_policies")
        assert loop._previous_policies == {}


class TestTemporalModeSemantics:
    """Tests documenting temporal mode semantics."""

    def test_temporal_mode_flow_documentation(self) -> None:
        """Document the expected flow for temporal mode.

        Temporal Flow:
        Iteration 1:
          1. Run simulation with current_policy → cost_1
          2. First iteration → always accept
          3. Store cost_1 in _previous_iteration_costs
          4. LLM generates new_policy

        Iteration 2:
          1. Apply new_policy from iteration 1
          2. Run simulation → cost_2
          3. Compare: cost_2 vs cost_1
             - If cost_2 <= cost_1: Accept, store cost_2
             - If cost_2 > cost_1: Reject, revert policy, keep cost_1
        """
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Simulate iteration 1
        loop._previous_iteration_costs = {}
        loop._current_iteration = 1
        cost_1 = 1000

        accepted_1 = loop._evaluate_temporal_acceptance("BANK_A", cost_1)
        assert accepted_1 is True
        assert loop._previous_iteration_costs["BANK_A"] == cost_1

        # Simulate iteration 2 with improvement
        loop._current_iteration = 2
        cost_2 = 800  # Improved

        accepted_2 = loop._evaluate_temporal_acceptance("BANK_A", cost_2)
        assert accepted_2 is True
        assert loop._previous_iteration_costs["BANK_A"] == cost_2

        # Simulate iteration 3 with regression
        loop._current_iteration = 3
        cost_3 = 1200  # Got worse

        accepted_3 = loop._evaluate_temporal_acceptance("BANK_A", cost_3)
        assert accepted_3 is False
        # Should keep cost_2 as baseline, not update to cost_3
        assert loop._previous_iteration_costs["BANK_A"] == cost_2
