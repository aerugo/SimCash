"""
Output strategy implementations for different execution modes.

Each strategy implements the OutputStrategy protocol to provide mode-specific
output behavior while using the same core execution logic.
"""

from io import StringIO
from typing import TYPE_CHECKING, Any, Optional

from payment_simulator._core import Orchestrator  # type: ignore[attr-defined]

if TYPE_CHECKING:
    from rich.progress import Progress, TaskID
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
        event_filter: Optional[EventFilter] = None,
        show_debug: bool = False
    ):
        """Initialize verbose mode output.

        Args:
            orch: Orchestrator instance
            agent_ids: List of agent IDs
            ticks_per_day: Ticks in one simulated day
            event_filter: Optional event filter
            show_debug: If True, show performance diagnostics
        """
        self.orch = orch
        self.agent_ids = agent_ids
        self.ticks_per_day = ticks_per_day
        self.event_filter = event_filter
        self.show_debug = show_debug

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
        """Log detailed tick information using shared display logic."""
        from payment_simulator.cli.execution.display import display_tick_verbose_output
        from payment_simulator.cli.execution.state_provider import OrchestratorStateProvider
        from payment_simulator.cli.output import log_performance_diagnostics

        # Create StateProvider wrapper for live orchestrator
        provider = OrchestratorStateProvider(orch)

        # Use shared display function (SINGLE SOURCE OF TRUTH)
        # This ensures live execution and replay can NEVER diverge
        self.prev_balances = display_tick_verbose_output(
            provider=provider,
            events=result.events,
            tick_num=result.tick,
            agent_ids=self.agent_ids,
            prev_balances=self.prev_balances,
            num_arrivals=result.num_arrivals,
            num_settlements=result.num_settlements,
            num_lsm_releases=result.num_lsm_releases,
            total_cost=result.total_cost,
            event_filter=self.event_filter,
        )

        # Show performance diagnostics if debug mode is enabled
        if self.show_debug and result.timing:
            log_performance_diagnostics(result.timing, result.tick)

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

            # Calculate credit utilization (Issue #4 fix - CORRECTED)
            # CRITICAL: Use total allowed overdraft (credit + collateral backing), not just unsecured_cap!
            allowed_overdraft = orch.get_agent_allowed_overdraft_limit(agent_id)
            credit_util = 0
            if allowed_overdraft and allowed_overdraft > 0:
                # If balance is negative, we're using credit equal to the overdraft amount
                # If balance is positive, we're not using any credit
                used = max(0, -balance)
                credit_util = (used / allowed_overdraft) * 100

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

    def __init__(self, quiet: bool, total_ticks: int, show_debug: bool = False):
        self.quiet = quiet
        self.total_ticks = total_ticks
        self.show_debug = show_debug
        self.progress: Optional[Progress] = None
        self.task: Optional[TaskID] = None

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
        # Show compact performance diagnostics if debug mode is enabled
        # Print to stderr so it appears alongside the progress bar
        if self.show_debug and result.timing:
            import sys
            total_ms = result.timing["total_micros"] / 1000.0

            # Get top phases
            phases = [
                ("Arrivals", result.timing["arrivals_micros"]),
                ("Policy", result.timing["policy_eval_micros"]),
                ("RTGS", result.timing["rtgs_settlement_micros"]),
                ("LSM", result.timing["lsm_micros"]),
            ]

            # Sort and take top 2
            sorted_phases = sorted(phases, key=lambda x: x[1], reverse=True)[:2]

            # Format phase info with milliseconds
            phase_strs = []
            for name, micros in sorted_phases:
                ms = micros / 1000.0
                if ms >= 0.01:  # Only show phases that took at least 0.01ms
                    phase_strs.append(f"{name}:{ms:.2f}ms")

            phase_info = ", ".join(phase_strs) if phase_strs else "balanced"

            # Print directly to stderr (bypasses Rich's Live display)
            print(f"⏱️  Tick {result.tick}: {total_ms:.2f}ms ({phase_info})", file=sys.stderr)

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
