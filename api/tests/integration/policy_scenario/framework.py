"""
Core framework for policy-scenario testing.

Provides PolicyScenarioTest and PolicyScenarioResult classes for
executing and validating policy-scenario tests.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from payment_simulator._core import Orchestrator

from .expectations import (
    OutcomeExpectation,
    ExpectationFailure,
    Constraint,
    Range,
    Exact,
)
from .metrics import ActualMetrics, MetricsCollector
from .builders import ScenarioDefinition


@dataclass
class PolicyScenarioResult:
    """Results of running a policy-scenario test.

    Contains:
    - Actual metrics collected
    - Expected metrics
    - Comparison results (passed/failed)
    - Detailed failure information
    """

    policy_config: Dict
    scenario: ScenarioDefinition
    actual: ActualMetrics
    expected: OutcomeExpectation
    passed: bool
    failures: List[ExpectationFailure]

    def detailed_report(self) -> str:
        """Generate human-readable test report."""
        lines = []
        lines.append("=" * 70)
        lines.append("Policy-Scenario Test Results")
        lines.append("=" * 70)

        # Policy info
        policy_type = self.policy_config.get("type", "Unknown")
        lines.append(f"\nPolicy: {policy_type}")
        if policy_type != "Fifo":
            params = {k: v for k, v in self.policy_config.items() if k != "type"}
            if params:
                lines.append(f"  Parameters: {params}")

        # Scenario info
        lines.append(f"\nScenario: {self.scenario.name}")
        if self.scenario.description:
            lines.append(f"  Description: {self.scenario.description}")
        lines.append(f"  Duration: {self.scenario.duration_ticks} ticks")
        lines.append(f"  Agents: {len(self.scenario.agents)}")

        # Results summary
        lines.append(f"\nResult: {'PASSED' if self.passed else 'FAILED'}")

        # Metric comparison
        lines.append("\nMetric Comparison:")
        lines.append("-" * 70)

        constraints = self.expected.get_all_constraints()

        for metric_name, constraint in constraints:
            actual_value = self.actual.get_metric(metric_name)

            if actual_value is None:
                lines.append(f"  ⚠️  {metric_name}: NOT COLLECTED")
                continue

            is_satisfied = constraint.contains(actual_value)
            symbol = "✓" if is_satisfied else "✗"

            # Format values nicely
            if metric_name in ['settlement_rate']:
                actual_str = f"{actual_value:.3f}"
            elif metric_name in ['total_cost', 'min_balance', 'avg_balance', 'max_balance']:
                actual_str = f"${actual_value/100:.2f}"
            elif metric_name in ['avg_settlement_delay', 'avg_queue_depth']:
                actual_str = f"{actual_value:.2f}"
            else:
                actual_str = f"{actual_value}"

            lines.append(f"  {symbol}  {metric_name}: {actual_str} (expected: {constraint})")

            # Show deviation for failures
            if not is_satisfied:
                deviation = constraint.distance(actual_value)
                if metric_name in ['total_cost', 'min_balance', 'avg_balance', 'max_balance']:
                    lines.append(f"      Deviation: ${deviation/100:.2f}")
                else:
                    lines.append(f"      Deviation: {deviation:.2f}")

        # Failure details
        if not self.passed:
            lines.append("\nFailed Expectations:")
            lines.append("-" * 70)
            for failure in self.failures:
                lines.append(f"  • {failure.short_description()}")

        lines.append("=" * 70)

        return "\n".join(lines)

    def __repr__(self) -> str:
        status = "PASSED" if self.passed else "FAILED"
        num_failures = len(self.failures)
        return (
            f"PolicyScenarioResult(status={status}, "
            f"failures={num_failures}, "
            f"scenario='{self.scenario.name}')"
        )


class PolicyScenarioTest:
    """Executable policy-scenario test with outcome verification.

    This class:
    1. Builds an Orchestrator from scenario + policy
    2. Runs simulation collecting metrics
    3. Compares actual vs expected outcomes
    4. Returns detailed results

    Example:
        test = PolicyScenarioTest(
            policy={"type": "LiquidityAware", "target_buffer": 300000, "urgency_threshold": 5},
            scenario=high_pressure_scenario,
            expectations=OutcomeExpectation(
                settlement_rate=Range(min=0.85, max=1.0),
                overdraft_violations=Exact(0)
            ),
            agent_id="BANK_A"
        )

        result = test.run()
        assert result.passed, result.detailed_report()
    """

    def __init__(
        self,
        policy: Dict,
        scenario: ScenarioDefinition,
        expectations: OutcomeExpectation,
        agent_id: Optional[str] = None,
    ):
        """Initialize policy-scenario test.

        Args:
            policy: Policy config dict (e.g., {"type": "Fifo"} or
                   {"type": "LiquidityAware", "target_buffer": 300000, ...})
            scenario: Scenario definition
            expectations: Expected outcomes
            agent_id: Agent to collect metrics for (default: first agent in scenario)
        """
        self.policy = policy
        self.scenario = scenario
        self.expectations = expectations

        # Default to first agent if not specified
        self.agent_id = agent_id or scenario.agents[0].agent_id

    def run(self) -> PolicyScenarioResult:
        """Run simulation and verify expectations.

        Returns:
            PolicyScenarioResult with actual metrics and pass/fail status
        """
        # Build orchestrator config
        # For simplicity, apply same policy to all agents
        # (Could be extended to support per-agent policies)
        policy_configs = {
            agent.agent_id: self.policy
            for agent in self.scenario.agents
        }

        orch_config = self.scenario.to_orchestrator_config(policy_configs)

        # Create orchestrator
        orch = Orchestrator.new(orch_config)

        # Create metrics collector
        collector = MetricsCollector(self.agent_id)

        # Run simulation
        for tick in range(self.scenario.duration_ticks):
            tick_result = orch.tick()

            # Record basic tick metrics
            collector.record_tick(orch, tick)

            # Extract agent-specific events for arrivals/settlements
            events = orch.get_tick_events(tick)
            for event in events:
                event_type = event.get("event_type")

                # Track arrivals for this agent
                if event_type == "Arrival":
                    if event.get("sender_id") == self.agent_id:
                        collector.record_arrival()

                # Track settlements for this agent's transactions
                elif event_type == "RtgsImmediateSettlement":
                    if event.get("sender") == self.agent_id or event.get("sender_id") == self.agent_id:
                        # Track settlement with delay if we have arrival_tick
                        arrival_tick = event.get("arrival_tick", tick)
                        collector.record_settlement(arrival_tick, tick)

                # Track deadline violations
                elif event_type == "DeadlineViolation":
                    if event.get("sender_id") == self.agent_id or event.get("agent_id") == self.agent_id:
                        collector.record_deadline_violation()

        # Finalize metrics
        actual = collector.finalize()

        # Compare with expectations
        failures = self._check_expectations(actual)

        result = PolicyScenarioResult(
            policy_config=self.policy,
            scenario=self.scenario,
            actual=actual,
            expected=self.expectations,
            passed=len(failures) == 0,
            failures=failures,
        )

        return result

    def _check_expectations(self, actual: ActualMetrics) -> List[ExpectationFailure]:
        """Compare actual metrics against expectations.

        Returns:
            List of failed expectations (empty if all passed)
        """
        failures = []

        for metric_name, constraint in self.expectations.get_all_constraints():
            actual_value = actual.get_metric(metric_name)

            if actual_value is None:
                # Metric not collected - skip or warn?
                # For now, skip
                continue

            if not constraint.contains(actual_value):
                # Expectation failed
                failure = ExpectationFailure(
                    metric_name=metric_name,
                    expected=constraint,
                    actual=actual_value,
                    distance=constraint.distance(actual_value),
                )
                failures.append(failure)

        return failures
