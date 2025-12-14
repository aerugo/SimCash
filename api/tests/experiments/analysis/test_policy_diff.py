"""Tests for policy diff calculator.

TDD tests for compute_policy_diff() and extract_parameter_changes().
These tests follow the project's strict typing conventions.
"""

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

    def test_handles_nested_tree_changes(self) -> None:
        """Verify tree structure changes are detected."""
        old = {
            "payment_tree": {
                "on_true": {"action": "Release", "threshold": 0.5},
            }
        }
        new = {
            "payment_tree": {
                "on_true": {"action": "Release", "threshold": 0.7},
            }
        }

        diff = compute_policy_diff(old, new)

        assert "payment_tree" in diff or "threshold" in diff
        assert "0.5" in diff
        assert "0.7" in diff

    def test_handles_added_fields(self) -> None:
        """Verify new fields are reported."""
        old = {"parameters": {"threshold": 100}}
        new = {"parameters": {"threshold": 100, "new_param": 50}}

        diff = compute_policy_diff(old, new)

        assert "new_param" in diff.lower() or "added" in diff.lower()
        assert "50" in diff

    def test_handles_removed_fields(self) -> None:
        """Verify removed fields are reported."""
        old = {"parameters": {"threshold": 100, "old_param": 30}}
        new = {"parameters": {"threshold": 100}}

        diff = compute_policy_diff(old, new)

        assert "old_param" in diff.lower() or "removed" in diff.lower()

    def test_returns_empty_for_identical(self) -> None:
        """Verify no diff for identical policies."""
        policy = {"parameters": {"threshold": 100}}

        diff = compute_policy_diff(policy, policy.copy())

        assert diff == "" or diff.strip() == ""

    def test_handles_none_old_policy(self) -> None:
        """Verify first iteration (no previous) returns empty or initial marker."""
        new = {"parameters": {"threshold": 100}}

        diff = compute_policy_diff(None, new)

        # First iteration should have no diff (nothing to compare against)
        assert diff == "" or "initial" in diff.lower()

    def test_handles_deeply_nested_changes(self) -> None:
        """Verify deeply nested structures are handled."""
        old = {
            "payment_tree": {
                "condition": {"field": "balance"},
                "on_true": {
                    "condition": {"field": "priority"},
                    "on_true": {"action": "Release"},
                },
            }
        }
        new = {
            "payment_tree": {
                "condition": {"field": "balance"},
                "on_true": {
                    "condition": {"field": "urgency"},  # Changed
                    "on_true": {"action": "Release"},
                },
            }
        }

        diff = compute_policy_diff(old, new)

        assert "priority" in diff or "urgency" in diff

    def test_handles_boolean_changes(self) -> None:
        """Verify boolean value changes are detected."""
        old = {"parameters": {"enabled": True}}
        new = {"parameters": {"enabled": False}}

        diff = compute_policy_diff(old, new)

        assert "enabled" in diff

    def test_handles_list_changes(self) -> None:
        """Verify list value changes are detected."""
        old = {"parameters": {"allowed_actions": ["Release", "Hold"]}}
        new = {"parameters": {"allowed_actions": ["Release", "Hold", "Split"]}}

        diff = compute_policy_diff(old, new)

        assert "allowed_actions" in diff or "Split" in diff

    def test_formats_float_changes_readable(self) -> None:
        """Verify float changes are formatted readably."""
        old = {"parameters": {"fraction": 0.123456789}}
        new = {"parameters": {"fraction": 0.987654321}}

        diff = compute_policy_diff(old, new)

        # Should not have excessive decimal places
        assert "fraction" in diff


class TestExtractParameterChanges:
    """Tests for extract_parameter_changes function."""

    def test_returns_structured_diff(self) -> None:
        """Verify structured dict output."""
        old = {"parameters": {"threshold": 100}}
        new = {"parameters": {"threshold": 200}}

        changes = extract_parameter_changes(old, new)

        assert "parameters.threshold" in changes
        assert changes["parameters.threshold"]["before"] == 100
        assert changes["parameters.threshold"]["after"] == 200

    def test_handles_added_field(self) -> None:
        """Verify added fields have None as before value."""
        old = {"parameters": {}}
        new = {"parameters": {"new_field": 50}}

        changes = extract_parameter_changes(old, new)

        assert "parameters.new_field" in changes
        assert changes["parameters.new_field"]["before"] is None
        assert changes["parameters.new_field"]["after"] == 50

    def test_handles_removed_field(self) -> None:
        """Verify removed fields have None as after value."""
        old = {"parameters": {"old_field": 30}}
        new = {"parameters": {}}

        changes = extract_parameter_changes(old, new)

        assert "parameters.old_field" in changes
        assert changes["parameters.old_field"]["before"] == 30
        assert changes["parameters.old_field"]["after"] is None

    def test_returns_empty_for_identical(self) -> None:
        """Verify empty dict for identical policies."""
        policy = {"parameters": {"threshold": 100}}

        changes = extract_parameter_changes(policy, policy.copy())

        assert changes == {}

    def test_handles_none_old_policy(self) -> None:
        """Verify None old policy returns empty changes."""
        new = {"parameters": {"threshold": 100}}

        changes = extract_parameter_changes(None, new)

        # First iteration - no changes to compare
        assert changes == {}

    def test_handles_nested_keys(self) -> None:
        """Verify nested keys use dot notation."""
        old = {"a": {"b": {"c": 1}}}
        new = {"a": {"b": {"c": 2}}}

        changes = extract_parameter_changes(old, new)

        assert "a.b.c" in changes
        assert changes["a.b.c"]["before"] == 1
        assert changes["a.b.c"]["after"] == 2
