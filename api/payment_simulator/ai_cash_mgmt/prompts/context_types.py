"""Data structures for building optimization context.

This module defines dataclasses used by context builders to structure
the information passed to LLMs during policy optimization.

Key types:
    SingleAgentIterationRecord: Record of one iteration for one agent
    SingleAgentContext: Complete context for single-agent optimization
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SingleAgentIterationRecord:
    """Record of a single iteration for ONE agent only.

    CRITICAL: This dataclass contains NO information about other agents.
    Each agent sees only its own policy history and changes.

    Attributes:
        iteration: The iteration number (1-indexed).
        metrics: Aggregated metrics from this iteration (cost, settlement rate, etc).
        policy: The policy used in this iteration (only THIS agent's policy).
        policy_changes: List of human-readable changes from previous iteration.
        was_accepted: True if this policy was kept (not rejected for worse performance).
        is_best_so_far: True if this is the best policy discovered so far.
        comparison_to_best: Human-readable comparison to the best policy.

    Example:
        >>> record = SingleAgentIterationRecord(
        ...     iteration=2,
        ...     metrics={"total_cost_mean": 800, "settlement_rate_mean": 1.0},
        ...     policy={"parameters": {"threshold": 4.0}},
        ...     policy_changes=["Changed 'threshold': 5.0 → 4.0 (↓1.0)"],
        ...     is_best_so_far=True,
        ... )
    """

    iteration: int
    metrics: dict[str, Any]
    policy: dict[str, Any]
    policy_changes: list[str] = field(default_factory=list)
    was_accepted: bool = True
    is_best_so_far: bool = False
    comparison_to_best: str = ""


@dataclass
class SingleAgentContext:
    """Complete context for policy optimization of a SINGLE agent.

    CRITICAL ISOLATION: This context contains ONLY the specified agent's data.
    No other agent's policy, history, or metrics are included.

    Attributes:
        agent_id: Identifier for this agent (e.g., "BANK_A").
        current_iteration: Current iteration number.
        current_policy: Current policy for THIS agent only.
        current_metrics: Aggregated metrics from current iteration.
        iteration_history: List of previous iteration records for THIS agent only.
        simulation_trace: Tick-by-tick event log from representative sample (shown to LLM).
        sample_seed: Seed used for the representative sample.
        sample_cost: Cost from the representative sample.
        mean_cost: Mean cost across all samples.
        cost_std: Standard deviation of costs.
        cost_breakdown: Breakdown of costs by type (delay, collateral, etc).
        cost_rates: Cost rate configuration from simulation.
        ticks_per_day: Number of ticks per simulation day.

    Example:
        >>> context = SingleAgentContext(
        ...     agent_id="BANK_A",
        ...     current_iteration=5,
        ...     current_policy={"parameters": {"threshold": 4.5}},
        ...     current_metrics={"total_cost_mean": 12500},
        ...     cost_breakdown={"delay": 6000, "collateral": 4000},
        ... )
    """

    agent_id: str | None = None
    current_iteration: int = 0
    current_policy: dict[str, Any] = field(default_factory=dict)
    current_metrics: dict[str, Any] = field(default_factory=dict)
    iteration_history: list[SingleAgentIterationRecord] = field(default_factory=list)
    # New unified naming
    simulation_trace: str | None = None
    sample_seed: int = 0
    sample_cost: int = 0
    mean_cost: int = 0
    cost_std: int = 0
    cost_breakdown: dict[str, int] = field(default_factory=dict)
    cost_rates: dict[str, Any] = field(default_factory=dict)
    ticks_per_day: int = 100

    # Deprecated aliases for backward compatibility
    @property
    def best_seed_output(self) -> str | None:
        """Deprecated: Use simulation_trace instead."""
        return self.simulation_trace

    @property
    def worst_seed_output(self) -> str | None:
        """Deprecated: No longer used - returns None."""
        return None

    @property
    def best_seed(self) -> int:
        """Deprecated: Use sample_seed instead."""
        return self.sample_seed

    @property
    def worst_seed(self) -> int:
        """Deprecated: No longer used - returns sample_seed."""
        return self.sample_seed

    @property
    def best_seed_cost(self) -> int:
        """Deprecated: Use sample_cost instead."""
        return self.sample_cost

    @property
    def worst_seed_cost(self) -> int:
        """Deprecated: No longer used - returns sample_cost."""
        return self.sample_cost

    @property
    def initial_simulation_output(self) -> str | None:
        """Deprecated: No longer used - initial simulation removed."""
        return None
