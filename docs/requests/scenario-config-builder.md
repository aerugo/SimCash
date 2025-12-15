# Feature Request: ScenarioConfigBuilder

**Status**: Proposed
**Priority**: Medium
**Related Bug**: Bootstrap evaluation ignoring `liquidity_pool` (commit `c06a880`)

## Problem Statement

The codebase currently has **multiple parallel helper methods** that extract agent configuration from scenario YAML files. This pattern is error-prone because:

1. **Easy to forget parameters**: When adding a new agent property, developers must remember to add extraction logic in multiple places
2. **No single source of truth**: The same extraction logic is duplicated across components
3. **Silent failures**: Missing parameters cause subtle bugs (like bootstrap ignoring `initial_liquidity_fraction`) rather than explicit errors

### Current State

`OptimizationLoop` has 4 separate helper methods that read from scenario config:

```python
# api/payment_simulator/experiments/runner/optimization.py

def _get_agent_opening_balance(self, agent_id: str) -> int:
    scenario = self._load_scenario_config()
    for agent in scenario.get("agents", []):
        if agent.get("id") == agent_id:
            return int(agent.get("opening_balance", 0))
    return 0

def _get_agent_credit_limit(self, agent_id: str) -> int:
    # Same pattern...

def _get_agent_max_collateral_capacity(self, agent_id: str) -> int | None:
    # Same pattern...

def _get_agent_liquidity_pool(self, agent_id: str) -> int | None:
    # Same pattern... (added after bug fix)
```

These are then passed individually to `BootstrapPolicyEvaluator`:

```python
evaluator = BootstrapPolicyEvaluator(
    opening_balance=self._get_agent_opening_balance(agent_id),
    credit_limit=self._get_agent_credit_limit(agent_id),
    max_collateral_capacity=self._get_agent_max_collateral_capacity(agent_id),
    liquidity_pool=self._get_agent_liquidity_pool(agent_id),  # Was missing!
)
```

### The Bug This Pattern Caused

When `liquidity_pool` was added to the scenario config schema, the extraction was added to the main simulation path but **not** to the bootstrap evaluation path. This caused:

- Bootstrap samples to run with `liquidity_pool=None`
- `PolicyConfigBuilder.extract_liquidity_config()` to skip `initial_liquidity_fraction` extraction
- Policy changes to have **zero effect** on costs
- Experiment 2 to produce invalid results (all deltas = 0)

## Proposed Solution

Create a `ScenarioConfigBuilder` class that provides a **single source of truth** for extracting agent configuration from scenario YAML.

### Design Goals

1. **Single extraction point**: One method to get all agent config properties
2. **Type safety**: Return a typed dataclass/TypedDict, not raw dicts
3. **Explicit failures**: Raise errors for missing required fields
4. **Canonical coercion**: Apply INV-1 (integer cents) coercion consistently
5. **Extensibility**: Easy to add new agent properties without forgetting callsites

### Proposed API

```python
# api/payment_simulator/config/scenario_config_builder.py

from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class AgentScenarioConfig:
    """Extracted agent configuration from scenario YAML.

    All monetary values are in integer cents (INV-1).
    """
    agent_id: str
    opening_balance: int
    credit_limit: int  # unsecured_cap in YAML
    max_collateral_capacity: int | None
    liquidity_pool: int | None
    # Future: Add new agent properties here


class ScenarioConfigBuilder:
    """Canonical extraction of agent configuration from scenario YAML.

    This builder ensures that scenario configs are interpreted identically
    across all components (main simulation, bootstrap evaluation, replay, etc.).

    Similar to PolicyConfigBuilder which ensures policy parameter extraction
    is consistent, this ensures scenario parameter extraction is consistent.

    Example:
        ```python
        builder = ScenarioConfigBuilder(scenario_dict)

        # Extract all config for an agent at once
        config = builder.extract_agent_config("BANK_A")

        # Use with BootstrapPolicyEvaluator
        evaluator = BootstrapPolicyEvaluator(
            opening_balance=config.opening_balance,
            credit_limit=config.credit_limit,
            max_collateral_capacity=config.max_collateral_capacity,
            liquidity_pool=config.liquidity_pool,
        )
        ```
    """

    def __init__(self, scenario_dict: dict[str, Any]) -> None:
        """Initialize with parsed scenario YAML."""
        self._scenario = scenario_dict
        self._agents_by_id: dict[str, dict[str, Any]] = {
            agent["id"]: agent
            for agent in scenario_dict.get("agents", [])
        }

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        """Extract all configuration for an agent.

        Args:
            agent_id: Agent ID to look up.

        Returns:
            AgentScenarioConfig with all extracted values.

        Raises:
            KeyError: If agent_id not found in scenario.
        """
        if agent_id not in self._agents_by_id:
            raise KeyError(f"Agent '{agent_id}' not found in scenario config")

        agent = self._agents_by_id[agent_id]

        return AgentScenarioConfig(
            agent_id=agent_id,
            opening_balance=int(agent.get("opening_balance", 0)),
            credit_limit=int(agent.get("unsecured_cap", 0)),
            max_collateral_capacity=self._extract_optional_int(
                agent, "max_collateral_capacity"
            ),
            liquidity_pool=self._extract_optional_int(
                agent, "liquidity_pool"
            ),
        )

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario."""
        return list(self._agents_by_id.keys())

    @staticmethod
    def _extract_optional_int(
        agent: dict[str, Any],
        key: str,
    ) -> int | None:
        """Extract optional integer field with INV-1 coercion."""
        value = agent.get(key)
        if value is not None:
            return int(value)
        return None
```

### Migration Path

1. **Phase 1**: Implement `ScenarioConfigBuilder` alongside existing helpers
2. **Phase 2**: Refactor `OptimizationLoop` to use the builder
3. **Phase 3**: Remove deprecated helper methods
4. **Phase 4**: Audit other components that read scenario config

### Usage After Migration

```python
# Before (fragile)
evaluator = BootstrapPolicyEvaluator(
    opening_balance=self._get_agent_opening_balance(agent_id),
    credit_limit=self._get_agent_credit_limit(agent_id),
    max_collateral_capacity=self._get_agent_max_collateral_capacity(agent_id),
    liquidity_pool=self._get_agent_liquidity_pool(agent_id),
)

# After (single extraction, can't forget fields)
config = self._scenario_builder.extract_agent_config(agent_id)
evaluator = BootstrapPolicyEvaluator(
    opening_balance=config.opening_balance,
    credit_limit=config.credit_limit,
    max_collateral_capacity=config.max_collateral_capacity,
    liquidity_pool=config.liquidity_pool,
)
```

Or even better, `BootstrapPolicyEvaluator` could accept `AgentScenarioConfig` directly:

```python
# Cleanest API
config = self._scenario_builder.extract_agent_config(agent_id)
evaluator = BootstrapPolicyEvaluator.from_scenario_config(config, cost_rates)
```

## Testing Requirements

1. **Unit tests**: Verify extraction logic for each field
2. **Type coercion tests**: Ensure INV-1 compliance (string "1000" -> int 1000)
3. **Missing field tests**: Verify defaults and error handling
4. **Integration tests**: Verify bootstrap evaluation uses all fields correctly
5. **Identity tests**: Ensure `ScenarioConfigBuilder` produces identical results to current helpers

## Related Components

| Component | Current State | After Migration |
|-----------|---------------|-----------------|
| `OptimizationLoop` | 4 helper methods | Uses `ScenarioConfigBuilder` |
| `BootstrapPolicyEvaluator` | Receives individual params | Could accept `AgentScenarioConfig` |
| `SandboxConfigBuilder` | Receives individual params | Could accept `AgentScenarioConfig` |
| `PolicyConfigBuilder` | Already centralized | No change (handles policy extraction) |

## Acceptance Criteria

- [ ] `ScenarioConfigBuilder` implemented with full type annotations
- [ ] All existing helper methods migrated or deprecated
- [ ] Unit tests cover all extraction paths
- [ ] Integration test proves bootstrap evaluation respects all agent config fields
- [ ] No more "forgot to pass X to bootstrap" class of bugs possible

## Appendix: Pattern Comparison

This follows the same pattern as `PolicyConfigBuilder`:

| Builder | Input | Output | Purpose |
|---------|-------|--------|---------|
| `PolicyConfigBuilder` | Policy dict | `LiquidityConfig`, `CollateralConfig` | Canonical extraction of policy parameters |
| `ScenarioConfigBuilder` | Scenario dict | `AgentScenarioConfig` | Canonical extraction of scenario parameters |

Both builders ensure that configuration interpretation is **identical across all components**, preventing divergence bugs.
