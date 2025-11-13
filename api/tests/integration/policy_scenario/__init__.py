"""
Policy-Scenario Testing Framework

A comprehensive framework for testing payment settlement policies against
defined scenarios with predicted outcomes.

This framework enables:
- Predictive testing: Define expected outcomes, verify they're achieved
- Comparative analysis: Benchmark multiple policies on same scenarios
- Complex scenarios: Multi-event crisis situations with outcome validation
- TDD workflow: Write expectations first, then implement/tune policies

Example usage:

    from policy_scenario import (
        PolicyScenarioTest,
        OutcomeExpectation,
        Range,
        ScenarioBuilder
    )

    # Define scenario
    scenario = (
        ScenarioBuilder("HighPressure")
        .with_duration(100)
        .add_agent("BANK_A", balance=1_000_000, arrival_rate=5.0)
        .add_agent("BANK_B", balance=20_000_000)
        .build()
    )

    # Define expectations
    expectations = OutcomeExpectation(
        settlement_rate=Range(min=0.85, max=1.0),
        overdraft_violations=Exact(0)
    )

    # Run test
    test = PolicyScenarioTest(policy_config, scenario, expectations)
    result = test.run()

    assert result.passed, result.detailed_report()

See: docs/policy_scenario_testing_architecture.md
"""

from .expectations import Range, Exact, OutcomeExpectation
from .metrics import ActualMetrics
from .framework import PolicyScenarioTest, PolicyScenarioResult
from .builders import ScenarioBuilder, ScenarioDefinition, AgentScenarioConfig
from .comparators import PolicyComparator, ComparisonResult

__all__ = [
    # Constraints
    "Range",
    "Exact",
    # Expectations
    "OutcomeExpectation",
    # Metrics
    "ActualMetrics",
    # Framework
    "PolicyScenarioTest",
    "PolicyScenarioResult",
    # Builders
    "ScenarioBuilder",
    "ScenarioDefinition",
    "AgentScenarioConfig",
    # Comparators
    "PolicyComparator",
    "ComparisonResult",
]
