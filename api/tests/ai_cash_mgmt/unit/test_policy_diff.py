"""Tests for policy_diff module.

Tests for policy diff computation and parameter trajectory extraction.
"""

from __future__ import annotations

import pytest


class TestComputePolicyDiff:
    """Tests for compute_policy_diff function."""

    def test_detects_added_parameter(self) -> None:
        """New parameters are detected."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"parameters": {}}
        new = {"parameters": {"threshold": 5.0}}

        diff = compute_policy_diff(old, new)

        assert any("Added" in d and "threshold" in d for d in diff)

    def test_detects_removed_parameter(self) -> None:
        """Removed parameters are detected."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"parameters": {"threshold": 5.0}}
        new = {"parameters": {}}

        diff = compute_policy_diff(old, new)

        assert any("Removed" in d and "threshold" in d for d in diff)

    def test_detects_changed_parameter_with_decrease(self) -> None:
        """Changed parameters show old → new with direction (↓)."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"parameters": {"threshold": 5.0}}
        new = {"parameters": {"threshold": 3.0}}

        diff = compute_policy_diff(old, new)

        assert any(
            "threshold" in d and "5.0" in d and "3.0" in d and "↓" in d
            for d in diff
        )

    def test_detects_changed_parameter_with_increase(self) -> None:
        """Changed parameters show old → new with direction (↑)."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"parameters": {"threshold": 3.0}}
        new = {"parameters": {"threshold": 5.0}}

        diff = compute_policy_diff(old, new)

        assert any(
            "threshold" in d and "3.0" in d and "5.0" in d and "↑" in d
            for d in diff
        )

    def test_detects_multiple_parameter_changes(self) -> None:
        """Multiple parameter changes are all detected."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"parameters": {"threshold": 5.0, "buffer": 1.0}}
        new = {"parameters": {"threshold": 4.0, "buffer": 1.5}}

        diff = compute_policy_diff(old, new)

        assert len(diff) >= 2
        assert any("threshold" in d for d in diff)
        assert any("buffer" in d for d in diff)

    def test_detects_tree_change(self) -> None:
        """Tree structure changes are detected."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"payment_tree": {"root": {"action": "queue"}}}
        new = {"payment_tree": {"root": {"action": "submit"}}}

        diff = compute_policy_diff(old, new)

        assert any("payment_tree" in d for d in diff)

    def test_detects_collateral_tree_change(self) -> None:
        """Collateral tree changes are detected."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {"strategic_collateral_tree": {"root": {"action": "post"}}}
        new = {"strategic_collateral_tree": {"root": {"action": "withdraw"}}}

        diff = compute_policy_diff(old, new)

        assert any("strategic_collateral_tree" in d for d in diff)

    def test_no_changes_returns_message(self) -> None:
        """Returns 'No changes' when policies identical."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        policy = {"parameters": {"threshold": 5.0}}

        diff = compute_policy_diff(policy, policy)

        assert any("No changes" in d for d in diff)

    def test_empty_policies_no_changes(self) -> None:
        """Empty policies report no changes."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        diff = compute_policy_diff({}, {})

        assert any("No changes" in d for d in diff)

    def test_missing_parameters_key(self) -> None:
        """Handles policies without 'parameters' key."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_policy_diff,
        )

        old = {}
        new = {"parameters": {"threshold": 5.0}}

        diff = compute_policy_diff(old, new)

        assert any("Added" in d and "threshold" in d for d in diff)


class TestComputeParameterTrajectory:
    """Tests for compute_parameter_trajectory function."""

    def test_extracts_values_across_iterations(self) -> None:
        """Parameter trajectory is extracted across iterations."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_trajectory,
        )

        history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={},
                policy={"parameters": {"threshold": 5.0}},
            ),
            SingleAgentIterationRecord(
                iteration=2,
                metrics={},
                policy={"parameters": {"threshold": 4.0}},
            ),
        ]

        trajectory = compute_parameter_trajectory(history, "threshold")

        assert trajectory == [(1, 5.0), (2, 4.0)]

    def test_missing_parameter_skips_iteration(self) -> None:
        """Iterations without the parameter are skipped."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_trajectory,
        )

        history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={},
                policy={"parameters": {"threshold": 5.0}},
            ),
            SingleAgentIterationRecord(
                iteration=2,
                metrics={},
                policy={"parameters": {}},  # Missing threshold
            ),
            SingleAgentIterationRecord(
                iteration=3,
                metrics={},
                policy={"parameters": {"threshold": 3.0}},
            ),
        ]

        trajectory = compute_parameter_trajectory(history, "threshold")

        assert trajectory == [(1, 5.0), (3, 3.0)]

    def test_empty_history_returns_empty(self) -> None:
        """Empty history returns empty trajectory."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_trajectory,
        )

        trajectory = compute_parameter_trajectory([], "threshold")

        assert trajectory == []

    def test_nonexistent_parameter_returns_empty(self) -> None:
        """Nonexistent parameter returns empty trajectory."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_trajectory,
        )

        history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={},
                policy={"parameters": {"threshold": 5.0}},
            ),
        ]

        trajectory = compute_parameter_trajectory(history, "nonexistent")

        assert trajectory == []

    def test_missing_parameters_key(self) -> None:
        """Handles policies without 'parameters' key."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_trajectory,
        )

        history = [
            SingleAgentIterationRecord(
                iteration=1,
                metrics={},
                policy={},  # No parameters key
            ),
        ]

        trajectory = compute_parameter_trajectory(history, "threshold")

        assert trajectory == []

    def test_preserves_iteration_order(self) -> None:
        """Trajectory preserves iteration order."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_trajectory,
        )

        history = [
            SingleAgentIterationRecord(
                iteration=3, metrics={}, policy={"parameters": {"x": 3.0}},
            ),
            SingleAgentIterationRecord(
                iteration=1, metrics={}, policy={"parameters": {"x": 1.0}},
            ),
            SingleAgentIterationRecord(
                iteration=2, metrics={}, policy={"parameters": {"x": 2.0}},
            ),
        ]

        trajectory = compute_parameter_trajectory(history, "x")

        # Should preserve list order, not sort by iteration
        assert trajectory == [(3, 3.0), (1, 1.0), (2, 2.0)]
