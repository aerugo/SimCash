"""Bootstrap-native context builder for LLM prompts.

This module provides a context builder that works directly with enriched
bootstrap evaluation results, eliminating the context/evaluation mismatch
where LLM context came from full simulation but costs came from bootstrap.

Key features:
- Works natively with EnrichedEvaluationResult
- Produces AgentSimulationContext compatible with existing prompt system
- Event trace formatting optimized for LLM consumption

Example:
    >>> from castro.bootstrap_context import EnrichedBootstrapContextBuilder
    >>> builder = EnrichedBootstrapContextBuilder(enriched_results, "BANK_A")
    >>> context = builder.build_agent_context()
    >>> best_trace = builder.format_event_trace_for_llm(builder.get_best_result())
"""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
        BootstrapEvent,
        EnrichedEvaluationResult,
    )

from castro.context_builder import AgentSimulationContext


class EnrichedBootstrapContextBuilder:
    """Builds LLM context directly from enriched bootstrap results.

    Unlike BootstrapContextBuilder (in context_builder.py) which adapts
    full simulation results, this builder works natively with
    EnrichedEvaluationResult objects from bootstrap sandbox evaluation.

    This eliminates the context/evaluation mismatch - the LLM now sees
    exactly what happened during the evaluations that produced the costs.

    Attributes:
        _results: List of enriched evaluation results.
        _agent_id: Agent being optimized.
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

    def get_best_result(self) -> EnrichedEvaluationResult:
        """Get result with lowest cost.

        Returns:
            EnrichedEvaluationResult with minimum total_cost.
        """
        return min(self._results, key=lambda r: r.total_cost)

    def get_worst_result(self) -> EnrichedEvaluationResult:
        """Get result with highest cost.

        Returns:
            EnrichedEvaluationResult with maximum total_cost.
        """
        return max(self._results, key=lambda r: r.total_cost)

    def format_event_trace_for_llm(
        self,
        result: EnrichedEvaluationResult,
        max_events: int = 50,
    ) -> str:
        """Format event trace for LLM prompt.

        Filters and formats events to be informative for the LLM:
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

        # Prioritize events by informativeness
        events = sorted(
            result.event_trace,
            key=lambda e: self._event_priority(e),
            reverse=True,
        )[:max_events]

        # Sort chronologically for presentation
        events = sorted(events, key=lambda e: e.tick)

        return self._format_events(events)

    def build_agent_context(self) -> AgentSimulationContext:
        """Build context compatible with existing prompt system.

        Creates AgentSimulationContext from enriched bootstrap results,
        including formatted event traces for best and worst samples.

        Returns:
            AgentSimulationContext with all fields populated.
        """
        costs = [r.total_cost for r in self._results]
        mean_cost = int(statistics.mean(costs))
        std_cost = int(statistics.stdev(costs)) if len(costs) > 1 else 0

        best = self.get_best_result()
        worst = self.get_worst_result()

        return AgentSimulationContext(
            agent_id=self._agent_id,
            best_seed=best.seed,
            best_seed_cost=best.total_cost,
            best_seed_output=self.format_event_trace_for_llm(best),
            worst_seed=worst.seed,
            worst_seed_cost=worst.total_cost,
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

        Args:
            event: Event whose details to format.

        Returns:
            Compact string representation of event details.
        """
        # Format key fields that are most informative
        key_fields = ["tx_id", "action", "amount", "cost", "agent_id", "sender_id"]
        parts = []
        for key in key_fields:
            if key in event.details:
                value = event.details[key]
                # Format amounts/costs as currency
                if key in ("amount", "cost") and isinstance(value, int):
                    parts.append(f"{key}=${value/100:.2f}")
                else:
                    parts.append(f"{key}={value}")

        # If no key fields found, show a summary of available fields
        if not parts:
            other_keys = list(event.details.keys())[:3]  # First 3 keys
            parts = [f"{k}={event.details[k]}" for k in other_keys]

        return ", ".join(parts) if parts else "(no details)"
