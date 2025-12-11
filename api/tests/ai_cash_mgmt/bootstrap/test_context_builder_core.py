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
