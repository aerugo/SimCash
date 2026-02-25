"""Tests for settlement optimization features (Phases 1-4)."""
from __future__ import annotations

import pytest

from payment_simulator.ai_cash_mgmt.prompts.context_types import SingleAgentContext
from payment_simulator.ai_cash_mgmt.prompts.event_filter import extract_balance_trajectory
from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
    SingleAgentContextBuilder,
)
from payment_simulator.ai_cash_mgmt.prompts.system_prompt_builder import (
    SystemPromptBuilder,
    build_system_prompt,
)


# ── Phase 1b: extract_balance_trajectory ─────────────────────────────

class TestExtractBalanceTrajectory:
    """Tests for the balance trajectory extraction function."""

    def test_empty_events_returns_empty(self) -> None:
        result = extract_balance_trajectory("BANK_A", [])
        assert result == ""

    def test_no_relevant_events_returns_empty(self) -> None:
        events = [
            {"tick": 0, "event_type": "ScenarioEventExecuted"},
        ]
        result = extract_balance_trajectory("BANK_A", events)
        assert result == ""

    def test_settlement_events_produce_table(self) -> None:
        events = [
            {
                "tick": 0,
                "event_type": "RtgsImmediateSettlement",
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 500_00,  # $500
                "sender_balance_before": 10000_00,
                "sender_balance_after": 9500_00,
            },
            {
                "tick": 1,
                "event_type": "RtgsImmediateSettlement",
                "sender": "BANK_B",
                "receiver": "BANK_A",
                "amount": 300_00,
                "sender_balance_before": 8000_00,
                "sender_balance_after": 7700_00,
            },
        ]
        result = extract_balance_trajectory("BANK_A", events)
        assert "Tick" in result
        assert "Balance" in result
        # Tick 0: outflow of $500, balance = $9500
        assert "$9,500.00" in result
        # Tick 1: inflow of $300
        assert "$300.00" in result

    def test_queued_payments_tracked(self) -> None:
        events = [
            {
                "tick": 3,
                "event_type": "QueuedRtgs",
                "sender_id": "BANK_A",
                "tx_id": "tx1",
                "amount": 200_00,
            },
            {
                "tick": 3,
                "event_type": "RtgsImmediateSettlement",
                "sender": "BANK_A",
                "receiver": "BANK_B",
                "amount": 100_00,
                "sender_balance_before": 150_00,
                "sender_balance_after": 50_00,
            },
        ]
        result = extract_balance_trajectory("BANK_A", events)
        # Should show queued count = 1
        assert "1" in result  # queue count
        # Feasibility: balance 50 / largest queued 200 = 0.25
        assert "0.2" in result or "⚠️" in result


# ── Phase 1a: Liquidity context ─────────────────────────────────────

class TestLiquidityContext:
    """Tests for RTGS liquidity context in user prompt."""

    def test_liquidity_context_shown_when_pool_set(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_policy={"parameters": {"initial_liquidity_fraction": 0.5}},
            liquidity_pool=1_000_000_00,  # $1M
            expected_daily_demand=240_000_00,  # $240K
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "RTGS SETTLEMENT ACCOUNT CONTEXT" in prompt
        assert "$1,000,000.00" in prompt
        assert "$500,000.00" in prompt  # committed = 0.5 * 1M
        assert "$240,000.00" in prompt

    def test_liquidity_context_hidden_when_no_pool(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            liquidity_pool=0,
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "RTGS SETTLEMENT ACCOUNT CONTEXT" not in prompt


# ── Phase 2c: Settlement floor warning ───────────────────────────────

class TestSettlementFloorWarning:
    """Tests for settlement floor warning in optimization guidance."""

    def test_settlement_below_floor_shows_urgent_warning(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            current_metrics={"settlement_rate_mean": 0.82},
            cost_breakdown={"delay_cost": 5000, "liquidity_opportunity_cost": 1000},
            min_settlement_rate=0.95,
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "SETTLEMENT BELOW MINIMUM" in prompt
        assert "82.0%" in prompt
        assert "95%" in prompt

    def test_settlement_above_floor_no_urgent_warning(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            current_metrics={"settlement_rate_mean": 0.98},
            cost_breakdown={"delay_cost": 5000},
            min_settlement_rate=0.95,
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "SETTLEMENT BELOW MINIMUM" not in prompt


# ── Phase 3a: Crunch tradeoff detection ──────────────────────────────

class TestCrunchTradeoff:
    """Tests for RTGS balance tradeoff detection."""

    def test_crunch_detected_when_both_costs_high(self) -> None:
        # Both delay and liquidity_opportunity > 20%
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            current_metrics={"settlement_rate_mean": 1.0},
            cost_breakdown={
                "delay_cost": 3000,
                "liquidity_opportunity_cost": 3000,
                "deadline_penalty": 1000,
            },
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "RTGS BALANCE TRADEOFF" in prompt

    def test_no_crunch_when_costs_not_both_high(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            current_metrics={"settlement_rate_mean": 1.0},
            cost_breakdown={
                "delay_cost": 100,
                "liquidity_opportunity_cost": 9000,
            },
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "RTGS BALANCE TRADEOFF" not in prompt


# ── Phase 1c + 2c: System prompt sections ────────────────────────────

class TestSystemPromptNewSections:
    """Tests for new system prompt sections."""

    def _make_constraints(self):
        """Create minimal ScenarioConstraints for testing."""
        from payment_simulator.ai_cash_mgmt.constraints import ScenarioConstraints
        return ScenarioConstraints(
            allowed_parameters=[],
            allowed_fields=["balance"],
            allowed_actions={"payment_tree": ["Release", "Hold"]},
            lsm_enabled=False,
        )

    def test_deferred_crediting_section_included(self) -> None:
        builder = SystemPromptBuilder(self._make_constraints())
        builder.with_deferred_crediting(True)
        prompt = builder.build()
        assert "DEFERRED CREDITING" in prompt
        assert "tick T+1" in prompt

    def test_deferred_crediting_section_excluded_when_off(self) -> None:
        builder = SystemPromptBuilder(self._make_constraints())
        builder.with_deferred_crediting(False)
        prompt = builder.build()
        assert "DEFERRED CREDITING" not in prompt

    def test_settlement_constraint_section_included(self) -> None:
        builder = SystemPromptBuilder(self._make_constraints())
        builder.with_min_settlement_rate(0.95)
        prompt = builder.build()
        assert "Settlement Constraint" in prompt
        assert "95%" in prompt

    def test_tree_composition_off_by_default(self) -> None:
        builder = SystemPromptBuilder(self._make_constraints())
        prompt = builder.build()
        assert "Tree Interaction Capabilities" not in prompt

    def test_tree_composition_on_when_enabled(self) -> None:
        builder = SystemPromptBuilder(self._make_constraints())
        builder.with_tree_composition(True)
        prompt = builder.build()
        assert "Tree Interaction Capabilities" in prompt
        assert "SetReleaseBudget" in prompt
        assert "bank_state_0" in prompt


# ── Phase 3b: Worst-case seed summary ────────────────────────────────

class TestWorstCaseSummary:
    """Tests for worst-case seed summary in user prompt."""

    def test_worst_case_shown_when_provided(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
            worst_seed_summary="Tick 5: balance dropped to $120. 4 payments queued.",
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "WORST-CASE ANALYSIS" in prompt
        assert "Tick 5" in prompt

    def test_worst_case_hidden_when_not_provided(self) -> None:
        ctx = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
        )
        builder = SingleAgentContextBuilder(ctx)
        prompt = builder.build()
        assert "WORST-CASE ANALYSIS" not in prompt
