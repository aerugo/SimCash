"""TDD tests for policy schema FFI."""

import json
import pytest


class TestPolicySchemaFFI:
    """Tests for get_policy_schema FFI function."""

    def test_get_policy_schema_exists(self):
        """FFI function should be importable."""
        from payment_simulator.backends import get_policy_schema
        assert callable(get_policy_schema)

    def test_get_policy_schema_returns_valid_json(self):
        """FFI function should return valid JSON string."""
        from payment_simulator.backends import get_policy_schema

        schema_json = get_policy_schema()
        assert isinstance(schema_json, str)

        # Should parse as JSON
        schema = json.loads(schema_json)
        assert isinstance(schema, dict)

    def test_get_policy_schema_has_required_keys(self):
        """Schema should have all required top-level keys."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())

        assert "version" in schema
        assert "generated_at" in schema
        assert "expressions" in schema
        assert "computations" in schema
        assert "actions" in schema

    def test_get_policy_schema_expressions_count(self):
        """Should have exactly 9 expression operators."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())
        assert len(schema["expressions"]) == 9

    def test_get_policy_schema_computations_count(self):
        """Should have exactly 12 computation operations."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())
        assert len(schema["computations"]) == 12

    def test_get_policy_schema_actions_count(self):
        """Should have exactly 16 action types."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())
        assert len(schema["actions"]) == 16

    def test_get_policy_schema_values_count(self):
        """Should have exactly 4 value types."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())
        assert len(schema["values"]) == 4

    def test_get_policy_schema_element_structure(self):
        """Each element should have required fields."""
        from payment_simulator.backends import get_policy_schema

        schema = json.loads(get_policy_schema())

        for expr in schema["expressions"]:
            assert "name" in expr
            assert "json_key" in expr
            assert "category" in expr
            assert "description" in expr
            assert "valid_in_trees" in expr
