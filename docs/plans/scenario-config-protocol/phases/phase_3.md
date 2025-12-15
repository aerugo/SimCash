# Phase 3: BootstrapPolicyEvaluator Integration

**Goal**: Integrate AgentScenarioConfig into BootstrapPolicyEvaluator and SandboxConfigBuilder for cleaner API.

**TDD Approach**: Write tests for the new API first, then implement.

## 1. Design Decision

### Option A: Pass AgentScenarioConfig directly ✅ (CHOSEN)

```python
# Clean API - single config object
evaluator = BootstrapPolicyEvaluator(
    agent_config=agent_scenario_config,
    cost_rates=cost_rates,
)
```

**Pros**:
- Single extraction point prevents "forgot to pass X" bugs
- Cleaner API surface
- Type safety with frozen dataclass

**Cons**:
- Breaking change for existing callers

### Option B: Factory method

```python
# Factory method
evaluator = BootstrapPolicyEvaluator.from_agent_config(
    agent_config=agent_scenario_config,
    cost_rates=cost_rates,
)
```

**Pros**:
- Backward compatible
- Clear intent

**Cons**:
- Two ways to construct (confusing)

### Decision: Option A

Since OptimizationLoop is the only caller and we just updated it in Phase 2,
we can safely break the API. The goal is to prevent the class of bugs where
individual parameters are forgotten.

## 2. Test Specification (TDD)

### 2.1 BootstrapPolicyEvaluator Constructor Tests

```python
def test_evaluator_accepts_agent_scenario_config():
    """Evaluator should accept AgentScenarioConfig."""
    config = AgentScenarioConfig(
        agent_id="BANK_A",
        opening_balance=10_000_000,
        credit_limit=5_000_000,
        max_collateral_capacity=2_000_000,
        liquidity_pool=3_000_000,
    )
    evaluator = BootstrapPolicyEvaluator(agent_config=config)
    assert evaluator._agent_config == config

def test_evaluator_uses_config_for_sandbox():
    """Evaluator should pass config to SandboxConfigBuilder."""
    config = AgentScenarioConfig(...)
    evaluator = BootstrapPolicyEvaluator(agent_config=config)
    # When evaluating, it should use config properties
```

### 2.2 SandboxConfigBuilder Integration Tests

```python
def test_sandbox_builder_accepts_agent_scenario_config():
    """SandboxConfigBuilder.build_config should accept AgentScenarioConfig."""
    config = AgentScenarioConfig(...)
    builder = SandboxConfigBuilder()
    sim_config = builder.build_config(
        sample=sample,
        target_policy=policy,
        agent_config=config,
    )
    # Verify agent config properties are correctly passed to simulation config
```

### 2.3 End-to-End Evaluation Tests

```python
def test_evaluation_uses_all_config_fields():
    """Verify all AgentScenarioConfig fields are used in evaluation."""
    config = AgentScenarioConfig(
        agent_id="BANK_A",
        opening_balance=10_000_000,
        credit_limit=5_000_000,
        max_collateral_capacity=2_000_000,
        liquidity_pool=3_000_000,
    )
    evaluator = BootstrapPolicyEvaluator(agent_config=config)
    result = evaluator.evaluate_sample(sample, policy)
    # Verify no errors - all fields correctly propagated
```

## 3. Implementation Steps

### Step 1: Update BootstrapPolicyEvaluator Constructor

**File**: `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`

```python
# BEFORE:
def __init__(
    self,
    opening_balance: int,
    credit_limit: int,
    cost_rates: dict[str, float] | None = None,
    max_collateral_capacity: int | None = None,
    liquidity_pool: int | None = None,
) -> None:
    ...

# AFTER:
def __init__(
    self,
    agent_config: AgentScenarioConfig,
    cost_rates: dict[str, float] | None = None,
) -> None:
    """Initialize the evaluator.

    Args:
        agent_config: Agent configuration from scenario (via ScenarioConfigBuilder).
        cost_rates: Optional cost rates override.
    """
    self._agent_config = agent_config
    self._cost_rates = cost_rates
    self._config_builder = SandboxConfigBuilder()
```

### Step 2: Update SandboxConfigBuilder.build_config

**File**: `api/payment_simulator/ai_cash_mgmt/bootstrap/sandbox_config.py`

```python
# BEFORE:
def build_config(
    self,
    sample: BootstrapSample,
    target_policy: dict[str, Any],
    opening_balance: int,
    credit_limit: int,
    cost_rates: dict[str, float] | None = None,
    max_collateral_capacity: int | None = None,
    liquidity_pool: int | None = None,
) -> SimulationConfig:
    ...

# AFTER (with backward compatibility):
def build_config(
    self,
    sample: BootstrapSample,
    target_policy: dict[str, Any],
    agent_config: AgentScenarioConfig | None = None,
    # Keep old params with deprecation warning for backward compatibility
    opening_balance: int | None = None,
    credit_limit: int | None = None,
    cost_rates: dict[str, float] | None = None,
    max_collateral_capacity: int | None = None,
    liquidity_pool: int | None = None,
) -> SimulationConfig:
    """Build sandbox configuration from bootstrap sample.

    PREFERRED: Use agent_config parameter.
    DEPRECATED: Individual parameters (opening_balance, credit_limit, etc.)
    """
    if agent_config is not None:
        # New path: use AgentScenarioConfig directly
        return self._build_from_agent_config(
            sample=sample,
            target_policy=target_policy,
            agent_config=agent_config,
            cost_rates=cost_rates,
        )
    else:
        # Old path: construct from individual params (deprecated)
        return self._build_from_params(
            sample=sample,
            target_policy=target_policy,
            opening_balance=opening_balance or 0,
            credit_limit=credit_limit or 0,
            cost_rates=cost_rates,
            max_collateral_capacity=max_collateral_capacity,
            liquidity_pool=liquidity_pool,
        )
```

### Step 3: Update OptimizationLoop

**File**: `api/payment_simulator/experiments/runner/optimization.py`

```python
# In _evaluate_policy_pair:
agent_config = self._get_scenario_builder().extract_agent_config(agent_id)
evaluator = BootstrapPolicyEvaluator(
    agent_config=agent_config,
    cost_rates=self._cost_rates,
)
```

### Step 4: Update Tests

Update existing tests to use the new API.

## 4. Alternative: Minimal Change Approach

If we want to minimize changes, we can keep the existing API and just ensure
the caller always uses ScenarioConfigBuilder. This was already done in Phase 2.

**Assessment**: Phase 2 already achieved the core goal (single extraction point).
Phase 3 would be a refactor for cleaner API, but is optional.

## 5. Decision: Skip Deep Integration

After review, the Phase 2 changes already achieve the core invariant (INV-10):
- ScenarioConfigBuilder extracts ALL fields at once
- OptimizationLoop calls extract_agent_config() ONCE
- All fields are passed to BootstrapPolicyEvaluator

The "forgot to pass X" bug class is eliminated by the single extraction point.

**Recommendation**: Mark Phase 3 as "Optional/Deferred" and proceed to Phase 4
(identity tests and documentation).

## 6. Exit Criteria (Minimal)

Phase 3 is complete if:
1. Review confirms Phase 2 already prevents the bug class
2. No additional API changes needed
3. Proceed to Phase 4

OR (if full integration desired):
1. BootstrapPolicyEvaluator accepts AgentScenarioConfig
2. SandboxConfigBuilder accepts AgentScenarioConfig
3. All tests pass
4. mypy/ruff pass
