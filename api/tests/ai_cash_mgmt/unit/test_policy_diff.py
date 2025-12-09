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


class TestComputeParameterChanges:
    """Tests for compute_parameter_changes function.

    This function returns structured parameter changes for audit persistence,
    as opposed to compute_policy_diff which returns human-readable strings.
    """

    def test_returns_list_of_change_dicts(self) -> None:
        """Returns list of structured change dictionaries."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"threshold": 5.0}}
        new = {"parameters": {"threshold": 3.0}}

        changes = compute_parameter_changes(old, new)

        assert isinstance(changes, list)
        assert len(changes) == 1
        assert isinstance(changes[0], dict)

    def test_change_dict_has_required_fields(self) -> None:
        """Each change dict has param, old, new, delta fields."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"threshold": 5.0}}
        new = {"parameters": {"threshold": 3.0}}

        changes = compute_parameter_changes(old, new)

        change = changes[0]
        assert "param" in change
        assert "old" in change
        assert "new" in change
        assert "delta" in change

    def test_calculates_delta_for_numeric_decrease(self) -> None:
        """Delta is calculated correctly for numeric decrease."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"threshold": 5.0}}
        new = {"parameters": {"threshold": 3.0}}

        changes = compute_parameter_changes(old, new)

        assert changes[0]["param"] == "threshold"
        assert changes[0]["old"] == 5.0
        assert changes[0]["new"] == 3.0
        assert changes[0]["delta"] == -2.0

    def test_calculates_delta_for_numeric_increase(self) -> None:
        """Delta is calculated correctly for numeric increase."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"threshold": 3.0}}
        new = {"parameters": {"threshold": 5.0}}

        changes = compute_parameter_changes(old, new)

        assert changes[0]["delta"] == 2.0

    def test_added_parameter_has_none_old(self) -> None:
        """Added parameters have old=None and delta=None."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {}}
        new = {"parameters": {"threshold": 5.0}}

        changes = compute_parameter_changes(old, new)

        added = [c for c in changes if c["param"] == "threshold"][0]
        assert added["old"] is None
        assert added["new"] == 5.0
        assert added["delta"] is None

    def test_removed_parameter_has_none_new(self) -> None:
        """Removed parameters have new=None and delta=None."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"threshold": 5.0}}
        new = {"parameters": {}}

        changes = compute_parameter_changes(old, new)

        removed = [c for c in changes if c["param"] == "threshold"][0]
        assert removed["old"] == 5.0
        assert removed["new"] is None
        assert removed["delta"] is None

    def test_multiple_changes_returns_all(self) -> None:
        """Multiple parameter changes are all returned."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"threshold": 5.0, "buffer": 1.0}}
        new = {"parameters": {"threshold": 4.0, "buffer": 1.5}}

        changes = compute_parameter_changes(old, new)

        assert len(changes) == 2
        param_names = {c["param"] for c in changes}
        assert param_names == {"threshold", "buffer"}

    def test_no_changes_returns_empty_list(self) -> None:
        """No changes returns empty list."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        policy = {"parameters": {"threshold": 5.0}}

        changes = compute_parameter_changes(policy, policy)

        assert changes == []

    def test_non_numeric_values_have_none_delta(self) -> None:
        """Non-numeric parameter changes have delta=None."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {"parameters": {"mode": "aggressive"}}
        new = {"parameters": {"mode": "conservative"}}

        changes = compute_parameter_changes(old, new)

        assert changes[0]["old"] == "aggressive"
        assert changes[0]["new"] == "conservative"
        assert changes[0]["delta"] is None

    def test_empty_policies_returns_empty_list(self) -> None:
        """Empty policies return empty list."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        changes = compute_parameter_changes({}, {})

        assert changes == []

    def test_missing_parameters_key_handled(self) -> None:
        """Handles policies without 'parameters' key."""
        from payment_simulator.ai_cash_mgmt.prompts.policy_diff import (
            compute_parameter_changes,
        )

        old = {}
        new = {"parameters": {"threshold": 5.0}}

        changes = compute_parameter_changes(old, new)

        assert len(changes) == 1
        assert changes[0]["param"] == "threshold"
        assert changes[0]["old"] is None
