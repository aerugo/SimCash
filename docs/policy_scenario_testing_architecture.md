# Policy-Scenario Testing Architecture

## Overview

This document describes the **Policy-Scenario Testing Architecture** - a comprehensive framework for testing payment settlement policies against defined scenarios with predicted outcomes.

## Problem Statement

Traditional unit testing focuses on implementation correctness, but policies in the payment simulator require **behavioral validation**:

- **Question**: "Given Policy X operating under Scenario Y, will outcome Z be achieved?"
- **Gap**: Current tests verify "policy executed" but not "policy achieved intended outcome"
- **Need**: Framework to define expected outcomes, run scenarios, and measure deviation

## Design Principles

1. **Predictive Testing**: Define expected outcomes with tolerance ranges
2. **TDD-Friendly**: Write expectations first, then verify behavior
3. **Composable**: Reusable components for building complex scenarios
4. **Clear Failures**: Detailed reporting when expectations aren't met
5. **Comparative**: Support multi-policy benchmarking
6. **Incremental Complexity**: Simple scenarios → Complex scenarios

## Architecture Components

### 1. OutcomeExpectation

**Purpose**: Define expected metrics and tolerances for a policy-scenario combination.

```python
@dataclass
class OutcomeExpectation:
    """Expected outcome metrics with tolerance ranges."""

    # Settlement metrics
    settlement_rate: Optional[Range] = None          # e.g., Range(min=0.85, max=1.0)
    avg_settlement_delay: Optional[Range] = None     # Average ticks from arrival to settlement

    # Queue metrics
    max_queue_depth: Optional[Range] = None          # Peak queue size
    avg_queue_depth: Optional[Range] = None          # Average queue size

    # Financial metrics
    total_cost: Optional[Range] = None               # Total costs incurred (cents)
    overdraft_violations: Optional[Exact] = None     # Exact count expected
    deadline_violations: Optional[Range] = None      # Count of missed deadlines

    # Liquidity metrics
    min_balance: Optional[Range] = None              # Lowest balance reached
    avg_balance: Optional[Range] = None              # Average balance

    # Policy-specific metrics (extensible)
    custom_metrics: Optional[Dict[str, Range]] = None
```

**Example**:
```python
# Expect high settlement rate with controlled queue
liquidity_aware_expectation = OutcomeExpectation(
    settlement_rate=Range(min=0.85, max=1.0),
    max_queue_depth=Range(min=0, max=15),
    overdraft_violations=Exact(0),
    min_balance=Range(min=0, max=float('inf'))
)
```

### 2. ScenarioDefinition

**Purpose**: Declarative scenario specification with parameters.

```python
@dataclass
class ScenarioDefinition:
    """Defines a test scenario with arrival patterns and events."""

    name: str
    description: str
    duration_ticks: int

    # Agent configurations
    agents: List[AgentScenarioConfig]

    # Scenario events (optional)
    events: List[ScenarioEvent] = field(default_factory=list)

    # Cost environment
    cost_rates: Optional[CostRates] = None

    # RNG seed for determinism
    seed: int = 12345
```

**Example**:
```python
high_pressure_scenario = ScenarioDefinition(
    name="HighPressure",
    description="High arrival rate that drains liquidity",
    duration_ticks=100,
    agents=[
        AgentScenarioConfig(
            agent_id="BANK_A",
            opening_balance=1_000_000,  # Low liquidity
            arrival_rate=5.0,            # High pressure
            arrival_amount_range=(100_000, 250_000),
            deadline_range=(10, 40)
        ),
        AgentScenarioConfig(
            agent_id="BANK_B",
            opening_balance=20_000_000,
            arrival_rate=0.0             # Receiver only
        )
    ]
)
```

### 3. PolicyScenarioTest

**Purpose**: Combines policy, scenario, and expectations into a runnable test.

```python
class PolicyScenarioTest:
    """Executable policy-scenario test with outcome verification."""

    def __init__(
        self,
        policy: PolicyConfig,
        scenario: ScenarioDefinition,
        expectations: OutcomeExpectation
    ):
        self.policy = policy
        self.scenario = scenario
        self.expectations = expectations

    def run(self) -> PolicyScenarioResult:
        """Run simulation and collect metrics."""
        # 1. Build orchestrator config from scenario + policy
        # 2. Run simulation for scenario.duration_ticks
        # 3. Collect metrics during execution
        # 4. Compare actual vs expected
        # 5. Return result with pass/fail + details
```

**Example**:
```python
test = PolicyScenarioTest(
    policy=PolicyConfig.LiquidityAware(
        target_buffer=200_000,
        urgency_threshold=5
    ),
    scenario=high_pressure_scenario,
    expectations=liquidity_aware_expectation
)

result = test.run()
assert result.passed, result.detailed_report()
```

### 4. PolicyScenarioResult

**Purpose**: Captures actual outcomes and comparison with expectations.

```python
@dataclass
class PolicyScenarioResult:
    """Results of running a policy-scenario test."""

    # Actual metrics collected
    actual: ActualMetrics

    # Expected metrics
    expected: OutcomeExpectation

    # Comparison results
    passed: bool
    failures: List[ExpectationFailure]

    def detailed_report(self) -> str:
        """Generate human-readable test report."""
        # Show expected vs actual for each metric
        # Highlight failures with deviation amounts
        # Include suggestions for threshold adjustments
```

**Example Output**:
```
Policy-Scenario Test Results
============================
Policy: LiquidityAware(buffer=200000, urgency=5)
Scenario: HighPressure (100 ticks, 5.0 arrivals/tick)

✓ Settlement Rate: 0.87 (expected: 0.85-1.0)
✗ Max Queue Depth: 23 (expected: 0-15) - EXCEEDED by 8
✓ Overdraft Violations: 0 (expected: exactly 0)
✓ Min Balance: 125,000 (expected: ≥0)

FAILED: 1 expectation not met
```

### 5. PolicyComparator

**Purpose**: Run multiple policies against the same scenario for benchmarking.

```python
class PolicyComparator:
    """Compare multiple policies on the same scenario."""

    def __init__(self, scenario: ScenarioDefinition):
        self.scenario = scenario

    def compare(
        self,
        policies: List[Tuple[str, PolicyConfig]],
        metrics: List[str]
    ) -> ComparisonResult:
        """Run all policies and compare specified metrics."""
        # Run each policy with same seed
        # Collect same metrics from all runs
        # Generate comparison table/chart
```

**Example**:
```python
comparator = PolicyComparator(high_pressure_scenario)

result = comparator.compare(
    policies=[
        ("FIFO", PolicyConfig.Fifo),
        ("LiquidityAware", PolicyConfig.LiquidityAware(
            target_buffer=200_000, urgency_threshold=5
        )),
        ("DeadlineAware", PolicyConfig.Deadline(urgency_threshold=5))
    ],
    metrics=["settlement_rate", "max_queue_depth", "deadline_violations"]
)

print(result.comparison_table())
```

**Output**:
```
Policy Comparison on HighPressure Scenario
==========================================
Policy              Settlement Rate   Max Queue   Deadline Violations
--------------      ---------------   ---------   -------------------
FIFO                0.92              18          5
LiquidityAware      0.87              23          8
DeadlineAware       0.89              20          2

Best: DeadlineAware (fewest violations)
```

### 6. ScenarioBuilder (Fluent API)

**Purpose**: Convenient API for building scenarios programmatically.

```python
class ScenarioBuilder:
    """Fluent API for constructing scenarios."""

    def __init__(self, name: str):
        self._scenario = ScenarioDefinition(name=name, ...)

    def with_duration(self, ticks: int) -> 'ScenarioBuilder':
        self._scenario.duration_ticks = ticks
        return self

    def add_agent(
        self,
        agent_id: str,
        balance: int,
        arrival_rate: float = 0.0,
        **kwargs
    ) -> 'ScenarioBuilder':
        # ...
        return self

    def add_crisis_event(
        self,
        tick: int,
        event_type: str,
        **params
    ) -> 'ScenarioBuilder':
        # ...
        return self

    def build(self) -> ScenarioDefinition:
        return self._scenario
```

**Example**:
```python
crisis_scenario = (
    ScenarioBuilder("LiquidityCrisis")
    .with_duration(200)
    .add_agent("BANK_A", balance=1_000_000, arrival_rate=3.0)
    .add_agent("BANK_B", balance=500_000, arrival_rate=2.0)
    .add_crisis_event(
        tick=50,
        event_type="collateral_adjustment",
        agent_id="BANK_A",
        haircut_change=-0.2  # Margin call
    )
    .add_crisis_event(
        tick=100,
        event_type="global_arrival_rate_change",
        multiplier=2.0  # Activity spike
    )
    .build()
)
```

## Testing Workflow

### Level 1: Simple Predictive Test

**Goal**: Verify single policy achieves expected outcome in simple scenario.

```python
def test_liquidity_aware_maintains_buffer_under_pressure():
    """LiquidityAware should maintain buffer despite high arrival rate."""

    # Define scenario
    scenario = ScenarioBuilder("HighPressure") \
        .with_duration(100) \
        .add_agent("BANK_A", balance=1_000_000, arrival_rate=5.0) \
        .add_agent("BANK_B", balance=20_000_000) \
        .build()

    # Define policy
    policy = PolicyConfig.LiquidityAware(
        target_buffer=300_000,
        urgency_threshold=5
    )

    # Define expectations
    expectations = OutcomeExpectation(
        settlement_rate=Range(min=0.80, max=1.0),
        min_balance=Range(min=0, max=float('inf')),  # No overdraft
        overdraft_violations=Exact(0)
    )

    # Run test
    test = PolicyScenarioTest(policy, scenario, expectations)
    result = test.run()

    assert result.passed, result.detailed_report()
```

### Level 2: Comparative Test

**Goal**: Verify policy outperforms baseline on specific metrics.

```python
def test_deadline_policy_reduces_violations_vs_fifo():
    """DeadlineAware should have fewer violations than FIFO."""

    scenario = create_mixed_deadline_scenario()

    comparator = PolicyComparator(scenario)
    result = comparator.compare(
        policies=[
            ("FIFO", PolicyConfig.Fifo),
            ("DeadlineAware", PolicyConfig.Deadline(urgency_threshold=5))
        ],
        metrics=["deadline_violations", "settlement_rate"]
    )

    # DeadlineAware should have fewer violations
    assert result.get_metric("DeadlineAware", "deadline_violations") < \
           result.get_metric("FIFO", "deadline_violations")

    # While maintaining reasonable settlement rate
    assert result.get_metric("DeadlineAware", "settlement_rate") >= 0.75
```

### Level 3: Complex Multi-Event Scenario

**Goal**: Verify policy handles complex crisis with multiple scenario events.

```python
def test_balanced_optimizer_handles_liquidity_crisis():
    """BalancedCostOptimizer should navigate crisis with acceptable costs."""

    # Complex scenario with multiple crisis events
    scenario = (
        ScenarioBuilder("LiquidityCrisis")
        .with_duration(500)
        .add_agent("BANK_A", balance=5_000_000, arrival_rate=2.0)
        .add_agent("BANK_B", balance=3_000_000, arrival_rate=1.5)
        .add_crisis_event(tick=100, event_type="collateral_haircut", amount=-0.3)
        .add_crisis_event(tick=150, event_type="global_arrival_spike", multiplier=3.0)
        .add_crisis_event(tick=300, event_type="large_payment", amount=2_000_000)
        .build()
    )

    policy = load_policy_json("balanced_cost_optimizer.json")

    expectations = OutcomeExpectation(
        settlement_rate=Range(min=0.75, max=1.0),
        total_cost=Range(min=0, max=500_000),  # Cost control
        overdraft_violations=Range(min=0, max=5),  # Some acceptable
        deadline_violations=Range(min=0, max=10)
    )

    test = PolicyScenarioTest(policy, scenario, expectations)
    result = test.run()

    assert result.passed, result.detailed_report()
```

### Level 4: Policy Optimization

**Goal**: Find optimal parameter values for a policy.

```python
def test_find_optimal_liquidity_buffer():
    """Determine optimal buffer size for LiquidityAware policy."""

    scenario = create_realistic_daily_scenario()

    buffer_values = [100_000, 200_000, 300_000, 500_000, 1_000_000]
    results = []

    for buffer in buffer_values:
        policy = PolicyConfig.LiquidityAware(
            target_buffer=buffer,
            urgency_threshold=5
        )

        test = PolicyScenarioTest(
            policy=policy,
            scenario=scenario,
            expectations=OutcomeExpectation(
                settlement_rate=Range(min=0.85, max=1.0)
            )
        )

        result = test.run()
        results.append((buffer, result.actual.total_cost, result.passed))

    # Find minimum cost that passes expectations
    passing_results = [(b, c) for b, c, passed in results if passed]
    optimal_buffer, min_cost = min(passing_results, key=lambda x: x[1])

    print(f"Optimal buffer: ${optimal_buffer/100:.2f} with cost ${min_cost/100:.2f}")
```

## Implementation Plan

### Phase 1: Core Framework (TDD)
1. Implement `Range`, `Exact` constraint types
2. Implement `OutcomeExpectation` with validation
3. Implement `ActualMetrics` collector
4. Implement `PolicyScenarioResult` with comparison logic
5. Write unit tests for each component

### Phase 2: Test Runner
1. Implement `PolicyScenarioTest.run()`
2. Integrate with Orchestrator FFI
3. Collect metrics during simulation
4. Generate comparison reports
5. Write integration test for simple scenario

### Phase 3: Builders & Utilities
1. Implement `ScenarioBuilder` fluent API
2. Implement `PolicyComparator`
3. Add helper functions for common scenarios
4. Write example tests demonstrating usage

### Phase 4: Advanced Features
1. Support for JSON policy loading
2. Regression testing (store baseline results)
3. Performance profiling integration
4. Visualization of results (charts)

## File Structure

```
api/tests/
├── integration/
│   └── policy_scenario/
│       ├── __init__.py
│       ├── framework.py          # Core classes (OutcomeExpectation, etc.)
│       ├── expectations.py       # Constraint types (Range, Exact, etc.)
│       ├── metrics.py            # Metrics collection
│       ├── builders.py           # ScenarioBuilder
│       ├── comparators.py        # PolicyComparator
│       └── test_examples.py      # Example tests
└── integration/
    ├── test_policy_scenario_simple.py       # Level 1 tests
    ├── test_policy_scenario_comparative.py  # Level 2 tests
    └── test_policy_scenario_complex.py      # Level 3-4 tests
```

## Success Criteria

A successful implementation should:

1. **Enable Predictive Testing**: Write "policy X achieves metric Y" tests
2. **Support TDD**: Define expectations before implementation
3. **Provide Clear Failures**: Detailed reports on what failed and by how much
4. **Scale to Complexity**: Simple scenarios → Multi-event crisis scenarios
5. **Enable Comparison**: Benchmark multiple policies objectively
6. **Maintain Determinism**: Same seed = same results (critical for debugging)

## Example Test Suite

```python
# test_policy_scenario_liquidity.py

class TestLiquidityAwarePolicy:
    """Comprehensive tests for LiquidityAware policy."""

    def test_maintains_buffer_under_normal_load(self):
        # Simple scenario, strict expectations
        ...

    def test_degrades_gracefully_under_high_pressure(self):
        # High load, relaxed settlement rate, strict buffer
        ...

    def test_outperforms_fifo_on_liquidity_preservation(self):
        # Comparative test
        ...

    def test_handles_large_payment_arrival(self):
        # Scenario event test
        ...

    def test_optimal_buffer_for_cost_minimization(self):
        # Parameter optimization
        ...
```

## Future Enhancements

1. **Visual Reporting**: Generate charts showing metrics over time
2. **Fuzzing**: Automatically generate random scenarios to find edge cases
3. **Regression Suite**: Store baseline results, alert on degradation
4. **Multi-Objective Optimization**: Find Pareto-optimal policy parameters
5. **Real-World Calibration**: Use historical data to validate policies

---

**Status**: Design Complete - Ready for Implementation
**Next Steps**: Implement Phase 1 (Core Framework) using TDD
