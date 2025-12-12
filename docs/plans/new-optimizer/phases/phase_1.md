# Phase 1: Schema Injection Helpers

## Objective
Create helper functions that extract schema information from Rust FFI and format it for LLM prompts, filtered by scenario constraints.

## TDD Approach
Write tests first, then implement the code to make them pass.

## Files to Create

### 1. Test File
`api/tests/ai_cash_mgmt/unit/test_schema_injection.py`

### 2. Implementation File
`api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py`

## Test Plan

### Test Group 1: Policy Schema Filtering

```python
class TestPolicySchemaFiltering:
    """Tests for filtering policy schema by scenario constraints."""

    def test_filter_actions_by_tree_type_payment():
        """Only allowed payment actions are included."""
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
        )
        schema = get_filtered_policy_schema(constraints)
        assert "Release" in schema
        assert "Hold" in schema
        assert "Split" not in schema
        assert "PaceAndRelease" not in schema

    def test_filter_actions_by_tree_type_bank():
        """Bank tree actions filtered correctly."""
        constraints = ScenarioConstraints(
            allowed_actions={
                "payment_tree": ["Release", "Hold"],
                "bank_tree": ["SetReleaseBudget", "NoAction"],
            },
        )
        schema = get_filtered_policy_schema(constraints)
        assert "SetReleaseBudget" in schema
        assert "SetState" not in schema

    def test_filter_actions_excludes_disabled_trees():
        """Disabled trees have no actions in schema."""
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
            # bank_tree not present = disabled
        )
        schema = get_filtered_policy_schema(constraints)
        assert "SetReleaseBudget" not in schema

    def test_filter_fields_only_allowed():
        """Only allowed fields are documented."""
        constraints = ScenarioConstraints(
            allowed_fields=["balance", "effective_liquidity", "ticks_to_deadline"],
        )
        schema = get_filtered_policy_schema(constraints)
        assert "balance" in schema
        assert "effective_liquidity" in schema
        assert "ticks_to_deadline" in schema
        assert "credit_limit" not in schema
        assert "lsm_bilateral_net" not in schema

    def test_filter_parameters_with_bounds():
        """Parameters include min/max/default bounds."""
        constraints = ScenarioConstraints(
            allowed_parameters=[
                ParameterSpec(name="urgency_threshold", param_type="float",
                              min_value=0, max_value=20, default=3.0,
                              description="Ticks before deadline"),
            ],
        )
        schema = get_filtered_policy_schema(constraints)
        assert "urgency_threshold" in schema
        assert "0" in schema  # min
        assert "20" in schema  # max
        assert "3.0" in schema  # default
```

### Test Group 2: Cost Schema Formatting

```python
class TestCostSchemaFormatting:
    """Tests for formatting cost schema documentation."""

    def test_cost_schema_includes_all_rates():
        """All relevant cost rates are documented."""
        schema = get_formatted_cost_schema()
        assert "overdraft_bps_per_tick" in schema
        assert "delay_cost_per_tick_per_cent" in schema
        assert "deadline_penalty" in schema
        assert "eod_penalty_per_transaction" in schema

    def test_cost_schema_includes_formulas():
        """Cost formulas are documented."""
        schema = get_formatted_cost_schema()
        assert "balance" in schema.lower() or "formula" in schema.lower()

    def test_cost_schema_includes_examples():
        """Cost examples are included."""
        schema = get_formatted_cost_schema()
        # Should include example calculations
        assert "$" in schema or "cents" in schema.lower()

    def test_cost_schema_from_rates():
        """Format cost schema from CostRates configuration."""
        rates = {
            "overdraft_bps_per_tick": 0.001,
            "delay_cost_per_tick_per_cent": 0.0001,
            "deadline_penalty": 50000,
        }
        schema = get_formatted_cost_schema(cost_rates=rates)
        assert "0.001" in schema
        assert "0.0001" in schema
        assert "50000" in schema
```

### Test Group 3: Parameter Bounds Formatting

```python
class TestParameterBoundsFormatting:
    """Tests for formatting parameter specifications."""

    def test_format_parameter_table():
        """Parameters formatted as readable table."""
        params = [
            ParameterSpec(name="urgency_threshold", param_type="float",
                          min_value=0, max_value=20, default=3.0,
                          description="Ticks before deadline"),
            ParameterSpec(name="liquidity_buffer", param_type="float",
                          min_value=0.5, max_value=3.0, default=1.0,
                          description="Liquidity safety margin"),
        ]
        formatted = format_parameter_bounds(params)

        # Should include all parameter names
        assert "urgency_threshold" in formatted
        assert "liquidity_buffer" in formatted

        # Should include ranges
        assert "[0, 20]" in formatted or "0-20" in formatted or "min: 0" in formatted.lower()

        # Should include descriptions
        assert "deadline" in formatted.lower()

    def test_format_empty_parameters():
        """Empty parameter list returns appropriate message."""
        formatted = format_parameter_bounds([])
        assert "no parameters" in formatted.lower() or formatted == ""
```

### Test Group 4: Action List Formatting

```python
class TestActionListFormatting:
    """Tests for formatting action lists per tree type."""

    def test_format_payment_actions():
        """Payment tree actions formatted correctly."""
        actions = ["Release", "Hold", "Split"]
        formatted = format_action_list("payment_tree", actions)
        assert "Release" in formatted
        assert "Hold" in formatted
        assert "Split" in formatted
        assert "payment_tree" in formatted.lower()

    def test_format_bank_actions():
        """Bank tree actions formatted correctly."""
        actions = ["SetReleaseBudget", "NoAction"]
        formatted = format_action_list("bank_tree", actions)
        assert "SetReleaseBudget" in formatted
        assert "NoAction" in formatted

    def test_format_collateral_actions():
        """Collateral tree actions formatted correctly."""
        actions = ["PostCollateral", "HoldCollateral"]
        formatted = format_action_list("strategic_collateral_tree", actions)
        assert "PostCollateral" in formatted
        assert "HoldCollateral" in formatted

    def test_format_disabled_tree():
        """Disabled tree indicated clearly."""
        formatted = format_action_list("bank_tree", [])
        assert "disabled" in formatted.lower() or "not enabled" in formatted.lower()
```

### Test Group 5: Field List Formatting

```python
class TestFieldListFormatting:
    """Tests for formatting field lists."""

    def test_format_field_list_basic():
        """Basic field list formatted correctly."""
        fields = ["balance", "effective_liquidity", "ticks_to_deadline"]
        formatted = format_field_list(fields)
        assert "balance" in formatted
        assert "effective_liquidity" in formatted
        assert "ticks_to_deadline" in formatted

    def test_format_field_list_grouped_by_category():
        """Fields grouped by category if possible."""
        fields = [
            "balance", "effective_liquidity",  # Agent fields
            "ticks_to_deadline", "remaining_amount",  # Transaction fields
            "system_tick_in_day", "ticks_remaining_in_day",  # Time fields
        ]
        formatted = format_field_list(fields)
        # Should contain all fields
        for field in fields:
            assert field in formatted

    def test_format_empty_field_list():
        """Empty field list handled gracefully."""
        formatted = format_field_list([])
        assert formatted == "" or "no fields" in formatted.lower()
```

### Test Group 6: Integration with Rust Schema

```python
class TestRustSchemaIntegration:
    """Tests that verify integration with Rust FFI schema."""

    def test_get_policy_schema_returns_json():
        """Rust FFI returns valid policy schema JSON."""
        from payment_simulator.backends import get_policy_schema
        schema_json = get_policy_schema()
        schema = json.loads(schema_json)

        assert "actions" in schema
        assert "expressions" in schema
        assert "values" in schema

    def test_get_cost_schema_returns_json():
        """Rust FFI returns valid cost schema JSON."""
        from payment_simulator.backends import get_cost_schema
        schema_json = get_cost_schema()
        schema = json.loads(schema_json)

        assert "cost_types" in schema

    def test_filter_uses_rust_schema():
        """Filtering uses actual Rust schema data."""
        constraints = ScenarioConstraints(
            allowed_actions={"payment_tree": ["Release", "Hold"]},
            allowed_fields=["balance"],
        )
        schema = get_filtered_policy_schema(constraints)

        # Should include Release action documentation from Rust
        assert "Release" in schema
        # Should NOT include actions not in allowed list
        assert "Split" not in schema
```

## Implementation Plan

### Step 1: Create Test File (TDD)
Create `api/tests/ai_cash_mgmt/unit/test_schema_injection.py` with all tests above.

### Step 2: Create Implementation Skeleton
Create `api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py` with function stubs.

### Step 3: Implement `format_parameter_bounds()`
Simplest function - format parameter specs into readable text.

### Step 4: Implement `format_field_list()`
Format allowed fields with optional grouping by category.

### Step 5: Implement `format_action_list()`
Format actions per tree type.

### Step 6: Implement `get_filtered_policy_schema()`
Main function that combines all formatting and filters by constraints.

### Step 7: Implement `get_formatted_cost_schema()`
Format cost schema from Rust or config.

### Step 8: Run All Tests
Verify all tests pass.

## API Design

```python
# api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py

def get_filtered_policy_schema(
    constraints: ScenarioConstraints,
    include_examples: bool = True,
) -> str:
    """Generate policy schema documentation filtered by constraints.

    Args:
        constraints: Scenario constraints defining what's allowed.
        include_examples: Whether to include JSON examples.

    Returns:
        Formatted markdown/text schema documentation.
    """
    ...

def get_formatted_cost_schema(
    cost_rates: dict[str, Any] | None = None,
) -> str:
    """Generate cost schema documentation.

    Args:
        cost_rates: Optional cost rate values to include.

    Returns:
        Formatted markdown/text cost documentation.
    """
    ...

def format_parameter_bounds(
    params: list[ParameterSpec],
) -> str:
    """Format parameter specifications as readable text.

    Args:
        params: List of parameter specifications.

    Returns:
        Formatted parameter table/list.
    """
    ...

def format_field_list(
    fields: list[str],
    group_by_category: bool = False,
) -> str:
    """Format field list as readable text.

    Args:
        fields: List of allowed field names.
        group_by_category: Whether to group by schema category.

    Returns:
        Formatted field list.
    """
    ...

def format_action_list(
    tree_type: str,
    actions: list[str],
) -> str:
    """Format action list for a tree type.

    Args:
        tree_type: Tree type (payment_tree, bank_tree, etc.)
        actions: List of allowed actions.

    Returns:
        Formatted action list with descriptions.
    """
    ...
```

## Acceptance Criteria

1. [ ] All tests pass
2. [ ] Functions have complete type annotations
3. [ ] Docstrings follow project conventions
4. [ ] Integration with Rust FFI verified
5. [ ] Filtering correctly excludes disallowed elements
6. [ ] Output is human-readable and LLM-friendly

## Dependencies

- `payment_simulator.backends.get_policy_schema()` (Rust FFI)
- `payment_simulator.backends.get_cost_schema()` (Rust FFI)
- `payment_simulator.ai_cash_mgmt.constraints.ScenarioConstraints`
- `payment_simulator.ai_cash_mgmt.constraints.ParameterSpec`

## Notes

- The Rust schema already includes comprehensive documentation
- We need to filter this down based on scenario constraints
- Output format should be markdown-friendly for LLM consumption
- Keep formatting consistent with existing prompt style
