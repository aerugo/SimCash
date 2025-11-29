"""API OutputStrategy Protocol.

Defines the protocol for API output strategies, parallel to CLI's OutputStrategy.

The API OutputStrategy enables:
- WebSocket streaming of tick events
- Webhook notifications on simulation events
- Server-Sent Events for real-time updates
- Consistent output formatting across all API responses

Key differences from CLI OutputStrategy:
1. Async methods (for WebSocket/SSE compatibility)
2. Uses structured dict data (not raw Orchestrator access)
3. Returns/streams structured data (not prints to console)
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class APIOutputStrategy(Protocol):
    """Protocol for API-specific output handling.

    Parallel to CLI's OutputStrategy but designed for HTTP/WebSocket contexts.
    All methods are async to support non-blocking I/O for streaming.

    Lifecycle:
        1. on_simulation_start() - Called before first tick
        2. on_tick_complete() - Called after each tick (for streaming)
        3. on_day_complete() - Called at end of each simulated day
        4. on_simulation_complete() - Called when simulation finishes
    """

    async def on_simulation_start(self, config: dict[str, Any]) -> None:
        """Called once before simulation starts.

        Args:
            config: Simulation configuration dict with:
                - simulation_id: Unique simulation identifier
                - total_ticks: Total ticks to run
                - ticks_per_day: Ticks per simulated day
                - num_days: Number of days to simulate
        """
        ...

    async def on_tick_complete(self, tick_data: dict[str, Any]) -> None:
        """Called after each tick completes.

        Args:
            tick_data: Tick results dict with:
                - tick: Tick number
                - events: List of events that occurred
                - arrivals: Number of transaction arrivals
                - settlements: Number of settlements
                - lsm_releases: Number of LSM releases
                - total_cost: Total cost incurred this tick
        """
        ...

    async def on_day_complete(self, day: int, day_stats: dict[str, Any]) -> None:
        """Called at end of each simulated day.

        Args:
            day: Day number (0-indexed)
            day_stats: Day statistics dict with:
                - arrivals: Total arrivals this day
                - settlements: Total settlements this day
                - lsm_releases: Total LSM releases this day
                - costs: Total costs this day
        """
        ...

    async def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        """Called once after simulation completes.

        Args:
            final_stats: Final statistics dict with:
                - duration_seconds: Total wall-clock time
                - total_arrivals: Total transactions arrived
                - total_settlements: Total settlements
                - ticks_per_second: Performance metric
        """
        ...


class NullOutputStrategy:
    """No-op implementation of APIOutputStrategy.

    Use this when no output handling is needed (e.g., batch processing).
    All methods are no-ops that return immediately.
    """

    _data: None = None  # Explicitly no state

    async def on_simulation_start(self, config: dict[str, Any]) -> None:
        """No-op: Does nothing."""
        pass

    async def on_tick_complete(self, tick_data: dict[str, Any]) -> None:
        """No-op: Does nothing."""
        pass

    async def on_day_complete(self, day: int, day_stats: dict[str, Any]) -> None:
        """No-op: Does nothing."""
        pass

    async def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        """No-op: Does nothing."""
        pass
