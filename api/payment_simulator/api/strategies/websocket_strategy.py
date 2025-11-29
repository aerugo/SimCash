"""WebSocket Output Strategy for real-time streaming.

Sends tick events and simulation state over WebSocket connection
for real-time client updates.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WebSocketOutputStrategy:
    """Streams simulation events over WebSocket.

    Sends JSON messages to connected WebSocket client on each
    tick completion and simulation lifecycle event.

    Message types:
        - simulation_start: Sent when simulation begins
        - tick_complete: Sent after each tick
        - day_complete: Sent at end of each day
        - simulation_complete: Sent when simulation finishes

    Usage:
        @router.websocket("/simulations/{sim_id}/stream")
        async def stream_simulation(websocket: WebSocket, sim_id: str):
            await websocket.accept()
            strategy = WebSocketOutputStrategy(websocket)
            # Run simulation with strategy...
    """

    def __init__(self, websocket: WebSocket) -> None:
        """Initialize WebSocket output strategy.

        Args:
            websocket: FastAPI WebSocket connection
        """
        self._ws = websocket
        self._closed = False

    @property
    def is_closed(self) -> bool:
        """Check if WebSocket connection is closed.

        Returns:
            True if connection was closed or errored
        """
        return self._closed

    async def _safe_send(self, data: dict[str, Any]) -> None:
        """Send data over WebSocket, handling errors gracefully.

        Args:
            data: Dict to send as JSON
        """
        if self._closed:
            return

        try:
            await self._ws.send_json(data)
        except Exception as e:
            logger.warning(f"WebSocket send failed: {e}")
            self._closed = True

    async def on_simulation_start(self, config: dict[str, Any]) -> None:
        """Send simulation start message.

        Args:
            config: Simulation configuration
        """
        await self._safe_send({
            "type": "simulation_start",
            "config": config,
        })

    async def on_tick_complete(self, tick_data: dict[str, Any]) -> None:
        """Send tick completion message.

        Args:
            tick_data: Tick results with events
        """
        await self._safe_send({
            "type": "tick_complete",
            "tick": tick_data.get("tick"),
            "events": tick_data.get("events", []),
            "arrivals": tick_data.get("arrivals", 0),
            "settlements": tick_data.get("settlements", 0),
            "lsm_releases": tick_data.get("lsm_releases", 0),
            "total_cost": tick_data.get("total_cost", 0),
        })

    async def on_day_complete(self, day: int, day_stats: dict[str, Any]) -> None:
        """Send day completion message.

        Args:
            day: Day number
            day_stats: Day statistics
        """
        await self._safe_send({
            "type": "day_complete",
            "day": day,
            "stats": day_stats,
        })

    async def on_simulation_complete(self, final_stats: dict[str, Any]) -> None:
        """Send simulation completion message.

        Args:
            final_stats: Final simulation statistics
        """
        await self._safe_send({
            "type": "simulation_complete",
            "final_stats": final_stats,
        })
