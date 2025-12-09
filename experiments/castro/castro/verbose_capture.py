"""Capture and filter verbose output from simulations.

This module provides functionality to:
1. Capture tick-by-tick events from the Rust Orchestrator
2. Filter events per agent using EventFilter
3. Format events into verbose output text

The VerboseOutput and VerboseOutputCapture classes enable the Castro
LLM optimizer to receive rich, filtered simulation context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from payment_simulator.cli.filters import EventFilter

if TYPE_CHECKING:
    from payment_simulator._core import Orchestrator


@dataclass
class VerboseOutput:
    """Verbose output from a simulation run.

    Contains all events captured during simulation, organized by tick,
    with methods to filter for specific agents.

    Attributes:
        events_by_tick: Dict mapping tick number to list of events at that tick.
        total_ticks: Number of ticks in the simulation.
        agent_ids: List of agent IDs in the simulation.

    Example:
        >>> output = VerboseOutput(events_by_tick={0: [...], 1: [...]}, total_ticks=10)
        >>> filtered = output.filter_for_agent("BANK_A")
        >>> print(filtered[:500])
    """

    events_by_tick: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    total_ticks: int = 0
    agent_ids: list[str] = field(default_factory=list)

    def get_all_events(self) -> list[dict[str, Any]]:
        """Get all events in tick order.

        Returns:
            List of all events, ordered by tick.
        """
        all_events: list[dict[str, Any]] = []
        for tick in sorted(self.events_by_tick.keys()):
            all_events.extend(self.events_by_tick[tick])
        return all_events

    def filter_for_agent(self, agent_id: str) -> str:
        """Get verbose output filtered for a specific agent.

        Uses EventFilter to ensure proper agent isolation (INV-1).
        Each agent only sees:
        - Events where they are the sender/actor
        - Settlement events where they are the receiver (incoming liquidity)

        Args:
            agent_id: Agent to filter for (e.g., "BANK_A")

        Returns:
            Filtered verbose output string showing only events
            relevant to this agent.
        """
        event_filter = EventFilter(agent_id=agent_id)
        lines: list[str] = []

        for tick in sorted(self.events_by_tick.keys()):
            tick_events = self.events_by_tick[tick]
            filtered_events = [
                e for e in tick_events if event_filter.matches(e, tick=tick)
            ]

            if filtered_events:
                lines.append(f"=== TICK {tick} ===")
                for event in filtered_events:
                    lines.append(self._format_event(event))
                lines.append("")  # Blank line between ticks

        return "\n".join(lines)

    def _format_event(self, event: dict[str, Any]) -> str:
        """Format a single event for verbose output.

        Args:
            event: Event dict from Rust FFI.

        Returns:
            Formatted string representation of the event.
        """
        event_type = event.get("event_type", "Unknown")

        # Format based on event type
        if event_type == "Arrival":
            sender = event.get("sender_id", "?")
            receiver = event.get("receiver_id", "?")
            amount = event.get("amount", 0)
            priority = event.get("priority", "?")
            deadline = event.get("deadline", "?")
            return (
                f"  [Arrival] {sender} → {receiver} "
                f"${amount / 100:.2f} (priority={priority}, deadline={deadline})"
            )

        elif event_type == "RtgsImmediateSettlement":
            sender = event.get("sender", "?")
            receiver = event.get("receiver", "?")
            amount = event.get("amount", 0)
            return f"  [Settlement] {sender} → {receiver} ${amount / 100:.2f}"

        elif event_type == "Queue2LiquidityRelease":
            sender = event.get("sender", event.get("sender_id", "?"))
            receiver = event.get("receiver", event.get("receiver_id", "?"))
            amount = event.get("amount", 0)
            wait_ticks = event.get("queue_wait_ticks", "?")
            return (
                f"  [QueueRelease] {sender} → {receiver} "
                f"${amount / 100:.2f} (waited {wait_ticks} ticks)"
            )

        elif event_type.startswith("Policy"):
            agent = event.get("agent_id", "?")
            decision = event.get("decision", event_type.replace("Policy", ""))
            tx_id = event.get("tx_id", "?")[:8] if event.get("tx_id") else "?"
            return f"  [{event_type}] {agent}: {decision} (tx={tx_id}...)"

        elif event_type == "CostAccrual":
            agent = event.get("agent_id", "?")
            cost_type = event.get("cost_type", "?")
            amount = event.get("amount", 0)
            return f"  [Cost] {agent}: {cost_type} ${amount / 100:.2f}"

        elif event_type == "TransactionWentOverdue":
            sender = event.get("sender_id", "?")
            tx_id = event.get("tx_id", "?")[:8] if event.get("tx_id") else "?"
            return f"  [Overdue] {sender} tx={tx_id}... missed deadline"

        elif event_type == "OverdueTransactionSettled":
            sender = event.get("sender_id", event.get("sender", "?"))
            amount = event.get("amount", 0)
            return f"  [OverdueSettled] {sender} ${amount / 100:.2f}"

        elif event_type in ("LsmBilateralOffset", "LsmCycleSettlement"):
            agents = event.get("agents", event.get("agent_ids", []))
            total_value = event.get("total_value", 0)
            return f"  [LSM] {' ↔ '.join(agents[:3])} total=${total_value / 100:.2f}"

        elif event_type == "QueuedRtgs":
            sender = event.get("sender_id", "?")
            amount = event.get("amount", 0)
            return f"  [Queued] {sender} ${amount / 100:.2f} added to queue"

        elif event_type == "CollateralPosted":
            agent = event.get("agent_id", "?")
            amount = event.get("amount", 0)
            return f"  [Collateral+] {agent} posted ${amount / 100:.2f}"

        elif event_type == "CollateralReleased":
            agent = event.get("agent_id", "?")
            amount = event.get("amount", 0)
            return f"  [Collateral-] {agent} released ${amount / 100:.2f}"

        else:
            # Generic fallback
            return f"  [{event_type}] {event}"


class VerboseOutputCapture:
    """Captures verbose output from simulation runs.

    Integrates with the Rust Orchestrator to capture all events
    during simulation and organize them for verbose output.

    Example:
        >>> capture = VerboseOutputCapture()
        >>> orch = Orchestrator.new(config)
        >>> output = capture.run_and_capture(orch, ticks=100)
        >>> filtered = output.filter_for_agent("BANK_A")
    """

    def run_and_capture(
        self,
        orch: Orchestrator,
        ticks: int,
    ) -> VerboseOutput:
        """Run simulation and capture all events.

        Runs the simulation for the specified number of ticks,
        capturing events at each tick.

        Args:
            orch: Initialized Orchestrator (will call tick() internally).
            ticks: Number of ticks to run.

        Returns:
            VerboseOutput with all captured events organized by tick.
        """
        events_by_tick: dict[int, list[dict[str, Any]]] = {}
        agent_ids = list(orch.get_agent_ids())

        for tick in range(ticks):
            orch.tick()
            tick_events = orch.get_tick_events(tick)
            if tick_events:
                events_by_tick[tick] = list(tick_events)

        return VerboseOutput(
            events_by_tick=events_by_tick,
            total_ticks=ticks,
            agent_ids=agent_ids,
        )

    def capture_from_existing(
        self,
        orch: Orchestrator,
        ticks: int,
    ) -> VerboseOutput:
        """Capture events from an already-run orchestrator.

        Use this when the simulation has already been run and you
        want to capture events retroactively.

        Args:
            orch: Orchestrator that has already been run.
            ticks: Number of ticks that were run.

        Returns:
            VerboseOutput with events from all ticks.
        """
        events_by_tick: dict[int, list[dict[str, Any]]] = {}
        agent_ids = list(orch.get_agent_ids())

        for tick in range(ticks):
            tick_events = orch.get_tick_events(tick)
            if tick_events:
                events_by_tick[tick] = list(tick_events)

        return VerboseOutput(
            events_by_tick=events_by_tick,
            total_ticks=ticks,
            agent_ids=agent_ids,
        )
