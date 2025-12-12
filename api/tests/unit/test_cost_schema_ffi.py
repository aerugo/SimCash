"""TDD tests for cost schema FFI."""

import json

import pytest


class TestCostSchemaFFI:
    """Tests for get_cost_schema FFI function."""

    def test_get_cost_schema_exists(self) -> None:
        """FFI function should be importable."""
        from payment_simulator.backends import get_cost_schema

        assert callable(get_cost_schema)

    def test_get_cost_schema_returns_valid_json(self) -> None:
        """FFI function should return valid JSON string."""
        from payment_simulator.backends import get_cost_schema

        schema_json = get_cost_schema()
        assert isinstance(schema_json, str)

        # Should parse as JSON
        schema = json.loads(schema_json)
        assert isinstance(schema, dict)

    def test_get_cost_schema_has_required_keys(self) -> None:
        """Schema should have all required top-level keys."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())

        assert "version" in schema
        assert "generated_at" in schema
        assert "cost_types" in schema

    def test_get_cost_schema_cost_types_count(self) -> None:
        """Should have exactly 9 cost types."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())
        assert len(schema["cost_types"]) == 9

    def test_get_cost_schema_element_structure(self) -> None:
        """Each cost element should have required fields."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())

        for cost in schema["cost_types"]:
            assert "name" in cost
            assert "display_name" in cost
            assert "category" in cost
            assert "description" in cost
            assert "incurred_at" in cost
            assert "formula" in cost
            assert "default_value" in cost
            assert "unit" in cost
            assert "data_type" in cost
            assert "source_location" in cost
            assert "see_also" in cost
            # example is optional
            # added_in is optional

    def test_get_cost_schema_categories(self) -> None:
        """Cost types should have valid categories."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())

        valid_categories = {"PerTick", "OneTime", "Daily", "Modifier"}

        for cost in schema["cost_types"]:
            assert cost["category"] in valid_categories, f"Invalid category: {cost['category']}"

    def test_get_cost_schema_per_tick_count(self) -> None:
        """Should have exactly 4 per-tick costs."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())
        per_tick_costs = [c for c in schema["cost_types"] if c["category"] == "PerTick"]

        assert len(per_tick_costs) == 4

    def test_get_cost_schema_one_time_count(self) -> None:
        """Should have exactly 2 one-time costs."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())
        one_time_costs = [c for c in schema["cost_types"] if c["category"] == "OneTime"]

        assert len(one_time_costs) == 2

    def test_get_cost_schema_daily_count(self) -> None:
        """Should have exactly 1 daily cost."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())
        daily_costs = [c for c in schema["cost_types"] if c["category"] == "Daily"]

        assert len(daily_costs) == 1

    def test_get_cost_schema_modifier_count(self) -> None:
        """Should have exactly 2 modifiers."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())
        modifiers = [c for c in schema["cost_types"] if c["category"] == "Modifier"]

        assert len(modifiers) == 2

    def test_get_cost_schema_expected_names(self) -> None:
        """Should have all expected cost type names."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())

        expected_names = {
            "overdraft_bps_per_tick",
            "delay_cost_per_tick_per_cent",
            "collateral_cost_per_tick_bps",
            "liquidity_cost_per_tick_bps",
            "deadline_penalty",
            "split_friction_cost",
            "eod_penalty_per_transaction",
            "overdue_delay_multiplier",
            "priority_delay_multipliers",
        }

        actual_names = {c["name"] for c in schema["cost_types"]}

        assert actual_names == expected_names

    def test_get_cost_schema_deterministic(self) -> None:
        """Schema should be deterministic (same output every time)."""
        from payment_simulator.backends import get_cost_schema

        schema1 = get_cost_schema()
        schema2 = get_cost_schema()

        assert schema1 == schema2

    def test_get_cost_schema_examples_present(self) -> None:
        """All cost types should have examples."""
        from payment_simulator.backends import get_cost_schema

        schema = json.loads(get_cost_schema())

        for cost in schema["cost_types"]:
            assert "example" in cost and cost["example"] is not None, (
                f"Cost type {cost['name']} missing example"
            )

            example = cost["example"]
            assert "scenario" in example
            assert "inputs" in example
            assert "calculation" in example
            assert "result" in example
