# Phase 3: Integration into sandbox_config.py

**Status**: In Progress
**Started**: 2025-12-14

---

## Objective

Integrate `StandardPolicyConfigBuilder` into `sandbox_config.py` to replace any duplicated policy parameter extraction logic. This ensures bootstrap evaluations use the canonical extraction logic.

---

## Current State Analysis

Looking at `sandbox_config.py`, the `_build_target_agent` method currently:
1. Takes `opening_balance`, `credit_limit`, `max_collateral_capacity` as parameters
2. Does NOT extract `liquidity_allocation_fraction` from policy

The `SandboxConfigBuilder.build_config()` method:
1. Passes `max_collateral_capacity` through to agent
2. Does NOT handle `liquidity_pool` or `liquidity_allocation_fraction`

**Key Finding**: The sandbox_config.py doesn't currently extract `initial_liquidity_fraction` from policies. It passes `max_collateral_capacity` but not liquidity fractions.

However, to ensure future compatibility and identical behavior, we should:
1. Add support for `liquidity_pool` parameter
2. Use PolicyConfigBuilder for any fraction extraction

---

## Changes Required

### Step 3.1: Add PolicyConfigBuilder to SandboxConfigBuilder

```python
from payment_simulator.config.policy_config_builder import StandardPolicyConfigBuilder

class SandboxConfigBuilder:
    def __init__(self) -> None:
        self._policy_builder = StandardPolicyConfigBuilder()
```

### Step 3.2: Update _build_target_agent signature

Add `liquidity_pool` parameter to support liquidity fraction extraction:

```python
def _build_target_agent(
    self,
    agent_id: str,
    policy: dict[str, Any],
    opening_balance: int,
    credit_limit: int,
    max_collateral_capacity: int | None = None,
    liquidity_pool: int | None = None,
) -> AgentConfig:
```

### Step 3.3: Use PolicyConfigBuilder for extraction

```python
def _build_target_agent(...) -> AgentConfig:
    # Build base config for extraction
    base_config: dict[str, Any] = {
        "opening_balance": opening_balance,
        "liquidity_pool": liquidity_pool,
        "max_collateral_capacity": max_collateral_capacity,
    }

    # Use canonical extraction
    liquidity_config = self._policy_builder.extract_liquidity_config(
        policy=policy,
        agent_config=base_config,
    )

    collateral_config = self._policy_builder.extract_collateral_config(
        policy=policy,
        agent_config=base_config,
    )

    return AgentConfig(
        id=agent_id,
        opening_balance=liquidity_config.get("opening_balance", opening_balance),
        unsecured_cap=credit_limit,
        max_collateral_capacity=collateral_config.get("max_collateral_capacity"),
        liquidity_pool=liquidity_config.get("liquidity_pool"),
        liquidity_allocation_fraction=liquidity_config.get("liquidity_allocation_fraction"),
        policy=self._parse_policy(policy),
    )
```

### Step 3.4: Update build_config to pass liquidity_pool

```python
def build_config(
    self,
    sample: BootstrapSample,
    target_policy: dict[str, Any],
    opening_balance: int,
    credit_limit: int,
    cost_rates: dict[str, float] | None = None,
    max_collateral_capacity: int | None = None,
    liquidity_pool: int | None = None,  # Add parameter
) -> SimulationConfig:
    # ...
    target_agent = self._build_target_agent(
        agent_id=sample.agent_id,
        policy=target_policy,
        opening_balance=opening_balance,
        credit_limit=credit_limit,
        max_collateral_capacity=max_collateral_capacity,
        liquidity_pool=liquidity_pool,  # Pass through
    )
```

---

## Tests to Run

1. Existing sandbox_config tests (should pass)
2. Existing bootstrap tests (should pass)
3. New integration test to verify PolicyConfigBuilder is used

---

## Exit Criteria

Phase 3 is complete when:
1. SandboxConfigBuilder uses StandardPolicyConfigBuilder
2. All existing tests pass
3. mypy passes
4. ruff passes
