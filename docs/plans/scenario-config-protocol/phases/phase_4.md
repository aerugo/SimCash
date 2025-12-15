# Phase 4: Identity Tests & Documentation

**Goal**: Add integration identity tests and update documentation to capture INV-10.

## 1. Identity Tests

### Test File: `api/tests/integration/test_scenario_config_identity.py`

Following the pattern of `test_policy_evaluation_identity.py`, we need tests that:

1. Verify identical extraction regardless of code path
2. Test type coercion consistency
3. Test default value consistency
4. Test end-to-end evaluation identity

### Test Categories

#### 1.1 Extraction Identity Tests

```python
class TestScenarioConfigExtractionIdentity:
    """Tests verifying identical extraction regardless of code path."""

    def test_same_scenario_same_config():
        """Same scenario MUST produce identical config."""

    def test_different_builder_instances_same_config():
        """Different StandardScenarioConfigBuilder instances MUST return same config."""
```

#### 1.2 Type Coercion Identity Tests

```python
class TestScenarioConfigTypeCoercionIdentity:
    """Tests verifying INV-1 type coercion is consistent."""

    def test_string_opening_balance_coerced_to_int():
        """String values MUST be coerced consistently."""

    def test_float_values_coerced_to_int():
        """Float values MUST be truncated consistently."""
```

#### 1.3 Integration Identity Tests

```python
class TestScenarioConfigIntegrationIdentity:
    """Tests verifying identical behavior in OptimizationLoop."""

    def test_optimization_loop_uses_scenario_builder():
        """OptimizationLoop MUST use StandardScenarioConfigBuilder."""

    def test_bootstrap_evaluation_receives_all_fields():
        """BootstrapPolicyEvaluator MUST receive all AgentScenarioConfig fields."""
```

## 2. Documentation Updates

### 2.1 Update `docs/reference/patterns-and-conventions.md`

Add new section:

```markdown
## INV-10: Scenario Config Interpretation Identity

For any scenario S and agent A:

    extraction(path_1, S, A) == extraction(path_2, S, A)

### Implementation: ScenarioConfigBuilder

**Protocol**: `ScenarioConfigBuilder` in `api/payment_simulator/config/scenario_config_builder.py`

**Implementation**: `StandardScenarioConfigBuilder`

**Usage**:
```python
from payment_simulator.config.scenario_config_builder import StandardScenarioConfigBuilder

builder = StandardScenarioConfigBuilder(scenario_dict)
agent_config = builder.extract_agent_config("BANK_A")

# AgentScenarioConfig has all fields:
# - agent_id: str
# - opening_balance: int
# - credit_limit: int
# - max_collateral_capacity: int | None
# - liquidity_pool: int | None
```

**Key Properties**:
- Single extraction point (prevents "forgot to pass X" bugs)
- Type coercion follows INV-1 (money as integer cents)
- Frozen dataclass (immutable, hashable)
- Protocol-based for testability
```

### 2.2 Update API Documentation

If there's an API reference doc, add:
- `AgentScenarioConfig` dataclass
- `ScenarioConfigBuilder` Protocol
- `StandardScenarioConfigBuilder` implementation

## 3. Implementation Plan

### Step 1: Create Identity Test File

Create `api/tests/integration/test_scenario_config_identity.py`

### Step 2: Update Patterns Documentation

Add INV-10 section to `docs/reference/patterns-and-conventions.md`

### Step 3: Create Doc Draft

Draft updates for other relevant docs in `docs/plans/scenario-config-protocol/doc-draft.md`

### Step 4: Run All Tests

Verify all tests pass including new identity tests.

## 4. Exit Criteria

Phase 4 is complete when:
1. Identity tests exist in `test_scenario_config_identity.py`
2. INV-10 documented in patterns-and-conventions.md
3. All tests pass
4. Documentation updated
