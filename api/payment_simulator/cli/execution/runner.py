"""
Core simulation runner with pluggable output strategies.

Implements the Template Method pattern to eliminate 4-way code duplication.
"""

import time
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from payment_simulator._core import Orchestrator
from payment_simulator.cli.filters import EventFilter

from .stats import SimulationStats, TickResult
from .persistence import PersistenceManager


@dataclass
class SimulationConfig:
    """Configuration for simulation execution.

    Attributes:
        total_ticks: Total number of ticks to execute
        ticks_per_day: Ticks in one simulated day
        num_days: Number of days to simulate
        persist: Whether to persist to database
        full_replay: Whether to capture per-tick data
        db_path: Database file path (if persist=True)
        sim_id: Simulation ID (if persist=True)
        event_filter: Optional event filter for verbose/event_stream modes
    """

    total_ticks: int
    ticks_per_day: int
    num_days: int
    persist: bool
    full_replay: bool
    db_path: str | None = None
    sim_id: str | None = None
    event_filter: EventFilter | None = None


class OutputStrategy(Protocol):
    """Protocol for mode-specific output handling.

    Each execution mode (normal, verbose, stream, event_stream) implements
    this protocol to provide custom output behavior while sharing the same
    core execution logic.

    This eliminates the 4-way code duplication in run.py.
    """

    def on_simulation_start(self, config: SimulationConfig) -> None:
        """Called once before simulation starts.

        Args:
            config: Simulation configuration
        """
        ...

    def on_tick_start(self, tick: int) -> None:
        """Called at the start of each tick.

        Args:
            tick: Tick number
        """
        ...

    def on_tick_complete(self, result: TickResult, orch: Orchestrator) -> None:
        """Called after tick execution completes.

        Args:
            result: TickResult with events and statistics
            orch: Orchestrator instance (for querying additional state)
        """
        ...

    def on_day_complete(self, day: int, day_stats: dict[str, Any], orch: Orchestrator) -> None:
        """Called at end of each day.

        Args:
            day: Day number
            day_stats: Statistics for this day
            orch: Orchestrator instance
        """
        ...

    def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        """Called once after simulation completes.

        Args:
            final_stats: Final statistics dictionary
        """
        ...


class SimulationRunner:
    """Core simulation runner with pluggable output and persistence.

    Implements the Template Method pattern:
    - Common execution flow (tick loop, EOD detection, etc.)
    - Pluggable output strategies for mode-specific behavior
    - Centralized persistence via PersistenceManager
    - Centralized statistics via SimulationStats

    This eliminates the 4-way duplication across execution modes.

    Usage:
        config = SimulationConfig(...)
        output_strategy = VerboseModeOutput(...)
        persistence = PersistenceManager(...) if persist else None

        runner = SimulationRunner(orch, config, output_strategy, persistence)
        final_stats = runner.run()
    """

    def __init__(
        self,
        orch: Orchestrator,
        config: SimulationConfig,
        output_strategy: OutputStrategy,
        persistence: Optional[PersistenceManager] = None,
    ):
        """Initialize simulation runner.

        Args:
            orch: Orchestrator instance
            config: Simulation configuration
            output_strategy: Output strategy implementation
            persistence: Optional persistence manager
        """
        self.orch = orch
        self.config = config
        self.output = output_strategy
        self.persistence = persistence
        self.stats = SimulationStats()

    def run(self) -> dict[str, Any]:
        """Execute simulation with configured strategy.

        This is the template method that implements the common execution flow:
        1. Notify start
        2. Initialize persistence
        3. Execute tick loop with EOD handling
        4. Persist final metadata
        5. Return statistics

        Returns:
            Final statistics dictionary

        Example:
            >>> runner = SimulationRunner(orch, config, output, persistence)
            >>> stats = runner.run()
            >>> print(stats["settlement_rate"])
            0.95
        """
        # Notify output strategy
        self.output.on_simulation_start(self.config)

        # Initialize persistence
        if self.persistence:
            self.persistence.persist_initial_snapshots(self.orch)

        # Execute tick loop
        start_time = time.time()

        for tick in range(self.config.total_ticks):
            # Execute tick
            result = self._execute_tick(tick)

            # Update statistics
            self.stats.update(result)

            # Notify output strategy
            self.output.on_tick_complete(result, self.orch)

            # Persistence (full replay buffering)
            if self.persistence:
                self.persistence.on_tick_complete(tick, self.orch)

            # End-of-day handling
            if self._is_end_of_day(tick):
                day = tick // self.config.ticks_per_day
                day_stats = self.stats.get_day_stats(day)

                # Notify output strategy
                self.output.on_day_complete(day, day_stats, self.orch)

                # Persistence (EOD data + flush replay buffers)
                if self.persistence:
                    self.persistence.on_day_complete(day, self.orch)

                # Reset day statistics
                self.stats.reset_day_stats()

        # Calculate duration
        duration = time.time() - start_time

        # Persist final metadata
        if self.persistence:
            # Note: These parameters would be passed via config in real implementation
            # For now, this is a placeholder showing the interface
            pass  # Will be implemented when integrating with run.py

        # Get final statistics
        final_stats = self.stats.to_dict()
        final_stats["duration_seconds"] = duration
        final_stats["ticks_per_second"] = (
            self.config.total_ticks / duration if duration > 0 else 0
        )

        # Notify output strategy
        self.output.on_simulation_complete(final_stats)

        return final_stats

    def _execute_tick(self, tick: int) -> TickResult:
        """Execute single tick and wrap result.

        Args:
            tick: Tick number

        Returns:
            TickResult with events and statistics
        """
        # Notify output strategy
        self.output.on_tick_start(tick)

        # Execute tick
        raw_result = self.orch.tick()

        # Get events
        events = self.orch.get_tick_events(tick)

        # Apply event filter if configured
        if self.config.event_filter:
            events = [e for e in events if self.config.event_filter.matches(e, tick)]

        # Calculate day
        day = tick // self.config.ticks_per_day

        return TickResult(
            tick=tick,
            day=day,
            num_arrivals=raw_result["num_arrivals"],
            num_settlements=raw_result["num_settlements"],
            num_lsm_releases=raw_result["num_lsm_releases"],
            total_cost=raw_result["total_cost"],
            events=events,
        )

    def _is_end_of_day(self, tick: int) -> bool:
        """Check if current tick is end of day.

        Args:
            tick: Tick number

        Returns:
            True if tick is last tick of a day
        """
        return (tick + 1) % self.config.ticks_per_day == 0
