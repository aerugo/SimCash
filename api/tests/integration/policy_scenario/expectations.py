"""
Outcome expectations and constraint types for policy-scenario testing.

This module defines the types used to specify expected outcomes from
policy-scenario tests, including:
- Range: Min/max constraints
- Exact: Exact value matching
- OutcomeExpectation: Complete set of expected metrics
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Tuple


@dataclass
class Range:
    """Numeric range constraint [min, max].

    Examples:
        Range(min=0.85, max=1.0)  # Settlement rate between 85% and 100%
        Range(min=0, max=15)       # Max queue depth ≤ 15
        Range(min=0)               # Any non-negative value
    """

    min: float = float('-inf')
    max: float = float('inf')

    def __post_init__(self):
        if self.min > self.max:
            raise ValueError(f"min ({self.min}) cannot be greater than max ({self.max})")

    def contains(self, value: float) -> bool:
        """Check if value falls within range."""
        return self.min <= value <= self.max

    def distance(self, value: float) -> float:
        """Calculate distance from value to range.

        Returns 0 if value is within range, otherwise the absolute distance
        to the nearest boundary.
        """
        if self.contains(value):
            return 0.0
        if value < self.min:
            return self.min - value
        return value - self.max

    def __repr__(self) -> str:
        if self.min == float('-inf') and self.max == float('inf'):
            return "Range(any)"
        elif self.min == float('-inf'):
            return f"Range(≤{self.max})"
        elif self.max == float('inf'):
            return f"Range(≥{self.min})"
        else:
            return f"Range({self.min}, {self.max})"


@dataclass
class Exact:
    """Exact value constraint.

    Examples:
        Exact(0)     # Exactly 0 overdraft violations
        Exact(100)   # Exactly 100 settlements expected
    """

    value: float

    def contains(self, actual: float) -> bool:
        """Check if actual equals expected value."""
        return actual == self.value

    def distance(self, actual: float) -> float:
        """Calculate distance from actual to expected."""
        return abs(actual - self.value)

    def __repr__(self) -> str:
        return f"Exact({self.value})"


# Type alias for any constraint type
Constraint = Range | Exact


@dataclass
class OutcomeExpectation:
    """Expected outcome metrics for a policy-scenario test.

    Defines the expected results when a specific policy operates under
    a specific scenario. Each metric can specify either a Range or Exact
    constraint.

    Example:
        expectations = OutcomeExpectation(
            settlement_rate=Range(min=0.85, max=1.0),
            max_queue_depth=Range(min=0, max=15),
            overdraft_violations=Exact(0),
            total_cost=Range(min=0, max=500_000)
        )
    """

    # Settlement metrics
    settlement_rate: Optional[Constraint] = None
    """Proportion of arrived transactions that settled (0.0-1.0)."""

    avg_settlement_delay: Optional[Constraint] = None
    """Average ticks from arrival to settlement."""

    num_settlements: Optional[Constraint] = None
    """Total number of settled transactions."""

    # Queue metrics
    max_queue_depth: Optional[Constraint] = None
    """Peak queue size across all ticks."""

    avg_queue_depth: Optional[Constraint] = None
    """Average queue size across all ticks."""

    # Financial metrics
    total_cost: Optional[Constraint] = None
    """Total costs incurred (overdraft + delay + penalties) in cents."""

    overdraft_violations: Optional[Constraint] = None
    """Number of ticks with negative balance (without credit)."""

    deadline_violations: Optional[Constraint] = None
    """Number of transactions that missed their deadline."""

    # Liquidity metrics
    min_balance: Optional[Constraint] = None
    """Lowest balance reached across all ticks (in cents)."""

    avg_balance: Optional[Constraint] = None
    """Average balance across all ticks (in cents)."""

    max_balance: Optional[Constraint] = None
    """Highest balance reached across all ticks (in cents)."""

    # Policy-specific custom metrics (extensible)
    custom_metrics: Dict[str, Constraint] = field(default_factory=dict)
    """Additional policy-specific metrics with constraints."""

    def get_all_constraints(self) -> List[Tuple[str, Constraint]]:
        """Get all defined constraints as (metric_name, constraint) tuples."""
        constraints = []

        # Standard metrics
        for metric_name in [
            'settlement_rate',
            'avg_settlement_delay',
            'num_settlements',
            'max_queue_depth',
            'avg_queue_depth',
            'total_cost',
            'overdraft_violations',
            'deadline_violations',
            'min_balance',
            'avg_balance',
            'max_balance',
        ]:
            constraint = getattr(self, metric_name)
            if constraint is not None:
                constraints.append((metric_name, constraint))

        # Custom metrics
        for name, constraint in self.custom_metrics.items():
            constraints.append((name, constraint))

        return constraints

    def __repr__(self) -> str:
        constraints = self.get_all_constraints()
        if not constraints:
            return "OutcomeExpectation(no constraints)"

        parts = [f"{name}={constraint}" for name, constraint in constraints]
        return f"OutcomeExpectation(\n  " + ",\n  ".join(parts) + "\n)"


@dataclass
class ExpectationFailure:
    """Represents a failed expectation with details."""

    metric_name: str
    expected: Constraint
    actual: float
    distance: float

    def __repr__(self) -> str:
        return (
            f"ExpectationFailure(\n"
            f"  metric='{self.metric_name}',\n"
            f"  expected={self.expected},\n"
            f"  actual={self.actual},\n"
            f"  deviation={self.distance}\n"
            f")"
        )

    def short_description(self) -> str:
        """One-line description for test reports."""
        if isinstance(self.expected, Exact):
            return (
                f"{self.metric_name}: {self.actual} "
                f"(expected exactly {self.expected.value}, "
                f"off by {self.distance})"
            )
        elif isinstance(self.expected, Range):
            if self.actual < self.expected.min:
                return (
                    f"{self.metric_name}: {self.actual} "
                    f"(expected ≥{self.expected.min}, "
                    f"below by {self.distance})"
                )
            else:
                return (
                    f"{self.metric_name}: {self.actual} "
                    f"(expected ≤{self.expected.max}, "
                    f"above by {self.distance})"
                )
        return f"{self.metric_name}: unexpected constraint type"
