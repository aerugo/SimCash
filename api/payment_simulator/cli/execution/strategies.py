"""
Output strategy implementations for different execution modes.

Each strategy implements the OutputStrategy protocol to provide mode-specific
output behavior while using the same core execution logic.
"""

from io import StringIO
from typing import Any

from payment_simulator._core import Orchestrator
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

        from payment_simulator.cli.output import output_json
        output_json(final_stats)


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
