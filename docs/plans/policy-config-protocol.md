# Plan: PolicyConfigBuilder Protocol

## Problem Statement

Currently, the logic for injecting policy parameters into agent configs is duplicated:

1. **`optimization.py`'s `_build_simulation_config()`** (lines 739-753):
   ```python
   if "liquidity_pool" in agent_config and isinstance(policy, dict):
       params = policy.get("parameters", {})
       fraction = params.get("initial_liquidity_fraction")
       if fraction is None:
           fraction = policy.get("initial_liquidity_fraction", 0.5)
       agent_config["liquidity_allocation_fraction"] = fraction
   ```

2. **`sandbox_config.py`'s `build_config()`** (lines 92-101):
   ```python
   if liquidity_pool is not None:
       params = target_policy.get("parameters", {})
       fraction = params.get("initial_liquidity_fraction")
       if fraction is None:
           fraction = target_policy.get("initial_liquidity_fraction")
       if fraction is not None:
           liquidity_allocation_fraction = float(fraction)
   ```

These implementations have **subtle differences** (default values, type handling) that could cause divergent behavior between:
- Main simulation (what user sees)
- Bootstrap sandbox (what optimization loop evaluates)

This is a **replay identity violation risk** - policies should behave identically regardless of where they're evaluated.

## Design: PolicyConfigBuilder Protocol

Following the StateProvider pattern, we'll create:

### 1. Protocol Definition

```python
# api/payment_simulator/config/policy_config_builder.py

from typing import Any, Protocol, TypedDict

class AgentLiquidityConfig(TypedDict, total=False):
    """Liquidity-related fields for agent config."""
    liquidity_pool: int | None
    liquidity_allocation_fraction: float | None
    max_collateral_capacity: int | None
    opening_balance: int


@runtime_checkable
class PolicyConfigBuilder(Protocol):
    """Protocol for building agent config from policy.

    This interface ensures identical policy interpretation
    across main simulation and bootstrap evaluation.
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> AgentLiquidityConfig:
        """Extract liquidity configuration from policy.

        Args:
            policy: Policy dict (may have nested or flat structure)
            agent_config: Base agent config from scenario

        Returns:
            AgentLiquidityConfig with computed values
        """
        ...
```

### 2. Single Implementation

```python
class StandardPolicyConfigBuilder:
    """Standard implementation of PolicyConfigBuilder.

    Used by both optimization.py and sandbox_config.py
    to ensure identical policy interpretation.
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> AgentLiquidityConfig:
        """Extract liquidity config using canonical logic.

        Handles both liquidity_pool mode (Castro-compliant)
        and max_collateral_capacity mode (collateral-based).
        """
        result: AgentLiquidityConfig = {}

        # Extract liquidity_pool from agent config
        liquidity_pool = agent_config.get("liquidity_pool")
        if liquidity_pool is not None:
            result["liquidity_pool"] = int(liquidity_pool)

            # Extract initial_liquidity_fraction from policy
            # Check both nested (parameters.X) and flat (X) structure
            params = policy.get("parameters", {})
            fraction = params.get("initial_liquidity_fraction")
            if fraction is None:
                fraction = policy.get("initial_liquidity_fraction")

            # Default to 0.5 (50%) if not specified
            if fraction is None:
                fraction = 0.5

            result["liquidity_allocation_fraction"] = float(fraction)

        # Extract max_collateral_capacity from agent config
        max_collateral = agent_config.get("max_collateral_capacity")
        if max_collateral is not None:
            result["max_collateral_capacity"] = int(max_collateral)

        # Opening balance passthrough
        opening_balance = agent_config.get("opening_balance", 0)
        result["opening_balance"] = int(opening_balance)

        return result
```

### 3. Usage in optimization.py

```python
# At class level or as dependency injection
self._policy_config_builder = StandardPolicyConfigBuilder()

def _build_simulation_config(self):
    # ...
    for agent_config in scenario_dict["agents"]:
        agent_id = agent_config.get("id")
        if agent_id in self._policies:
            policy = self._policies[agent_id]

            # Use shared builder for liquidity config
            liquidity_config = self._policy_config_builder.extract_liquidity_config(
                policy=policy,
                agent_config=agent_config,
            )
            agent_config.update(liquidity_config)

            # Rest of config building...
```

### 4. Usage in sandbox_config.py

```python
class SandboxConfigBuilder:
    def __init__(self) -> None:
        self._policy_config_builder = StandardPolicyConfigBuilder()

    def build_config(
        self,
        sample: BootstrapSample,
        target_policy: dict[str, Any],
        opening_balance: int,
        credit_limit: int,
        cost_rates: dict[str, float] | None = None,
        liquidity_pool: int | None = None,
        max_collateral_capacity: int | None = None,
    ) -> SimulationConfig:
        # Build base agent config
        base_config = {
            "opening_balance": opening_balance,
            "liquidity_pool": liquidity_pool,
            "max_collateral_capacity": max_collateral_capacity,
        }

        # Use shared builder
        liquidity_config = self._policy_config_builder.extract_liquidity_config(
            policy=target_policy,
            agent_config=base_config,
        )

        # Build target agent with extracted config
        target_agent = self._build_target_agent(
            agent_id=sample.agent_id,
            policy=target_policy,
            opening_balance=liquidity_config.get("opening_balance", opening_balance),
            credit_limit=credit_limit,
            max_collateral_capacity=liquidity_config.get("max_collateral_capacity"),
            liquidity_pool=liquidity_config.get("liquidity_pool"),
            liquidity_allocation_fraction=liquidity_config.get("liquidity_allocation_fraction"),
        )
```

## Implementation Steps

1. **Create `policy_config_builder.py`** with Protocol and StandardPolicyConfigBuilder
2. **Update `optimization.py`** to use StandardPolicyConfigBuilder
3. **Update `sandbox_config.py`** to use StandardPolicyConfigBuilder
4. **Add unit tests** verifying both code paths produce identical configs
5. **Remove duplicated logic** from both files

## Testing Strategy

```python
# tests/unit/test_policy_config_builder.py

def test_identical_config_extraction():
    """Verify optimization.py and sandbox_config.py produce identical results."""
    builder = StandardPolicyConfigBuilder()

    policy = {"initial_liquidity_fraction": 0.25}
    agent_config = {"liquidity_pool": 10_000_000, "opening_balance": 0}

    result = builder.extract_liquidity_config(policy, agent_config)

    assert result["liquidity_pool"] == 10_000_000
    assert result["liquidity_allocation_fraction"] == 0.25
    assert result["opening_balance"] == 0


def test_nested_vs_flat_policy_structure():
    """Both nested and flat policy structures produce same result."""
    builder = StandardPolicyConfigBuilder()
    agent_config = {"liquidity_pool": 1_000_000}

    nested_policy = {"parameters": {"initial_liquidity_fraction": 0.15}}
    flat_policy = {"initial_liquidity_fraction": 0.15}

    nested_result = builder.extract_liquidity_config(nested_policy, agent_config)
    flat_result = builder.extract_liquidity_config(flat_policy, agent_config)

    assert nested_result == flat_result


def test_default_fraction():
    """Missing fraction defaults to 0.5."""
    builder = StandardPolicyConfigBuilder()
    agent_config = {"liquidity_pool": 1_000_000}
    policy = {}

    result = builder.extract_liquidity_config(policy, agent_config)

    assert result["liquidity_allocation_fraction"] == 0.5
```

## Benefits

1. **Single Source of Truth**: One implementation, used everywhere
2. **Testable**: Unit test the builder in isolation
3. **Extensible**: Easy to add new policy parameters
4. **Type-safe**: Protocol ensures implementations match interface
5. **Replay Identity**: Guarantees identical behavior in simulation and evaluation

## Future Extensions

The PolicyConfigBuilder could be extended to handle:
- Collateral allocation parameters (`initial_collateral_fraction`)
- Payment timing preferences
- Queue priority settings
- Any policy parameter that affects agent config

---

*Plan created: 2025-12-14*
*Status: Ready for implementation*
