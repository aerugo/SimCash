# Phase 6: Documentation Updates

**Status**: In Progress
**Started**: 2025-12-14

---

## Objective

Update reference documentation to reflect the new PolicyConfigBuilder pattern and Policy Evaluation Identity invariant.

---

## Files to Update

### 1. `docs/reference/patterns-and-conventions.md`

**Changes:**
- Add INV-9: Policy Evaluation Identity invariant
- Add Pattern 7: PolicyConfigBuilder
- Update Key Source Files table

### 2. Create doc-draft.md

Store draft documentation changes for review.

---

## Documentation Draft

### INV-9: Policy Evaluation Identity

**Rule**: For any policy P and scenario S, policy parameter extraction MUST produce identical results regardless of which code path processes them.

```python
# Both paths MUST use StandardPolicyConfigBuilder
extraction(optimization_path, P, S) == extraction(bootstrap_path, P, S)
```

**Requirements**:
- ALL code paths that apply policies to agents MUST use `StandardPolicyConfigBuilder`
- Parameter extraction logic (e.g., `initial_liquidity_fraction`) MUST be in one place
- Default values MUST be consistent across all paths
- Type coercion MUST be consistent across all paths

**Where it applies**:
- `optimization.py._build_simulation_config()` - deterministic evaluation
- `sandbox_config.py._build_target_agent()` - bootstrap evaluation

### Pattern 7: PolicyConfigBuilder

**Purpose**: Ensure identical policy parameter extraction across all code paths.

```python
@runtime_checkable
class PolicyConfigBuilder(Protocol):
    """Protocol for building agent config from policy."""

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> LiquidityConfig:
        """Extract liquidity configuration from policy."""
        ...

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral configuration from policy."""
        ...
```

**Implementations**:
- `StandardPolicyConfigBuilder`: The single source of truth for extraction

**Usage**:
```python
# In optimization.py
builder = StandardPolicyConfigBuilder()
liquidity_config = builder.extract_liquidity_config(policy, agent_config)
agent_config["liquidity_allocation_fraction"] = liquidity_config.get("liquidity_allocation_fraction")

# In sandbox_config.py
builder = StandardPolicyConfigBuilder()
liquidity_config = builder.extract_liquidity_config(policy, agent_config)
# Use extracted values for AgentConfig
```

**Key Features**:
- Nested takes precedence: `policy.parameters.x` wins over `policy.x`
- Default fraction: 0.5 when `liquidity_pool` exists but fraction not specified
- Type coercion: String/int values coerced to appropriate types

**Anti-patterns**:
- ❌ Duplicating extraction logic in multiple files
- ❌ Different default values in different code paths
- ❌ Direct policy parameter access without using builder

---

## Exit Criteria

Phase 6 is complete when:
1. patterns-and-conventions.md updated with INV-9 and Pattern 7
2. Key Source Files table updated
3. All documentation reviewed for accuracy
