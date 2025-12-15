"""Enriched data structures for bootstrap-based policy evaluation.

This module defines immutable data structures for capturing detailed
evaluation results including event traces and cost breakdowns:

1. BootstrapEvent - Single event captured during evaluation
2. CostBreakdown - Itemized cost breakdown by type
3. EnrichedEvaluationResult - Full evaluation result with event trace

All money amounts are integers representing cents (project invariant INV-1).
All dataclasses are frozen (immutable) per project convention.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class BootstrapEvent:
    """Event captured during bootstrap evaluation.

    Minimal format optimized for LLM consumption.
    All monetary values in integer cents (INV-1).

    Attributes:
        tick: The discrete time tick when this event occurred.
        event_type: Type of event (e.g., "arrival", "decision", "settlement", "cost").
        details: Additional event-specific data as a dict.
    """

    tick: int
    event_type: str
    details: dict[str, Any]


@dataclass(frozen=True)
class CostBreakdown:
    """Breakdown of costs by type (integer cents).

    Provides an itemized view of different cost components to help
    the LLM understand which cost types are contributing most to
    the total cost.

    All values are in integer cents (INV-1).

    Attributes:
        delay_cost: Cost from transaction delays (per-tick accrual).
        overdraft_cost: Cost from balance going negative.
        deadline_penalty: One-time penalty when deadline is missed.
        eod_penalty: Penalty for unsettled transactions at end of day.
    """

    delay_cost: int
    overdraft_cost: int
    deadline_penalty: int
    eod_penalty: int

    @property
    def total(self) -> int:
        """Sum of all cost components.

        Returns:
            Total cost in integer cents.
        """
        return (
            self.delay_cost
            + self.overdraft_cost
            + self.deadline_penalty
            + self.eod_penalty
        )


@dataclass(frozen=True)
class EnrichedEvaluationResult:
    """Evaluation result with event trace and cost breakdown.

    Extends the basic EvaluationResult with:
    - event_trace: Full trace of events for LLM context
    - cost_breakdown: Itemized costs for understanding cost drivers
    - per_agent_costs: Per-agent cost breakdown for multi-agent scenarios

    This allows the LLM to see exactly what happened during evaluation
    and understand which cost types to optimize.

    All monetary values in integer cents (INV-1).

    Attributes:
        sample_idx: Index of the bootstrap sample (for tracking).
        seed: RNG seed used for this sample (for reproducibility).
        total_cost: Total cost incurred across all agents (integer cents).
        settlement_rate: Fraction of transactions settled (0.0 to 1.0).
        avg_delay: Average delay in ticks for settled transactions.
        event_trace: Tuple of BootstrapEvent capturing what happened.
        cost_breakdown: Itemized cost breakdown by type.
        per_agent_costs: Mapping of agent_id to individual cost (integer cents).
            Empty dict if not provided (backward compatibility - falls back to total_cost).
    """

    sample_idx: int
    seed: int
    total_cost: int  # Integer cents (project invariant INV-1)
    settlement_rate: float
    avg_delay: float
    event_trace: tuple[BootstrapEvent, ...]  # Tuple for immutability
    cost_breakdown: CostBreakdown
    per_agent_costs: dict[str, int] = field(default_factory=dict)  # Agent ID -> cost in cents
