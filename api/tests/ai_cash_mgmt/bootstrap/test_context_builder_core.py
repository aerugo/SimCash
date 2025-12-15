"""TDD tests for core EnrichedBootstrapContextBuilder.

These tests verify the context builder works correctly when
moved to the core ai_cash_mgmt module.

Write these tests FIRST, then implement.
"""

from __future__ import annotations

import pytest


class TestAgentSimulationContextImport:
    """Tests for importing AgentSimulationContext from core."""

    def test_importable_from_bootstrap_init(self) -> None:
        """AgentSimulationContext should be importable from bootstrap."""
        from payment_simulator.ai_cash_mgmt.bootstrap import AgentSimulationContext

        assert AgentSimulationContext is not None

    def test_importable_from_context_builder_module(self) -> None:
        """Direct import from context_builder module should work."""
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            AgentSimulationContext,
        )

        assert AgentSimulationContext is not None


class TestEnrichedBootstrapContextBuilderImport:
    """Tests for importing builder from new core location."""

    def test_importable_from_ai_cash_mgmt_bootstrap(self) -> None:
        """EnrichedBootstrapContextBuilder should be importable from core."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        assert EnrichedBootstrapContextBuilder is not None

    def test_importable_from_context_builder_module(self) -> None:
        """Should be exported in bootstrap __init__.py."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        # Direct import should also work
        from payment_simulator.ai_cash_mgmt.bootstrap.context_builder import (
            EnrichedBootstrapContextBuilder as DirectImport,
        )

        assert EnrichedBootstrapContextBuilder is DirectImport


class TestEnrichedBootstrapContextBuilderFunctionality:
    """Tests for core functionality of context builder."""

    @pytest.fixture
    def sample_enriched_results(self) -> list:
        """Create sample EnrichedEvaluationResult list."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        return [
            EnrichedEvaluationResult(
                sample_idx=0,
                seed=12345,
                total_cost=1000,
                settlement_rate=0.95,
                avg_delay=2.5,
                event_trace=[
                    BootstrapEvent(tick=0, event_type="Arrival", details={"amount": 500}),
                    BootstrapEvent(
                        tick=1, event_type="RtgsImmediateSettlement", details={"amount": 500}
                    ),
                ],
                cost_breakdown=CostBreakdown(
                    delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
                ),
            ),
            EnrichedEvaluationResult(
                sample_idx=1,
                seed=67890,
                total_cost=800,
                settlement_rate=1.0,
                avg_delay=1.0,
                event_trace=[
                    BootstrapEvent(tick=0, event_type="Arrival", details={"amount": 300}),
                ],
                cost_breakdown=CostBreakdown(
                    delay_cost=50, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
                ),
            ),
            EnrichedEvaluationResult(
                sample_idx=2,
                seed=11111,
                total_cost=1500,
                settlement_rate=0.8,
                avg_delay=5.0,
                event_trace=[],
                cost_breakdown=CostBreakdown(
                    delay_cost=200, overdraft_cost=100, deadline_penalty=0, eod_penalty=0
                ),
            ),
        ]

    def test_get_best_result_returns_lowest_cost(
        self, sample_enriched_results: list
    ) -> None:
        """get_best_result returns result with minimum total_cost."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST_AGENT",
        )
        best = builder.get_best_result()
        assert best.total_cost == 800
        assert best.seed == 67890

    def test_get_worst_result_returns_highest_cost(
        self, sample_enriched_results: list
    ) -> None:
        """get_worst_result returns result with maximum total_cost."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST_AGENT",
        )
        worst = builder.get_worst_result()
        assert worst.total_cost == 1500
        assert worst.seed == 11111

    def test_format_event_trace_limits_events(
        self, sample_enriched_results: list
    ) -> None:
        """format_event_trace_for_llm respects max_events limit."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Create result with many events
        many_events = [
            BootstrapEvent(tick=i, event_type="Arrival", details={}) for i in range(100)
        ]
        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=1,
            total_cost=1000,
            settlement_rate=0.9,
            avg_delay=3.0,
            event_trace=many_events,
            cost_breakdown=CostBreakdown(
                delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
        )
        builder = EnrichedBootstrapContextBuilder([result], "TEST")

        formatted = builder.format_event_trace_for_llm(result, max_events=20)

        # Should not contain more than 20 events
        tick_count = formatted.count("[tick ")
        assert tick_count <= 20

    def test_format_event_trace_empty_returns_placeholder(
        self, sample_enriched_results: list
    ) -> None:
        """format_event_trace_for_llm returns placeholder for empty trace."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=1,
            total_cost=1000,
            settlement_rate=0.9,
            avg_delay=3.0,
            event_trace=[],
            cost_breakdown=CostBreakdown(
                delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
        )
        builder = EnrichedBootstrapContextBuilder([result], "TEST")

        formatted = builder.format_event_trace_for_llm(result)

        assert "(No events captured)" in formatted

    def test_build_agent_context_returns_correct_type(
        self, sample_enriched_results: list
    ) -> None:
        """build_agent_context returns AgentSimulationContext."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            AgentSimulationContext,
            EnrichedBootstrapContextBuilder,
        )

        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST_AGENT",
        )
        context = builder.build_agent_context()

        assert isinstance(context, AgentSimulationContext)
        assert context.agent_id == "TEST_AGENT"
        assert context.best_seed == 67890
        assert context.worst_seed == 11111

    def test_costs_are_integer_cents(self, sample_enriched_results: list) -> None:
        """All costs in context should be integer cents (INV-1)."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        builder = EnrichedBootstrapContextBuilder(
            results=sample_enriched_results,
            agent_id="TEST",
        )
        context = builder.build_agent_context()

        assert isinstance(context.best_seed_cost, int)
        assert isinstance(context.worst_seed_cost, int)
        assert isinstance(context.mean_cost, int)

    def test_empty_results_raises_error(self) -> None:
        """Builder should raise ValueError for empty results."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        with pytest.raises(ValueError, match="empty"):
            EnrichedBootstrapContextBuilder(results=[], agent_id="TEST")


def _castro_available() -> bool:
    """Check if castro module is available."""
    try:
        import castro  # noqa: F401

        return True
    except ImportError:
        return False


class TestCastroBackwardCompatibility:
    """Tests ensuring Castro can still import the builder.

    These tests run in Castro's environment only.
    """

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_can_import_from_new_location(self) -> None:
        """Castro should be able to import from core location."""
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )

        assert EnrichedBootstrapContextBuilder is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_old_castro_import_path_works(self) -> None:
        """Old Castro import should work (via re-export)."""
        from castro.bootstrap_context import EnrichedBootstrapContextBuilder

        assert EnrichedBootstrapContextBuilder is not None

    @pytest.mark.skipif(
        not _castro_available(),
        reason="Castro module not available in this environment",
    )
    def test_castro_and_core_same_class(self) -> None:
        """Castro re-export should be the same class as core."""
        from castro.bootstrap_context import (
            EnrichedBootstrapContextBuilder as CastroClass,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder as CoreClass,
        )

        assert CastroClass is CoreClass


class TestPerAgentCostTracking:
    """Tests for per-agent cost tracking in context builder.

    REGRESSION: The context builder was using total_cost (sum of all agents)
    as the per-agent mean_cost, causing all agents to show the same cost
    in experiment final results.

    The fix requires EnrichedEvaluationResult to track per_agent_costs
    and the context builder to extract the correct agent's cost.
    """

    def test_mean_cost_reflects_agent_specific_cost_not_total(self) -> None:
        """mean_cost should be the specific agent's cost, not total simulation cost.

        REGRESSION TEST: Previously, mean_cost was set to total_cost which
        is the SUM of all agent costs. This caused all agents to show
        the same cost value (the total) in experiment final results.

        Example scenario:
        - BANK_A cost: 0 cents (free rider, no liquidity posted)
        - BANK_B cost: 2000 cents (20% liquidity opportunity cost)
        - total_cost: 2000 cents (0 + 2000)

        Bug behavior: Both agents showed mean_cost=2000
        Correct behavior: BANK_A.mean_cost=0, BANK_B.mean_cost=2000
        """
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Simulate Castro Experiment 1 results:
        # - BANK_A (free rider): 0% liquidity, $0 cost
        # - BANK_B (first mover): 20% liquidity, $20 cost
        # - total_cost: $20 (Bank A $0 + Bank B $20)
        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=42,
            total_cost=2000,  # Total: $20.00 (both agents combined)
            settlement_rate=1.0,
            avg_delay=0.0,
            event_trace=(),
            cost_breakdown=CostBreakdown(
                delay_cost=0,
                overdraft_cost=0,
                deadline_penalty=0,
                eod_penalty=0,
            ),
            # NEW FIELD: Per-agent costs
            per_agent_costs={"BANK_A": 0, "BANK_B": 2000},
        )

        # Build context for BANK_A (the free rider with $0 cost)
        builder_a = EnrichedBootstrapContextBuilder([result], "BANK_A")
        context_a = builder_a.build_agent_context()

        # Build context for BANK_B (the first mover with $20 cost)
        builder_b = EnrichedBootstrapContextBuilder([result], "BANK_B")
        context_b = builder_b.build_agent_context()

        # CRITICAL: mean_cost should be per-agent, NOT total
        # Bug: Both would show 2000 (total_cost)
        # Fix: BANK_A=0, BANK_B=2000
        assert context_a.mean_cost == 0, (
            f"BANK_A mean_cost should be 0 (agent's cost), "
            f"got {context_a.mean_cost} (likely using total_cost)"
        )
        assert context_b.mean_cost == 2000, (
            f"BANK_B mean_cost should be 2000 (agent's cost), "
            f"got {context_b.mean_cost}"
        )

    def test_best_worst_seed_cost_reflects_agent_specific_cost(self) -> None:
        """best_seed_cost and worst_seed_cost should be per-agent.

        When identifying best/worst seeds, the costs should be
        the specific agent's costs, not total simulation costs.
        """
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Two samples with different cost distributions
        # Sample 1: BANK_A=100, BANK_B=500, total=600
        # Sample 2: BANK_A=200, BANK_B=300, total=500
        sample1 = EnrichedEvaluationResult(
            sample_idx=0,
            seed=111,
            total_cost=600,
            settlement_rate=1.0,
            avg_delay=0.0,
            event_trace=(),
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            per_agent_costs={"BANK_A": 100, "BANK_B": 500},
        )
        sample2 = EnrichedEvaluationResult(
            sample_idx=1,
            seed=222,
            total_cost=500,
            settlement_rate=1.0,
            avg_delay=0.0,
            event_trace=(),
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            per_agent_costs={"BANK_A": 200, "BANK_B": 300},
        )

        # For BANK_A: Best=seed 111 (cost 100), Worst=seed 222 (cost 200)
        builder_a = EnrichedBootstrapContextBuilder([sample1, sample2], "BANK_A")
        context_a = builder_a.build_agent_context()

        assert context_a.best_seed == 111, "BANK_A best seed should be 111 (cost 100)"
        assert context_a.best_seed_cost == 100
        assert context_a.worst_seed == 222, "BANK_A worst seed should be 222 (cost 200)"
        assert context_a.worst_seed_cost == 200

        # For BANK_B: Best=seed 222 (cost 300), Worst=seed 111 (cost 500)
        builder_b = EnrichedBootstrapContextBuilder([sample1, sample2], "BANK_B")
        context_b = builder_b.build_agent_context()

        assert context_b.best_seed == 222, "BANK_B best seed should be 222 (cost 300)"
        assert context_b.best_seed_cost == 300
        assert context_b.worst_seed == 111, "BANK_B worst seed should be 111 (cost 500)"
        assert context_b.worst_seed_cost == 500

    def test_backward_compatibility_without_per_agent_costs(self) -> None:
        """Results without per_agent_costs should still work (fallback to total).

        For backward compatibility, if per_agent_costs is not provided,
        the builder should fall back to using total_cost (old behavior).
        """
        from payment_simulator.ai_cash_mgmt.bootstrap import (
            EnrichedBootstrapContextBuilder,
        )
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        # Old-style result without per_agent_costs
        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=42,
            total_cost=1000,
            settlement_rate=1.0,
            avg_delay=0.0,
            event_trace=(),
            cost_breakdown=CostBreakdown(
                delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
            # No per_agent_costs - should fall back to total_cost
        )

        builder = EnrichedBootstrapContextBuilder([result], "ANY_AGENT")
        context = builder.build_agent_context()

        # Should fall back to total_cost when per_agent_costs not available
        assert context.mean_cost == 1000
