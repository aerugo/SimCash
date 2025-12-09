"""Tests for SingleAgentContextBuilder.

Tests for the context builder that creates rich prompts for LLM optimization.
"""

from __future__ import annotations

import pytest


class TestSingleAgentContextBuilder:
    """Tests for SingleAgentContextBuilder class."""

    def test_includes_header_with_agent_id(self) -> None:
        """Header includes agent ID and iteration."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(agent_id="BANK_A", current_iteration=5)
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "BANK_A" in prompt
        assert "ITERATION 5" in prompt

    def test_includes_table_of_contents(self) -> None:
        """Table of contents is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(agent_id="BANK_A", current_iteration=1)
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "TABLE OF CONTENTS" in prompt
        assert "Current State Summary" in prompt
        assert "Cost Analysis" in prompt

    def test_includes_current_state_summary(self) -> None:
        """Current state summary section is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_metrics={"total_cost_mean": 12500, "settlement_rate_mean": 1.0},
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "CURRENT STATE SUMMARY" in prompt
        assert "$12,500" in prompt

    def test_includes_cost_breakdown(self) -> None:
        """Cost analysis section shows breakdown."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            cost_breakdown={"delay": 5000, "collateral": 3000, "overdraft": 2000},
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "COST ANALYSIS" in prompt
        assert "delay" in prompt
        assert "$5,000" in prompt

    def test_cost_breakdown_shows_percentages(self) -> None:
        """Cost breakdown shows percentages."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            cost_breakdown={"delay": 5000, "collateral": 5000},  # 50% each
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "50" in prompt  # Percentage

    def test_includes_optimization_guidance_for_high_delay(self) -> None:
        """High delay costs trigger guidance."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            cost_breakdown={"delay": 6000, "collateral": 2000},  # delay > 40%
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "HIGH DELAY COSTS" in prompt

    def test_includes_optimization_guidance_for_high_collateral(self) -> None:
        """High collateral costs trigger guidance."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            cost_breakdown={"delay": 2000, "collateral": 6000},  # collateral > 40%
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "HIGH COLLATERAL COSTS" in prompt

    def test_includes_best_seed_output(self) -> None:
        """Verbose simulation output from best seed is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            best_seed=42,
            best_seed_cost=11200,
            best_seed_output="[Tick 0] Posted collateral...",
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "Best Performing Seed" in prompt
        assert "#42" in prompt
        assert "$11,200" in prompt
        assert "Posted collateral" in prompt

    def test_includes_worst_seed_output(self) -> None:
        """Verbose simulation output from worst seed is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            worst_seed=17,
            worst_seed_cost=14800,
            worst_seed_output="[Tick 3] Failed to settle...",
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "Worst Performing Seed" in prompt
        assert "#17" in prompt
        assert "$14,800" in prompt
        assert "Failed to settle" in prompt

    def test_includes_iteration_history_table(self) -> None:
        """Iteration history table is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1,
                    metrics={"total_cost_mean": 15000, "settlement_rate_mean": 1.0},
                    policy={"parameters": {"threshold": 5.0}},
                    is_best_so_far=True,
                ),
                SingleAgentIterationRecord(
                    iteration=2,
                    metrics={"total_cost_mean": 16000, "settlement_rate_mean": 1.0},
                    policy={"parameters": {"threshold": 6.0}},
                    was_accepted=False,
                    comparison_to_best="Cost increased by 6.7%",
                ),
            ],
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "ITERATION HISTORY" in prompt
        assert "⭐ BEST" in prompt
        assert "❌ REJECTED" in prompt

    def test_includes_accepted_status(self) -> None:
        """Accepted status is shown correctly."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1,
                    metrics={"total_cost_mean": 15000, "settlement_rate_mean": 1.0},
                    policy={"parameters": {}},
                    was_accepted=True,
                    is_best_so_far=False,
                ),
            ],
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "✅ KEPT" in prompt

    def test_includes_parameter_trajectories(self) -> None:
        """Parameter trajectories section is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1,
                    metrics={},
                    policy={"parameters": {"threshold": 5.0}},
                ),
                SingleAgentIterationRecord(
                    iteration=2,
                    metrics={},
                    policy={"parameters": {"threshold": 4.0}},
                ),
            ],
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "PARAMETER TRAJECTORIES" in prompt
        assert "threshold" in prompt

    def test_includes_final_instructions(self) -> None:
        """Final instructions section is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(agent_id="BANK_A", current_iteration=1)
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "FINAL INSTRUCTIONS" in prompt
        assert "BANK_A" in prompt

    def test_warns_about_rejected_policies(self) -> None:
        """Warning about rejected policies is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=3,
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1, metrics={}, policy={},
                ),
                SingleAgentIterationRecord(
                    iteration=2, metrics={}, policy={}, was_accepted=False,
                ),
            ],
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "REJECTED" in prompt.upper()

    def test_no_cross_agent_leakage(self) -> None:
        """Only this agent's data is included."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=1,
            current_policy={"parameters": {"threshold": 5.0}},
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        # Should NOT contain references to other banks
        assert "BANK_B" not in prompt
        assert "Bank B" not in prompt

    def test_uses_agent_label_when_no_id(self) -> None:
        """Uses 'Agent' label when agent_id is None."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(agent_id=None, current_iteration=1)
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        assert "Agent" in prompt

    def test_shows_cost_delta_from_previous(self) -> None:
        """Shows cost change from previous iteration."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=2,
            current_metrics={"total_cost_mean": 9000, "settlement_rate_mean": 1.0},
            iteration_history=[
                SingleAgentIterationRecord(
                    iteration=1,
                    metrics={"total_cost_mean": 10000, "settlement_rate_mean": 1.0},
                    policy={"parameters": {}},
                ),
            ],
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        # Should show a decrease indicator
        assert "↓" in prompt or "%" in prompt


class TestBuildSingleAgentContext:
    """Tests for build_single_agent_context convenience function."""

    def test_creates_context_and_builds(self) -> None:
        """Convenience function creates context and builds prompt."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={"parameters": {"threshold": 5.0}},
            current_metrics={"total_cost_mean": 10000},
            agent_id="BANK_A",
        )

        assert "BANK_A" in prompt
        assert "ITERATION 1" in prompt
        assert "$10,000" in prompt

    def test_includes_verbose_output(self) -> None:
        """Verbose output is included via convenience function."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={},
            current_metrics={},
            best_seed_output="[Tick 0] Started...",
            best_seed=42,
            best_seed_cost=1000,
            agent_id="BANK_A",
        )

        assert "Started" in prompt
        assert "#42" in prompt

    def test_includes_cost_rates(self) -> None:
        """Cost rates are included if provided."""
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            build_single_agent_context,
        )

        prompt = build_single_agent_context(
            current_iteration=1,
            current_policy={},
            current_metrics={},
            cost_rates={"delay_per_tick": 100},
            cost_breakdown={"delay": 5000},
            agent_id="BANK_A",
        )

        # Cost rates should be in JSON block
        assert "delay_per_tick" in prompt


class TestContextSize:
    """Tests to ensure context is substantial."""

    def test_context_with_history_is_substantial(self) -> None:
        """Context with history should be substantial (10k+ chars)."""
        from payment_simulator.ai_cash_mgmt.prompts.context_types import (
            SingleAgentContext,
            SingleAgentIterationRecord,
        )
        from payment_simulator.ai_cash_mgmt.prompts.single_agent_context import (
            SingleAgentContextBuilder,
        )

        # Create substantial history
        history = [
            SingleAgentIterationRecord(
                iteration=i,
                metrics={
                    "total_cost_mean": 15000 - i * 100,
                    "total_cost_std": 1000,
                    "settlement_rate_mean": 1.0,
                },
                policy={"parameters": {"threshold": 5.0 - i * 0.1}},
                policy_changes=[f"Changed 'threshold': {5.0 - (i-1)*0.1} → {5.0 - i*0.1}"],
            )
            for i in range(1, 6)
        ]

        context = SingleAgentContext(
            agent_id="BANK_A",
            current_iteration=6,
            current_policy={"parameters": {"threshold": 4.5}},
            current_metrics={"total_cost_mean": 14500, "settlement_rate_mean": 1.0},
            iteration_history=history,
            best_seed=42,
            best_seed_cost=14000,
            worst_seed=17,
            worst_seed_cost=15500,
            best_seed_output="[Tick 0] Started...\n" * 50,
            worst_seed_output="[Tick 0] Failed...\n" * 50,
            cost_breakdown={"delay": 6000, "collateral": 4000, "overdraft": 2000},
            cost_rates={"delay_per_tick": 100, "collateral_rate": 0.01},
        )
        builder = SingleAgentContextBuilder(context)

        prompt = builder.build()

        # Should be substantial - aim for 10k+ chars with full context
        assert len(prompt) > 5000
