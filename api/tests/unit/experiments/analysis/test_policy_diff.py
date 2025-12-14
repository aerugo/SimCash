"""Unit tests for policy diff calculator."""

from __future__ import annotations

import pytest

from payment_simulator.experiments.analysis.policy_diff import (
    compute_policy_diff,
    extract_parameter_changes,
)


class TestComputePolicyDiff:
    """Tests for compute_policy_diff function."""

    def test_detects_parameter_change(self) -> None:
        """Verify parameter changes are detected and formatted."""
        old = {"parameters": {"threshold": 100}}
        new = {"parameters": {"threshold": 200}}
        diff = compute_policy_diff(old, new)

        assert "threshold" in diff
        assert "100" in diff
        assert "200" in diff
        assert "->" in diff

    def test_handles_nested_tree_changes(self) -> None:
        """Verify tree structure changes are detected."""
        old = {
            "payment_tree": {
                "type": "Condition",
                "on_true": {"type": "Action", "action": "Submit"},
            },
        }
        new = {
            "payment_tree": {
                "type": "Condition",
                "on_true": {"type": "Action", "action": "Defer"},
            },
        }
        diff = compute_policy_diff(old, new)

        assert "action" in diff
        assert "Submit" in diff
        assert "Defer" in diff

    def test_handles_added_fields(self) -> None:
        """Verify new fields are reported as additions."""
        old = {"parameters": {"a": 1}}
        new = {"parameters": {"a": 1, "b": 2}}
        diff = compute_policy_diff(old, new)

        assert "parameters.b" in diff
        assert "+" in diff  # Added indicator

    def test_handles_removed_fields(self) -> None:
        """Verify removed fields are reported."""
        old = {"parameters": {"a": 1, "b": 2}}
        new = {"parameters": {"a": 1}}
        diff = compute_policy_diff(old, new)

        assert "parameters.b" in diff
        assert "-" in diff  # Removed indicator

    def test_returns_empty_for_identical(self) -> None:
        """Verify no diff for identical policies."""
        policy = {"parameters": {"threshold": 100}, "version": "2.0"}
        diff = compute_policy_diff(policy, policy)

        assert diff == ""

    def test_ignores_policy_id_and_version(self) -> None:
        """Verify policy_id and version are not compared."""
        old = {"policy_id": "old-id", "version": "1.0", "threshold": 100}
        new = {"policy_id": "new-id", "version": "2.0", "threshold": 100}
        diff = compute_policy_diff(old, new)

        # Should be empty since policy_id and version are skipped
        assert diff == ""

    def test_handles_list_changes(self) -> None:
        """Verify list element changes are detected."""
        old = {"weights": [0.1, 0.2, 0.3]}
        new = {"weights": [0.1, 0.5, 0.3]}
        diff = compute_policy_diff(old, new)

        assert "weights[1]" in diff
        assert "0.2" in diff or "0.5" in diff

    def test_handles_deeply_nested_changes(self) -> None:
        """Verify deeply nested changes are detected."""
        old = {"level1": {"level2": {"level3": {"value": 10}}}}
        new = {"level1": {"level2": {"level3": {"value": 20}}}}
        diff = compute_policy_diff(old, new)

        assert "level1.level2.level3.value" in diff
        assert "10" in diff
        assert "20" in diff


class TestExtractParameterChanges:
    """Tests for extract_parameter_changes function."""

    def test_returns_structured_changes(self) -> None:
        """Verify structured parameter changes are returned."""
        old = {"parameters": {"threshold": 100}}
        new = {"parameters": {"threshold": 200}}
        changes = extract_parameter_changes(old, new)

        assert "parameters.threshold" in changes
        assert changes["parameters.threshold"]["before"] == 100
        assert changes["parameters.threshold"]["after"] == 200
        assert changes["parameters.threshold"]["type"] == "changed"

    def test_marks_added_as_type_added(self) -> None:
        """Verify added fields have type='added'."""
        old = {}
        new = {"new_field": "value"}
        changes = extract_parameter_changes(old, new)

        assert "new_field" in changes
        assert changes["new_field"]["type"] == "added"
        assert changes["new_field"]["before"] is None

    def test_marks_removed_as_type_removed(self) -> None:
        """Verify removed fields have type='removed'."""
        old = {"old_field": "value"}
        new = {}
        changes = extract_parameter_changes(old, new)

        assert "old_field" in changes
        assert changes["old_field"]["type"] == "removed"
        assert changes["old_field"]["after"] is None

    def test_returns_empty_for_identical(self) -> None:
        """Verify empty dict for identical policies."""
        policy = {"a": 1, "b": 2}
        changes = extract_parameter_changes(policy, policy)

        assert changes == {}

    def test_handles_bool_changes(self) -> None:
        """Verify boolean changes are detected."""
        old = {"enabled": True}
        new = {"enabled": False}
        changes = extract_parameter_changes(old, new)

        assert "enabled" in changes
        assert changes["enabled"]["before"] is True
        assert changes["enabled"]["after"] is False

    def test_handles_string_changes(self) -> None:
        """Verify string changes are detected."""
        old = {"name": "old_name"}
        new = {"name": "new_name"}
        changes = extract_parameter_changes(old, new)

        assert "name" in changes
        assert changes["name"]["before"] == "old_name"
        assert changes["name"]["after"] == "new_name"

    def test_handles_float_changes(self) -> None:
        """Verify float changes are detected."""
        old = {"rate": 0.5}
        new = {"rate": 0.75}
        changes = extract_parameter_changes(old, new)

        assert "rate" in changes
        assert changes["rate"]["before"] == 0.5
        assert changes["rate"]["after"] == 0.75
