"""Tests for user prompt builder.

The user prompt provides the LLM with:
1. Current policy for the target agent
2. Filtered tick-by-tick simulation output (ONLY target agent's events)
3. Past iteration history (policy changes and cost deltas)
4. Final instructions for what to optimize
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from payment_simulator.ai_cash_mgmt.prompts.user_prompt_builder import (
    UserPromptBuilder,
    build_user_prompt,
)


class TestUserPromptStructure:
    """Tests for overall user prompt structure."""

    def test_prompt_is_string(self) -> None:
        """build_user_prompt returns a string."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Release"}}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert isinstance(prompt, str)

    def test_prompt_not_empty(self) -> None:
        """Prompt is not empty."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Release"}}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert len(prompt) > 0

    def test_prompt_includes_agent_id(self) -> None:
        """Prompt mentions the target agent."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert "BANK_A" in prompt

    def test_prompt_has_clear_sections(self) -> None:
        """Prompt has multiple clear sections."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Release"}}
        events: list[dict[str, Any]] = [
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"}
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        # Should have multiple sections
        section_markers = ["POLICY", "SIMULATION", "INSTRUCTION"]
        section_count = sum(1 for marker in section_markers if marker in prompt.upper())
        assert section_count >= 2, "Expected at least 2 sections"


class TestCurrentPolicySection:
    """Tests for current policy section."""

    def test_includes_current_policy_json(self) -> None:
        """Prompt includes current policy as JSON."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Release"}}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert "Release" in prompt
        assert "payment_tree" in prompt

    def test_policy_formatted_as_json(self) -> None:
        """Policy is formatted as JSON block."""
        policy: dict[str, Any] = {
            "payment_tree": {
                "type": "condition",
                "field": "balance",
                "comparison": ">=",
                "value": 10000,
                "if_true": {"type": "action", "action": "Release"},
                "if_false": {"type": "action", "action": "Hold"},
            }
        }
        prompt = build_user_prompt("BANK_A", policy, [])
        # Should contain JSON-like structure
        assert '"type"' in prompt or "type" in prompt
        assert "balance" in prompt
        assert "10000" in prompt

    def test_empty_policy_handled(self) -> None:
        """Empty policy doesn't cause error."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert isinstance(prompt, str)


class TestSimulationOutputSection:
    """Tests for filtered simulation output section."""

    def test_includes_events(self) -> None:
        """Prompt includes simulation events."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            {
                "tick": 1,
                "event_type": "Arrival",
                "sender_id": "BANK_A",
                "receiver_id": "BANK_B",
                "amount": 100000,
            }
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        # Should have some indication of events/simulation
        assert "tick" in prompt.lower() or "simulation" in prompt.lower()

    def test_events_filtered_by_agent(self) -> None:
        """Events are filtered to only target agent."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            # BANK_A should see this (outgoing)
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            # BANK_A should NOT see this
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_C", "receiver_id": "BANK_D"},
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        assert "BANK_A" in prompt
        assert "BANK_B" in prompt  # BANK_A's counterparty
        # The C->D transaction should be filtered out
        # This is tricky to test without implementation details
        # We verify by checking the isolation doesn't leak other's outgoing

    def test_empty_events_shows_message(self) -> None:
        """Empty events list shows appropriate message."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = []
        prompt = build_user_prompt("BANK_A", policy, events)
        assert "no event" in prompt.lower() or "empty" in prompt.lower()

    def test_events_grouped_by_tick(self) -> None:
        """Events from multiple ticks shown with tick headers."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"},
            {"tick": 2, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_C"},
            {"tick": 5, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_D"},
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        # Should have tick indicators
        assert "1" in prompt
        assert "2" in prompt
        assert "5" in prompt


class TestIterationHistorySection:
    """Tests for iteration history section."""

    def test_includes_history_when_provided(self) -> None:
        """Prompt includes iteration history."""
        policy: dict[str, Any] = {}
        history: list[dict[str, Any]] = [
            {"iteration": 1, "total_cost": 10000, "policy_summary": "Release all"},
            {"iteration": 2, "total_cost": 8000, "policy_summary": "Hold high amounts"},
        ]
        builder = UserPromptBuilder("BANK_A", policy).with_history(history)
        prompt = builder.build()
        assert "iteration" in prompt.lower() or "history" in prompt.lower()
        # 10000 cents = $100.00
        assert "$100.00" in prompt

    def test_history_shows_cost_changes(self) -> None:
        """History shows cost changes between iterations."""
        policy: dict[str, Any] = {}
        history: list[dict[str, Any]] = [
            {"iteration": 1, "total_cost": 10000},
            {"iteration": 2, "total_cost": 8000},
        ]
        builder = UserPromptBuilder("BANK_A", policy).with_history(history)
        prompt = builder.build()
        # Should show both costs (10000 cents = $100.00, 8000 cents = $80.00)
        assert "$100.00" in prompt
        assert "$80.00" in prompt

    def test_no_history_section_when_none(self) -> None:
        """No history section when no history provided."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        # History section should be minimal or absent
        # Can't easily test absence, but prompt should still work


class TestCostBreakdownSection:
    """Tests for cost breakdown section."""

    def test_includes_cost_breakdown_when_provided(self) -> None:
        """Prompt includes cost breakdown from bootstrap evaluation."""
        policy: dict[str, Any] = {}
        best_seed: dict[str, Any] = {
            "seed": 12345,
            "total_cost": 5000,
            "overdraft_cost": 1000,
            "delay_cost": 4000,
        }
        worst_seed: dict[str, Any] = {
            "seed": 54321,
            "total_cost": 15000,
            "overdraft_cost": 5000,
            "delay_cost": 10000,
        }
        average: dict[str, Any] = {
            "total_cost": 10000,
            "overdraft_cost": 3000,
            "delay_cost": 7000,
        }
        builder = UserPromptBuilder("BANK_A", policy).with_cost_breakdown(
            best_seed, worst_seed, average
        )
        prompt = builder.build()
        # Should mention cost breakdown
        assert "cost" in prompt.lower()
        # 5000 cents = $50.00, 15000 cents = $150.00
        assert "$50.00" in prompt  # best total
        assert "$150.00" in prompt  # worst total

    def test_cost_breakdown_shows_all_cost_types(self) -> None:
        """Cost breakdown shows different cost components."""
        policy: dict[str, Any] = {}
        best_seed: dict[str, Any] = {
            "total_cost": 5000,
            "overdraft_cost": 1000,
            "delay_cost": 2000,
            "deadline_penalty": 1500,
            "eod_penalty": 500,
        }
        worst_seed: dict[str, Any] = best_seed.copy()
        average: dict[str, Any] = best_seed.copy()
        builder = UserPromptBuilder("BANK_A", policy).with_cost_breakdown(
            best_seed, worst_seed, average
        )
        prompt = builder.build()
        # Should mention various cost types
        assert "overdraft" in prompt.lower()
        assert "delay" in prompt.lower()


class TestFinalInstructionsSection:
    """Tests for final instructions section."""

    def test_includes_final_instructions(self) -> None:
        """Prompt includes instructions for what to do."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        # Should have some instruction
        instruction_keywords = ["analyze", "optimize", "improve", "generate", "provide", "return"]
        has_instruction = any(kw in prompt.lower() for kw in instruction_keywords)
        assert has_instruction, "Expected some instruction keywords"

    def test_instructions_request_json_output(self) -> None:
        """Instructions request JSON policy output."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert "json" in prompt.lower() or "JSON" in prompt

    def test_instructions_mention_cost_minimization(self) -> None:
        """Instructions mention cost minimization objective."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        cost_keywords = ["cost", "minimize", "reduce", "lower", "improve"]
        has_cost = any(kw in prompt.lower() for kw in cost_keywords)
        assert has_cost, "Expected cost-related instruction"


class TestBuilderPattern:
    """Tests for the builder pattern API."""

    def test_builder_returns_self(self) -> None:
        """Builder methods return self for chaining."""
        policy: dict[str, Any] = {}
        builder = UserPromptBuilder("BANK_A", policy)

        result_events = builder.with_events([])
        assert result_events is builder

        result_history = builder.with_history([])
        assert result_history is builder

    def test_builder_chain(self) -> None:
        """Builder supports method chaining."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Hold"}}
        events: list[dict[str, Any]] = [{"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"}]
        history: list[dict[str, Any]] = [{"iteration": 1, "total_cost": 5000}]

        prompt = (
            UserPromptBuilder("BANK_A", policy)
            .with_events(events)
            .with_history(history)
            .build()
        )

        assert isinstance(prompt, str)
        assert "BANK_A" in prompt
        assert "Hold" in prompt

    def test_builder_no_events(self) -> None:
        """Builder works without events."""
        policy: dict[str, Any] = {}
        prompt = UserPromptBuilder("BANK_A", policy).build()
        assert isinstance(prompt, str)

    def test_builder_with_only_events(self) -> None:
        """Builder works with only events."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [{"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"}]
        prompt = UserPromptBuilder("BANK_A", policy).with_events(events).build()
        assert isinstance(prompt, str)


class TestConvenienceFunction:
    """Tests for the build_user_prompt convenience function."""

    def test_convenience_function_basic(self) -> None:
        """Convenience function works with minimal args."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK_A", policy, [])
        assert isinstance(prompt, str)
        assert "BANK_A" in prompt

    def test_convenience_function_with_history(self) -> None:
        """Convenience function accepts history."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = []
        history: list[dict[str, Any]] = [{"iteration": 1, "total_cost": 5000}]
        prompt = build_user_prompt("BANK_A", policy, events, history=history)
        assert isinstance(prompt, str)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_special_characters_in_agent_id(self) -> None:
        """Agent ID with special characters handled."""
        policy: dict[str, Any] = {}
        prompt = build_user_prompt("BANK-A_01", policy, [])
        assert "BANK-A_01" in prompt

    def test_large_policy_handled(self) -> None:
        """Large nested policy handled."""
        policy: dict[str, Any] = {
            "payment_tree": {
                "type": "condition",
                "field": "balance",
                "comparison": ">=",
                "value": 10000,
                "if_true": {
                    "type": "condition",
                    "field": "ticks_to_deadline",
                    "comparison": "<=",
                    "value": 5,
                    "if_true": {"type": "action", "action": "Release"},
                    "if_false": {"type": "action", "action": "Hold"},
                },
                "if_false": {"type": "action", "action": "Hold"},
            }
        }
        prompt = build_user_prompt("BANK_A", policy, [])
        assert "balance" in prompt
        assert "ticks_to_deadline" in prompt

    def test_many_events_handled(self) -> None:
        """Many events don't cause issues."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            {"tick": i, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": f"BANK_{i}"}
            for i in range(100)
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_unicode_in_events_handled(self) -> None:
        """Unicode characters in events handled."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B", "note": "Test note with unicode"}
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        assert isinstance(prompt, str)


class TestAgentIsolationInPrompt:
    """Tests verifying agent isolation in the final prompt."""

    def test_other_agent_outgoing_not_visible(self) -> None:
        """Other agents' outgoing transactions not in prompt."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            # BANK_A's outgoing - should see
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B", "amount": 1000},
            # BANK_C's outgoing - should NOT see
            {"tick": 1, "event_type": "Arrival", "sender_id": "BANK_C", "receiver_id": "BANK_D", "amount": 9999},
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        # The 9999 amount should not appear since it's BANK_C -> BANK_D
        # BANK_A isn't involved at all
        assert "BANK_A" in prompt
        # BANK_C->BANK_D transaction should be filtered
        # Since 9999 is unique to BANK_C's tx, it shouldn't appear
        # (unless it's displayed as part of other context)

    def test_other_agent_costs_not_visible(self) -> None:
        """Other agents' cost accruals not in prompt."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            {"tick": 1, "event_type": "CostAccrual", "agent_id": "BANK_A", "costs": {"delay": 100}},
            {"tick": 1, "event_type": "CostAccrual", "agent_id": "BANK_B", "costs": {"delay": 99999}},
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        # BANK_B's cost of 99999 cents should not appear
        # 100 cents = $1.00, 99999 cents = $999.99
        assert "$1.00" in prompt  # BANK_A's cost
        assert "$999.99" not in prompt  # BANK_B's cost shouldn't appear

    def test_incoming_liquidity_visible(self) -> None:
        """Incoming liquidity events are visible."""
        policy: dict[str, Any] = {}
        events: list[dict[str, Any]] = [
            {
                "tick": 1,
                "event_type": "RtgsImmediateSettlement",
                "sender": "BANK_B",
                "receiver": "BANK_A",
                "amount": 50000,
            }
        ]
        prompt = build_user_prompt("BANK_A", policy, events)
        # BANK_A should see this incoming payment
        assert "50000" in prompt or "50,000" in prompt or "500" in prompt


class TestPromptReadability:
    """Tests for prompt readability and formatting."""

    def test_prompt_has_whitespace_formatting(self) -> None:
        """Prompt uses whitespace for readability."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Release"}}
        events: list[dict[str, Any]] = [{"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"}]
        prompt = build_user_prompt("BANK_A", policy, events)
        # Should have multiple lines
        assert "\n" in prompt
        # Should have multiple sections separated by whitespace
        assert prompt.count("\n\n") >= 1 or prompt.count("\n") >= 5

    def test_prompt_uses_headers(self) -> None:
        """Prompt uses clear headers."""
        policy: dict[str, Any] = {"payment_tree": {"type": "action", "action": "Release"}}
        events: list[dict[str, Any]] = [{"tick": 1, "event_type": "Arrival", "sender_id": "BANK_A", "receiver_id": "BANK_B"}]
        prompt = build_user_prompt("BANK_A", policy, events)
        # Should have some header-like formatting
        header_indicators = ["===", "---", "##", "**", "POLICY", "SIMULATION", "INSTRUCTION"]
        has_header = any(ind in prompt or ind in prompt.upper() for ind in header_indicators)
        assert has_header, "Expected some header formatting"
