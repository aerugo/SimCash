"""JSON Output Strategy for API responses.

Collects tick data during simulation execution and builds a complete
JSON response at the end. Used for standard REST API responses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from payment_simulator.api.services.data_service import DataService


class JSONOutputStrategy:
    """Collects simulation data for JSON API response.

    Accumulates tick-by-tick data during execution and builds
    a complete response structure when simulation completes.

    Usage:
        strategy = JSONOutputStrategy()
        await strategy.on_simulation_start(config)
        for tick in range(total_ticks):
            await strategy.on_tick_complete(tick_data)
        await strategy.on_simulation_complete(final_stats)

        response = strategy.get_response()
    """

    def __init__(self, data_service: DataService | None = None) -> None:
        """Initialize JSON output strategy.

        Args:
            data_service: Optional DataService for fetching costs/state.
                         If not provided, costs must be included in tick data.
        """
        self._data_service = data_service
        self._collected: dict[str, Any] = {
            "ticks": [],
            "days": [],
        }
        self._config: dict[str, Any] = {}
        self._final_stats: dict[str, Any] = {}

    async def on_simulation_start(self, config: dict[str, Any]) -> None:
        """Store simulation configuration.

        Args:
            config: Simulation configuration
        """
        self._config = config.copy()

    async def on_tick_complete(self, tick_data: dict[str, Any]) -> None:
        """Collect tick data.

        Args:
            tick_data: Tick results dict
        """
        self._collected["ticks"].append(tick_data.copy())

    async def on_day_complete(self, day: int, day_stats: dict[str, Any]) -> None:
        """Collect day statistics.

        Args:
            day: Day number
            day_stats: Day statistics
        """
        self._collected["days"].append({
            "day": day,
            **day_stats,
        })

    async def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        """Store final statistics.

        Args:
            final_stats: Final simulation statistics
        """
        self._final_stats = final_stats.copy()

    def get_collected_data(self) -> dict[str, Any]:
        """Get raw collected data.

        Returns:
            Dict with 'ticks' and 'days' lists
        """
        return self._collected

    def get_response(self) -> dict[str, Any]:
        """Build complete JSON response.

        Returns:
            Complete response dict with config, ticks, and final_stats
        """
        return {
            "simulation_id": self._config.get("simulation_id"),
            "total_ticks": self._config.get("total_ticks"),
            "ticks_per_day": self._config.get("ticks_per_day"),
            "num_days": self._config.get("num_days"),
            "ticks": self._collected["ticks"],
            "days": self._collected["days"],
            "final_stats": self._final_stats,
        }

    def get_agent_costs(self, agent_ids: list[str]) -> dict[str, Any]:
        """Get agent costs using DataService.

        Args:
            agent_ids: List of agent IDs

        Returns:
            Dict mapping agent_id -> cost breakdown

        Raises:
            ValueError: If no DataService configured
        """
        if self._data_service is None:
            raise ValueError("No DataService configured for cost lookup")

        return self._data_service.get_costs(agent_ids)
