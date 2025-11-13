# Policy-Scenario Testing Framework

## Overview

This framework enables **predictive, scenario-based testing** of payment settlement policies. Unlike traditional unit tests that verify "did it execute?", these tests verify **"did it achieve the expected outcome?"**

## Key Capabilities

1. **Predictive Testing**: Define expected outcomes (settlement rates, costs, queue depths) and verify they're achieved
2. **Comparative Analysis**: Run multiple policies on the same scenario and benchmark performance
3. **Complex Scenarios**: Test policies under crisis conditions with multiple scenario events
4. **TDD Workflow**: Write expectations first, then implement/tune policies
5. **Deterministic**: Same seed = same results (critical for debugging)

## Quick Start

### Basic Test Example

```python
from policy_scenario import (
    PolicyScenarioTest,
    OutcomeExpectation,
    Range,
    Exact,
    ScenarioBuilder
)

# 1. Define scenario
scenario = (
    ScenarioBuilder("HighPressure")
    .with_description("High arrival rate stress test")
    .with_duration(100)
    .add_agent("BANK_A", balance=5_000_000, arrival_rate=4.0)
    .add_agent("BANK_B", balance=20_000_000)
    .build()
)

# 2. Define policy
policy = {
    "type": "LiquidityAware",
    "target_buffer": 2_000_000,
    "urgency_threshold": 5
}

# 3. Define expected outcomes
expectations = OutcomeExpectation(
    settlement_rate=Range(min=0.80, max=1.0),
    overdraft_violations=Exact(0),
    max_queue_depth=Range(min=0, max=50)
)

# 4. Run and verify
test = PolicyScenarioTest(policy, scenario, expectations, agent_id="BANK_A")
result = test.run()

assert result.passed, result.detailed_report()
```

### Comparative Test Example

```python
from policy_scenario import PolicyComparator

comparator = PolicyComparator(scenario)

result = comparator.compare(
    policies=[
        ("FIFO", {"type": "Fifo"}),
        ("LiquidityAware", {
            "type": "LiquidityAware",
            "target_buffer": 2_000_000,
            "urgency_threshold": 5
        }),
        ("DeadlineAware", {
            "type": "Deadline",
            "urgency_threshold": 5
        })
    ],
    metrics=["settlement_rate", "deadline_violations", "max_queue_depth"],
    agent_id="BANK_A"
)

print(result.comparison_table())
```

## Architecture Components

### 1. OutcomeExpectation

Defines expected metrics with constraints:

- **Range**: Min/max bounds (e.g., `Range(min=0.85, max=1.0)`)
- **Exact**: Exact value (e.g., `Exact(0)` for zero violations)

**Available Metrics**:
- `settlement_rate`: Proportion of transactions settled (0.0-1.0)
- `avg_settlement_delay`: Average ticks from arrival to settlement
- `num_settlements`: Total settlements
- `max_queue_depth`: Peak queue size
- `avg_queue_depth`: Average queue size
- `total_cost`: Total costs (cents)
- `overdraft_violations`: Number of ticks with illegal overdraft
- `deadline_violations`: Transactions that missed deadline
- `min_balance`, `avg_balance`, `max_balance`: Balance metrics (cents)
- `custom_metrics`: Dict for policy-specific metrics

### 2. ScenarioBuilder

Fluent API for building scenarios:

```python
scenario = (
    ScenarioBuilder("MyScenario")
    .with_description("Description here")
    .with_duration(ticks=200)
    .with_ticks_per_day(100)
    .with_seed(12345)
    .add_agent(
        "BANK_A",
        balance=5_000_000,
        credit_limit=1_000_000,
        arrival_rate=3.0,
        arrival_amount_range=(100_000, 300_000),
        deadline_range=(5, 30)
    )
    .add_collateral_adjustment(
        tick=100,
        agent_id="BANK_A",
        haircut_change=-0.2  # Margin call
    )
    .add_arrival_rate_change(
        tick=150,
        multiplier=2.0  # Market spike
    )
    .add_large_payment(
        tick=180,
        sender="BANK_A",
        receiver="BANK_B",
        amount=2_000_000,
        deadline_offset=10
    )
    .build()
)
```

### 3. PolicyScenarioTest

Runs a single policy against a scenario and verifies expectations:

```python
test = PolicyScenarioTest(
    policy=policy_config_dict,
    scenario=scenario_definition,
    expectations=outcome_expectation,
    agent_id="BANK_A"  # Agent to collect metrics for
)

result = test.run()

if result.passed:
    print("✓ Test passed!")
else:
    print(result.detailed_report())
```

**Result includes**:
- `actual`: ActualMetrics collected
- `expected`: OutcomeExpectation
- `passed`: bool
- `failures`: List of ExpectationFailure objects
- `detailed_report()`: Human-readable report

### 4. PolicyComparator

Compares multiple policies on the same scenario:

```python
comparator = PolicyComparator(scenario)

result = comparator.compare(
    policies=[
        ("Policy1", config1),
        ("Policy2", config2),
    ],
    metrics=["settlement_rate", "total_cost"],
    agent_id="BANK_A"
)

# Get specific metric
sr1 = result.get_metric("Policy1", "settlement_rate")

# Print comparison table
print(result.comparison_table())
```

## Testing Levels

### Level 1: Simple Predictive Tests

Single policy, simple scenario, clear expectations.

**Use for**: Verifying basic policy behavior

**Example**: "LiquidityAware maintains buffer under pressure"

See: `test_policy_scenario_simple.py`

### Level 2: Comparative Tests

Multiple policies, same scenario, relative performance.

**Use for**: Policy benchmarking

**Example**: "LiquidityAware preserves balance better than FIFO"

See: `test_policy_scenario_comparative.py`

### Level 3: Complex Scenarios

Multi-event crisis scenarios with sophisticated expectations.

**Use for**: Stress testing policies

**Example**: "BalancedOptimizer handles liquidity crisis with acceptable costs"

See: `test_policy_scenario_complex.py` (TODO)

### Level 4: Parameter Optimization

Find optimal parameter values for a policy.

**Use for**: Policy tuning

**Example**: "Determine optimal buffer size for LiquidityAware"

## Running Tests

### Setup Environment

```bash
cd api
uv sync --extra dev
```

### Run All Policy-Scenario Tests

```bash
.venv/bin/python -m pytest tests/integration/test_policy_scenario_*.py -v
```

### Run Specific Test

```bash
.venv/bin/python -m pytest tests/integration/test_policy_scenario_simple.py::TestFifoPolicy::test_fifo_with_ample_liquidity_settles_all -xvs
```

### Run Comparative Tests

```bash
.venv/bin/python -m pytest tests/integration/test_policy_scenario_comparative.py -v
```

## Example Test Output

### Successful Test

```
Policy-Scenario Test Results
======================================================================
Policy: LiquidityAware
  Parameters: {'target_buffer': 2000000, 'urgency_threshold': 5}

Scenario: HighPressure
  Description: High arrival rate stress test
  Duration: 100 ticks
  Agents: 2

Result: PASSED

Metric Comparison:
----------------------------------------------------------------------
  ✓  settlement_rate: 0.872 (expected: Range(0.8, 1.0))
  ✓  overdraft_violations: 0 (expected: Exact(0))
  ✓  max_queue_depth: 23 (expected: Range(0, 50))
  ✓  min_balance: $125,000.00 (expected: Range(≥0))

======================================================================
```

### Failed Test

```
Policy-Scenario Test Results
======================================================================
Policy: LiquidityAware
  Parameters: {'target_buffer': 5000000, 'urgency_threshold': 5}

Scenario: HighPressure
  Duration: 100 ticks

Result: FAILED

Metric Comparison:
----------------------------------------------------------------------
  ✓  settlement_rate: 0.450 (expected: Range(0.8, 1.0))
  ✗  max_queue_depth: 67 (expected: Range(0, 50)) - EXCEEDED by 17
      Deviation: 17.00
  ✓  overdraft_violations: 0 (expected: Exact(0))

Failed Expectations:
----------------------------------------------------------------------
  • max_queue_depth: 67 (expected ≤50, above by 17)

======================================================================
```

### Comparison Output

```
Policy Comparison: HighPressure
======================================================================
+----------------+------------------+-----------------------+-----------------+
| Policy         | settlement_rate  | deadline_violations   | max_queue_depth |
+----------------+------------------+-----------------------+-----------------+
| FIFO           | 0.920            | 8                     | 18              |
| LiquidityAware | 0.872            | 12                    | 23              |
| DeadlineAware  | 0.895            | 3                     | 20              |
+----------------+------------------+-----------------------+-----------------+

Best Performance:
  settlement_rate: FIFO (0.920)
  deadline_violations: DeadlineAware (3)
  max_queue_depth: FIFO (18)
```

## Design Principles

1. **Determinism First**: Same seed + same config = same results
2. **Clear Failures**: Report shows exactly what failed and by how much
3. **Composable**: Reusable scenarios, policies, expectations
4. **Extensible**: Custom metrics, custom scenarios
5. **TDD-Friendly**: Write expectations before implementation

## Common Patterns

### Testing Policy Under Various Conditions

```python
# Test same policy under different scenarios
policy = {"type": "LiquidityAware", "target_buffer": 2_000_000, "urgency_threshold": 5}

low_pressure = ScenarioBuilder("LowPressure").with_duration(100).add_agent("BANK_A", balance=10_000_000, arrival_rate=1.0).build()
high_pressure = ScenarioBuilder("HighPressure").with_duration(100).add_agent("BANK_A", balance=10_000_000, arrival_rate=5.0).build()

# Expect better performance under low pressure
low_expectations = OutcomeExpectation(settlement_rate=Range(min=0.95, max=1.0))
high_expectations = OutcomeExpectation(settlement_rate=Range(min=0.75, max=1.0))
```

### Finding Optimal Parameters

```python
buffers = [1_000_000, 2_000_000, 3_000_000, 5_000_000]
results = []

for buffer in buffers:
    policy = {"type": "LiquidityAware", "target_buffer": buffer, "urgency_threshold": 5}
    test = PolicyScenarioTest(policy, scenario, minimal_expectations)
    result = test.run()
    results.append((buffer, result.actual.total_cost))

# Find buffer with minimum cost
optimal = min(results, key=lambda x: x[1])
print(f"Optimal buffer: ${optimal[0]/100:.2f} (cost: ${optimal[1]/100:.2f})")
```

### Regression Testing

```python
# Store baseline results
baseline = {
    "settlement_rate": 0.875,
    "max_queue_depth": 22,
    "deadline_violations": 8
}

# Test new policy version
result = test.run()

# Verify no regression (within tolerance)
assert abs(result.actual.settlement_rate - baseline["settlement_rate"]) < 0.05
assert abs(result.actual.max_queue_depth - baseline["max_queue_depth"]) < 5
```

## Extending the Framework

### Adding Custom Metrics

```python
# In your test
expectations = OutcomeExpectation(
    settlement_rate=Range(min=0.85, max=1.0),
    custom_metrics={
        "bilateral_settlements": Range(min=5, max=20),
        "lsm_efficiency": Range(min=0.6, max=1.0)
    }
)

# Collect custom metrics
collector = MetricsCollector("BANK_A")
# ... during simulation ...
collector.custom_metrics["bilateral_settlements"] = count_bilaterals(events)
collector.custom_metrics["lsm_efficiency"] = calculate_lsm_efficiency(events)
```

### Custom Scenario Events

```python
scenario = (
    ScenarioBuilder("CustomScenario")
    .add_event(
        tick=100,
        event_type="CustomEventType",
        param1=value1,
        param2=value2
    )
    .build()
)
```

## Tips and Best Practices

1. **Use Deterministic Seeds**: Always specify `with_seed()` for reproducibility
2. **Start Simple**: Test with Level 1 tests first, then progress to comparative
3. **Meaningful Tolerances**: Use Range bounds that reflect acceptable variance
4. **Print Results**: Use `print(result.detailed_report())` when debugging
5. **Comparative Tests**: Always run FIFO as baseline for comparison
6. **Document Assumptions**: Add comments explaining why you expect certain outcomes

## Troubleshooting

### Test Failures

**Symptom**: Test fails with "settlement_rate below expected"

**Fix**: Check if scenario is too demanding. Adjust either:
- Scenario parameters (lower arrival rate, higher balance)
- Expectations (widen Range bounds)
- Policy parameters (tune for scenario)

**Symptom**: "Metric not collected"

**Fix**: Verify MetricsCollector is recording the metric during simulation

### Import Errors

**Symptom**: `ModuleNotFoundError: No module named 'policy_scenario'`

**Fix**: Tests must be run via pytest from the `api/` directory:
```bash
cd api
.venv/bin/python -m pytest tests/integration/test_policy_scenario_*.py
```

### Non-Determinism

**Symptom**: Same test produces different results

**Fix**: Ensure:
1. Scenario has fixed seed: `.with_seed(12345)`
2. No external randomness (system time, etc.)
3. Orchestrator config is identical

## Architecture Documentation

For detailed architecture design, see:
- [`docs/policy_scenario_testing_architecture.md`](../../../../docs/policy_scenario_testing_architecture.md)

For policy DSL reference:
- [`docs/policy_dsl_guide.md`](../../../../docs/policy_dsl_guide.md)

## Examples

- **Simple Tests**: `test_policy_scenario_simple.py`
- **Comparative Tests**: `test_policy_scenario_comparative.py`
- **Complex Tests**: `test_policy_scenario_complex.py` (TODO)

---

**Status**: Framework Implemented (Nov 2025)
**Next Steps**: Add Level 3 complex scenario tests, visualization tools
