"""Unit tests for PolicyStabilityTracker.

Tests for tracking initial_liquidity_fraction stability across agents
for multi-agent convergence detection.
"""

from __future__ import annotations

import pytest

from payment_simulator.experiments.runner.policy_stability import PolicyStabilityTracker


class TestPolicyStabilityTracker:
    """Tests for PolicyStabilityTracker."""

    def test_record_fraction_single_agent(self) -> None:
        """Recording a fraction stores it correctly."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)

        history = tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.5)

    def test_record_fraction_multiple_agents(self) -> None:
        """Can track multiple agents independently."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=1, fraction=0.7)

        assert tracker.get_history("BANK_A") == [(1, 0.3)]
        assert tracker.get_history("BANK_B") == [(1, 0.7)]

    def test_record_fraction_multiple_iterations(self) -> None:
        """Tracks fractions across multiple iterations."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.4)

        history = tracker.get_history("BANK_A")
        assert len(history) == 3
        assert history == [(1, 0.5), (2, 0.3), (3, 0.4)]

    def test_record_fraction_overwrites_same_iteration(self) -> None:
        """Recording same iteration overwrites previous value."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)

        history = tracker.get_history("BANK_A")
        assert len(history) == 1
        assert history[0] == (1, 0.5)

    def test_agent_stable_for_exact_window(self) -> None:
        """Agent is stable when fraction unchanged for exact window."""
        tracker = PolicyStabilityTracker()
        # 5 iterations with same fraction
        for i in range(1, 6):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_agent_stable_for_more_than_window(self) -> None:
        """Agent is stable when fraction unchanged for more than window."""
        tracker = PolicyStabilityTracker()
        # 7 iterations with same fraction
        for i in range(1, 8):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_agent_stable_for_less_than_window(self) -> None:
        """Agent is NOT stable when history shorter than window."""
        tracker = PolicyStabilityTracker()
        # Only 3 iterations
        for i in range(1, 4):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is False

    def test_agent_stable_for_with_change_in_window(self) -> None:
        """Agent is NOT stable when fraction changed within window."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.6)  # Changed!
        tracker.record_fraction("BANK_A", iteration=4, fraction=0.6)
        tracker.record_fraction("BANK_A", iteration=5, fraction=0.6)

        # Only 3 iterations at 0.6, need 5
        assert tracker.agent_stable_for("BANK_A", window=5) is False

    def test_agent_stable_after_initial_changes(self) -> None:
        """Agent becomes stable after initial exploration."""
        tracker = PolicyStabilityTracker()
        # Initial exploration
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.4)
        # Stabilized
        for i in range(4, 9):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.4)

        # Last 5 iterations (4,5,6,7,8) all at 0.4
        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_all_agents_stable_true(self) -> None:
        """All agents stable returns True when all are stable."""
        tracker = PolicyStabilityTracker()
        for i in range(1, 6):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)
            tracker.record_fraction("BANK_B", iteration=i, fraction=0.3)

        assert tracker.all_agents_stable(["BANK_A", "BANK_B"], window=5) is True

    def test_all_agents_stable_one_unstable(self) -> None:
        """All agents stable returns False when any agent unstable."""
        tracker = PolicyStabilityTracker()
        for i in range(1, 6):
            tracker.record_fraction("BANK_A", iteration=i, fraction=0.5)

        # BANK_B changed at iteration 4
        tracker.record_fraction("BANK_B", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=2, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=3, fraction=0.3)
        tracker.record_fraction("BANK_B", iteration=4, fraction=0.4)  # Changed!
        tracker.record_fraction("BANK_B", iteration=5, fraction=0.4)

        assert tracker.all_agents_stable(["BANK_A", "BANK_B"], window=5) is False

    def test_all_agents_stable_empty_list(self) -> None:
        """Empty agent list is trivially stable."""
        tracker = PolicyStabilityTracker()
        assert tracker.all_agents_stable([], window=5) is True

    def test_floating_point_tolerance(self) -> None:
        """Treats minor floating-point differences as equal."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.50000001)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=4, fraction=0.49999999)
        tracker.record_fraction("BANK_A", iteration=5, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=5) is True

    def test_floating_point_tolerance_large_difference(self) -> None:
        """Large differences are detected as changes."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.51)  # 0.01 diff
        tracker.record_fraction("BANK_A", iteration=4, fraction=0.51)
        tracker.record_fraction("BANK_A", iteration=5, fraction=0.51)

        # 0.51 != 0.5 (difference > tolerance)
        assert tracker.agent_stable_for("BANK_A", window=5) is False

    def test_unknown_agent_not_stable(self) -> None:
        """Unknown agent is not stable (no history)."""
        tracker = PolicyStabilityTracker()

        assert tracker.agent_stable_for("UNKNOWN", window=5) is False

    def test_get_last_fraction(self) -> None:
        """Can retrieve last recorded fraction for an agent."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.3)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.5)

        assert tracker.get_last_fraction("BANK_A") == 0.5

    def test_get_last_fraction_unknown_agent(self) -> None:
        """Returns None for unknown agent."""
        tracker = PolicyStabilityTracker()

        assert tracker.get_last_fraction("UNKNOWN") is None

    def test_reset_clears_all_history(self) -> None:
        """Reset clears all tracking state."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_B", iteration=1, fraction=0.3)

        tracker.reset()

        assert tracker.get_history("BANK_A") == []
        assert tracker.get_history("BANK_B") == []
        assert tracker.get_last_fraction("BANK_A") is None

    def test_window_of_one(self) -> None:
        """Window of 1 requires just one data point."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)

        assert tracker.agent_stable_for("BANK_A", window=1) is True

    def test_out_of_order_iteration_recording(self) -> None:
        """History stays sorted even with out-of-order recording."""
        tracker = PolicyStabilityTracker()
        tracker.record_fraction("BANK_A", iteration=3, fraction=0.4)
        tracker.record_fraction("BANK_A", iteration=1, fraction=0.5)
        tracker.record_fraction("BANK_A", iteration=2, fraction=0.3)

        history = tracker.get_history("BANK_A")
        assert history == [(1, 0.5), (2, 0.3), (3, 0.4)]
