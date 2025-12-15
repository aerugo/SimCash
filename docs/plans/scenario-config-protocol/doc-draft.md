# ScenarioConfigBuilder Documentation Draft

## Summary of Documentation Updates

### 1. `docs/reference/patterns-and-conventions.md`

Added the following sections:

#### INV-10: Scenario Config Interpretation Identity

Added as a new invariant after INV-9, describing:
- The rule for identical extraction
- Requirements for using StandardScenarioConfigBuilder
- Where it applies (optimization.py, BootstrapPolicyEvaluator)
- Rationale including reference to the bug that motivated it

#### Pattern 8: ScenarioConfigBuilder

Added as a new architectural pattern after Pattern 7 (PolicyConfigBuilder), including:
- Purpose statement linked to INV-10
- AgentScenarioConfig dataclass definition
- ScenarioConfigBuilder Protocol definition
- StandardScenarioConfigBuilder as the canonical implementation
- Usage example showing single extraction point
- Key features (immutable, type coercion, defaults)
- Anti-patterns to avoid
- Related file references

## Files Modified

1. `/docs/reference/patterns-and-conventions.md` - Added INV-10 and Pattern 8

## Files Created

1. `/api/payment_simulator/config/scenario_config_builder.py` - Protocol and implementation
2. `/api/tests/unit/test_scenario_config_builder.py` - Unit tests (27 tests)
3. `/api/tests/integration/test_scenario_config_identity.py` - Identity tests (16 tests)
4. Various phase planning documents in `/docs/plans/scenario-config-protocol/`

## Key Changes to Existing Files

1. `/api/payment_simulator/experiments/runner/optimization.py`:
   - Added `StandardScenarioConfigBuilder` import
   - Added `_scenario_builder` attribute
   - Added `_get_scenario_builder()` method
   - Updated `_evaluate_policy_pair()` to use ScenarioConfigBuilder
   - Removed 4 deprecated helper methods:
     - `_get_agent_opening_balance()`
     - `_get_agent_credit_limit()`
     - `_get_agent_max_collateral_capacity()`
     - `_get_agent_liquidity_pool()`

2. `/api/tests/integration/test_real_bootstrap_evaluation.py`:
   - Updated `TestAgentConfigHelpers` → `TestAgentConfigExtraction`
   - Updated tests to use ScenarioConfigBuilder pattern

## Cross-Reference Checklist

The following documentation references should be consistent:

- [x] INV-10 references INV-9 (Policy Evaluation Identity)
- [x] INV-10 references INV-1 (Money is Always i64)
- [x] Pattern 8 references INV-10
- [x] Pattern 8 references Pattern 7 (PolicyConfigBuilder)
- [x] CLAUDE.md root file lists Pattern 8 approach
