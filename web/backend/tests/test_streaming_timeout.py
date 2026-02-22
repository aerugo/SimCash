"""Test that streaming optimization has a timeout and doesn't hang forever."""
import asyncio
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.asyncio
async def test_stream_optimize_timeout_on_hang():
    """Simulate a hanging LLM call — should timeout via chunk stall detection."""
    import app.streaming_optimizer as so

    # Temporarily lower the stall timeout for testing
    original_stall = so.LLM_CHUNK_STALL_SECONDS
    original_total = so.LLM_CALL_TIMEOUT_SECONDS
    so.LLM_CHUNK_STALL_SECONDS = 2  # 2 seconds for test
    so.LLM_CALL_TIMEOUT_SECONDS = 2  # 2 seconds total
    original_max_retries = so.MAX_RETRIES
    so.MAX_RETRIES = 1  # No retries for test

    class HangingStream:
        """Simulates a stream that connects but never produces responses."""
        def stream_responses(self, debounce_by=None):
            return self._hang()

        async def _hang(self):
            await asyncio.sleep(999999)
            yield None, True  # pragma: no cover

        def usage(self):
            return MagicMock(input_tokens=0, output_tokens=0, details={})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class HangingAgent:
        def run_stream(self, prompt, model_settings=None):
            return HangingStream()

    mock_day = MagicMock()
    mock_day.day_num = 1
    mock_day.seed = 42
    mock_day.per_agent_costs = {"BANK_A": 49800}
    mock_day.per_agent_cost_std = {"BANK_A": 0}
    mock_day.costs = {"BANK_A": {"delay_cost": 0, "penalty_cost": 0, "liquidity_cost": 49800, "total": 49800}}
    mock_day.events = []
    mock_day.total_cost = 49800
    mock_day.rejected_policies = {}
    mock_day.policies = {"BANK_A": {
        "version": "2.0",
        "parameters": {"initial_liquidity_fraction": 1.0},
        "payment_tree": {"type": "action", "action": "Release", "node_id": "r"},
        "bank_tree": {"type": "action", "action": "NoAction", "node_id": "b"},
    }}

    raw_yaml = {
        "cost_rates": {"liquidity_cost_bps": 83, "delay_cost_per_tick": 0.2, "deadline_penalty": 500},
        "agents": [{"id": "BANK_A", "initial_balance": 10000}],
    }

    try:
        with patch.object(so, '_create_agent', return_value=HangingAgent()):
            events = []
            async for event in so.stream_optimize(
                "BANK_A", mock_day.policies["BANK_A"], mock_day, [mock_day], raw_yaml,
                constraint_preset="simple",
            ):
                events.append(event)

        # Should get model_info + error (not hang forever)
        event_types = [e["type"] for e in events]
        assert "error" in event_types, f"Expected error event from timeout, got: {event_types}"

        # Verify the error mentions stall or timeout
        error_events = [e for e in events if e["type"] == "error"]
        assert any("stall" in e["message"].lower() or "timeout" in e["message"].lower() or "timed out" in e["message"].lower()
                    for e in error_events), f"Error should mention stall/timeout: {error_events}"
    finally:
        so.LLM_CHUNK_STALL_SECONDS = original_stall
        so.LLM_CALL_TIMEOUT_SECONDS = original_total
        so.MAX_RETRIES = original_max_retries


@pytest.mark.asyncio
async def test_stream_optimize_total_timeout():
    """Simulate a slow stream that produces chunks but never finishes."""
    import app.streaming_optimizer as so

    original_total = so.LLM_CALL_TIMEOUT_SECONDS
    so.LLM_CALL_TIMEOUT_SECONDS = 3  # 3 seconds total
    original_max_retries = so.MAX_RETRIES
    so.MAX_RETRIES = 1  # No retries for test

    class SlowStream:
        """Produces responses slowly, exceeding total timeout."""
        def stream_responses(self, debounce_by=None):
            return self._slow()

        async def _slow(self):
            from pydantic_ai.messages import TextPart, ModelResponse
            accumulated = ""
            for i in range(100):
                await asyncio.sleep(0.5)  # Response every 0.5s — won't stall but total > 3s
                accumulated += f"chunk_{i} "
                part = TextPart(content=accumulated)
                response = MagicMock()
                response.parts = [part]
                yield response, (i == 99)

        def usage(self):
            return MagicMock(input_tokens=0, output_tokens=0, details={})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

    class SlowAgent:
        def run_stream(self, prompt, model_settings=None):
            return SlowStream()

    mock_day = MagicMock()
    mock_day.day_num = 1
    mock_day.seed = 42
    mock_day.per_agent_costs = {"BANK_A": 49800}
    mock_day.per_agent_cost_std = {"BANK_A": 0}
    mock_day.costs = {"BANK_A": {"delay_cost": 0, "penalty_cost": 0, "liquidity_cost": 49800, "total": 49800}}
    mock_day.events = []
    mock_day.total_cost = 49800
    mock_day.rejected_policies = {}
    mock_day.policies = {"BANK_A": {
        "version": "2.0",
        "parameters": {"initial_liquidity_fraction": 1.0},
        "payment_tree": {"type": "action", "action": "Release", "node_id": "r"},
        "bank_tree": {"type": "action", "action": "NoAction", "node_id": "b"},
    }}

    raw_yaml = {
        "cost_rates": {"liquidity_cost_bps": 83, "delay_cost_per_tick": 0.2, "deadline_penalty": 500},
        "agents": [{"id": "BANK_A", "initial_balance": 10000}],
    }

    try:
        with patch.object(so, '_create_agent', return_value=SlowAgent()):
            events = []
            async for event in so.stream_optimize(
                "BANK_A", mock_day.policies["BANK_A"], mock_day, [mock_day], raw_yaml,
                constraint_preset="simple",
            ):
                events.append(event)

        event_types = [e["type"] for e in events]
        # Should get some chunks then an error
        assert "chunk" in event_types, "Should have gotten some chunks before timeout"
        assert "error" in event_types, f"Expected error event from total timeout, got: {event_types}"
    finally:
        so.LLM_CALL_TIMEOUT_SECONDS = original_total
        so.MAX_RETRIES = original_max_retries
