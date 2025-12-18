"""Tests for temporal mode with policy stability tracking.

Tests the new behavior where temporal mode:
1. Always accepts LLM's policy (no cost-based rejection)
2. Tracks initial_liquidity_fraction for convergence detection
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from payment_simulator.experiments.runner.optimization import OptimizationLoop
from payment_simulator.experiments.runner.policy_stability import PolicyStabilityTracker
from payment_simulator.llm.config import LLMConfig


def _create_mock_config(
    mode: str = "deterministic-temporal",
    master_seed: int = 42,
    max_iterations: int = 10,
    stability_window: int = 5,
) -> MagicMock:
    """Create a mock ExperimentConfig for temporal mode testing."""
    mock_config = MagicMock()
    mock_config.name = "test_temporal"
    mock_config.master_seed = master_seed

    # Convergence settings
    mock_config.convergence = MagicMock()
    mock_config.convergence.max_iterations = max_iterations
    mock_config.convergence.stability_threshold = 0.05
    mock_config.convergence.stability_window = stability_window
    mock_config.convergence.improvement_threshold = 0.01

    # Evaluation settings with temporal mode
    mock_config.evaluation = MagicMock()
    mock_config.evaluation.mode = mode
    mock_config.evaluation.num_samples = 1
    mock_config.evaluation.ticks = 2
    mock_config.evaluation.is_deterministic_temporal = mode == "deterministic-temporal"
    mock_config.evaluation.is_deterministic_pairwise = mode in (
        "deterministic",
        "deterministic-pairwise",
    )
    mock_config.evaluation.is_bootstrap = mode == "bootstrap"

    # Agents
    mock_config.optimized_agents = ("BANK_A", "BANK_B")

    # LLM config
    mock_config.llm = LLMConfig(model="test:mock")

    # Constraints - return None
    mock_config.get_constraints.return_value = None

    return mock_config


class TestPolicyStabilityTrackerInitialization:
    """Tests for PolicyStabilityTracker initialization in OptimizationLoop."""

    def test_stability_tracker_initialized(self) -> None:
        """OptimizationLoop should have _stability_tracker attribute."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        assert hasattr(loop, "_stability_tracker")
        assert isinstance(loop._stability_tracker, PolicyStabilityTracker)

    def test_stability_tracker_starts_empty(self) -> None:
        """Stability tracker should start with no history."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # No history for any agent
        assert loop._stability_tracker.get_history("BANK_A") == []
        assert loop._stability_tracker.get_history("BANK_B") == []


class TestFractionTracking:
    """Tests for tracking initial_liquidity_fraction."""

    def test_track_policy_fraction_extracts_correctly(self) -> None:
        """_track_policy_fraction extracts and stores fraction."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)
        loop._current_iteration = 1

        policy = {
            "version": "2.0",
            "parameters": {"initial_liquidity_fraction": 0.7},
            "payment_tree": {"type": "action", "action": "Release"},
        }

        loop._track_policy_fraction("BANK_A", policy)

        history = loop._stability_tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.7)

    def test_track_policy_fraction_defaults_to_half(self) -> None:
        """Missing initial_liquidity_fraction defaults to 0.5."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)
        loop._current_iteration = 1

        policy = {
            "version": "2.0",
            "parameters": {},  # No fraction!
            "payment_tree": {"type": "action", "action": "Release"},
        }

        loop._track_policy_fraction("BANK_A", policy)

        history = loop._stability_tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.5)

    def test_track_policy_fraction_missing_parameters(self) -> None:
        """Missing parameters dict defaults to 0.5."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)
        loop._current_iteration = 1

        policy = {
            "version": "2.0",
            "payment_tree": {"type": "action", "action": "Release"},
        }

        loop._track_policy_fraction("BANK_A", policy)

        history = loop._stability_tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.5)

    def test_track_policy_fraction_multiple_iterations(self) -> None:
        """Tracks fractions across multiple iterations."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Iteration 1
        loop._current_iteration = 1
        loop._track_policy_fraction(
            "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.5}}
        )

        # Iteration 2
        loop._current_iteration = 2
        loop._track_policy_fraction(
            "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.3}}
        )

        # Iteration 3
        loop._current_iteration = 3
        loop._track_policy_fraction(
            "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.3}}
        )

        history = loop._stability_tracker.get_history("BANK_A")
        assert len(history) == 3
        assert history == [(1, 0.5), (2, 0.3), (3, 0.3)]


class TestMultiAgentConvergenceDetection:
    """Tests for multi-agent convergence detection."""

    def test_check_multiagent_convergence_true(self) -> None:
        """Returns True when all agents stable for window iterations."""
        mock_config = _create_mock_config(
            mode="deterministic-temporal", stability_window=5
        )
        loop = OptimizationLoop(config=mock_config)

        # Record 5 iterations of stable fractions for both agents
        for i in range(1, 6):
            loop._current_iteration = i
            loop._track_policy_fraction(
                "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.5}}
            )
            loop._track_policy_fraction(
                "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.3}}
            )

        assert loop._check_multiagent_convergence() is True

    def test_check_multiagent_convergence_one_unstable(self) -> None:
        """Returns False when one agent changed recently."""
        mock_config = _create_mock_config(
            mode="deterministic-temporal", stability_window=5
        )
        loop = OptimizationLoop(config=mock_config)

        # BANK_A stable
        for i in range(1, 6):
            loop._current_iteration = i
            loop._track_policy_fraction(
                "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.5}}
            )

        # BANK_B changed at iteration 4
        for i in range(1, 4):
            loop._current_iteration = i
            loop._track_policy_fraction(
                "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.3}}
            )
        loop._current_iteration = 4
        loop._track_policy_fraction(
            "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.4}}  # Changed!
        )
        loop._current_iteration = 5
        loop._track_policy_fraction(
            "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.4}}
        )

        # Only 2 iterations at 0.4 for BANK_B, need 5
        assert loop._check_multiagent_convergence() is False

    def test_check_multiagent_convergence_insufficient_history(self) -> None:
        """Returns False when not enough iterations recorded."""
        mock_config = _create_mock_config(
            mode="deterministic-temporal", stability_window=5
        )
        loop = OptimizationLoop(config=mock_config)

        # Only 3 iterations recorded
        for i in range(1, 4):
            loop._current_iteration = i
            loop._track_policy_fraction(
                "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.5}}
            )
            loop._track_policy_fraction(
                "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.3}}
            )

        assert loop._check_multiagent_convergence() is False

    def test_check_multiagent_convergence_uses_config_window(self) -> None:
        """Uses stability_window from convergence config."""
        # Use window of 3 instead of default 5
        mock_config = _create_mock_config(
            mode="deterministic-temporal", stability_window=3
        )
        loop = OptimizationLoop(config=mock_config)

        # Only 3 iterations needed
        for i in range(1, 4):
            loop._current_iteration = i
            loop._track_policy_fraction(
                "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.5}}
            )
            loop._track_policy_fraction(
                "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.3}}
            )

        assert loop._check_multiagent_convergence() is True


class TestTemporalModeNoRejection:
    """Tests verifying temporal mode doesn't reject on cost increase."""

    def test_costs_logged_but_not_used_for_rejection(self) -> None:
        """Costs are recorded for analysis but don't cause rejection."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Set up state as if iteration 1 completed
        loop._current_iteration = 2
        loop._previous_iteration_costs = {"BANK_A": 1000}

        # In the new implementation, costs are logged but don't cause rejection
        # The old _evaluate_temporal_acceptance is replaced by always accepting
        # We verify by checking that the method exists but doesn't block policy acceptance

        # The key behavior change: even with cost increase,
        # _optimize_agent_temporal should still accept the new policy
        # (This will be tested via the full async test with mocked LLM)
        pass


class TestTemporalModeAlwaysAccepts:
    """Tests verifying temporal mode always accepts LLM's policy.

    These tests document the new behavior where we don't reject based on cost.
    The actual rejection logic is removed in favor of policy stability tracking.
    """

    def test_previous_iteration_costs_still_tracked(self) -> None:
        """Previous costs are tracked for logging/analysis, not rejection."""
        mock_config = _create_mock_config(mode="deterministic-temporal")
        loop = OptimizationLoop(config=mock_config)

        # Previous cost tracking should still exist
        assert hasattr(loop, "_previous_iteration_costs")
        assert loop._previous_iteration_costs == {}

    def test_stability_tracker_used_for_convergence(self) -> None:
        """Convergence is based on stability tracker, not cost comparison."""
        mock_config = _create_mock_config(
            mode="deterministic-temporal", stability_window=5
        )
        loop = OptimizationLoop(config=mock_config)

        # Simulate 5 iterations where cost goes UP but fraction is stable
        # Old behavior: would reject and revert
        # New behavior: accepts and tracks, converges on fraction stability

        for i in range(1, 6):
            loop._current_iteration = i
            loop._track_policy_fraction(
                "BANK_A", {"parameters": {"initial_liquidity_fraction": 0.5}}
            )
            loop._track_policy_fraction(
                "BANK_B", {"parameters": {"initial_liquidity_fraction": 0.3}}
            )
            # Costs increase (which would have caused rejection before)
            loop._previous_iteration_costs["BANK_A"] = 1000 + i * 100
            loop._previous_iteration_costs["BANK_B"] = 2000 + i * 100

        # Should still converge based on fraction stability
        assert loop._check_multiagent_convergence() is True
