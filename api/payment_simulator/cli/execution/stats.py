"""
Centralized statistics tracking for simulation execution.

Eliminates duplication of statistics tracking across 4 execution modes.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class TickResult:
    """Result of executing a single tick.

    This is a normalized representation of tick execution that can be
    consumed by output strategies and statistics tracking.

    Attributes:
        tick: Tick number (0-indexed)
        day: Day number (0-indexed)
        num_arrivals: Number of new transactions this tick
        num_settlements: Number of settled transactions this tick
        num_lsm_releases: Number of transactions released from LSM this tick
        total_cost: Total costs accrued this tick (cents)
        events: List of all events that occurred this tick
        timing: Optional timing information for performance diagnostics
    """

    tick: int
    day: int
    num_arrivals: int
    num_settlements: int
    num_lsm_releases: int
    total_cost: int
    events: list[dict[str, Any]]
    timing: dict[str, Any] | None = None


class SimulationStats:
    """Centralized statistics tracking for simulation execution.

    Maintains both total (simulation-wide) and day (current day) statistics.
    Day statistics reset at end of each day for EOD reporting.

    This class eliminates the 4-way duplication of statistics tracking
    across normal, verbose, stream, and event_stream modes.

    Usage:
        stats = SimulationStats()

        for tick in range(total_ticks):
            result = execute_tick(tick)
            stats.update(result)

            if is_end_of_day(tick):
                day_stats = stats.get_day_stats(day)
                report_eod(day_stats)
                stats.reset_day_stats()

        final_stats = stats.to_dict()
        output_json(final_stats)
    """

    def __init__(self) -> None:
        """Initialize statistics with all counters at zero."""
        # Total statistics (across all days)
        self.total_arrivals = 0
        self.total_settlements = 0
        self.total_lsm_releases = 0
        self.total_costs = 0

        # Day statistics (reset at EOD)
        self.day_arrivals = 0
        self.day_settlements = 0
        self.day_lsm_releases = 0
        self.day_costs = 0

    def update(self, result: TickResult) -> None:
        """Update statistics with tick result.

        Increments both total and day counters.

        Args:
            result: TickResult from executing a single tick

        Example:
            >>> stats = SimulationStats()
            >>> result = TickResult(
            ...     tick=0, day=0, num_arrivals=10, num_settlements=8,
            ...     num_lsm_releases=2, total_cost=5000, events=[]
            ... )
            >>> stats.update(result)
            >>> stats.total_arrivals
            10
            >>> stats.day_arrivals
            10
        """
        # Update totals
        self.total_arrivals += result.num_arrivals
        self.total_settlements += result.num_settlements
        self.total_lsm_releases += result.num_lsm_releases
        self.total_costs += result.total_cost

        # Update day stats
        self.day_arrivals += result.num_arrivals
        self.day_settlements += result.num_settlements
        self.day_lsm_releases += result.num_lsm_releases
        self.day_costs += result.total_cost

    def get_day_stats(self, day: int) -> dict[str, Any]:
        """Get statistics for current day.

        Returns accumulated day statistics since last reset.

        Args:
            day: Day number for labeling

        Returns:
            Dictionary with day statistics

        Example:
            >>> stats = SimulationStats()
            >>> # ... update with tick results ...
            >>> day_stats = stats.get_day_stats(0)
            >>> day_stats["arrivals"]
            42
        """
        return {
            "day": day,
            "arrivals": self.day_arrivals,
            "settlements": self.day_settlements,
            "lsm_releases": self.day_lsm_releases,
            "costs": self.day_costs,
        }

    def reset_day_stats(self) -> None:
        """Reset day statistics for next day.

        Zeros day counters while preserving totals. Called at end of each day.

        Example:
            >>> stats = SimulationStats()
            >>> stats.update(result)
            >>> stats.day_arrivals
            10
            >>> stats.reset_day_stats()
            >>> stats.day_arrivals
            0
            >>> stats.total_arrivals  # Totals preserved
            10
        """
        self.day_arrivals = 0
        self.day_settlements = 0
        self.day_lsm_releases = 0
        self.day_costs = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for final output.

        Returns total statistics with calculated settlement rate.

        Returns:
            Dictionary with all statistics for JSON output

        Example:
            >>> stats = SimulationStats()
            >>> # ... run simulation ...
            >>> final_stats = stats.to_dict()
            >>> final_stats["settlement_rate"]
            0.95
        """
        return {
            "total_arrivals": self.total_arrivals,
            "total_settlements": self.total_settlements,
            "total_lsm_releases": self.total_lsm_releases,
            "total_costs": self.total_costs,
            "settlement_rate": (
                self.total_settlements / self.total_arrivals
                if self.total_arrivals > 0
                else 0
            ),
        }
