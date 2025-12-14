# Phase 2: StandardPolicyConfigBuilder Implementation

**Status**: In Progress
**Started**: 2025-12-14

---

## Objective

Implement the `StandardPolicyConfigBuilder` class to make all 23 tests pass. This is the TDD "green phase" - implementing code to satisfy the test specifications.

---

## Test Breakdown

### Tests to Pass (21 failing, 2 passing)

**Liquidity Config Tests (8):**
1. `test_extracts_fraction_from_nested_parameters` - nested policy["parameters"]["initial_liquidity_fraction"]
2. `test_extracts_fraction_from_flat_policy` - flat policy["initial_liquidity_fraction"]
3. `test_nested_takes_precedence_over_flat` - nested wins over flat
4. `test_default_fraction_when_not_specified` - default 0.5 when liquidity_pool exists
5. `test_extracts_liquidity_pool_from_agent_config` - liquidity_pool from agent_config
6. `test_no_fraction_when_no_liquidity_pool` - no fraction if no pool
7. `test_opening_balance_passthrough` - passthrough from agent_config
8. `test_opening_balance_defaults_to_zero` - default 0

**Collateral Config Tests (4):**
1. `test_extracts_max_collateral_capacity` - from agent_config
2. `test_extracts_initial_collateral_fraction_nested` - nested structure
3. `test_extracts_initial_collateral_fraction_flat` - flat structure
4. `test_no_collateral_fraction_if_not_specified` - no fraction if not in policy

**Edge Case Tests (7):**
1. `test_empty_policy_dict` - empty policy
2. `test_empty_agent_config` - empty agent_config
3. `test_none_liquidity_pool_handled` - None treated as absent
4. `test_type_coercion_liquidity_pool_string` - string→int
5. `test_type_coercion_fraction_string` - string→float
6. `test_type_coercion_fraction_int` - int→float
7. `test_type_coercion_opening_balance_float` - float→int

**Type Tests (2):**
1. `test_liquidity_config_is_dict` - return is dict
2. `test_collateral_config_is_dict` - return is dict

---

## Implementation Strategy

### Step 2.1: Implement extract_liquidity_config

```python
def extract_liquidity_config(
    self,
    policy: dict[str, Any],
    agent_config: dict[str, Any],
) -> LiquidityConfig:
    """Extract liquidity config using canonical logic."""
    result: LiquidityConfig = {}

    # 1. Extract opening_balance (always set, defaults to 0)
    opening_balance = agent_config.get("opening_balance", 0)
    result["opening_balance"] = int(opening_balance)

    # 2. Extract liquidity_pool from agent_config
    liquidity_pool = agent_config.get("liquidity_pool")
    if liquidity_pool is not None:
        result["liquidity_pool"] = int(liquidity_pool)

        # 3. Only extract fraction if liquidity_pool exists
        # Check nested parameters first (takes precedence)
        params = policy.get("parameters", {})
        fraction = params.get("initial_liquidity_fraction") if params else None

        # Fall back to flat structure
        if fraction is None:
            fraction = policy.get("initial_liquidity_fraction")

        # Default to 0.5 if not specified
        if fraction is None:
            fraction = 0.5

        result["liquidity_allocation_fraction"] = float(fraction)

    return result
```

### Step 2.2: Implement extract_collateral_config

```python
def extract_collateral_config(
    self,
    policy: dict[str, Any],
    agent_config: dict[str, Any],
) -> CollateralConfig:
    """Extract collateral config using canonical logic."""
    result: CollateralConfig = {}

    # 1. Extract max_collateral_capacity from agent_config
    max_collateral = agent_config.get("max_collateral_capacity")
    if max_collateral is not None:
        result["max_collateral_capacity"] = int(max_collateral)

    # 2. Extract initial_collateral_fraction from policy
    # Check nested parameters first
    params = policy.get("parameters", {})
    fraction = params.get("initial_collateral_fraction") if params else None

    # Fall back to flat structure
    if fraction is None:
        fraction = policy.get("initial_collateral_fraction")

    if fraction is not None:
        result["initial_collateral_fraction"] = float(fraction)

    return result
```

---

## Type Coercion Rules

| Source Type | Target Type | Conversion |
|-------------|-------------|------------|
| str → int | int("1000") = 1000 |
| float → int | int(100.99) = 100 |
| str → float | float("0.5") = 0.5 |
| int → float | float(1) = 1.0 |

---

## Exit Criteria

Phase 2 is complete when:
1. All 23 tests pass
2. mypy passes
3. ruff passes
4. Implementation matches the test specifications exactly

---

## Notes

- No extra logic beyond what tests specify
- Type coercion using Python built-in int() and float()
- TypedDict return types ensure correct structure
