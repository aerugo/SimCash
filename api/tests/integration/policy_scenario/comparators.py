"""
Policy comparison utilities for benchmarking multiple policies.

Provides PolicyComparator for running multiple policies against the same
scenario and comparing their performance.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional

from .builders import ScenarioDefinition
from .framework import PolicyScenarioTest, PolicyScenarioResult
from .expectations import OutcomeExpectation
from .metrics import ActualMetrics


def _simple_table(headers: List[str], rows: List[List[str]]) -> str:
    """Simple table formatter (replaces tabulate dependency)."""
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build separator
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"

    # Build header
    header_row = "|" + "|".join(
        f" {h:<{col_widths[i]}} " for i, h in enumerate(headers)
    ) + "|"

    # Build rows
    data_rows = []
    for row in rows:
        row_str = "|" + "|".join(
            f" {str(cell):<{col_widths[i]}} " for i, cell in enumerate(row)
        ) + "|"
        data_rows.append(row_str)

    # Assemble table
    table_lines = [separator, header_row, separator]
    table_lines.extend(data_rows)
    table_lines.append(separator)

    return "\n".join(table_lines)


@dataclass
class ComparisonResult:
    """Results of comparing multiple policies on the same scenario.

    Contains:
    - Results for each policy
    - Comparison table
    - Best policy for each metric
    """

    scenario: ScenarioDefinition
    policy_names: List[str]
    results: Dict[str, PolicyScenarioResult]
    metrics_compared: List[str]

    def get_metric(self, policy_name: str, metric_name: str) -> Optional[float]:
        """Get metric value for a specific policy.

        Args:
            policy_name: Name of the policy
            metric_name: Name of the metric

        Returns:
            Metric value, or None if not available
        """
        result = self.results.get(policy_name)
        if not result:
            return None

        return result.actual.get_metric(metric_name)

    def comparison_table(self) -> str:
        """Generate comparison table showing all policies and metrics."""
        # Build table headers
        headers = ["Policy"] + self.metrics_compared

        # Build table rows
        rows = []
        for policy_name in self.policy_names:
            result = self.results[policy_name]

            row = [policy_name]
            for metric_name in self.metrics_compared:
                value = result.actual.get_metric(metric_name)

                if value is None:
                    row.append("N/A")
                else:
                    # Format based on metric type
                    if metric_name == 'settlement_rate':
                        row.append(f"{value:.3f}")
                    elif metric_name in ['total_cost', 'min_balance', 'avg_balance', 'max_balance']:
                        row.append(f"${value/100:,.2f}")
                    elif metric_name in ['avg_settlement_delay', 'avg_queue_depth']:
                        row.append(f"{value:.2f}")
                    else:
                        row.append(f"{int(value)}")

            rows.append(row)

        # Generate table
        table = _simple_table(headers, rows)

        # Add title
        output = []
        output.append(f"Policy Comparison: {self.scenario.name}")
        output.append("=" * 70)
        output.append(table)

        # Find best policy for each metric
        output.append("\nBest Performance:")
        for metric_name in self.metrics_compared:
            best = self._find_best_policy(metric_name)
            if best:
                policy_name, value = best
                if metric_name in ['total_cost', 'min_balance', 'avg_balance', 'max_balance']:
                    value_str = f"${value/100:,.2f}"
                elif metric_name == 'settlement_rate':
                    value_str = f"{value:.3f}"
                else:
                    value_str = f"{value:.2f}" if isinstance(value, float) else f"{int(value)}"

                output.append(f"  {metric_name}: {policy_name} ({value_str})")

        return "\n".join(output)

    def _find_best_policy(self, metric_name: str) -> Optional[Tuple[str, float]]:
        """Find policy with best value for a metric.

        'Best' is defined as:
        - Higher is better: settlement_rate, *_balance
        - Lower is better: violations, costs, delays, queue depths
        """
        values = []
        for policy_name in self.policy_names:
            value = self.get_metric(policy_name, metric_name)
            if value is not None:
                values.append((policy_name, value))

        if not values:
            return None

        # Determine if higher or lower is better
        higher_is_better = metric_name in [
            'settlement_rate',
            'avg_balance',
            'max_balance',
        ]

        if higher_is_better:
            return max(values, key=lambda x: x[1])
        else:
            return min(values, key=lambda x: x[1])

    def __repr__(self) -> str:
        return (
            f"ComparisonResult(scenario='{self.scenario.name}', "
            f"policies={len(self.policy_names)}, "
            f"metrics={len(self.metrics_compared)})"
        )


class PolicyComparator:
    """Compare multiple policies on the same scenario.

    Example:
        comparator = PolicyComparator(high_pressure_scenario)

        result = comparator.compare(
            policies=[
                ("FIFO", {"type": "Fifo"}),
                ("LiquidityAware", {
                    "type": "LiquidityAware",
                    "target_buffer": 300000,
                    "urgency_threshold": 5
                }),
            ],
            metrics=["settlement_rate", "max_queue_depth", "total_cost"],
            agent_id="BANK_A"
        )

        print(result.comparison_table())
    """

    def __init__(self, scenario: ScenarioDefinition):
        """Initialize comparator with a scenario.

        Args:
            scenario: Scenario to test all policies against
        """
        self.scenario = scenario

    def compare(
        self,
        policies: List[Tuple[str, Dict]],
        metrics: List[str],
        agent_id: Optional[str] = None,
        expectations: Optional[OutcomeExpectation] = None,
    ) -> ComparisonResult:
        """Run all policies and compare specified metrics.

        Args:
            policies: List of (name, policy_config) tuples
            metrics: List of metric names to compare
            agent_id: Agent to collect metrics for (default: first agent)
            expectations: Optional expectations (applied to all policies)

        Returns:
            ComparisonResult with all policy results and comparison
        """
        # Default to minimal expectations if not provided
        if expectations is None:
            expectations = OutcomeExpectation()  # No constraints

        # Default agent
        if agent_id is None:
            agent_id = self.scenario.agents[0].agent_id

        # Run each policy
        results = {}
        policy_names = []

        for policy_name, policy_config in policies:
            test = PolicyScenarioTest(
                policy=policy_config,
                scenario=self.scenario,
                expectations=expectations,
                agent_id=agent_id,
            )

            result = test.run()
            results[policy_name] = result
            policy_names.append(policy_name)

        return ComparisonResult(
            scenario=self.scenario,
            policy_names=policy_names,
            results=results,
            metrics_compared=metrics,
        )
