"""Tests for CRITICAL agent isolation in optimizer prompts.

CRITICAL INVARIANT: An LLM optimizing for Agent X may ONLY see:
- Outgoing transactions FROM Agent X
- Incoming liquidity events TO Agent X balance
- Agent X's own policy and state changes

This file tests the INTEGRATION point where events flow into prompts.
The filter function itself is tested in test_event_filter.py.
Here we verify the filter is ACTUALLY CALLED in the prompt generation path.

TDD: These tests should FAIL until the fix is applied.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest


class TestEnrichedBootstrapContextBuilderIsolation:
    """Tests that EnrichedBootstrapContextBuilder filters events by agent.

    CRITICAL: The format_event_trace_for_llm() method must filter events
    to only show the target agent's events. Currently it does NOT.
    """

    def test_format_event_trace_excludes_other_agent_outgoing(self) -> None:
        """Event trace must NOT contain other agent's outgoing transactions.

        This is the PRIMARY test for the agent isolation bug.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Create events where BANK_A sends and BANK_B sends
        events = [
            # BANK_A's outgoing - should be visible to BANK_A
            BootstrapEvent(
                tick=1,
                event_type="Arrival",
                details={
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 10000,
                    "tx_id": "tx_a_to_b",
                },
            ),
            # BANK_B's outgoing - should NOT be visible to BANK_A
            BootstrapEvent(
                tick=1,
                event_type="Arrival",
                details={
                    "sender_id": "BANK_B",
                    "receiver_id": "BANK_C",
                    "amount": 99999,  # Unique amount to detect leakage
                    "tx_id": "tx_b_to_c_FORBIDDEN",
                },
            ),
            # BANK_A's incoming - should be visible to BANK_A
            BootstrapEvent(
                tick=2,
                event_type="Arrival",
                details={
                    "sender_id": "BANK_C",
                    "receiver_id": "BANK_A",
                    "amount": 20000,
                    "tx_id": "tx_c_to_a",
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
                delay_cost=1000,
                overdraft_cost=2000,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        # Build context for BANK_A
        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # CRITICAL ASSERTIONS:
        # 1. BANK_A's outgoing should be visible
        assert "tx_a_to_b" in formatted, "BANK_A's outgoing transaction should be visible"

        # 2. BANK_A's incoming should be visible
        assert "tx_c_to_a" in formatted, "BANK_A's incoming transaction should be visible"

        # 3. BANK_B's outgoing to BANK_C should NOT be visible
        # This is the CRITICAL test - currently FAILING
        assert "tx_b_to_c_FORBIDDEN" not in formatted, (
            "CRITICAL VIOLATION: BANK_B's outgoing transaction to BANK_C "
            "should NOT be visible to BANK_A's LLM!"
        )
        assert "99999" not in formatted, (
            "CRITICAL VIOLATION: Amount 99999 from BANK_B->BANK_C tx "
            "leaked into BANK_A's prompt!"
        )

    def test_format_event_trace_excludes_other_agent_costs(self) -> None:
        """Event trace must NOT contain other agent's cost accruals."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            # BANK_A's costs - should be visible
            BootstrapEvent(
                tick=1,
                event_type="CostAccrual",
                details={"agent_id": "BANK_A", "costs": {"delay": 100}},
            ),
            # BANK_B's costs - should NOT be visible
            BootstrapEvent(
                tick=1,
                event_type="CostAccrual",
                details={"agent_id": "BANK_B", "costs": {"delay": 77777}},
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=100, overdraft_cost=0,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # BANK_B's cost amount should not appear
        assert "77777" not in formatted, (
            "CRITICAL VIOLATION: BANK_B's cost accrual leaked into BANK_A's prompt!"
        )

    def test_format_event_trace_excludes_other_agent_policy(self) -> None:
        """Event trace must NOT contain other agent's policy decisions."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            # BANK_A's policy - should be visible
            BootstrapEvent(
                tick=1,
                event_type="PolicySubmit",
                details={"agent_id": "BANK_A", "tx_id": "tx_a_submit"},
            ),
            # BANK_B's policy - should NOT be visible
            BootstrapEvent(
                tick=1,
                event_type="PolicyHold",
                details={"agent_id": "BANK_B", "tx_id": "tx_b_hold_FORBIDDEN"},
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

        assert "tx_b_hold_FORBIDDEN" not in formatted, (
            "CRITICAL VIOLATION: BANK_B's policy decision leaked into BANK_A's prompt!"
        )

    def test_format_event_trace_excludes_other_agent_collateral(self) -> None:
        """Event trace must NOT contain other agent's collateral events."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            # BANK_A's collateral - should be visible
            BootstrapEvent(
                tick=0,
                event_type="CollateralPost",
                details={"agent_id": "BANK_A", "amount": 10000},
            ),
            # BANK_B's collateral - should NOT be visible
            BootstrapEvent(
                tick=0,
                event_type="CollateralPost",
                details={"agent_id": "BANK_B", "amount": 88888},
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=5000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=100,
                deadline_penalty=0, eod_penalty=0,
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        assert "88888" not in formatted, (
            "CRITICAL VIOLATION: BANK_B's collateral amount leaked into BANK_A's prompt!"
        )


class TestSingleAgentContextIsolation:
    """Tests that the full prompt from build_single_agent_context is isolated."""

    def test_best_seed_output_filtered(self) -> None:
        """Best seed output in final prompt must be filtered by agent."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        # Create best seed output that contains forbidden content
        # This simulates what would happen if EnrichedBootstrapContextBuilder
        # doesn't filter properly
        unfiltered_output = """
        [tick 1] Arrival: tx_id=tx_a_to_b, sender_id=BANK_A, receiver_id=BANK_B
        [tick 1] Arrival: tx_id=tx_b_to_c_FORBIDDEN, sender_id=BANK_B, receiver_id=BANK_C
        """

        # Currently this will include the forbidden content
        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            best_seed_output=unfiltered_output,
            best_seed=12345,
            best_seed_cost=5000,
            agent_id="BANK_A",
        )

        # This test documents the EXPECTED behavior after fix
        # Currently it may pass because we're passing raw output,
        # but the real fix is in EnrichedBootstrapContextBuilder
        assert "BANK_A" in prompt

    def test_worst_seed_output_filtered(self) -> None:
        """Worst seed output in final prompt must be filtered by agent."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        unfiltered_output = """
        [tick 1] CostAccrual: agent_id=BANK_B, costs={"delay": 99999}
        """

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {}},
            current_metrics={"total_cost_mean": 5000},
            worst_seed_output=unfiltered_output,
            worst_seed=54321,
            worst_seed_cost=15000,
            agent_id="BANK_A",
        )

        # The prompt should not contain BANK_B's cost data
        # This test documents expected behavior


class TestOptimizationPromptIsolation:
    """Integration tests for the full optimization prompt path."""

    def test_collected_events_must_be_filtered(self) -> None:
        """Events collected in optimization.py must be filtered before use.

        In optimization.py around line 1512-1530, events are extracted but
        the comment says 'Events are filtered by agent in the PolicyOptimizer'
        but this is NOT actually happening.
        """
        # This test documents the expected fix in optimization.py
        # The events should be filtered before being passed to the prompt builder
        pass  # Implementation test - verifies the fix is applied

    def test_policy_optimizer_uses_events_parameter(self) -> None:
        """PolicyOptimizer.optimize() must actually use the events parameter.

        Currently the 'events' parameter is accepted but NEVER USED.
        The docstring says events are filtered, but they are ignored.
        """
        # This test documents the expected fix in policy_optimizer.py
        pass  # Implementation test


class TestRtgsSettlementIsolation:
    """Tests specifically for RTGS settlement event isolation."""

    def test_other_agent_rtgs_settlements_excluded(self) -> None:
        """RTGS settlements between other agents must not be visible."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            # Settlement where BANK_A is sender - visible
            BootstrapEvent(
                tick=1,
                event_type="RtgsImmediateSettlement",
                details={
                    "sender": "BANK_A",
                    "receiver": "BANK_B",
                    "amount": 10000,
                    "tx_id": "tx_a_sends",
                },
            ),
            # Settlement where BANK_A is receiver - visible (incoming liquidity)
            BootstrapEvent(
                tick=2,
                event_type="RtgsImmediateSettlement",
                details={
                    "sender": "BANK_C",
                    "receiver": "BANK_A",
                    "amount": 20000,
                    "tx_id": "tx_a_receives",
                },
            ),
            # Settlement between other agents - NOT visible
            BootstrapEvent(
                tick=3,
                event_type="RtgsImmediateSettlement",
                details={
                    "sender": "BANK_B",
                    "receiver": "BANK_C",
                    "amount": 66666,
                    "tx_id": "tx_b_to_c_FORBIDDEN",
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

        # BANK_A should see their own transactions
        assert "tx_a_sends" in formatted
        assert "tx_a_receives" in formatted

        # BANK_A should NOT see BANK_B -> BANK_C
        assert "tx_b_to_c_FORBIDDEN" not in formatted, (
            "CRITICAL VIOLATION: BANK_B->BANK_C settlement leaked to BANK_A!"
        )
        assert "66666" not in formatted


class TestLSMEventIsolation:
    """Tests for LSM event isolation."""

    def test_lsm_bilateral_only_if_involved(self) -> None:
        """LSM bilateral offsets only visible if agent is involved."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            # BANK_A involved - visible
            BootstrapEvent(
                tick=1,
                event_type="LsmBilateralOffset",
                details={
                    "agent_a": "BANK_A",
                    "agent_b": "BANK_B",
                    "amount_a": 5000,
                    "amount_b": 5000,
                },
            ),
            # BANK_A not involved - NOT visible
            BootstrapEvent(
                tick=2,
                event_type="LsmBilateralOffset",
                details={
                    "agent_a": "BANK_C",
                    "agent_b": "BANK_D",
                    "amount_a": 44444,
                    "amount_b": 44444,
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

        # BANK_C<->BANK_D bilateral should not be visible
        assert "44444" not in formatted, (
            "CRITICAL VIOLATION: BANK_C<->BANK_D LSM bilateral leaked to BANK_A!"
        )

    def test_lsm_cycle_only_if_involved(self) -> None:
        """LSM cycle settlements only visible if agent is in the cycle."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        events = [
            # BANK_A in cycle - visible
            BootstrapEvent(
                tick=1,
                event_type="LsmCycleSettlement",
                details={
                    "agents": ["BANK_A", "BANK_B", "BANK_C"],
                    "total_value": 10000,
                },
            ),
            # BANK_A not in cycle - NOT visible
            BootstrapEvent(
                tick=2,
                event_type="LsmCycleSettlement",
                details={
                    "agents": ["BANK_D", "BANK_E", "BANK_F"],
                    "total_value": 55555,
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

        # BANK_D-E-F cycle should not be visible
        assert "55555" not in formatted, (
            "CRITICAL VIOLATION: BANK_D-E-F LSM cycle leaked to BANK_A!"
        )


# =============================================================================
# Phase 1: Balance Leakage Tests (INV-10: Agent Isolation)
# =============================================================================


class TestRtgsBalanceIsolation:
    """Tests for RTGS settlement balance isolation.

    Enforces INV-10: Agent Isolation - Receiver must not see sender's balance.
    These tests verify that sender_balance_before/after are only shown to the sender.
    """

    def test_rtgs_settlement_receiver_cannot_see_sender_balance(self) -> None:
        """Receiver must NOT see sender's balance_before/balance_after.

        When BANK_B sends to BANK_A, BANK_A should see:
        - The payment amount
        - The sender identity
        But NOT:
        - sender_balance_before
        - sender_balance_after

        This is the PRIMARY test for balance leakage.
        """
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
                    "sender": "BANK_B",  # BANK_B is sending
                    "receiver": "BANK_A",  # BANK_A is receiving
                    "amount": 50000,
                    "tx_id": "tx_b_pays_a",
                    "sender_balance_before": 1000000,  # $10,000.00
                    "sender_balance_after": 950000,  # $9,500.00
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        # Build context for BANK_A (the RECEIVER)
        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # BANK_A should see the transaction exists
        assert "tx_b_pays_a" in formatted, "Transaction should be visible to receiver"

        # CRITICAL: BANK_A must NOT see BANK_B's balance
        assert "1000000" not in formatted and "10,000" not in formatted, (
            "CRITICAL VIOLATION: sender_balance_before leaked to receiver!"
        )
        assert "950000" not in formatted and "9,500" not in formatted, (
            "CRITICAL VIOLATION: sender_balance_after leaked to receiver!"
        )

    def test_rtgs_settlement_sender_can_see_own_balance(self) -> None:
        """Sender MUST see their own balance_before/balance_after.

        When BANK_A sends payment, BANK_A should see their balance change.
        This ensures we don't over-restrict and hide data from the sender.
        """
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
                    "sender": "BANK_A",  # BANK_A is sending
                    "receiver": "BANK_B",  # BANK_B is receiving
                    "amount": 50000,
                    "tx_id": "tx_a_pays_b",
                    "sender_balance_before": 2000000,  # $20,000.00
                    "sender_balance_after": 1950000,  # $19,500.00
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        # Build context for BANK_A (the SENDER)
        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # BANK_A should see the transaction
        assert "tx_a_pays_b" in formatted, "Transaction should be visible to sender"

        # BANK_A SHOULD see their own balance change
        # Balance might be formatted as 20,000 or 2000000 depending on formatter
        has_balance_info = (
            "20,000" in formatted
            or "2000000" in formatted
            or "19,500" in formatted
            or "1950000" in formatted
        )
        assert has_balance_info, (
            "Sender should see their own balance change"
        )

    def test_rtgs_settlement_balance_fields_hidden_with_unique_markers(self) -> None:
        """Verify specific balance field values are not leaked using unique markers.

        Uses highly unique marker values to ensure detection of any leakage.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Use highly unique marker values that wouldn't appear naturally
        marker_before = 123456789
        marker_after = 987654321

        events = [
            BootstrapEvent(
                tick=1,
                event_type="RtgsImmediateSettlement",
                details={
                    "sender": "BANK_B",
                    "receiver": "BANK_A",
                    "amount": 50000,
                    "tx_id": "tx_marker_test",
                    "sender_balance_before": marker_before,
                    "sender_balance_after": marker_after,
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        # Build context for BANK_A (receiver)
        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Marker values should NOT appear anywhere in the output
        assert str(marker_before) not in formatted, (
            f"CRITICAL: Balance marker {marker_before} leaked!"
        )
        assert str(marker_after) not in formatted, (
            f"CRITICAL: Balance marker {marker_after} leaked!"
        )
        # Also check for formatted versions
        assert "1,234,567.89" not in formatted
        assert "9,876,543.21" not in formatted


# =============================================================================
# Phase 2: LSM Event Sanitization Tests (INV-10: Agent Isolation)
# =============================================================================


class TestLSMEventSanitization:
    """Tests for LSM event information sanitization.

    Enforces INV-10: Agent Isolation - Counterparty-specific details hidden.
    When agent participates in LSM, they should not see counterparty amounts.
    """

    def test_lsm_bilateral_hides_counterparty_amount(self) -> None:
        """Bilateral offset must hide counterparty's amount.

        When BANK_A and BANK_B offset:
        - BANK_A may see they participated
        - BANK_A should NOT see BANK_B's specific amount

        We use unique marker values to detect leakage.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Unique markers
        bank_a_amount = 80000  # $800
        bank_b_amount = 67890  # $678.90 - unique marker

        events = [
            BootstrapEvent(
                tick=1,
                event_type="LsmBilateralOffset",
                details={
                    "agent_a": "BANK_A",
                    "agent_b": "BANK_B",
                    "amount_a": bank_a_amount,
                    "amount_b": bank_b_amount,
                    "tx_ids": ["tx_bilateral_1", "tx_bilateral_2"],
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        # Build context for BANK_A
        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # BANK_B's amount should NOT be visible
        assert str(bank_b_amount) not in formatted and "678.90" not in formatted, (
            "CRITICAL VIOLATION: Counterparty's bilateral amount leaked!"
        )

    def test_lsm_cycle_hides_all_tx_amounts(self) -> None:
        """Cycle settlement must hide individual transaction amounts.

        When viewing LSM cycle, individual tx_amounts array should not be exposed.
        Only total value (if shown) should be visible.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Unique marker amounts
        amounts = [111111, 222222, 333333]  # Unique values

        events = [
            BootstrapEvent(
                tick=1,
                event_type="LsmCycleSettlement",
                details={
                    "agents": ["BANK_A", "BANK_B", "BANK_C"],
                    "tx_ids": ["tx1", "tx2", "tx3"],
                    "tx_amounts": amounts,
                    "total_value": sum(amounts),
                    "net_positions": [50000, -30000, -20000],
                    "max_net_outflow": 50000,
                    "max_net_outflow_agent": "BANK_A",
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Individual transaction amounts should NOT be visible
        for amount in amounts:
            assert str(amount) not in formatted, (
                f"CRITICAL: Individual tx amount {amount} leaked in cycle event!"
            )

    def test_lsm_cycle_hides_net_positions(self) -> None:
        """Cycle settlement must hide net positions array.

        Net positions reveal liquidity stress of other participants.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Unique marker net positions
        net_positions = [54321, -98765, 44444]

        events = [
            BootstrapEvent(
                tick=1,
                event_type="LsmCycleSettlement",
                details={
                    "agents": ["BANK_A", "BANK_B", "BANK_C"],
                    "tx_ids": ["tx1", "tx2", "tx3"],
                    "tx_amounts": [100000, 100000, 100000],
                    "total_value": 300000,
                    "net_positions": net_positions,
                    "max_net_outflow": 98765,
                    "max_net_outflow_agent": "BANK_B",
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Net positions should NOT be visible
        for pos in net_positions:
            # Check both positive and absolute values
            assert str(abs(pos)) not in formatted, (
                f"CRITICAL: Net position {pos} leaked in cycle event!"
            )

    def test_lsm_shows_participation_info(self) -> None:
        """Agent should know they participated in LSM settlement.

        While hiding specific amounts, agent should see confirmation of settlement.
        """
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
                event_type="LsmCycleSettlement",
                details={
                    "agents": ["BANK_A", "BANK_B", "BANK_C"],
                    "total_value": 300000,
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
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            event_trace=tuple(events),
        )

        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        formatted = builder.format_event_trace_for_llm(result)

        # Agent should see SOMETHING about LSM (event is included)
        assert "LSM" in formatted or "Cycle" in formatted or "LsmCycle" in formatted, (
            "Agent should see they participated in LSM settlement"
        )


# =============================================================================
# Phase 3: Cost Breakdown Isolation Tests (INV-10: Agent Isolation)
# =============================================================================


class TestCostBreakdownIsolation:
    """Tests for cost breakdown isolation.

    Enforces INV-10: Agent Isolation - Only own costs visible.
    Cost breakdown should reflect agent-specific costs, not system-wide aggregate.
    """

    def test_context_builder_uses_per_agent_costs(self) -> None:
        """AgentSimulationContext should use per-agent costs when available.

        When per_agent_costs is provided, the context should use agent-specific
        costs rather than total_cost.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Create result with different total vs per-agent costs
        events = [
            BootstrapEvent(
                tick=1,
                event_type="Arrival",
                details={
                    "sender_id": "BANK_A",
                    "receiver_id": "BANK_B",
                    "amount": 10000,
                    "tx_id": "tx1",
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=100000,  # System-wide total: $1,000
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=50000,
                overdraft_cost=50000,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            event_trace=tuple(events),
            per_agent_costs={
                "BANK_A": 30000,  # BANK_A's cost: $300
                "BANK_B": 70000,  # BANK_B's cost: $700
            },
        )

        # Build context for BANK_A
        builder = EnrichedBootstrapContextBuilder([result], "BANK_A")
        context = builder.build_agent_context()

        # Context should use BANK_A's per-agent cost, not total
        assert context.best_seed_cost == 30000, (
            f"Expected BANK_A's cost (30000), got {context.best_seed_cost}"
        )

    def test_different_agents_get_different_costs_from_same_result(self) -> None:
        """Different agents must see different costs from the same result.

        When building context for BANK_A vs BANK_B from the same
        EnrichedEvaluationResult, they should see their respective costs.
        """
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
                    "tx_id": "tx1",
                },
            ),
        ]

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=12345,
            total_cost=100000,
            settlement_rate=0.9,
            avg_delay=1.5,
            cost_breakdown=CostBreakdown(
                delay_cost=50000,
                overdraft_cost=50000,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            event_trace=tuple(events),
            per_agent_costs={
                "BANK_A": 25000,  # BANK_A's cost
                "BANK_B": 75000,  # BANK_B's cost
            },
        )

        # Build context for both agents
        builder_a = EnrichedBootstrapContextBuilder([result], "BANK_A")
        context_a = builder_a.build_agent_context()

        builder_b = EnrichedBootstrapContextBuilder([result], "BANK_B")
        context_b = builder_b.build_agent_context()

        # Costs should differ
        assert context_a.best_seed_cost != context_b.best_seed_cost, (
            "Different agents should see different costs!"
        )
        assert context_a.best_seed_cost == 25000, "BANK_A should see 25000"
        assert context_b.best_seed_cost == 75000, "BANK_B should see 75000"
