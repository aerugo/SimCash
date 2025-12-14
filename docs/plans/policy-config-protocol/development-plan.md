# PolicyConfigBuilder Protocol - Development Plan

**Version**: 1.0
**Created**: 2025-12-14
**Status**: In Progress

---

## Executive Summary

This plan addresses the **policy configuration duplication** identified in `initial_findings.md`. Currently, policy parameter extraction (e.g., `initial_liquidity_fraction`) is duplicated between:
- `optimization.py`'s `_build_simulation_config()`
- `sandbox_config.py`'s `SandboxConfigBuilder`

These implementations have **subtle differences** in default values and type handling that could cause divergent behavior between main simulation and bootstrap evaluation.

### Absolute Invariant

**All transactions MUST be evaluated identically regardless of which code path processes them.**

This is the "Policy Evaluation Identity" invariant - analogous to the project's Replay Identity (INV-5), but for policy configuration instead of display.

---

## Solution Design: PolicyConfigBuilder Protocol

Following the established **StateProvider pattern**, we create a Protocol-based abstraction:

```
┌─────────────────────────────────────────────────────────────┐
│              PolicyConfigBuilder Protocol                    │
│              (Single Source of Truth)                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
          ┌───────┴────────┐
          │ Standard       │
          │ Implementation │
          └───────┬────────┘
                  │
     ┌────────────┴─────────────┐
     │                          │
     ▼                          ▼
┌────────────────┐      ┌──────────────────┐
│ optimization.py│      │ sandbox_config.py│
│ (Main Sim)     │      │ (Bootstrap Eval) │
└────────────────┘      └──────────────────┘
```

### Key Design Decisions

1. **Protocol-based**: Enables future alternative implementations if needed
2. **TypedDict return types**: Explicit field typing for safety
3. **No default parameter coupling**: Each extraction method is self-contained
4. **Immutable config builder**: No mutable state, thread-safe by design

---

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Protocol definition + test cases | Test-first design | 8-10 tests |
| 2 | StandardPolicyConfigBuilder implementation | Red-green-refactor | 5-7 tests |
| 3 | Integration into sandbox_config.py | Integration tests | 3-5 tests |
| 4 | Integration into optimization.py | Integration tests | 3-5 tests |
| 5 | Policy Evaluation Identity tests | End-to-end verification | 5-8 tests |
| 6 | Documentation updates | N/A | N/A |

---

## Phase 1: Protocol Definition and Test Cases

**Goal**: Define the `PolicyConfigBuilder` protocol with comprehensive test cases BEFORE implementation.

### Deliverables
1. `api/payment_simulator/config/policy_config_builder.py` with:
   - `LiquidityConfig` TypedDict
   - `CollateralConfig` TypedDict
   - `PolicyConfigBuilder` Protocol
   - Empty `StandardPolicyConfigBuilder` class (fails tests)

2. `api/tests/unit/test_policy_config_builder.py` with:
   - Tests for liquidity config extraction
   - Tests for collateral config extraction
   - Tests for nested vs flat policy structures
   - Tests for default values
   - Tests for edge cases (None, missing keys)

### Protocol Specification

```python
from typing import Protocol, TypedDict, Any, runtime_checkable

class LiquidityConfig(TypedDict, total=False):
    """Liquidity-related configuration extracted from policy."""
    liquidity_pool: int | None
    liquidity_allocation_fraction: float | None
    opening_balance: int

class CollateralConfig(TypedDict, total=False):
    """Collateral-related configuration extracted from policy."""
    max_collateral_capacity: int | None
    initial_collateral_fraction: float | None

@runtime_checkable
class PolicyConfigBuilder(Protocol):
    """Protocol for building agent config from policy.

    This interface ensures IDENTICAL policy interpretation
    across main simulation and bootstrap evaluation paths.

    INVARIANT: For any given (policy, agent_config) pair,
    the extracted configuration MUST be byte-for-byte identical
    regardless of which code path calls this builder.
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> LiquidityConfig:
        """Extract liquidity configuration from policy.

        Handles both nested and flat policy structures:
        - Nested: policy["parameters"]["initial_liquidity_fraction"]
        - Flat: policy["initial_liquidity_fraction"]

        Args:
            policy: Policy dict (may have nested or flat structure)
            agent_config: Base agent config from scenario

        Returns:
            LiquidityConfig with computed values
        """
        ...

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral configuration from policy.

        Args:
            policy: Policy dict
            agent_config: Base agent config from scenario

        Returns:
            CollateralConfig with computed values
        """
        ...
```

### Test Specification

```python
# Test categories for Phase 1

class TestLiquidityConfigExtraction:
    """Tests for extract_liquidity_config method."""

    def test_extracts_fraction_from_nested_parameters(self):
        """Nested policy["parameters"]["initial_liquidity_fraction"]."""

    def test_extracts_fraction_from_flat_policy(self):
        """Flat policy["initial_liquidity_fraction"]."""

    def test_nested_takes_precedence_over_flat(self):
        """If both exist, nested wins."""

    def test_default_fraction_when_not_specified(self):
        """Missing fraction defaults to 0.5."""

    def test_extracts_liquidity_pool_from_agent_config(self):
        """liquidity_pool comes from agent_config, not policy."""

    def test_no_fraction_when_no_liquidity_pool(self):
        """No liquidity_allocation_fraction if no liquidity_pool."""

    def test_opening_balance_passthrough(self):
        """opening_balance extracted from agent_config."""

class TestCollateralConfigExtraction:
    """Tests for extract_collateral_config method."""

    def test_extracts_max_collateral_capacity(self):
        """max_collateral_capacity from agent_config."""

    def test_extracts_initial_collateral_fraction(self):
        """initial_collateral_fraction from policy."""

class TestEdgeCases:
    """Edge case handling."""

    def test_empty_policy_dict(self):
        """Empty policy should return defaults."""

    def test_none_values_handled(self):
        """None values don't cause errors."""

    def test_type_coercion_to_int(self):
        """String/float values coerced to int where needed."""

    def test_type_coercion_to_float(self):
        """String/int values coerced to float where needed."""
```

---

## Phase 2: StandardPolicyConfigBuilder Implementation

**Goal**: Implement the builder following strict TDD - make tests pass one by one.

### Deliverables
1. Complete `StandardPolicyConfigBuilder` implementation
2. All Phase 1 tests passing
3. 100% test coverage for the module

### Implementation Strategy

```python
class StandardPolicyConfigBuilder:
    """Standard implementation of PolicyConfigBuilder.

    Used by BOTH optimization.py AND sandbox_config.py
    to ensure IDENTICAL policy interpretation.

    This is the SINGLE SOURCE OF TRUTH for policy→config transformation.
    """

    def extract_liquidity_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> LiquidityConfig:
        """Extract liquidity config using canonical logic."""
        result: LiquidityConfig = {}

        # 1. Extract liquidity_pool from agent config
        liquidity_pool = agent_config.get("liquidity_pool")
        if liquidity_pool is not None:
            result["liquidity_pool"] = int(liquidity_pool)

            # 2. Extract initial_liquidity_fraction from policy
            # Nested takes precedence over flat
            params = policy.get("parameters", {})
            fraction = params.get("initial_liquidity_fraction")
            if fraction is None:
                fraction = policy.get("initial_liquidity_fraction")

            # 3. Default to 0.5 if not specified
            if fraction is None:
                fraction = 0.5

            result["liquidity_allocation_fraction"] = float(fraction)

        # 4. Opening balance passthrough
        opening_balance = agent_config.get("opening_balance", 0)
        result["opening_balance"] = int(opening_balance)

        return result

    def extract_collateral_config(
        self,
        policy: dict[str, Any],
        agent_config: dict[str, Any],
    ) -> CollateralConfig:
        """Extract collateral config using canonical logic."""
        result: CollateralConfig = {}

        max_collateral = agent_config.get("max_collateral_capacity")
        if max_collateral is not None:
            result["max_collateral_capacity"] = int(max_collateral)

        # Extract initial_collateral_fraction
        params = policy.get("parameters", {})
        fraction = params.get("initial_collateral_fraction")
        if fraction is None:
            fraction = policy.get("initial_collateral_fraction")
        if fraction is not None:
            result["initial_collateral_fraction"] = float(fraction)

        return result
```

---

## Phase 3: Integration into sandbox_config.py

**Goal**: Replace duplicated logic in `SandboxConfigBuilder` with `StandardPolicyConfigBuilder`.

### Changes Required

**Before (duplicated logic):**
```python
def _build_target_agent(
    self,
    agent_id: str,
    policy: dict[str, Any],
    opening_balance: int,
    credit_limit: int,
    max_collateral_capacity: int | None = None,
) -> AgentConfig:
    return AgentConfig(
        id=agent_id,
        opening_balance=opening_balance,
        unsecured_cap=credit_limit,
        max_collateral_capacity=max_collateral_capacity,
        policy=self._parse_policy(policy),
    )
```

**After (using PolicyConfigBuilder):**
```python
def __init__(self) -> None:
    self._policy_builder = StandardPolicyConfigBuilder()

def _build_target_agent(
    self,
    agent_id: str,
    policy: dict[str, Any],
    opening_balance: int,
    credit_limit: int,
    max_collateral_capacity: int | None = None,
    liquidity_pool: int | None = None,
) -> AgentConfig:
    # Build base config for extraction
    base_config = {
        "opening_balance": opening_balance,
        "liquidity_pool": liquidity_pool,
        "max_collateral_capacity": max_collateral_capacity,
    }

    # Use canonical extraction
    liquidity_config = self._policy_builder.extract_liquidity_config(
        policy=policy,
        agent_config=base_config,
    )

    return AgentConfig(
        id=agent_id,
        opening_balance=liquidity_config.get("opening_balance", opening_balance),
        unsecured_cap=credit_limit,
        max_collateral_capacity=max_collateral_capacity,
        liquidity_pool=liquidity_config.get("liquidity_pool"),
        liquidity_allocation_fraction=liquidity_config.get("liquidity_allocation_fraction"),
        policy=self._parse_policy(policy),
    )
```

### Integration Tests

```python
class TestSandboxConfigBuilderIntegration:
    """Integration tests for PolicyConfigBuilder in sandbox_config.py."""

    def test_liquidity_fraction_extracted_via_builder(self):
        """Verify sandbox uses PolicyConfigBuilder for fraction."""

    def test_nested_policy_structure_works(self):
        """Nested parameters.initial_liquidity_fraction works."""

    def test_default_fraction_applied(self):
        """Missing fraction gets 0.5 default."""
```

---

## Phase 4: Integration into optimization.py

**Goal**: Replace duplicated logic in `OptimizationLoop._build_simulation_config()`.

### Changes Required

**Before (duplicated logic in _build_simulation_config):**
```python
# Lines 739-753 of optimization.py (conceptual)
if "liquidity_pool" in agent_config and isinstance(policy, dict):
    params = policy.get("parameters", {})
    fraction = params.get("initial_liquidity_fraction")
    if fraction is None:
        fraction = policy.get("initial_liquidity_fraction", 0.5)
    agent_config["liquidity_allocation_fraction"] = fraction
```

**After (using PolicyConfigBuilder):**
```python
def __init__(self, ...):
    # ... existing init ...
    self._policy_builder = StandardPolicyConfigBuilder()

def _build_simulation_config(self) -> dict[str, Any]:
    # ... existing code ...

    if "agents" in scenario_dict:
        for agent_config in scenario_dict["agents"]:
            agent_id = agent_config.get("id")
            if agent_id in self._policies:
                policy = self._policies[agent_id]

                # Use canonical extraction
                liquidity_config = self._policy_builder.extract_liquidity_config(
                    policy=policy,
                    agent_config=agent_config,
                )

                # Apply extracted config
                if liquidity_config.get("liquidity_allocation_fraction") is not None:
                    agent_config["liquidity_allocation_fraction"] = (
                        liquidity_config["liquidity_allocation_fraction"]
                    )

                # ... rest of policy handling ...
```

### Integration Tests

```python
class TestOptimizationLoopIntegration:
    """Integration tests for PolicyConfigBuilder in optimization.py."""

    def test_liquidity_fraction_extracted_via_builder(self):
        """Verify optimization uses PolicyConfigBuilder for fraction."""

    def test_consistent_with_sandbox(self):
        """Same policy produces same config in both paths."""
```

---

## Phase 5: Policy Evaluation Identity Tests

**Goal**: Comprehensive end-to-end tests verifying identical evaluation on both paths.

This is the **critical phase** that validates our absolute invariant.

### Gold Standard Identity Tests

```python
class TestPolicyEvaluationIdentity:
    """
    CRITICAL: These tests enforce the Policy Evaluation Identity invariant.

    For any policy P and scenario S:
        cost(main_simulation(P, S)) == cost(bootstrap_evaluation(P, S))

    Any failure here indicates a violation of the invariant.
    """

    def test_identical_liquidity_fraction_extraction(self):
        """Same policy produces identical fraction in both paths."""
        policy = {"parameters": {"initial_liquidity_fraction": 0.3}}
        agent_config = {"liquidity_pool": 10_000_000, "opening_balance": 0}

        # Path 1: Via optimization.py logic
        main_config = build_main_simulation_config(policy, agent_config)

        # Path 2: Via sandbox_config.py logic
        bootstrap_config = build_bootstrap_config(policy, agent_config)

        assert main_config["liquidity_allocation_fraction"] == \
               bootstrap_config["liquidity_allocation_fraction"]

    def test_identical_costs_same_transactions(self):
        """Same policy+transactions produce identical costs on both paths."""

    def test_nested_vs_flat_consistency(self):
        """Nested and flat produce same results in both paths."""

    def test_default_fraction_consistency(self):
        """Default 0.5 applied identically in both paths."""

    def test_full_simulation_vs_bootstrap_cost_match(self):
        """
        Run full simulation and bootstrap evaluation on same scenario.
        Costs must match.

        This is the ultimate identity test.
        """
```

### Property-Based Tests

```python
from hypothesis import given, strategies as st

class TestPolicyEvaluationIdentityPropertyBased:
    """Property-based tests for comprehensive coverage."""

    @given(
        fraction=st.floats(min_value=0.0, max_value=1.0),
        liquidity_pool=st.integers(min_value=0, max_value=100_000_000),
    )
    def test_any_fraction_extracts_identically(self, fraction, liquidity_pool):
        """Any valid fraction value extracts identically in both paths."""

    @given(
        nested=st.booleans(),
        fraction=st.floats(min_value=0.0, max_value=1.0) | st.none(),
    )
    def test_nested_or_flat_always_consistent(self, nested, fraction):
        """Nested or flat structure, always consistent extraction."""
```

---

## Phase 6: Documentation Updates

**Goal**: Update reference documentation to reflect the new pattern.

### Files to Update

1. **`docs/reference/ai_cash_mgmt/index.md`** (or appropriate section)
   - Add section on PolicyConfigBuilder pattern
   - Document the Policy Evaluation Identity invariant

2. **`docs/reference/patterns-and-conventions.md`**
   - Add INV-8: Policy Evaluation Identity invariant
   - Add PolicyConfigBuilder to pattern list

3. **`docs/reference/architecture/`**
   - Update relevant architecture docs

### Documentation Draft Location

Draft documentation will be accumulated in:
`docs/plans/policy-config-protocol/doc-draft.md`

---

## Success Criteria

### Functional Requirements
- [ ] PolicyConfigBuilder protocol defined with full typing
- [ ] StandardPolicyConfigBuilder implementation complete
- [ ] sandbox_config.py uses PolicyConfigBuilder
- [ ] optimization.py uses PolicyConfigBuilder
- [ ] All existing tests pass
- [ ] New identity tests pass

### Non-Functional Requirements
- [ ] No regression in test coverage
- [ ] mypy passes with strict mode
- [ ] ruff passes with no warnings
- [ ] Documentation updated

### Identity Invariant Verification
- [ ] Same policy → same config in both paths
- [ ] Same config → same cost in both paths
- [ ] Property-based tests pass for all valid inputs

---

## Risk Mitigation

### Risk 1: Breaking Existing Behavior
**Mitigation**:
- TDD approach ensures tests define expected behavior first
- Run full test suite after each phase
- Create identity tests before integration

### Risk 2: Type Inconsistencies
**Mitigation**:
- Use TypedDict for explicit typing
- Enable mypy strict mode
- Add type coercion in implementation

### Risk 3: Edge Cases Not Covered
**Mitigation**:
- Property-based testing with Hypothesis
- Explicit None handling tests
- Edge case test category

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1 | ~1 hour | None |
| Phase 2 | ~1 hour | Phase 1 |
| Phase 3 | ~30 min | Phase 2 |
| Phase 4 | ~30 min | Phase 2 |
| Phase 5 | ~1 hour | Phase 3, 4 |
| Phase 6 | ~30 min | Phase 5 |

**Total Estimated Duration**: ~4.5 hours

---

## References

- `docs/reference/api/state-provider.md` - StateProvider pattern (model for this design)
- `docs/reference/patterns-and-conventions.md` - Project patterns and invariants
- `initial_findings.md` - Problem statement and initial design sketch
- `api/CLAUDE.md` - Python code style requirements

---

*Plan created: 2025-12-14*
*Status: Ready for Phase 1*
