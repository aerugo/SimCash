"""API Output Strategies module.

Provides OutputStrategy implementations for different API output modes,
parallel to CLI's OutputStrategy pattern.

Available strategies:
    - JSONOutputStrategy: Collects data for JSON response
    - WebSocketOutputStrategy: Streams events over WebSocket
    - NullOutputStrategy: No-op implementation

Factory function:
    create_output_strategy(mode, **kwargs) -> APIOutputStrategy
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .json_strategy import JSONOutputStrategy
from .protocol import APIOutputStrategy, NullOutputStrategy
from .websocket_strategy import WebSocketOutputStrategy

if TYPE_CHECKING:
    from fastapi import WebSocket


__all__ = [
    "APIOutputStrategy",
    "JSONOutputStrategy",
    "WebSocketOutputStrategy",
    "NullOutputStrategy",
    "create_output_strategy",
]


def create_output_strategy(
    mode: str = "json",
    websocket: WebSocket | None = None,
    **kwargs: Any,
) -> APIOutputStrategy:
    """Factory function to create appropriate output strategy.

    Args:
        mode: Output mode - 'json', 'websocket', or 'null'
        websocket: WebSocket connection (required for 'websocket' mode)
        **kwargs: Additional arguments passed to strategy constructor

    Returns:
        APIOutputStrategy implementation

    Raises:
        ValueError: If mode is 'websocket' but no websocket provided
        ValueError: If mode is unknown

    Examples:
        # JSON response mode (default)
        strategy = create_output_strategy(mode="json")

        # WebSocket streaming mode
        strategy = create_output_strategy(mode="websocket", websocket=ws)

        # No-op mode (for testing/batch)
        strategy = create_output_strategy(mode="null")
    """
    if mode == "json":
        return JSONOutputStrategy(**kwargs)

    if mode == "websocket":
        if websocket is None:
            raise ValueError("WebSocket mode requires a websocket connection")
        return WebSocketOutputStrategy(websocket=websocket)

    if mode == "null":
        return NullOutputStrategy()

    raise ValueError(f"Unknown output strategy mode: {mode}")
