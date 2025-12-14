# Phase 4: Integration into optimization.py

**Status**: In Progress
**Started**: 2025-12-14

---

## Objective

Integrate `StandardPolicyConfigBuilder` into `optimization.py` to replace duplicated policy parameter extraction logic in `_build_simulation_config()`. This ensures identical behavior between deterministic evaluation and bootstrap evaluation.

---

## Current State Analysis

From `initial_findings.md`, the duplicated logic is at lines 739-753 in `optimization.py`:

```python
if "liquidity_pool" in agent_config and isinstance(policy, dict):
    params = policy.get("parameters", {})
    fraction = params.get("initial_liquidity_fraction")
    if fraction is None:
        fraction = policy.get("initial_liquidity_fraction", 0.5)
    agent_config["liquidity_allocation_fraction"] = fraction
```

This logic has **subtle differences** from the sandbox_config.py implementation:
- Default value handling differs
- Type coercion differs

---

## Changes Required

### Step 4.1: Add import and initialization

```python
from payment_simulator.config.policy_config_builder import StandardPolicyConfigBuilder

class OptimizationLoop:
    def __init__(self, ...):
        # ... existing init ...
        self._policy_builder = StandardPolicyConfigBuilder()
```

### Step 4.2: Replace duplicated logic in _build_simulation_config

**Before:**
```python
if "liquidity_pool" in agent_config and isinstance(policy, dict):
    params = policy.get("parameters", {})
    fraction = params.get("initial_liquidity_fraction")
    if fraction is None:
        fraction = policy.get("initial_liquidity_fraction", 0.5)
    agent_config["liquidity_allocation_fraction"] = fraction
```

**After:**
```python
# Use canonical extraction via PolicyConfigBuilder
liquidity_config = self._policy_builder.extract_liquidity_config(
    policy=policy,
    agent_config=agent_config,
)
# Apply extracted fraction if present
if liquidity_config.get("liquidity_allocation_fraction") is not None:
    agent_config["liquidity_allocation_fraction"] = (
        liquidity_config["liquidity_allocation_fraction"]
    )
```

---

## Testing Strategy

1. Run existing optimization tests to ensure no regression
2. Create integration test verifying identical extraction in both paths

---

## Exit Criteria

Phase 4 is complete when:
1. optimization.py uses StandardPolicyConfigBuilder
2. Duplicated extraction logic is removed
3. All existing tests pass
4. mypy passes
5. ruff passes
