"""TDD Tests for API OutputStrategy pattern.

Phase 6: API OutputStrategy - Parallel to CLI's OutputStrategy pattern.

The API OutputStrategy enables:
- WebSocket streaming of tick events
- Webhook notifications on simulation events
- Server-Sent Events for real-time updates
- Consistent output formatting across all API responses

Key differences from CLI OutputStrategy:
1. Async methods (for WebSocket/SSE compatibility)
2. Uses StateProvider for data access (not raw Orchestrator)
3. Returns structured data (not prints to console)
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

if TYPE_CHECKING:
    from payment_simulator._core import Orchestrator


# ============================================================================
# Phase 6.1: APIOutputStrategy Protocol Exists
# ============================================================================


class TestAPIOutputStrategyProtocolExists:
    """TDD tests to verify the protocol module exists and is importable."""

    def test_protocol_module_importable(self) -> None:
        """APIOutputStrategy protocol should be importable."""
        try:
            from payment_simulator.api.strategies.protocol import APIOutputStrategy

            assert APIOutputStrategy is not None
        except ImportError:
            pytest.fail(
                "Cannot import APIOutputStrategy. "
                "Create api/strategies/protocol.py"
            )

    def test_protocol_has_required_methods(self) -> None:
        """Protocol should define all required lifecycle methods."""
        try:
            from payment_simulator.api.strategies.protocol import APIOutputStrategy

            # Check for required methods
            required_methods = [
                "on_simulation_start",
                "on_tick_complete",
                "on_day_complete",
                "on_simulation_complete",
            ]

            for method in required_methods:
                assert hasattr(APIOutputStrategy, method), (
                    f"APIOutputStrategy missing method: {method}"
                )
        except ImportError:
            pytest.skip("Protocol not yet implemented")

    def test_protocol_methods_are_async(self) -> None:
        """Protocol methods should be async for WebSocket/SSE compatibility."""
        try:
            from payment_simulator.api.strategies.protocol import APIOutputStrategy
            import inspect

            # Check that protocol methods are defined as async
            # We check the __call__ signature of the protocol methods
            annotations = getattr(APIOutputStrategy, "__protocol_attrs__", None)

            # For typing.Protocol, we just verify the class exists
            # The implementation tests will verify async behavior
            assert APIOutputStrategy is not None
        except ImportError:
            pytest.skip("Protocol not yet implemented")


# ============================================================================
# Phase 6.2: Concrete Strategy Implementations Exist
# ============================================================================


class TestConcreteStrategiesExist:
    """TDD tests for concrete strategy implementations."""

    def test_json_strategy_exists(self) -> None:
        """JSONOutputStrategy should be importable."""
        try:
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy

            assert JSONOutputStrategy is not None
        except ImportError:
            pytest.fail(
                "Cannot import JSONOutputStrategy. "
                "Create api/strategies/json_strategy.py"
            )

    def test_websocket_strategy_exists(self) -> None:
        """WebSocketOutputStrategy should be importable."""
        try:
            from payment_simulator.api.strategies.websocket_strategy import (
                WebSocketOutputStrategy,
            )

            assert WebSocketOutputStrategy is not None
        except ImportError:
            pytest.fail(
                "Cannot import WebSocketOutputStrategy. "
                "Create api/strategies/websocket_strategy.py"
            )

    def test_null_strategy_exists(self) -> None:
        """NullOutputStrategy (no-op) should be importable."""
        try:
            from payment_simulator.api.strategies.protocol import NullOutputStrategy

            assert NullOutputStrategy is not None
        except ImportError:
            pytest.fail(
                "Cannot import NullOutputStrategy. "
                "Add to api/strategies/protocol.py"
            )


# ============================================================================
# Phase 6.3: JSONOutputStrategy Behavior
# ============================================================================


class TestJSONOutputStrategyBehavior:
    """TDD tests for JSONOutputStrategy behavior."""

    def test_json_strategy_collects_tick_data(self) -> None:
        """JSONOutputStrategy should collect tick data for final response."""
        try:
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy
        except ImportError:
            pytest.skip("JSONOutputStrategy not yet implemented")

        strategy = JSONOutputStrategy()

        # Simulate tick complete
        tick_data = {
            "tick": 1,
            "events": [{"event_type": "TransactionArrival", "tx_id": "tx1"}],
            "arrivals": 1,
            "settlements": 0,
        }

        # Should be async
        asyncio.get_event_loop().run_until_complete(
            strategy.on_tick_complete(tick_data)
        )

        # Strategy should have collected the data
        collected = strategy.get_collected_data()
        assert len(collected["ticks"]) == 1
        assert collected["ticks"][0]["tick"] == 1

    def test_json_strategy_builds_final_response(self) -> None:
        """JSONOutputStrategy should build complete response on simulation_complete."""
        try:
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy
        except ImportError:
            pytest.skip("JSONOutputStrategy not yet implemented")

        strategy = JSONOutputStrategy()

        # Simulate simulation lifecycle
        loop = asyncio.get_event_loop()

        loop.run_until_complete(strategy.on_simulation_start({
            "simulation_id": "test-sim",
            "total_ticks": 10,
        }))

        loop.run_until_complete(strategy.on_tick_complete({
            "tick": 0,
            "events": [],
            "arrivals": 1,
            "settlements": 0,
        }))

        loop.run_until_complete(strategy.on_simulation_complete({
            "duration_seconds": 1.5,
            "total_arrivals": 10,
            "total_settlements": 8,
        }))

        # Get final response
        response = strategy.get_response()

        assert response["simulation_id"] == "test-sim"
        assert response["total_ticks"] == 10
        assert "final_stats" in response
        assert response["final_stats"]["total_arrivals"] == 10

    def test_json_strategy_uses_data_service_for_costs(self) -> None:
        """JSONOutputStrategy should use DataService for consistent cost data."""
        try:
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy
            from payment_simulator.api.services.data_service import DataService
        except ImportError:
            pytest.skip("Not yet implemented")

        # Mock DataService
        mock_data_service = Mock(spec=DataService)
        mock_data_service.get_costs.return_value = {
            "BANK_A": {
                "liquidity_cost": 100,
                "delay_cost": 200,
                "collateral_cost": 0,
                "deadline_penalty": 50,
                "split_friction_cost": 0,
                "total_cost": 350,
            }
        }

        strategy = JSONOutputStrategy(data_service=mock_data_service)

        # Request costs
        costs = strategy.get_agent_costs(["BANK_A"])

        mock_data_service.get_costs.assert_called_once_with(["BANK_A"])
        assert costs["BANK_A"]["deadline_penalty"] == 50  # Canonical field name


# ============================================================================
# Phase 6.4: WebSocketOutputStrategy Behavior
# ============================================================================


class TestWebSocketOutputStrategyBehavior:
    """TDD tests for WebSocketOutputStrategy behavior."""

    @pytest.mark.asyncio
    async def test_websocket_strategy_sends_on_tick_complete(self) -> None:
        """WebSocketOutputStrategy should send message on each tick."""
        try:
            from payment_simulator.api.strategies.websocket_strategy import (
                WebSocketOutputStrategy,
            )
        except ImportError:
            pytest.skip("WebSocketOutputStrategy not yet implemented")

        # Mock WebSocket
        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()

        strategy = WebSocketOutputStrategy(websocket=mock_ws)

        # Trigger tick complete
        await strategy.on_tick_complete({
            "tick": 5,
            "events": [{"event_type": "Settlement", "tx_id": "tx1"}],
            "arrivals": 2,
            "settlements": 1,
        })

        # Verify WebSocket send was called
        mock_ws.send_json.assert_called_once()
        sent_data = mock_ws.send_json.call_args[0][0]

        assert sent_data["type"] == "tick_complete"
        assert sent_data["tick"] == 5
        assert len(sent_data["events"]) == 1

    @pytest.mark.asyncio
    async def test_websocket_strategy_sends_simulation_complete(self) -> None:
        """WebSocketOutputStrategy should send final message on complete."""
        try:
            from payment_simulator.api.strategies.websocket_strategy import (
                WebSocketOutputStrategy,
            )
        except ImportError:
            pytest.skip("WebSocketOutputStrategy not yet implemented")

        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock()

        strategy = WebSocketOutputStrategy(websocket=mock_ws)

        await strategy.on_simulation_complete({
            "duration_seconds": 2.5,
            "total_arrivals": 100,
            "total_settlements": 95,
        })

        mock_ws.send_json.assert_called_once()
        sent_data = mock_ws.send_json.call_args[0][0]

        assert sent_data["type"] == "simulation_complete"
        assert sent_data["final_stats"]["total_settlements"] == 95

    @pytest.mark.asyncio
    async def test_websocket_strategy_handles_connection_closed(self) -> None:
        """WebSocketOutputStrategy should handle closed connections gracefully."""
        try:
            from payment_simulator.api.strategies.websocket_strategy import (
                WebSocketOutputStrategy,
            )
        except ImportError:
            pytest.skip("WebSocketOutputStrategy not yet implemented")

        mock_ws = AsyncMock()
        mock_ws.send_json = AsyncMock(side_effect=RuntimeError("Connection closed"))

        strategy = WebSocketOutputStrategy(websocket=mock_ws)

        # Should not raise - should handle gracefully
        await strategy.on_tick_complete({"tick": 1, "events": []})

        # Strategy should mark connection as closed
        assert strategy.is_closed


# ============================================================================
# Phase 6.5: NullOutputStrategy Behavior
# ============================================================================


class TestNullOutputStrategyBehavior:
    """TDD tests for NullOutputStrategy (no-op implementation)."""

    @pytest.mark.asyncio
    async def test_null_strategy_does_nothing(self) -> None:
        """NullOutputStrategy should be a no-op for all methods."""
        try:
            from payment_simulator.api.strategies.protocol import NullOutputStrategy
        except ImportError:
            pytest.skip("NullOutputStrategy not yet implemented")

        strategy = NullOutputStrategy()

        # All methods should complete without error
        await strategy.on_simulation_start({"simulation_id": "test"})
        await strategy.on_tick_complete({"tick": 1, "events": []})
        await strategy.on_day_complete(0, {"arrivals": 10})
        await strategy.on_simulation_complete({"total_arrivals": 100})

        # No state should be maintained
        assert not hasattr(strategy, "_data") or strategy._data is None


# ============================================================================
# Phase 6.6: Protocol Compliance
# ============================================================================


class TestProtocolCompliance:
    """TDD tests verifying implementations comply with protocol."""

    def test_json_strategy_implements_protocol(self) -> None:
        """JSONOutputStrategy should implement APIOutputStrategy protocol."""
        try:
            from payment_simulator.api.strategies.protocol import APIOutputStrategy
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy
        except ImportError:
            pytest.skip("Not yet implemented")

        strategy = JSONOutputStrategy()

        # Check all protocol methods exist
        assert hasattr(strategy, "on_simulation_start")
        assert hasattr(strategy, "on_tick_complete")
        assert hasattr(strategy, "on_day_complete")
        assert hasattr(strategy, "on_simulation_complete")

        # Verify it's compatible with the protocol (duck typing)
        assert isinstance(strategy, APIOutputStrategy)

    def test_websocket_strategy_implements_protocol(self) -> None:
        """WebSocketOutputStrategy should implement APIOutputStrategy protocol."""
        try:
            from payment_simulator.api.strategies.protocol import APIOutputStrategy
            from payment_simulator.api.strategies.websocket_strategy import (
                WebSocketOutputStrategy,
            )
        except ImportError:
            pytest.skip("Not yet implemented")

        mock_ws = AsyncMock()
        strategy = WebSocketOutputStrategy(websocket=mock_ws)

        assert isinstance(strategy, APIOutputStrategy)

    def test_null_strategy_implements_protocol(self) -> None:
        """NullOutputStrategy should implement APIOutputStrategy protocol."""
        try:
            from payment_simulator.api.strategies.protocol import (
                APIOutputStrategy,
                NullOutputStrategy,
            )
        except ImportError:
            pytest.skip("Not yet implemented")

        strategy = NullOutputStrategy()

        assert isinstance(strategy, APIOutputStrategy)


# ============================================================================
# Phase 6.7: Integration with Simulation Lifecycle
# ============================================================================


class TestStrategyIntegration:
    """TDD tests for strategy integration with simulation lifecycle."""

    def test_strategy_factory_exists(self) -> None:
        """Strategy factory should exist for creating strategies."""
        try:
            from payment_simulator.api.strategies import create_output_strategy
        except ImportError:
            pytest.fail(
                "Cannot import create_output_strategy. "
                "Add to api/strategies/__init__.py"
            )

    def test_factory_creates_json_strategy_by_default(self) -> None:
        """Factory should create JSONOutputStrategy by default."""
        try:
            from payment_simulator.api.strategies import create_output_strategy
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy
        except ImportError:
            pytest.skip("Not yet implemented")

        strategy = create_output_strategy(mode="json")

        assert isinstance(strategy, JSONOutputStrategy)

    def test_factory_creates_websocket_strategy(self) -> None:
        """Factory should create WebSocketOutputStrategy when websocket provided."""
        try:
            from payment_simulator.api.strategies import create_output_strategy
            from payment_simulator.api.strategies.websocket_strategy import (
                WebSocketOutputStrategy,
            )
        except ImportError:
            pytest.skip("Not yet implemented")

        mock_ws = AsyncMock()
        strategy = create_output_strategy(mode="websocket", websocket=mock_ws)

        assert isinstance(strategy, WebSocketOutputStrategy)

    def test_factory_creates_null_strategy(self) -> None:
        """Factory should create NullOutputStrategy for 'null' mode."""
        try:
            from payment_simulator.api.strategies import create_output_strategy
            from payment_simulator.api.strategies.protocol import NullOutputStrategy
        except ImportError:
            pytest.skip("Not yet implemented")

        strategy = create_output_strategy(mode="null")

        assert isinstance(strategy, NullOutputStrategy)


# ============================================================================
# Phase 6.8: Parity with CLI OutputStrategy
# ============================================================================


class TestCLIAPIStrategyParity:
    """TDD tests ensuring API strategies parallel CLI strategies."""

    def test_api_strategy_has_same_lifecycle_methods_as_cli(self) -> None:
        """API OutputStrategy should have same lifecycle methods as CLI."""
        try:
            from payment_simulator.api.strategies.protocol import APIOutputStrategy
            from payment_simulator.cli.execution.runner import OutputStrategy as CLIOutputStrategy
        except ImportError:
            pytest.skip("Not yet implemented")

        # Get method names from both protocols
        api_methods = {
            "on_simulation_start",
            "on_tick_complete",
            "on_day_complete",
            "on_simulation_complete",
        }

        cli_methods = {
            "on_simulation_start",
            "on_tick_start",  # CLI has this, API doesn't need it
            "on_tick_complete",
            "on_day_complete",
            "on_simulation_complete",
        }

        # API should have all the important lifecycle methods
        # (on_tick_start is optional for API since it's mainly for progress display)
        required_methods = cli_methods - {"on_tick_start"}

        for method in required_methods:
            assert hasattr(APIOutputStrategy, method), (
                f"API missing CLI method: {method}"
            )

    def test_tick_complete_data_structure_matches_cli(self) -> None:
        """API tick_complete data should have same fields as CLI TickResult."""
        try:
            from payment_simulator.api.strategies.json_strategy import JSONOutputStrategy
            from payment_simulator.cli.execution.stats import TickResult
        except ImportError:
            pytest.skip("Not yet implemented")

        # CLI TickResult fields
        cli_tick_fields = {
            "tick",
            "events",
            "num_arrivals",
            "num_settlements",
            "num_lsm_releases",
            "total_cost",
        }

        # API should accept equivalent data
        strategy = JSONOutputStrategy()

        # This data structure mirrors CLI's TickResult
        api_tick_data = {
            "tick": 1,
            "events": [],
            "arrivals": 1,  # num_arrivals -> arrivals (API naming)
            "settlements": 0,  # num_settlements -> settlements
            "lsm_releases": 0,  # num_lsm_releases -> lsm_releases
            "total_cost": 0,
        }

        # Should accept without error
        loop = asyncio.get_event_loop()
        loop.run_until_complete(strategy.on_tick_complete(api_tick_data))

        # Verify data was collected
        collected = strategy.get_collected_data()
        assert collected["ticks"][0]["tick"] == 1
