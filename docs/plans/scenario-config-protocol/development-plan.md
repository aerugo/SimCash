# ScenarioConfigBuilder Development Plan

**Status**: Complete ✅
**Created**: 2025-12-15
**Completed**: 2025-12-15
**Related**: docs/requests/scenario-config-builder.md

## Problem Statement

The codebase has **multiple parallel helper methods** that extract agent configuration from scenario YAML files. This pattern caused a bug where `liquidity_pool` was missing from bootstrap evaluation (commit `c06a880`), resulting in invalid experiment results.

### Current Anti-Pattern

```python
# OptimizationLoop has 4+ separate extraction methods:
def _get_agent_opening_balance(self, agent_id: str) -> int: ...
def _get_agent_credit_limit(self, agent_id: str) -> int: ...
def _get_agent_max_collateral_capacity(self, agent_id: str) -> int | None: ...
def _get_agent_liquidity_pool(self, agent_id: str) -> int | None: ...

# Each must be called separately, easy to forget one!
evaluator = BootstrapPolicyEvaluator(
    opening_balance=self._get_agent_opening_balance(agent_id),
    credit_limit=self._get_agent_credit_limit(agent_id),
    max_collateral_capacity=self._get_agent_max_collateral_capacity(agent_id),
    liquidity_pool=self._get_agent_liquidity_pool(agent_id),  # WAS MISSING!
)
```

## Solution: ScenarioConfigBuilder Protocol

Following the successful patterns of:
- **StateProvider**: Unified data access for run/replay (INV-5: Replay Identity)
- **PolicyConfigBuilder**: Unified policy parameter extraction (INV-9: Policy Evaluation Identity)

We introduce **ScenarioConfigBuilder** with a new invariant:

### INV-10: Scenario Config Interpretation Identity

> For any scenario S and agent A, scenario configuration extraction MUST produce
> identical results regardless of which code path performs the extraction.

```python
# Both paths MUST use StandardScenarioConfigBuilder
extraction(optimization_path, S, A) == extraction(bootstrap_path, S, A)
```

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│          ScenarioConfigBuilder Protocol                 │
│          (Single Source of Truth)                       │
└────────────────┬───────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │ AgentScenario  │  ← Typed dataclass
         │ Config         │
         └───────┬────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌────────────────┐      ┌──────────────────┐
│ OptimizationLoop│      │ Bootstrap        │
│ (Deterministic  │      │ PolicyEvaluator  │
│  Simulation)    │      │ (Resampling)     │
└────────────────┘      └──────────────────┘
```

## Design

### AgentScenarioConfig (Frozen Dataclass)

```python
@dataclass(frozen=True)
class AgentScenarioConfig:
    """Canonical agent configuration extracted from scenario YAML.

    All monetary values are in integer cents (INV-1).
    This is a value object - immutable and hashable.
    """
    agent_id: str
    opening_balance: int
    credit_limit: int  # unsecured_cap in YAML
    max_collateral_capacity: int | None
    liquidity_pool: int | None
```

### ScenarioConfigBuilder Protocol

```python
@runtime_checkable
class ScenarioConfigBuilder(Protocol):
    """Protocol for extracting agent configuration from scenario.

    Implementations MUST satisfy Scenario Config Interpretation Identity:
    Same (scenario, agent_id) → Same AgentScenarioConfig, always.
    """

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        """Extract all configuration for an agent."""
        ...

    def list_agent_ids(self) -> list[str]:
        """Return all agent IDs in the scenario."""
        ...
```

### StandardScenarioConfigBuilder Implementation

```python
class StandardScenarioConfigBuilder:
    """Canonical implementation of ScenarioConfigBuilder.

    Used by ALL code paths that need agent configuration from scenario YAML.
    This is the SINGLE SOURCE OF TRUTH.
    """

    def __init__(self, scenario_dict: dict[str, Any]) -> None:
        self._scenario = scenario_dict
        self._agents_by_id = {
            agent["id"]: agent
            for agent in scenario_dict.get("agents", [])
        }

    def extract_agent_config(self, agent_id: str) -> AgentScenarioConfig:
        # Single extraction point with canonical coercion
        ...
```

## Phased Development Plan

### Phase 1: Core Protocol and Implementation (TDD)

**Goal**: Create ScenarioConfigBuilder protocol and StandardScenarioConfigBuilder.

**Deliverables**:
1. `api/payment_simulator/config/scenario_config_builder.py`
   - AgentScenarioConfig dataclass
   - ScenarioConfigBuilder Protocol
   - StandardScenarioConfigBuilder implementation
2. `api/tests/unit/test_scenario_config_builder.py`
   - Unit tests for extraction logic
   - Type coercion tests (INV-1)
   - Missing field handling tests
   - Default value tests

**Tests First (TDD)**:
- [ ] Test: Extract opening_balance correctly
- [ ] Test: Extract credit_limit (from unsecured_cap)
- [ ] Test: Extract optional fields (None when not present)
- [ ] Test: Type coercion (string → int, INV-1)
- [ ] Test: Agent not found raises KeyError
- [ ] Test: list_agent_ids returns all IDs

### Phase 2: Migrate OptimizationLoop

**Goal**: Replace 4 helper methods with ScenarioConfigBuilder.

**Deliverables**:
1. Modify `OptimizationLoop.__init__` to create builder
2. Replace helper method calls with `builder.extract_agent_config()`
3. Update `_evaluate_policy_pair` to use builder
4. Delete deprecated helper methods

**Migration Steps**:
1. Add `_scenario_builder: StandardScenarioConfigBuilder` attribute
2. Replace calls to `_get_agent_*` with builder
3. Add integration test verifying identical behavior
4. Remove deprecated methods

### Phase 3: Integrate with BootstrapPolicyEvaluator

**Goal**: Pass AgentScenarioConfig to BootstrapPolicyEvaluator.

**Options Evaluated**:
1. **Option A**: Pass AgentScenarioConfig directly (cleanest)
2. **Option B**: Factory method `from_scenario_config()` (medium)
3. **Option C**: Keep current params (minimal change)

**Decision**: Option A - Pass AgentScenarioConfig directly

**Deliverables**:
1. Add `AgentScenarioConfig` parameter to evaluator
2. Update SandboxConfigBuilder to accept AgentScenarioConfig
3. Remove redundant individual parameters

### Phase 4: Identity Tests and Documentation

**Goal**: Verify INV-10 and update docs.

**Deliverables**:
1. `api/tests/integration/test_scenario_config_identity.py`
   - Identity test: Same scenario → Same config
   - End-to-end: Both paths produce identical configs
2. Update `docs/reference/patterns-and-conventions.md`
   - Add INV-10: Scenario Config Interpretation Identity
   - Document ScenarioConfigBuilder pattern
3. Update `docs/reference/architecture/` as needed

## Success Criteria

- [ ] All extraction happens through StandardScenarioConfigBuilder
- [ ] No more `_get_agent_*` methods in OptimizationLoop
- [ ] BootstrapPolicyEvaluator receives AgentScenarioConfig
- [ ] Identity tests pass for both code paths
- [ ] "Forgot to pass X" class of bugs eliminated
- [ ] Full type safety (mypy/pyright pass)
- [ ] Documentation updated

## Risk Mitigation

### Risk: Breaking existing behavior
**Mitigation**:
- Write identity tests FIRST (TDD)
- Run full test suite after each change
- Compare output before/after migration

### Risk: FFI compatibility
**Mitigation**:
- AgentScenarioConfig is Python-only
- FFI config building remains separate (uses Pydantic → dict)
- No changes to Rust side needed

## Files to Modify

### New Files
- `api/payment_simulator/config/scenario_config_builder.py`
- `api/tests/unit/test_scenario_config_builder.py`
- `api/tests/integration/test_scenario_config_identity.py`

### Modified Files
- `api/payment_simulator/experiments/runner/optimization.py`
- `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`
- `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`
- `docs/reference/patterns-and-conventions.md`

### Deleted Code
- `OptimizationLoop._get_agent_opening_balance()`
- `OptimizationLoop._get_agent_credit_limit()`
- `OptimizationLoop._get_agent_max_collateral_capacity()`
- `OptimizationLoop._get_agent_liquidity_pool()`

## Progress Tracking

| Phase | Status | Start Date | End Date | Notes |
|-------|--------|------------|----------|-------|
| 1     | Not Started | - | - | Core protocol |
| 2     | Not Started | - | - | OptimizationLoop migration |
| 3     | Not Started | - | - | BootstrapPolicyEvaluator integration |
| 4     | Not Started | - | - | Identity tests & docs |

## Appendix: Pattern Comparison

| Builder | Input | Output | Purpose |
|---------|-------|--------|---------|
| `PolicyConfigBuilder` | Policy dict | `LiquidityConfig`, `CollateralConfig` | Canonical policy→config extraction |
| `ScenarioConfigBuilder` | Scenario dict | `AgentScenarioConfig` | Canonical scenario→agent config extraction |
| `StateProvider` | FFI/Database | Various TypedDicts | Canonical state access (replay identity) |

All three patterns share the same philosophy: **single source of truth** to prevent divergence bugs.
