"""Bootstrap-native context builder for LLM prompts.

This module provides a context builder that works directly with enriched
bootstrap evaluation results, eliminating the context/evaluation mismatch
where LLM context came from full simulation but costs came from bootstrap.

Originally from Castro experiments, now part of core for reuse by any experiment.

Key features:
- Works natively with EnrichedEvaluationResult
- Produces AgentSimulationContext for LLM prompt generation
- Event trace formatting optimized for LLM consumption
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from payment_simulator.ai_cash_mgmt.prompts.event_filter import (
    filter_events_for_agent,
)

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
        BootstrapEvent,
        EnrichedEvaluationResult,
    )


@dataclass
class AgentSimulationContext:
    """Context data for a single agent from bootstrap samples.

    Aggregates statistics and verbose output for a specific agent
    across all bootstrap samples.

    All costs are integer cents (INV-1 compliance).

    Attributes:
        agent_id: Agent identifier (e.g., "BANK_A").
        best_seed: Seed that produced lowest cost for this agent.
        best_seed_cost: Cost at best seed (integer cents).
        best_seed_output: Filtered verbose output from best seed.
        worst_seed: Seed that produced highest cost for this agent.
        worst_seed_cost: Cost at worst seed (integer cents).
        worst_seed_output: Filtered verbose output from worst seed.
        mean_cost: Mean cost across all samples (integer cents).
        cost_std: Standard deviation of costs.
    """

    agent_id: str
    best_seed: int
    best_seed_cost: int
    best_seed_output: str | None
    worst_seed: int
    worst_seed_cost: int
    worst_seed_output: str | None
    mean_cost: int
    cost_std: int


class EnrichedBootstrapContextBuilder:
    """Builds LLM context directly from enriched bootstrap results.

    Unlike simulation-based context builders which require full simulation runs,
    this builder works natively with EnrichedEvaluationResult objects from
    bootstrap sandbox evaluation.

    This eliminates the context/evaluation mismatch - the LLM now sees
    exactly what happened during the evaluations that produced the costs.

    Attributes:
        _results: List of enriched evaluation results.
        _agent_id: Agent being optimized.

    Example:
        >>> from payment_simulator.ai_cash_mgmt.bootstrap import (
        ...     EnrichedBootstrapContextBuilder,
        ... )
        >>> builder = EnrichedBootstrapContextBuilder(enriched_results, "BANK_A")
        >>> context = builder.build_agent_context()
        >>> best_trace = builder.format_event_trace_for_llm(builder.get_best_result())
    """

    def __init__(
        self,
        results: list[EnrichedEvaluationResult],
        agent_id: str,
    ) -> None:
        """Initialize the context builder.

        Args:
            results: Enriched evaluation results from bootstrap sandbox.
            agent_id: ID of the agent being optimized.

        Raises:
            ValueError: If results list is empty.
        """
        if not results:
            msg = "results list cannot be empty"
            raise ValueError(msg)
        self._results = results
        self._agent_id = agent_id

    def format_event_trace_for_llm(
        self,
        result: EnrichedEvaluationResult,
        max_events: int = 50,
    ) -> str:
        """Format event trace for LLM prompt.

        CRITICAL: Filters events to only show those relevant to the target agent.
        This enforces agent isolation - an LLM optimizing Agent X must NEVER see
        Agent Y's outgoing transactions or internal state.

        Also filters and formats events to be informative for the LLM:
        - Enforces agent isolation via filter_events_for_agent
        - Prioritizes policy decisions and cost events
        - Limits total events to prevent prompt bloat
        - Sorts chronologically for readability

        Args:
            result: Enriched evaluation result containing event trace.
            max_events: Maximum number of events to include.

        Returns:
            Formatted string representation of event trace.
        """
        if not result.event_trace:
            return "(No events captured)"

        # CRITICAL: Convert events to dicts and filter by agent
        # This enforces agent isolation - only show events relevant to target agent
        #
        # We pair each event with its index, filter, then retrieve by index
        indexed_events = list(enumerate(result.event_trace))
        indexed_dicts = [
            (i, self._bootstrap_event_to_dict(e))
            for i, e in indexed_events
        ]

        # Filter the dicts
        filtered_indices = {
            i for i, d in indexed_dicts
            if d in filter_events_for_agent(self._agent_id, [d])
        }

        # Retrieve the original events by their indices
        filtered_events = [
            e for i, e in indexed_events
            if i in filtered_indices
        ]

        if not filtered_events:
            return f"(No events for {self._agent_id})"

        # Prioritize events by informativeness
        events = sorted(
            filtered_events,
            key=lambda e: self._event_priority(e),
            reverse=True,
        )[:max_events]

        # Sort chronologically for presentation
        events = sorted(events, key=lambda e: e.tick)

        return self._format_events(events)

    def _bootstrap_event_to_dict(self, event: BootstrapEvent) -> dict[str, Any]:
        """Convert a BootstrapEvent to a dict for filtering.

        Args:
            event: BootstrapEvent to convert.

        Returns:
            Dict representation compatible with filter_events_for_agent.
        """
        return {
            "tick": event.tick,
            "event_type": event.event_type,
            **event.details,
        }

    def _get_agent_cost(self, result: EnrichedEvaluationResult) -> int:
        """Get cost for the target agent from a result.

        Uses per_agent_costs if available, otherwise falls back to total_cost.

        Args:
            result: Evaluation result to extract cost from.

        Returns:
            Cost for this agent in integer cents.
        """
        if result.per_agent_costs and self._agent_id in result.per_agent_costs:
            return result.per_agent_costs[self._agent_id]
        # Backward compatibility: fall back to total_cost
        return result.total_cost

    def get_best_result(self) -> EnrichedEvaluationResult:
        """Get result with lowest cost for this agent.

        Uses per-agent cost when available, total_cost otherwise.

        Returns:
            EnrichedEvaluationResult with minimum cost for this agent.
        """
        return min(self._results, key=lambda r: self._get_agent_cost(r))

    def get_worst_result(self) -> EnrichedEvaluationResult:
        """Get result with highest cost for this agent.

        Uses per-agent cost when available, total_cost otherwise.

        Returns:
            EnrichedEvaluationResult with maximum cost for this agent.
        """
        return max(self._results, key=lambda r: self._get_agent_cost(r))

    def build_agent_context(self) -> AgentSimulationContext:
        """Build context compatible with prompt system.

        Creates AgentSimulationContext from enriched bootstrap results,
        including formatted event traces for best and worst samples.

        Uses per-agent costs when available for accurate per-agent reporting.

        Returns:
            AgentSimulationContext with all fields populated.
        """
        # Use per-agent costs for this specific agent
        costs = [self._get_agent_cost(r) for r in self._results]
        mean_cost = int(statistics.mean(costs))
        std_cost = int(statistics.stdev(costs)) if len(costs) > 1 else 0

        best = self.get_best_result()
        worst = self.get_worst_result()

        return AgentSimulationContext(
            agent_id=self._agent_id,
            best_seed=best.seed,
            best_seed_cost=self._get_agent_cost(best),
            best_seed_output=self.format_event_trace_for_llm(best),
            worst_seed=worst.seed,
            worst_seed_cost=self._get_agent_cost(worst),
            worst_seed_output=self.format_event_trace_for_llm(worst),
            mean_cost=mean_cost,
            cost_std=std_cost,
        )

    def _event_priority(self, event: BootstrapEvent) -> int:
        """Score event by informativeness for LLM.

        Higher scores = more informative events.

        Args:
            event: Event to score.

        Returns:
            Priority score (higher = more important).
        """
        priority_map = {
            "PolicyDecision": 100,  # Most informative - shows decision points
            "DelayCostAccrual": 80,  # Shows cost drivers
            "OverdraftCostAccrual": 80,
            "DeadlinePenalty": 90,  # Shows missed deadlines
            "RtgsImmediateSettlement": 50,  # Settlement outcomes
            "Queue2LiquidityRelease": 50,
            "LsmBilateralOffset": 50,
            "LsmCycleSettlement": 50,
            "Arrival": 30,  # Context events
        }
        return priority_map.get(event.event_type, 10)

    def _format_events(self, events: list[BootstrapEvent]) -> str:
        """Format events as a readable string.

        Args:
            events: Events to format.

        Returns:
            Formatted string with one event per line.
        """
        lines = []
        for event in events:
            details_str = self._format_event_details(event)
            lines.append(f"[tick {event.tick}] {event.event_type}: {details_str}")
        return "\n".join(lines)

    def _format_event_details(self, event: BootstrapEvent) -> str:
        """Format event details for readability.

        CRITICAL: This method enforces INV-10 (Agent Isolation) by sanitizing
        event details to hide counterparty-specific information.

        Args:
            event: Event whose details to format.

        Returns:
            Compact string representation of event details.
        """
        # Handle settlement events specially - enforces balance isolation
        if event.event_type == "RtgsImmediateSettlement":
            return self._format_settlement_event(event)

        # Handle LSM events specially - enforces counterparty isolation
        if event.event_type == "LsmBilateralOffset":
            return self._format_lsm_bilateral(event)

        if event.event_type == "LsmCycleSettlement":
            return self._format_lsm_cycle(event)

        # Format key fields that are most informative
        key_fields = ["tx_id", "action", "amount", "cost", "agent_id", "sender_id"]
        parts = []
        for key in key_fields:
            if key in event.details:
                value = event.details[key]
                # Format amounts/costs as currency
                if key in ("amount", "cost") and isinstance(value, int):
                    parts.append(f"{key}=${value / 100:.2f}")
                else:
                    parts.append(f"{key}={value}")

        # If no key fields found, show a summary of available fields
        if not parts:
            other_keys = list(event.details.keys())[:3]  # First 3 keys
            parts = [f"{k}={event.details[k]}" for k in other_keys]

        return ", ".join(parts) if parts else "(no details)"

    def _format_settlement_event(self, event: BootstrapEvent) -> str:
        """Format settlement event with balance changes.

        CRITICAL: Enforces INV-10 (Agent Isolation) - only shows balance
        to the sender, NOT to the receiver. This prevents information
        leakage about counterparty's liquidity position.

        Args:
            event: Settlement event to format.

        Returns:
            Formatted string with balance change information (sender only).
        """
        d = event.details
        parts = []

        # Transaction ID
        if "tx_id" in d:
            parts.append(f"tx_id={d['tx_id']}")

        # Amount
        if "amount" in d and isinstance(d["amount"], int):
            parts.append(f"amount=${d['amount'] / 100:.2f}")

        result = ", ".join(parts)

        # CRITICAL FIX: Only show balance to sender, not receiver
        # This enforces INV-10 (Agent Isolation)
        sender = d.get("sender")
        if sender == self._agent_id:
            balance_before = d.get("sender_balance_before")
            balance_after = d.get("sender_balance_after")
            if balance_before is not None and balance_after is not None:
                before_fmt = f"${balance_before / 100:,.2f}"
                after_fmt = f"${balance_after / 100:,.2f}"
                result += f"\n  Balance: {before_fmt} → {after_fmt}"

        return result

    def _format_lsm_bilateral(self, event: BootstrapEvent) -> str:
        """Format LSM bilateral offset with agent isolation.

        CRITICAL: Enforces INV-10 (Agent Isolation) - only shows the
        viewing agent's side of the offset. Counterparty's specific
        amount is hidden to prevent information leakage.

        Args:
            event: LSM bilateral offset event.

        Returns:
            Sanitized string showing only agent's own position.
        """
        d = event.details
        agent_a = d.get("agent_a")
        agent_b = d.get("agent_b")
        amount_a = d.get("amount_a", 0)
        amount_b = d.get("amount_b", 0)

        # Determine which side is the viewing agent
        if self._agent_id == agent_a:
            own_amount = amount_a
            counterparty = agent_b
        elif self._agent_id == agent_b:
            own_amount = amount_b
            counterparty = agent_a
        else:
            # Shouldn't happen if filtering works, but safe fallback
            return f"LSM Bilateral: {agent_a} <-> {agent_b}"

        # Only show own amount, not counterparty's
        own_fmt = f"${own_amount / 100:,.2f}"
        return f"Bilateral offset with {counterparty}: Your payment {own_fmt} settled"

    def _format_lsm_cycle(self, event: BootstrapEvent) -> str:
        """Format LSM cycle settlement with agent isolation.

        CRITICAL: Enforces INV-10 (Agent Isolation) - shows participation
        and total value saved, but hides individual transaction amounts
        and net positions which would reveal counterparty liquidity stress.

        Args:
            event: LSM cycle settlement event.

        Returns:
            Sanitized string showing participation without counterparty details.
        """
        d = event.details
        agents = d.get("agents", [])
        total_value = d.get("total_value", 0)

        # Show participation and total, but NOT:
        # - tx_amounts (individual transaction sizes)
        # - net_positions (liquidity stress indicators)
        # - max_net_outflow_agent (identifies struggling bank)
        total_fmt = f"${total_value / 100:,.2f}"
        num_participants = len(agents)

        return f"LSM Cycle: {num_participants} participants, Total: {total_fmt}"
