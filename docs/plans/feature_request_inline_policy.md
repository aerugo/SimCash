# Feature Request: Inline Policy Type for Embedded Decision Tree DSL

**Date**: 2025-12-03
**Requested by**: Castro experiment test suite
**Priority**: High (blocks 35+ Castro experiment tests)

---

## Summary

Add an `Inline` policy type that allows embedding decision tree DSL structures directly in configuration dictionaries, complementing the existing `FromJson` policy type that loads from external files.

---

## Background

### Current Behavior

SimCash supports loading decision tree policies from external JSON files via `FromJson`:

```yaml
agents:
  - id: BANK_A
    policy:
      type: FromJson
      json_path: "experiments/castro/policies/seed_policy.json"
```

The schema (`api/payment_simulator/config/schemas.py`) defines these policy types:

```python
PolicyConfig = (
    FifoPolicy
    | DeadlinePolicy
    | LiquidityAwarePolicy
    | LiquiditySplittingPolicy
    | MockSplittingPolicy
    | FromJsonPolicy
)
```

### The Problem

The Castro experiment tests need to **dynamically create and modify policies in code** without writing temporary JSON files. Tests attempt to use an `Inline` type:

```python
"policy": {
    "type": "Inline",
    "decision_trees": {
        "version": "2.0",
        "policy_id": "test_policy",
        "parameters": {
            "initial_liquidity_fraction": 0.5,
            "urgency_threshold": 3.0,
        },
        "strategic_collateral_tree": {
            "type": "condition",
            "node_id": "tick_zero",
            "condition": {"op": "==", "left": {"field": "system_tick_in_day"}, "right": {"value": 0.0}},
            "on_true": {"type": "action", "node_id": "post", "action": "PostCollateral", ...},
            "on_false": {"type": "action", "node_id": "hold", "action": "HoldCollateral"},
        },
        "payment_tree": {
            "type": "action",
            "node_id": "release",
            "action": "Release",
        },
    },
}
```

This fails with Pydantic validation errors because `Inline` is not a recognized policy type.

### Impact

**47 test failures** in the Castro experiment suite, with **~35 directly caused** by the missing `Inline` policy type:

| Test File | Failures Due to Missing Inline |
|-----------|-------------------------------|
| `test_seed_policy.py` | 2 |
| `test_castro_deferred_crediting.py` | 6 |
| `test_experiment_framework.py` | 12+ |
| `test_experiment_integration.py` | 12+ |
| `test_deadline_cap_at_eod.py` | 5+ |

---

## Proposed Solution

### New Policy Type

Add `InlinePolicy` to the schema:

```python
class InlinePolicy(BaseModel):
    """Inline policy with embedded decision tree DSL."""

    type: Literal["Inline"] = "Inline"
    decision_trees: dict[str, Any] = Field(
        ...,
        description="Embedded decision tree DSL structure (same format as seed_policy.json)"
    )
```

Update the policy union:

```python
PolicyConfig = (
    FifoPolicy
    | DeadlinePolicy
    | LiquidityAwarePolicy
    | LiquiditySplittingPolicy
    | MockSplittingPolicy
    | FromJsonPolicy
    | InlinePolicy  # NEW
)
```

### FFI Conversion

In `SimulationConfig.to_ffi_dict()`, handle `InlinePolicy` similarly to `FromJsonPolicy` but pass the embedded dict directly instead of loading from file:

```python
def _convert_policy_to_ffi(self, policy: PolicyConfig) -> dict[str, Any]:
    if isinstance(policy, InlinePolicy):
        return {
            "type": "DecisionTreeDsl",
            "decision_trees": policy.decision_trees,
        }
    elif isinstance(policy, FromJsonPolicy):
        # Load from file and return same structure
        with open(policy.json_path) as f:
            return {
                "type": "DecisionTreeDsl",
                "decision_trees": json.load(f),
            }
    # ... other policy types
```

### Rust Backend

The Rust backend should already support receiving the decision tree structure directly (since `FromJson` loads and passes it). The `Inline` type is purely a Python-side convenience for embedding in configs.

If the Rust side expects a file path, it would need a small update to accept either:
- `{"type": "FromJson", "json_path": "..."}` - load from file
- `{"type": "Inline", "decision_trees": {...}}` - use embedded structure

---

## Acceptance Criteria

1. [ ] New `InlinePolicy` Pydantic model in `api/payment_simulator/config/schemas.py`
2. [ ] `InlinePolicy` added to `PolicyConfig` union type
3. [ ] FFI conversion handles `InlinePolicy` correctly
4. [ ] Rust backend accepts inline decision trees (if not already supported)
5. [ ] All Castro experiment tests using `"type": "Inline"` pass
6. [ ] Documentation updated with examples of both `FromJson` and `Inline` usage
7. [ ] Existing `FromJson` behavior unchanged

---

## Use Cases

### 1. Dynamic Policy Testing

Create policies programmatically in tests without file I/O:

```python
def test_zero_liquidity_posts_nothing():
    config = {
        "agents": [{
            "id": "A",
            "policy": {
                "type": "Inline",
                "decision_trees": {
                    "parameters": {"initial_liquidity_fraction": 0.0},
                    "strategic_collateral_tree": {...},
                    "payment_tree": {...},
                }
            }
        }]
    }
    orch = Orchestrator.new(config)
    # ... test assertions
```

### 2. LLM Policy Optimization

The LLM optimizer can generate policies as dicts and pass them directly:

```python
def optimize_policy(current_policy: dict) -> dict:
    # LLM generates new policy as dict
    new_policy = llm.generate_policy(current_policy)

    # Use directly without writing to file
    config["agents"][0]["policy"] = {
        "type": "Inline",
        "decision_trees": new_policy,
    }
    return run_simulation(config)
```

### 3. Parameter Sweeps

Run experiments varying policy parameters without managing temp files:

```python
for fraction in [0.0, 0.25, 0.5, 0.75, 1.0]:
    policy = base_policy.copy()
    policy["parameters"]["initial_liquidity_fraction"] = fraction

    config["agents"][0]["policy"] = {
        "type": "Inline",
        "decision_trees": policy,
    }
    results.append(run_simulation(config))
```

---

## Alternatives Considered

### 1. Write Temporary JSON Files

Tests could write policies to temp files and use `FromJson`.

**Rejected**:
- Adds file I/O overhead
- Complicates test cleanup
- Makes tests harder to read (policy not visible inline)

### 2. Modify FromJson to Accept Dict or Path

Make `json_path` accept either a file path or a dict.

**Rejected**:
- Confusing API (field named `json_path` accepting non-path)
- Type validation becomes ambiguous

### 3. Keep Tests Using FromJson with Fixtures

Create JSON fixtures for all test scenarios.

**Rejected**:
- Explosion of fixture files
- Can't dynamically vary parameters in tests
- Poor developer experience

---

## Testing

After implementation, run the Castro experiment test suite:

```bash
cd /home/user/SimCash/api
.venv/bin/python -m pytest ../experiments/castro/tests/ -v
```

**Expected**: ~35 previously failing tests should now pass.

---

## References

- Castro experiment tests: `experiments/castro/tests/`
- Current policy schema: `api/payment_simulator/config/schemas.py:394-438`
- Seed policy structure: `experiments/castro/policies/seed_policy.json`
- Test failure analysis: Castro experiment test run 2025-12-03
