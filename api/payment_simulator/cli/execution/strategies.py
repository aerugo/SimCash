"""
Output strategy implementations for different execution modes.

Each strategy implements the OutputStrategy protocol to provide mode-specific
output behavior while using the same core execution logic.
"""

from io import StringIO
from typing import Any, Optional

from payment_simulator._core import Orchestrator
from payment_simulator.cli.filters import EventFilter
from payment_simulator.cli.execution.runner import OutputStrategy, SimulationConfig
from payment_simulator.cli.execution.stats import TickResult


class QuietOutputStrategy:
    """Minimal output strategy (suppresses all logs, only final JSON)."""

    def on_simulation_start(self, config: SimulationConfig) -> None:
        pass

    def on_tick_start(self, tick: int) -> None:
        pass

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        pass

    def on_day_complete(self, day: int, day_stats: dict[str, Any], orch: Orchestrator) -> None:
        pass

    def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        # Output final JSON
        from payment_simulator.cli.output import output_json
        output_json(final_stats)


class VerboseModeOutput:
    """Verbose mode: detailed real-time event logging with rich formatting.

    Displays comprehensive tick-by-tick information including:
    - Transaction arrivals with full details
    - Policy decisions by agents
    - Settlement activity (RTGS + LSM)
    - Agent queue states
    - Cost breakdowns
    - End-of-day summaries
    """

    def __init__(
        self,
        orch: Orchestrator,
        agent_ids: list[str],
        ticks_per_day: int,
        event_filter: Optional[EventFilter] = None
    ):
        """Initialize verbose mode output.

        Args:
            orch: Orchestrator instance
            agent_ids: List of agent IDs
            ticks_per_day: Ticks in one simulated day
            event_filter: Optional event filter
        """
        self.orch = orch
        self.agent_ids = agent_ids
        self.ticks_per_day = ticks_per_day
        self.event_filter = event_filter

        # Track previous balances for change detection
        self.prev_balances = {
            agent_id: orch.get_agent_balance(agent_id) for agent_id in agent_ids
        }

    def on_simulation_start(self, config: SimulationConfig) -> None:
        """Start verbose mode (suppress startup message)."""
        from payment_simulator.cli.output import log_info
        log_info(f"Running {config.total_ticks} ticks (verbose mode)...", quiet=True)

    def on_tick_start(self, tick: int) -> None:
        """Log tick header."""
        from payment_simulator.cli.output import log_tick_start
        log_tick_start(tick)

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        """Log detailed tick information across 8 sections."""
        from payment_simulator.cli.output import (
            log_transaction_arrivals,
            log_policy_decisions,
            log_settlement_details,
            log_queued_rtgs,
            log_lsm_cycle_visualization,
            log_collateral_activity,
            log_agent_queues_detailed,
            log_cost_accrual_events,
            log_cost_breakdown,
            log_tick_summary,
        )

        # Apply event filter if specified
        display_events = result.events
        if self.event_filter:
            display_events = [e for e in result.events if self.event_filter.matches(e, result.tick)]

        # ═══════════════════════════════════════════════════════════
        # SECTION 1: ARRIVALS (detailed)
        # ═══════════════════════════════════════════════════════════
        if result.num_arrivals > 0:
            log_transaction_arrivals(orch, display_events)

        # ═══════════════════════════════════════════════════════════
        # SECTION 2: POLICY DECISIONS
        # ═══════════════════════════════════════════════════════════
        log_policy_decisions(display_events)

        # ═══════════════════════════════════════════════════════════
        # SECTION 3: SETTLEMENTS (detailed with mechanisms)
        # ═══════════════════════════════════════════════════════════
        if result.num_settlements > 0 or any(
            e.get("event_type") in ["LsmBilateralOffset", "LsmCycleSettlement"]
            for e in display_events
        ):
            log_settlement_details(orch, display_events, result.tick)

        # ═══════════════════════════════════════════════════════════
        # SECTION 3.5: QUEUED TRANSACTIONS (RTGS)
        # ═══════════════════════════════════════════════════════════
        log_queued_rtgs(display_events)

        # ═══════════════════════════════════════════════════════════
        # SECTION 4: LSM CYCLE VISUALIZATION
        # ═══════════════════════════════════════════════════════════
        log_lsm_cycle_visualization(display_events)

        # ═══════════════════════════════════════════════════════════
        # SECTION 5: COLLATERAL ACTIVITY
        # ═══════════════════════════════════════════════════════════
        log_collateral_activity(display_events)

        # ═══════════════════════════════════════════════════════════
        # SECTION 6: AGENT STATES (detailed queues)
        # ═══════════════════════════════════════════════════════════
        for agent_id in self.agent_ids:
            current_balance = orch.get_agent_balance(agent_id)
            balance_change = current_balance - self.prev_balances[agent_id]

            # Only show agents with activity or non-empty queues
            queue1_size = orch.get_queue1_size(agent_id)
            rtgs_queue = orch.get_rtgs_queue_contents()
            agent_in_rtgs = any(
                orch.get_transaction_details(tx_id).get("sender_id") == agent_id
                for tx_id in rtgs_queue
                if orch.get_transaction_details(tx_id)
            )

            if balance_change != 0 or queue1_size > 0 or agent_in_rtgs:
                log_agent_queues_detailed(
                    orch, agent_id, current_balance, balance_change
                )

            self.prev_balances[agent_id] = current_balance

        # ═══════════════════════════════════════════════════════════
        # SECTION 6.5: COST ACCRUAL EVENTS
        # ═══════════════════════════════════════════════════════════
        log_cost_accrual_events(display_events)

        # ═══════════════════════════════════════════════════════════
        # SECTION 7: COST BREAKDOWN
        # ═══════════════════════════════════════════════════════════
        if result.total_cost > 0:
            log_cost_breakdown(orch, self.agent_ids)

        # ═══════════════════════════════════════════════════════════
        # SECTION 8: TICK SUMMARY
        # ═══════════════════════════════════════════════════════════
        total_queued = sum(orch.get_queue1_size(aid) for aid in self.agent_ids)
        log_tick_summary(
            result.num_arrivals,
            result.num_settlements,
            result.num_lsm_releases,
            total_queued,
        )

    def on_day_complete(self, day: int, day_stats: dict[str, Any], orch: Orchestrator) -> None:
        """Log end-of-day summary with agent performance."""
        from payment_simulator.cli.output import (
            log_end_of_day_event,
            log_end_of_day_statistics,
        )

        # Gather agent statistics for end-of-day summary
        agent_stats = []
        for agent_id in self.agent_ids:
            balance = orch.get_agent_balance(agent_id)
            credit_limit = orch.get_agent_credit_limit(agent_id)

            # Calculate credit utilization
            credit_util = 0
            if credit_limit and credit_limit > 0:
                used = max(0, credit_limit - balance)
                credit_util = (used / credit_limit) * 100

            # Get queue sizes
            queue1_size = orch.get_queue1_size(agent_id)
            rtgs_queue = orch.get_rtgs_queue_contents()
            queue2_size = sum(
                1
                for tx_id in rtgs_queue
                if orch.get_transaction_details(tx_id)
                and orch.get_transaction_details(tx_id).get("sender_id") == agent_id
            )

            # Get costs for this agent (cumulative for the day)
            costs = orch.get_agent_accumulated_costs(agent_id)
            agent_total_costs = 0
            if costs:
                agent_total_costs = sum([
                    costs.get("liquidity_cost", 0),
                    costs.get("delay_cost", 0),
                    costs.get("collateral_cost", 0),
                    costs.get("deadline_penalty", 0),
                    costs.get("split_friction_cost", 0),
                ])

            agent_stats.append({
                "id": agent_id,
                "final_balance": balance,
                "credit_utilization": credit_util,
                "queue1_size": queue1_size,
                "queue2_size": queue2_size,
                "total_costs": agent_total_costs,
            })

        # Get EOD events for display
        events = orch.get_tick_events((day + 1) * self.ticks_per_day - 1)
        log_end_of_day_event(events)

        log_end_of_day_statistics(
            day=day,
            total_arrivals=day_stats["arrivals"],
            total_settlements=day_stats["settlements"],
            total_lsm_releases=day_stats["lsm_releases"],
            total_costs=day_stats["costs"],
            agent_stats=agent_stats,
        )

    def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        """Log simulation completion summary."""
        from payment_simulator.cli.output import log_success

        duration = final_stats.get("duration_seconds", 0)
        ticks_per_second = final_stats.get("ticks_per_second", 0)
        total_ticks = int(duration * ticks_per_second) if duration > 0 else 0

        log_success(
            f"\nSimulation complete: {total_ticks} ticks in {duration:.2f}s ({ticks_per_second:.1f} ticks/s)",
            quiet=False
        )


class NormalModeOutput:
    """Normal mode: progress bar + final JSON output."""

    def __init__(self, quiet: bool, total_ticks: int):
        self.quiet = quiet
        self.total_ticks = total_ticks
        self.progress = None
        self.task = None

    def on_simulation_start(self, config: SimulationConfig) -> None:
        if not self.quiet:
            from payment_simulator.cli.output import create_progress
            self.progress = create_progress()
            self.task = self.progress.add_task(
                "[cyan]Running simulation...",
                total=self.total_ticks
            )
            self.progress.__enter__()

    def on_tick_start(self, tick: int) -> None:
        pass

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        if self.progress:
            self.progress.update(self.task, advance=1)

    def on_day_complete(self, day: int, day_stats: dict[str, Any], orch: Orchestrator) -> None:
        pass

    def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        if self.progress:
            self.progress.__exit__(None, None, None)

        # Note: JSON output is handled by run.py after building full output structure
        # with agent states, simulation metadata, etc. (lines 1442-1482 in run.py)


class StreamModeOutput:
    """Stream mode: JSONL output per tick."""

    def on_simulation_start(self, config: SimulationConfig) -> None:
        from payment_simulator.cli.output import log_info
        log_info(f"Running {config.total_ticks} ticks (streaming)...", quiet=True)

    def on_tick_start(self, tick: int) -> None:
        pass

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        from payment_simulator.cli.output import output_jsonl
        output_jsonl({
            "tick": result.tick,
            "arrivals": result.num_arrivals,
            "settlements": result.num_settlements,
            "lsm_releases": result.num_lsm_releases,
            "costs": result.total_cost,
        })

    def on_day_complete(self, day: int, day_stats: dict[str, Any], orch: Orchestrator) -> None:
        pass

    def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        from payment_simulator.cli.output import log_success
        log_success(f"Completed {final_stats['total_arrivals']} transactions", quiet=True)


class EventStreamModeOutput:
    """Event stream mode: JSONL output per event."""

    def on_simulation_start(self, config: SimulationConfig) -> None:
        from payment_simulator.cli.output import log_info
        log_info(f"Running {config.total_ticks} ticks (event stream mode)...", quiet=True)

    def on_tick_start(self, tick: int) -> None:
        pass

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        from payment_simulator.cli.output import log_event_chronological

        for event in result.events:
            log_event_chronological(event, result.tick, quiet=False)

    def on_day_complete(self, day: int, day_stats: dict[str, Any], orch: Orchestrator) -> None:
        pass

    def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        from payment_simulator.cli.output import log_success, log_info, output_json

        ticks_per_second = final_stats.get("ticks_per_second", 0)
        duration = final_stats.get("duration_seconds", 0)
        total_ticks = int(final_stats.get("total_arrivals", 0) / 5)  # Approximation

        log_success(
            f"\nSimulation complete: {total_ticks} ticks in {duration:.2f}s ({ticks_per_second:.1f} ticks/s)",
            quiet=False
        )

        # Output final stats as JSON
        output_json(final_stats)
