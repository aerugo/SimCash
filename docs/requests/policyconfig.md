# Feature Request: Unified Policy-to-FFI Config Builder

## Problem Statement

The current `PolicyConfigBuilder` Protocol does not fully guarantee identical policy evaluation between the **main simulation path** (optimization.py) and the **bootstrap evaluation path** (sandbox_config.py). While we've introduced shared helper methods (`extract_liquidity_config()`, `is_tree_policy()`), the overall config-building logic remains duplicated across both paths.

### Current Architecture (Problematic)

```
┌─────────────────────────────────────────────────────────────────┐
│                     LLM-Generated Policy                        │
│            {"payment_tree": {...}, "parameters": {...}}         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌──────────────────────┐         ┌──────────────────────┐
│   optimization.py    │         │  sandbox_config.py   │
│                      │         │                      │
│ 1. extract_liquidity │         │ 1. extract_liquidity │
│    _config() ✓       │         │    _config() ✓       │
│                      │         │                      │
│ 2. is_tree_policy()  │         │ 2. is_tree_policy()  │
│    ✓ (now shared)    │         │    ✓ (now shared)    │
│                      │         │                      │
│ 3. Build scenario    │         │ 3. Build AgentConfig │
│    dict manually     │ ❌ DIFFERENT │   objects       │
│                      │         │                      │
│ 4. SimulationConfig  │         │ 4. SimulationConfig  │
│    .from_dict()      │ ❌ DIFFERENT │   constructor   │
│                      │         │                      │
│ 5. .to_ffi_dict()    │         │ 5. .to_ffi_dict()    │
└──────────────────────┘         └──────────────────────┘
           │                               │
           ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │ FFI Config A │  ❓ SAME?     │ FFI Config B │
    └──────────────┘               └──────────────┘
```

### Why This Is Dangerous

1. **Steps 3-4 are different** between paths - any logic added to one path must be manually replicated to the other
2. **No compile-time enforcement** - divergence is only caught by integration tests (if they exist)
3. **Future maintenance risk** - new policy features will likely only be implemented in one path
4. **Violation of DRY** - policy interpretation logic is conceptually duplicated

---

## Proposed Solution: Follow the StateProvider Pattern

The StateProvider pattern (from `cli/execution/state_provider.py`) provides a proven model for guaranteeing identical behavior across two execution paths.

### How StateProvider Works

```
┌─────────────────────────────────────────────────────────────────┐
│              display_tick_verbose_output()                      │
│              (SINGLE SOURCE OF TRUTH)                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                  Uses ONLY Protocol
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌──────────────────────┐         ┌──────────────────────┐
│ OrchestratorState    │         │ DatabaseState        │
│ Provider             │         │ Provider             │
│ (Live FFI)           │         │ (Replay DB)          │
└──────────────────────┘         └──────────────────────┘
```

**Key insight**: Both paths call the **same function** (`display_tick_verbose_output`), which only uses the Protocol interface. The implementations (OrchestratorStateProvider, DatabaseStateProvider) are thin adapters.

### Proposed Architecture: AgentFFIConfigBuilder

```
┌─────────────────────────────────────────────────────────────────┐
│                     LLM-Generated Policy                        │
│            {"payment_tree": {...}, "parameters": {...}}         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│              build_agent_ffi_config()                           │
│              (SINGLE SOURCE OF TRUTH)                           │
│                                                                 │
│   Input:  policy: dict, base_agent_config: dict                 │
│   Output: FFI-ready agent config dict                           │
│                                                                 │
│   Contains ALL policy interpretation logic:                     │
│   - Liquidity fraction extraction (nested/flat)                 │
│   - Tree policy detection                                       │
│   - Policy serialization (InlineJsonPolicy wrapping)            │
│   - Type conversion and defaults                                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           │                               │
           ▼                               ▼
┌──────────────────────┐         ┌──────────────────────┐
│   optimization.py    │         │  sandbox_config.py   │
│                      │         │                      │
│ Call build_agent_    │         │ Call build_agent_    │
│ ffi_config() for     │         │ ffi_config() for     │
│ each agent           │         │ target agent         │
└──────────────────────┘         └──────────────────────┘
           │                               │
           ▼                               ▼
    ┌──────────────┐               ┌──────────────┐
    │ FFI Config A │  ✓ IDENTICAL  │ FFI Config B │
    └──────────────┘               └──────────────┘
```

---

## Detailed Design

### New Module: `api/payment_simulator/config/agent_ffi_config.py`

```python
"""Agent FFI config builder - SINGLE SOURCE OF TRUTH.

This module provides the ONLY way to convert a policy dict + base agent config
into an FFI-ready agent configuration. Both optimization.py and sandbox_config.py
MUST use this module to guarantee identical policy evaluation.

Design follows the StateProvider pattern from cli/execution/state_provider.py.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict


class AgentFFIConfig(TypedDict, total=False):
    """FFI-ready agent configuration.

    All fields that can be passed to Rust via FFI.
    """
    id: str
    opening_balance: int
    unsecured_cap: int
    max_collateral_capacity: int | None
    liquidity_pool: int | None
    liquidity_allocation_fraction: float | None
    policy: dict[str, Any]  # Already serialized for FFI


def build_agent_ffi_config(
    policy: dict[str, Any],
    base_config: dict[str, Any],
) -> AgentFFIConfig:
    """Build FFI-ready agent config from policy and base config.

    SINGLE SOURCE OF TRUTH for policy interpretation.

    This function handles:
    1. Liquidity fraction extraction (nested/flat structures)
    2. Tree policy detection and InlineJsonPolicy wrapping
    3. Type conversion and defaults
    4. All other policy-to-config mappings

    Args:
        policy: LLM-generated policy dict. Supports:
            - Nested: {"parameters": {"initial_liquidity_fraction": 0.25}}
            - Flat: {"initial_liquidity_fraction": 0.25}
            - Tree: {"payment_tree": {...}, "bank_tree": {...}}
        base_config: Agent config from scenario YAML. Contains:
            - id, opening_balance, unsecured_cap
            - liquidity_pool, max_collateral_capacity (optional)

    Returns:
        AgentFFIConfig ready to be passed to Rust FFI.

    Example:
        >>> policy = {"payment_tree": {"action": "Release"},
        ...           "parameters": {"initial_liquidity_fraction": 0.25}}
        >>> base = {"id": "BANK_A", "opening_balance": 0, "liquidity_pool": 1000000}
        >>> config = build_agent_ffi_config(policy, base)
        >>> config["liquidity_allocation_fraction"]
        0.25
        >>> config["policy"]["type"]
        'InlineJson'
    """
    result: AgentFFIConfig = {}

    # Pass through base config fields
    result["id"] = base_config["id"]
    result["opening_balance"] = int(base_config.get("opening_balance", 0))
    result["unsecured_cap"] = int(base_config.get("unsecured_cap", 0))

    # Handle liquidity_pool mode (Castro-compliant)
    liquidity_pool = base_config.get("liquidity_pool")
    if liquidity_pool is not None:
        result["liquidity_pool"] = int(liquidity_pool)
        result["liquidity_allocation_fraction"] = _extract_fraction(policy)

    # Handle max_collateral_capacity mode
    max_collateral = base_config.get("max_collateral_capacity")
    if max_collateral is not None:
        result["max_collateral_capacity"] = int(max_collateral)

    # Convert policy to FFI format
    result["policy"] = _serialize_policy_for_ffi(policy)

    return result


def _extract_fraction(policy: dict[str, Any]) -> float:
    """Extract initial_liquidity_fraction from policy.

    Checks nested structure first, then flat, defaults to 0.5.
    """
    # Nested: policy["parameters"]["initial_liquidity_fraction"]
    params = policy.get("parameters", {})
    fraction = params.get("initial_liquidity_fraction")

    # Flat: policy["initial_liquidity_fraction"]
    if fraction is None:
        fraction = policy.get("initial_liquidity_fraction")

    # Default to 50%
    if fraction is None:
        return 0.5

    return float(fraction)


def _is_tree_policy(policy: dict[str, Any]) -> bool:
    """Check if policy contains decision trees."""
    tree_keys = (
        "payment_tree",
        "bank_tree",
        "strategic_collateral_tree",
        "end_of_tick_collateral_tree",
    )
    return any(key in policy for key in tree_keys)


def _serialize_policy_for_ffi(policy: dict[str, Any]) -> dict[str, Any]:
    """Serialize policy dict for FFI transport.

    Tree policies are wrapped in InlineJsonPolicy format.
    Simple policies (Fifo, LiquidityAware) pass through.
    """
    if _is_tree_policy(policy):
        return {
            "type": "InlineJson",
            "json_string": json.dumps(policy),
        }
    else:
        return policy
```

### Updated Usage in optimization.py

```python
# BEFORE (current - problematic)
if isinstance(policy, dict):
    liquidity_config = self._policy_config_builder.extract_liquidity_config(...)
    if "liquidity_allocation_fraction" in liquidity_config:
        agent_config["liquidity_allocation_fraction"] = ...

    if self._policy_config_builder.is_tree_policy(policy):
        agent_config["policy"] = {"type": "InlineJson", ...}
    else:
        agent_config["policy"] = policy

# AFTER (proposed - guaranteed identical)
from payment_simulator.config.agent_ffi_config import build_agent_ffi_config

# Replace entire agent config with unified builder output
agent_ffi_config = build_agent_ffi_config(
    policy=policy,
    base_config=agent_config,
)
# Merge into scenario dict
agent_config.update(agent_ffi_config)
```

### Updated Usage in sandbox_config.py

```python
# BEFORE (current - problematic)
def _build_target_agent(self, agent_id, policy, opening_balance, ...):
    return AgentConfig(
        id=agent_id,
        opening_balance=opening_balance,
        ...
        policy=self._parse_policy(policy),  # Separate serialization logic!
    )

# AFTER (proposed - guaranteed identical)
from payment_simulator.config.agent_ffi_config import build_agent_ffi_config

def _build_target_agent(self, agent_id, policy, base_config, ...):
    # Use SAME builder as optimization.py
    ffi_config = build_agent_ffi_config(
        policy=policy,
        base_config=base_config,
    )
    return AgentConfig(**ffi_config)
```

---

## Key Differences from Current Approach

| Aspect | Current (PolicyConfigBuilder) | Proposed (build_agent_ffi_config) |
|--------|-------------------------------|-----------------------------------|
| Scope | Partial - only extracts some fields | Complete - produces final FFI config |
| Usage | Both paths call helpers, then do their own logic | Both paths call ONE function |
| Guarantee | Shared helpers, but divergence possible | Identical output by construction |
| Testing | Must test both paths separately | Test ONE function, coverage is automatic |
| Maintenance | Changes must be made in 2+ places | Changes in ONE place propagate everywhere |

---

## Implementation Plan

### Phase 1: Create Unified Builder (No Breaking Changes)
1. Create `api/payment_simulator/config/agent_ffi_config.py`
2. Implement `build_agent_ffi_config()` with all current logic
3. Add comprehensive unit tests
4. Keep existing `PolicyConfigBuilder` for backwards compatibility

### Phase 2: Migrate optimization.py
1. Replace inline config building with `build_agent_ffi_config()` calls
2. Verify all existing tests pass
3. Add integration test comparing old vs new output

### Phase 3: Migrate sandbox_config.py
1. Replace `_build_target_agent()` internals with `build_agent_ffi_config()`
2. Remove now-unused `_parse_policy()` method
3. Verify bootstrap evaluation produces identical results

### Phase 4: Cleanup
1. Deprecate `PolicyConfigBuilder` (or keep as internal helper)
2. Document the new pattern in CLAUDE.md
3. Add invariant test: "both paths produce byte-identical FFI configs"

---

## Verification Strategy

### Invariant Test (Critical)

```python
def test_ffi_config_identity():
    """Both paths MUST produce identical FFI configs."""
    policy = {
        "payment_tree": {"action": "Release"},
        "parameters": {"initial_liquidity_fraction": 0.25},
    }
    base_config = {
        "id": "BANK_A",
        "opening_balance": 0,
        "liquidity_pool": 10_000_000,
        "unsecured_cap": 0,
    }

    # Path 1: Direct call (what sandbox_config.py will use)
    config_1 = build_agent_ffi_config(policy, base_config)

    # Path 2: Via optimization.py flow (simulated)
    config_2 = build_agent_ffi_config(policy, base_config)

    # MUST be identical
    assert config_1 == config_2

    # Verify specific fields
    assert config_1["liquidity_allocation_fraction"] == 0.25
    assert config_1["policy"]["type"] == "InlineJson"
```

### Bootstrap Equivalence Test

```python
def test_bootstrap_uses_same_config_as_simulation():
    """Bootstrap sandbox config MUST match main simulation config for same agent."""
    # Run optimization.py to get main simulation config
    # Run sandbox_config.py to get bootstrap config
    # Compare agent configs - MUST be identical
```

---

## Success Criteria

1. **Single Source of Truth**: ONE function (`build_agent_ffi_config`) handles all policy-to-FFI conversion
2. **No Divergence Possible**: Both paths call the same function, making divergence impossible
3. **Comprehensive Tests**: Invariant tests prove identical behavior
4. **Documented Pattern**: CLAUDE.md updated with new pattern reference
5. **Zero Regressions**: All existing tests pass unchanged

---

## References

- **StateProvider Pattern**: `api/payment_simulator/cli/execution/state_provider.py`
- **Current PolicyConfigBuilder**: `api/payment_simulator/config/policy_config_builder.py`
- **Main Simulation Path**: `api/payment_simulator/experiments/runner/optimization.py`
- **Bootstrap Path**: `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`
- **Replay Identity Documentation**: `CLAUDE.md` (section: "Replay Identity")
