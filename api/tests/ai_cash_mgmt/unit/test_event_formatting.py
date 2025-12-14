"""Tests for improved event formatting in optimizer prompts.

Events should be formatted in a readable, CLI-style format with:
- Tick grouping with clear headers
- Settlement events showing balance changes
- Consistent currency formatting ($X,XXX.XX)
- Clear visual markers for different event types

TDD: These tests should FAIL until the fix is applied.
"""

from __future__ import annotations

import re

import pytest


class TestCurrencyFormatting:
    """Tests for proper currency formatting in event output."""

    def test_amount_formatted_as_dollars(self) -> None:
        """Amounts should be formatted as $X.XX, not raw cents."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            BootstrapEvent(
                tick=1,
                event_type="Arrival",
                details={
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 1234500,  # $12,345.00
                    "tx_id": "tx_test",
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Should NOT contain raw cents like "1234500"
        assert "1234500" not in formatted, (
            "Amount should not be shown as raw cents (1234500)"
        )

        # Should contain dollar formatted amount
        # Could be "$12,345.00" or "$12345.00" depending on locale
        assert "$12" in formatted or "12,345" in formatted, (
            "Amount should be formatted as dollars, not raw cents"
        )

    def test_cost_formatted_as_dollars(self) -> None:
        """Cost amounts should be formatted as dollars."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            BootstrapEvent(
                tick=1,
                event_type="CostAccrual",
                details={
                    "agent_id": "BANK_A",
                    "costs": {"delay": 50000},  # $500.00
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=50000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=50000, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Should NOT contain raw cents
        assert "50000" not in formatted, (
            "Cost should not be shown as raw cents (50000)"
        )


class TestTickGrouping:
    """Tests for events grouped by tick with clear headers."""

    def test_events_have_tick_headers(self) -> None:
        """Events should be grouped under tick headers."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            BootstrapEvent(
                tick=1,
                event_type="Arrival",
                details={"sender_id": "BANK_A", "receiver_id": "BANK_B", "tx_id": "tx1"},
            ),
            BootstrapEvent(
                tick=2,
                event_type="Arrival",
                details={"sender_id": "BANK_A", "receiver_id": "BANK_B", "tx_id": "tx2"},
            ),
            BootstrapEvent(
                tick=5,
                event_type="RtgsImmediateSettlement",
                details={"sender": "BANK_A", "receiver": "BANK_B", "tx_id": "tx1"},
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Should have clear tick separators or headers
        # Look for patterns like "Tick 1", "═══ Tick 1 ═══", etc.
        tick_headers = re.findall(r"[Tt]ick\s*\d+", formatted)
        assert len(tick_headers) >= 2, (
            f"Expected multiple tick headers but found: {tick_headers}"
        )


class TestSettlementBalanceChanges:
    """Tests for settlement events showing balance changes."""

    def test_rtgs_settlement_shows_balance_change(self) -> None:
        """RTGS settlements should show balance before/after like CLI does."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            BootstrapEvent(
                tick=1,
                event_type="RtgsImmediateSettlement",
                details={
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 100000,  # $1,000.00
                    "tx_id": "tx_test",
                    "sender_balance_before": 500000,  # $5,000.00
                    "sender_balance_after": 400000,  # $4,000.00
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Should show balance information
        # Could be "Balance: $5,000.00 → $4,000.00" or similar
        assert "balance" in formatted.lower() or "→" in formatted, (
            "Settlement should show balance change information"
        )


class TestVisualMarkers:
    """Tests for visual markers (emojis, icons) on different event types."""

    def test_outgoing_transaction_marked_clearly(self) -> None:
        """Outgoing transactions should have clear visual marker."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            BootstrapEvent(
                tick=1,
                event_type="Arrival",
                details={
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 10000,
                    "tx_id": "tx_outgoing",
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Should have visual marker like emoji or "Outgoing" label
        has_emoji = any(char in formatted for char in "📤📥✅💰🔄💸")
        has_direction = "outgoing" in formatted.lower() or "incoming" in formatted.lower()
        has_arrow = "→" in formatted

        assert has_emoji or has_direction or has_arrow, (
            "Transaction direction should be visually marked"
        )

    def test_settlement_marked_with_success(self) -> None:
        """Successful settlements should have success marker."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            BootstrapEvent(
                tick=1,
                event_type="RtgsImmediateSettlement",
                details={
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 10000,
                    "tx_id": "tx_settled",
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Should have success marker
        has_success_emoji = "✅" in formatted or "✓" in formatted
        has_success_word = "settled" in formatted.lower() or "success" in formatted.lower()

        assert has_success_emoji or has_success_word, (
            "Settlement should have success marker"
        )
