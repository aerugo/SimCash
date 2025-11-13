"""
Metrics collection for policy-scenario testing.

This module provides ActualMetrics and MetricsCollector classes for
gathering simulation metrics during policy-scenario tests.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from payment_simulator._core import Orchestrator


@dataclass
class ActualMetrics:
    """Actual metrics collected from a simulation run."""

    # Settlement metrics
    settlement_rate: float = 0.0
    avg_settlement_delay: float = 0.0
    num_settlements: int = 0
    num_arrivals: int = 0

    # Queue metrics
    max_queue_depth: int = 0
    avg_queue_depth: float = 0.0
    queue_depths_per_tick: List[int] = field(default_factory=list)

    # Financial metrics
    total_cost: int = 0  # cents
    overdraft_violations: int = 0
    deadline_violations: int = 0

    # Liquidity metrics
    min_balance: int = 0  # cents
    avg_balance: float = 0.0
    max_balance: int = 0
    balances_per_tick: List[int] = field(default_factory=list)

    # Custom metrics (extensible)
    custom_metrics: Dict[str, float] = field(default_factory=dict)

    def get_metric(self, name: str) -> Optional[float]:
        """Get metric value by name."""
        if hasattr(self, name):
            return getattr(self, name)
        return self.custom_metrics.get(name)

    def __repr__(self) -> str:
        return (
            f"ActualMetrics(\n"
            f"  settlement_rate={self.settlement_rate:.3f},\n"
            f"  num_settlements={self.num_settlements}/{self.num_arrivals},\n"
            f"  max_queue_depth={self.max_queue_depth},\n"
            f"  avg_queue_depth={self.avg_queue_depth:.2f},\n"
            f"  total_cost=${self.total_cost/100:.2f},\n"
            f"  overdraft_violations={self.overdraft_violations},\n"
            f"  deadline_violations={self.deadline_violations},\n"
            f"  balance_range=[${self.min_balance/100:.2f}, ${self.max_balance/100:.2f}],\n"
            f"  avg_balance=${self.avg_balance/100:.2f}\n"
            f")"
        )


class MetricsCollector:
    """Collects metrics during simulation execution.

    Usage:
        collector = MetricsCollector(agent_id="BANK_A")
        for tick in range(num_ticks):
            orch.tick()
            collector.record_tick(orch, tick)
        metrics = collector.finalize()
    """

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.num_arrivals = 0
        self.num_settlements = 0
        self.settlement_delays: List[int] = []
        self.queue_depths: List[int] = []
        self.balances: List[int] = []
        self.deadline_violations = 0
        self.overdraft_violations = 0
        self.total_cost = 0

    def record_tick(self, orch: Orchestrator, tick: int):
        """Record metrics for a single tick.

        Args:
            orch: Orchestrator instance after tick() has been called
            tick: Current tick number
        """
        # Get agent state
        agent_state = orch.get_agent_state(self.agent_id)
        balance = agent_state["balance"]
        queue_size = agent_state["queue_size"]

        # Record queue depth
        self.queue_depths.append(queue_size)

        # Record balance
        self.balances.append(balance)

        # Track overdraft (negative balance without credit is violation)
        if balance < 0:
            credit_limit = agent_state.get("credit_limit", 0)
            if abs(balance) > credit_limit:
                self.overdraft_violations += 1

    def record_arrival(self, count: int = 1):
        """Record transaction arrivals."""
        self.num_arrivals += count

    def record_settlement(self, arrival_tick: int, settlement_tick: int):
        """Record a settlement with its delay."""
        self.num_settlements += 1
        delay = settlement_tick - arrival_tick
        self.settlement_delays.append(delay)

    def record_deadline_violation(self):
        """Record a deadline violation."""
        self.deadline_violations += 1

    def record_cost(self, cost: int):
        """Record costs in cents."""
        self.total_cost += cost

    def finalize(self) -> ActualMetrics:
        """Compute final metrics from collected data."""
        settlement_rate = (
            self.num_settlements / self.num_arrivals
            if self.num_arrivals > 0
            else 0.0
        )

        avg_settlement_delay = (
            sum(self.settlement_delays) / len(self.settlement_delays)
            if self.settlement_delays
            else 0.0
        )

        max_queue_depth = max(self.queue_depths) if self.queue_depths else 0

        avg_queue_depth = (
            sum(self.queue_depths) / len(self.queue_depths)
            if self.queue_depths
            else 0.0
        )

        min_balance = min(self.balances) if self.balances else 0
        max_balance = max(self.balances) if self.balances else 0
        avg_balance = (
            sum(self.balances) / len(self.balances)
            if self.balances
            else 0.0
        )

        return ActualMetrics(
            settlement_rate=settlement_rate,
            avg_settlement_delay=avg_settlement_delay,
            num_settlements=self.num_settlements,
            num_arrivals=self.num_arrivals,
            max_queue_depth=max_queue_depth,
            avg_queue_depth=avg_queue_depth,
            queue_depths_per_tick=self.queue_depths,
            total_cost=self.total_cost,
            overdraft_violations=self.overdraft_violations,
            deadline_violations=self.deadline_violations,
            min_balance=min_balance,
            max_balance=max_balance,
            avg_balance=avg_balance,
            balances_per_tick=self.balances,
        )
