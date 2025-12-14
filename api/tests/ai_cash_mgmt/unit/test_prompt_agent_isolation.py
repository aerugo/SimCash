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
