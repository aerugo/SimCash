# Phase 2: Migrate OptimizationLoop to ScenarioConfigBuilder

**Goal**: Replace the 4 helper methods in OptimizationLoop with ScenarioConfigBuilder.

**TDD Approach**: Write migration tests FIRST, then perform migration.

## 1. Current State Analysis

### Methods to Replace

From `api/payment_simulator/experiments/runner/optimization.py`:

```python
def _get_agent_opening_balance(self, agent_id: str) -> int:
    """Get opening balance for an agent from scenario config."""
    scenario = self._load_scenario_config()
    for agent in scenario.get("agents", []):
        if agent.get("id") == agent_id:
            return int(agent.get("opening_balance", 0))
    return 0

def _get_agent_credit_limit(self, agent_id: str) -> int:
    """Get credit limit (unsecured_cap) for an agent from scenario config."""
    # Similar pattern...

def _get_agent_max_collateral_capacity(self, agent_id: str) -> int | None:
    """Get max collateral capacity for an agent from scenario config."""
    # Similar pattern...

def _get_agent_liquidity_pool(self, agent_id: str) -> int | None:
    """Get liquidity pool for an agent from scenario config."""
    # Similar pattern...
```

### Usage Sites (in `_evaluate_policy_pair`)

```python
evaluator = BootstrapPolicyEvaluator(
    opening_balance=self._get_agent_opening_balance(agent_id),
    credit_limit=self._get_agent_credit_limit(agent_id),
    cost_rates=self._cost_rates,
    max_collateral_capacity=self._get_agent_max_collateral_capacity(agent_id),
    liquidity_pool=self._get_agent_liquidity_pool(agent_id),
)
```

## 2. Test Specification (TDD)

### 2.1 Identity Tests (Before Migration)

First, capture current behavior to ensure migration doesn't break anything:

```python
def test_optimization_loop_extracts_config_correctly():
    """Current extraction methods produce expected values."""
    # Create scenario with known values
    scenario = {
        "agents": [
            {
                "id": "BANK_A",
                "opening_balance": 1_000_000,
                "unsecured_cap": 500_000,
                "max_collateral_capacity": 200_000,
                "liquidity_pool": 300_000,
            }
        ]
    }

    loop = OptimizationLoop(config=..., config_dir=...)
    loop._scenario_dict = scenario  # Inject scenario

    # Current methods
    assert loop._get_agent_opening_balance("BANK_A") == 1_000_000
    assert loop._get_agent_credit_limit("BANK_A") == 500_000
    assert loop._get_agent_max_collateral_capacity("BANK_A") == 200_000
    assert loop._get_agent_liquidity_pool("BANK_A") == 300_000
```

### 2.2 Post-Migration Tests

After migration, verify builder produces identical results:

```python
def test_scenario_builder_matches_old_methods():
    """ScenarioConfigBuilder produces same values as old methods."""
    scenario = {
        "agents": [{"id": "BANK_A", "opening_balance": 1_000_000, ...}]
    }
    builder = StandardScenarioConfigBuilder(scenario)
    config = builder.extract_agent_config("BANK_A")

    # Must match old behavior
    assert config.opening_balance == 1_000_000
    assert config.credit_limit == 500_000
    # etc.
```

## 3. Migration Steps

### Step 1: Add `_scenario_builder` attribute

Add to `OptimizationLoop.__init__`:

```python
# In __init__, after _scenario_dict is set to None:
self._scenario_builder: StandardScenarioConfigBuilder | None = None
```

Add property to lazily initialize:

```python
@property
def _get_scenario_builder(self) -> StandardScenarioConfigBuilder:
    """Get or create StandardScenarioConfigBuilder."""
    if self._scenario_builder is None:
        scenario = self._load_scenario_config()
        self._scenario_builder = StandardScenarioConfigBuilder(scenario)
    return self._scenario_builder
```

### Step 2: Update `_evaluate_policy_pair`

Replace individual calls with builder extraction:

```python
# BEFORE:
evaluator = BootstrapPolicyEvaluator(
    opening_balance=self._get_agent_opening_balance(agent_id),
    credit_limit=self._get_agent_credit_limit(agent_id),
    cost_rates=self._cost_rates,
    max_collateral_capacity=self._get_agent_max_collateral_capacity(agent_id),
    liquidity_pool=self._get_agent_liquidity_pool(agent_id),
)

# AFTER:
agent_config = self._get_scenario_builder.extract_agent_config(agent_id)
evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config.opening_balance,
    credit_limit=agent_config.credit_limit,
    cost_rates=self._cost_rates,
    max_collateral_capacity=agent_config.max_collateral_capacity,
    liquidity_pool=agent_config.liquidity_pool,
)
```

### Step 3: Delete deprecated methods

After tests pass, delete:
- `_get_agent_opening_balance`
- `_get_agent_credit_limit`
- `_get_agent_max_collateral_capacity`
- `_get_agent_liquidity_pool`

### Step 4: Update imports

Add to imports:

```python
from payment_simulator.config.scenario_config_builder import (
    StandardScenarioConfigBuilder,
)
```

## 4. Verification

After migration:

- [ ] All existing tests pass
- [ ] BootstrapPolicyEvaluator receives correct values
- [ ] No deprecated methods remain
- [ ] mypy passes
- [ ] ruff passes

## 5. Files to Modify

- `api/payment_simulator/experiments/runner/optimization.py`

## 6. Rollback Plan

If issues arise:
1. Git stash/revert changes
2. Re-run test suite to confirm rollback
3. Investigate issue before re-attempting

## 7. Exit Criteria

Phase 2 is complete when:
1. OptimizationLoop uses StandardScenarioConfigBuilder
2. All 4 helper methods are deleted
3. All tests pass
4. Extraction is now a single operation (can't forget fields)
