"""Tests for pretty LLM event formatting.

This test suite verifies that the new pretty formatting functions work correctly
for generating LLM-friendly event traces that match the CLI verbose output.
"""
from io import StringIO
from typing import Any

import pytest
from rich.console import Console

from payment_simulator.cli.execution.state_provider import (
    BootstrapEventStateProvider,
    OrchestratorStateProvider,
)
from payment_simulator.cli.output import (
    format_events_as_text,
    format_tick_range_as_text,
    log_tick_start,
)


class TestFormatEventsAsText:
    """Test format_events_as_text() function."""

    def test_empty_events_returns_empty_output(self) -> None:
        """format_events_as_text should handle empty events gracefully."""
        # Create a minimal mock provider
        provider = MockStateProvider(balance=1000000)

        result = format_events_as_text(
            provider=provider,
            events=[],
            tick=0,
            agent_ids=["BANK_A"],
        )

        # Should return something (tick header at minimum)
        assert isinstance(result, str)
        assert "Tick 0" in result

    def test_arrival_event_formatted(self) -> None:
        """format_events_as_text should format arrival events."""
        provider = MockStateProvider(balance=1000000)

        events = [
            {
                "tick": 0,
                "event_type": "Arrival",
                "tx_id": "tx_12345678",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 150000,  # $1,500.00 in cents
                "priority": 5,
                "deadline_tick": 10,
            }
        ]

        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=0,
            agent_ids=["BANK_A", "BANK_B"],
        )

        assert "tx_12345" in result  # Truncated TX ID
        assert "BANK_A" in result
        assert "BANK_B" in result
        # Amount should be formatted
        assert "$1,500.00" in result or "$1500.00" in result or "1,500" in result

    def test_settlement_event_formatted(self) -> None:
        """format_events_as_text should format settlement events."""
        provider = MockStateProvider(balance=1000000)

        events = [
            {
                "tick": 5,
                "event_type": "RtgsImmediateSettlement",
                "tx_id": "tx_settlement_1",
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 50000,  # $500.00
                "sender_balance_before": 1000000,
                "sender_balance_after": 950000,
            }
        ]

        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=5,
            agent_ids=["BANK_A", "BANK_B"],
        )

        assert "settled" in result.lower() or "rtgs" in result.lower()

    def test_output_is_plain_text(self) -> None:
        """format_events_as_text should produce plain text without ANSI codes."""
        provider = MockStateProvider(balance=1000000)

        events = [
            {
                "tick": 0,
                "event_type": "Arrival",
                "tx_id": "tx_12345678",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
                "priority": 8,  # HIGH priority
                "deadline_tick": 5,
            }
        ]

        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=0,
            agent_ids=["BANK_A", "BANK_B"],
        )

        # Should not contain ANSI escape codes
        assert "\x1b[" not in result
        assert "\033[" not in result


class TestFormatTickRangeAsText:
    """Test format_tick_range_as_text() function."""

    def test_formats_multiple_ticks(self) -> None:
        """format_tick_range_as_text should format events across multiple ticks."""
        provider = MockStateProvider(balance=1000000)

        tick_events = {
            0: [
                {
                    "tick": 0,
                    "event_type": "Arrival",
                    "tx_id": "tx_tick0",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 100000,
                    "priority": 5,
                    "deadline_tick": 10,
                }
            ],
            1: [
                {
                    "tick": 1,
                    "event_type": "RtgsImmediateSettlement",
                    "tx_id": "tx_tick0",
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 100000,
                }
            ],
        }

        result = format_tick_range_as_text(
            provider=provider,
            tick_events_by_tick=tick_events,
            agent_ids=["BANK_A", "BANK_B"],
        )

        assert "Tick 0" in result
        assert "Tick 1" in result

    def test_empty_ticks_handled(self) -> None:
        """format_tick_range_as_text should handle empty tick dictionaries."""
        provider = MockStateProvider(balance=1000000)

        result = format_tick_range_as_text(
            provider=provider,
            tick_events_by_tick={},
            agent_ids=["BANK_A"],
        )

        assert isinstance(result, str)


class TestBootstrapEventStateProvider:
    """Test BootstrapEventStateProvider adapter."""

    def test_creates_from_bootstrap_events(self) -> None:
        """BootstrapEventStateProvider should work with BootstrapEvent-like objects."""
        # Create mock events (simulating BootstrapEvent structure)
        events = [
            MockBootstrapEvent(
                tick=0,
                event_type="Arrival",
                details={
                    "tx_id": "tx_123",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 50000,
                    "priority": 5,
                    "deadline_tick": 10,
                },
            )
        ]

        provider = BootstrapEventStateProvider(
            events=events,
            agent_id="BANK_A",
            opening_balance=1000000,
        )

        # Should be able to query basic state
        assert provider.get_agent_balance("BANK_A") == 1000000
        assert provider.get_queue1_size("BANK_A") == 0  # Empty by default

    def test_caches_transactions_from_arrivals(self) -> None:
        """BootstrapEventStateProvider should cache transaction details from Arrival events."""
        events = [
            MockBootstrapEvent(
                tick=0,
                event_type="Arrival",
                details={
                    "tx_id": "tx_cached_123",
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 75000,
                    "priority": 7,
                    "deadline_tick": 15,
                },
            )
        ]

        provider = BootstrapEventStateProvider(
            events=events,
            agent_id="BANK_A",
            opening_balance=500000,
        )

        # Should be able to retrieve transaction details
        tx = provider.get_transaction_details("tx_cached_123")
        assert tx is not None
        # TransactionDetails is a TypedDict, access via dict-style
        assert tx["tx_id"] == "tx_cached_123"
        assert tx["amount"] == 75000
        assert tx["priority"] == 7

    def test_get_event_dicts_returns_converted_events(self) -> None:
        """BootstrapEventStateProvider.get_event_dicts should return dict representations."""
        events = [
            MockBootstrapEvent(
                tick=0,
                event_type="Arrival",
                details={"tx_id": "tx_dict_test"},
            )
        ]

        provider = BootstrapEventStateProvider(
            events=events,
            agent_id="BANK_A",
        )

        event_dicts = provider.get_event_dicts()
        assert len(event_dicts) == 1
        assert event_dicts[0]["tick"] == 0
        assert event_dicts[0]["event_type"] == "Arrival"
        assert event_dicts[0]["tx_id"] == "tx_dict_test"


class TestLogTickStartWithCustomConsole:
    """Test that log_tick_start accepts custom console parameter."""

    def test_writes_to_custom_console(self) -> None:
        """log_tick_start should write to custom console when provided."""
        buffer = StringIO()
        custom_console = Console(file=buffer, force_terminal=False, no_color=True, width=120)

        log_tick_start(tick=42, custom_console=custom_console)

        output = buffer.getvalue()
        assert "Tick 42" in output

    def test_no_ansi_codes_with_no_color(self) -> None:
        """log_tick_start with no_color console should produce plain text."""
        buffer = StringIO()
        custom_console = Console(file=buffer, force_terminal=False, no_color=True, width=120)

        log_tick_start(tick=99, custom_console=custom_console)

        output = buffer.getvalue()
        # Should not contain ANSI escape codes
        assert "\x1b[" not in output
        assert "\033[" not in output


# =============================================================================
# Mock Classes for Testing
# =============================================================================


class MockStateProvider:
    """Minimal StateProvider for testing format functions."""

    def __init__(self, balance: int = 0) -> None:
        self._balance = balance

    def get_agent_balance(self, agent_id: str) -> int:
        return self._balance

    def get_agent_unsecured_cap(self, agent_id: str) -> int:
        return 0

    def get_agent_queue1_contents(self, agent_id: str) -> list[str]:
        return []

    def get_rtgs_queue_contents(self) -> list[str]:
        return []

    def get_agent_collateral_posted(self, agent_id: str) -> int:
        return 0

    def get_transaction_details(self, tx_id: str) -> Any:
        return None

    def get_agent_accumulated_costs(self, agent_id: str) -> Any:
        from payment_simulator.cli.execution.state_provider import AccumulatedCosts
        return AccumulatedCosts(
            liquidity_cost=0,
            delay_cost=0,
            collateral_cost=0,
            penalty_cost=0,
            split_friction_cost=0,
            deadline_penalty=0,
            total_cost=0,
        )

    def get_queue1_size(self, agent_id: str) -> int:
        return 0

    def get_queue2_size(self, agent_id: str) -> int:
        return 0

    def get_transactions_near_deadline(self, within_ticks: int) -> list[Any]:
        return []

    def get_overdue_transactions(self) -> list[Any]:
        return []


class MockBootstrapEvent:
    """Mock BootstrapEvent for testing without importing the real class."""

    def __init__(self, tick: int, event_type: str, details: dict[str, Any]) -> None:
        self.tick = tick
        self.event_type = event_type
        self.details = details


# =============================================================================
# Agent Isolation Tests (INV-11 Compliance)
# =============================================================================


class TestAgentIsolationInPrettyFormatting:
    """Test that agent isolation invariant is maintained in pretty LLM formatting.

    INV-11: The optimization prompt of BANK_A may NEVER contain any leakage
    on the policy or balance of transactions of BANK_B.

    These tests ensure that when formatting events for a specific agent's LLM
    context, other agents' sensitive data (especially balances) is not exposed.
    """

    def test_sender_balance_hidden_when_receiver_is_target_agent(self) -> None:
        """When BANK_A receives settlement from BANK_B, BANK_B's balance must be hidden.

        This is the critical test case for agent isolation:
        - BANK_B sends $500 to BANK_A
        - BANK_B's balance before/after should NOT appear in BANK_A's LLM context
        """
        # Use a distinct balance for BANK_A ($5,000) vs BANK_B's event values ($8,000 and $7,500)
        provider = MockStateProvider(balance=500000)  # $5,000.00 - BANK_A's balance

        # Settlement event where BANK_B is sender and BANK_A is receiver
        # Use BANK_B balance values that are distinctly different from BANK_A's
        events = [
            {
                "tick": 5,
                "event_type": "RtgsImmediateSettlement",
                "tx_id": "tx_isolation_test",
                "sender": "BANK_B",  # Other agent (not the target)
                "receiver": "BANK_A",  # Target agent
                "amount": 50000,  # $500.00
                "sender_balance_before": 800000,  # $8,000.00 - BANK_B's balance (MUST NOT APPEAR)
                "sender_balance_after": 750000,  # $7,500.00 - BANK_B's balance (MUST NOT APPEAR)
            }
        ]

        # Format with filter_agent=BANK_A (the target agent receiving the payment)
        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=5,
            agent_ids=["BANK_A", "BANK_B"],
            filter_agent="BANK_A",  # CRITICAL: Agent isolation filter
        )

        # The settlement event should be shown (BANK_A is receiver)
        assert "BANK_A" in result
        assert "BANK_B" in result

        # BANK_A's own balance ($5,000) should be shown in Agent Financial Stats
        assert "$5,000.00" in result or "5,000.00" in result

        # CRITICAL: BANK_B's balance should NOT be shown
        # $8,000.00 (before) and $7,500.00 (after) should NOT appear
        assert "$8,000.00" not in result
        assert "$7,500.00" not in result
        assert "8,000.00" not in result
        assert "7,500.00" not in result

    def test_sender_balance_shown_when_sender_is_target_agent(self) -> None:
        """When BANK_A sends payment, BANK_A's own balance should be shown.

        BANK_A is allowed to see its own balance changes in its LLM context.
        """
        provider = MockStateProvider(balance=1000000)

        # Settlement event where BANK_A is sender (outgoing payment)
        events = [
            {
                "tick": 5,
                "event_type": "RtgsImmediateSettlement",
                "tx_id": "tx_own_balance",
                "sender": "BANK_A",  # Target agent is the sender
                "receiver": "BANK_B",
                "amount": 50000,
                "sender_balance_before": 1000000,  # $10,000.00 - BANK_A's own balance
                "sender_balance_after": 950000,  # $9,500.00 - BANK_A's own balance
            }
        ]

        # Format with filter_agent=BANK_A
        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=5,
            agent_ids=["BANK_A", "BANK_B"],
            filter_agent="BANK_A",
        )

        # BANK_A's own balance SHOULD be shown (it's their own data)
        assert "10,000.00" in result or "9,500.00" in result

    def test_all_balances_shown_when_no_filter_agent(self) -> None:
        """When filter_agent is None (CLI mode), all balances should be shown.

        This is the default behavior for CLI run/replay where operators see all data.
        """
        provider = MockStateProvider(balance=1000000)

        events = [
            {
                "tick": 5,
                "event_type": "RtgsImmediateSettlement",
                "tx_id": "tx_no_filter",
                "sender": "BANK_B",
                "receiver": "BANK_A",
                "amount": 50000,
                "sender_balance_before": 1000000,
                "sender_balance_after": 950000,
            }
        ]

        # Format WITHOUT filter_agent (default CLI mode)
        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=5,
            agent_ids=["BANK_A", "BANK_B"],
            filter_agent=None,  # No filtering
        )

        # All balances should be visible in CLI mode
        assert "10,000.00" in result or "9,500.00" in result

    def test_format_tick_range_passes_filter_agent(self) -> None:
        """format_tick_range_as_text should propagate filter_agent to format_events_as_text."""
        provider = MockStateProvider(balance=1000000)

        tick_events = {
            0: [
                {
                    "tick": 0,
                    "event_type": "RtgsImmediateSettlement",
                    "tx_id": "tx_range_test",
                    "sender": "BANK_B",  # Other agent
                    "receiver": "BANK_A",  # Target agent
                    "amount": 50000,
                    "sender_balance_before": 500000,  # $5,000.00 - BANK_B's balance
                    "sender_balance_after": 450000,  # $4,500.00 - BANK_B's balance
                }
            ],
        }

        # Format with filter_agent
        result = format_tick_range_as_text(
            provider=provider,
            tick_events_by_tick=tick_events,
            agent_ids=["BANK_A", "BANK_B"],
            filter_agent="BANK_A",
        )

        # BANK_B's balance should NOT be shown
        assert "$5,000.00" not in result
        assert "$4,500.00" not in result
        assert "5,000.00" not in result
        assert "4,500.00" not in result

    def test_multiple_settlements_isolation(self) -> None:
        """Test isolation with multiple settlements in same tick."""
        provider = MockStateProvider(balance=1000000)

        events = [
            # Settlement 1: BANK_A sends to BANK_B (BANK_A's balance visible)
            {
                "tick": 5,
                "event_type": "RtgsImmediateSettlement",
                "tx_id": "tx_outgoing",
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 30000,
                "sender_balance_before": 1000000,  # BANK_A: $10,000
                "sender_balance_after": 970000,  # BANK_A: $9,700
            },
            # Settlement 2: BANK_B sends to BANK_A (BANK_B's balance hidden)
            {
                "tick": 5,
                "event_type": "RtgsImmediateSettlement",
                "tx_id": "tx_incoming",
                "sender": "BANK_B",
                "receiver": "BANK_A",
                "amount": 20000,
                "sender_balance_before": 800000,  # BANK_B: $8,000 (should be hidden)
                "sender_balance_after": 780000,  # BANK_B: $7,800 (should be hidden)
            },
        ]

        result = format_events_as_text(
            provider=provider,
            events=events,
            tick=5,
            agent_ids=["BANK_A", "BANK_B"],
            filter_agent="BANK_A",
        )

        # BANK_A's own balance (from outgoing settlement) should be visible
        # Note: checking for presence of BANK_A's balance values
        has_bank_a_balance = "10,000.00" in result or "9,700.00" in result

        # BANK_B's balance (from incoming settlement) should NOT be visible
        assert "$8,000.00" not in result
        assert "$7,800.00" not in result
        assert "8,000.00" not in result
        assert "7,800.00" not in result

        # BANK_A's balance should still be visible for their outgoing transaction
        assert has_bank_a_balance, "BANK_A's own balance should be visible for outgoing transactions"
