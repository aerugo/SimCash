"""Tests for BootstrapContextBuilder.

These tests verify the context builder that transforms enriched bootstrap
evaluation results into LLM-consumable context.

Key functionality:
- get_best_result() returns result with lowest cost
- get_worst_result() returns result with highest cost
- format_event_trace_for_llm() limits and prioritizes events
- build_agent_context() returns compatible AgentSimulationContext
"""

from __future__ import annotations

from typing import Any

import pytest


class TestBootstrapContextBuilderBestWorst:
    """Tests for get_best_result and get_worst_result methods."""

    def test_get_best_result_returns_lowest_cost(self) -> None:
        """get_best_result returns result with minimum cost."""
        from castro.bootstrap_context import BootstrapContextBuilder

        results = [
            _create_enriched_result(sample_idx=0, total_cost=1000),
            _create_enriched_result(sample_idx=1, total_cost=500),  # Best
            _create_enriched_result(sample_idx=2, total_cost=800),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        best = builder.get_best_result()
        assert best.total_cost == 500
        assert best.sample_idx == 1

    def test_get_worst_result_returns_highest_cost(self) -> None:
        """get_worst_result returns result with maximum cost."""
        from castro.bootstrap_context import BootstrapContextBuilder

        results = [
            _create_enriched_result(sample_idx=0, total_cost=1000),  # Worst
            _create_enriched_result(sample_idx=1, total_cost=500),
            _create_enriched_result(sample_idx=2, total_cost=800),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        worst = builder.get_worst_result()
        assert worst.total_cost == 1000
        assert worst.sample_idx == 0

    def test_single_result_is_both_best_and_worst(self) -> None:
        """With single result, best and worst are the same."""
        from castro.bootstrap_context import BootstrapContextBuilder

        results = [_create_enriched_result(sample_idx=0, total_cost=1000)]
        builder = BootstrapContextBuilder(results, "BANK_A")

        best = builder.get_best_result()
        worst = builder.get_worst_result()
        assert best.sample_idx == worst.sample_idx


class TestBootstrapContextBuilderFormatting:
    """Tests for format_event_trace_for_llm method."""

    def test_format_event_trace_limits_events(self) -> None:
        """format_event_trace_for_llm limits number of events."""
        from castro.bootstrap_context import BootstrapContextBuilder
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
        )

        events = [
            BootstrapEvent(tick=i, event_type="arrival", details={"tx_id": f"tx-{i}"})
            for i in range(100)
        ]
        result = _create_enriched_result(sample_idx=0, total_cost=1000, events=events)
        builder = BootstrapContextBuilder([result], "BANK_A")

        formatted = builder.format_event_trace_for_llm(result, max_events=20)

        # Should contain limited events (not all 100)
        # Count tick references as proxy for event count
        assert isinstance(formatted, str)
        assert len(formatted) > 0
        # The output should be truncated, so checking it's not too long
        assert formatted.count("tick") <= 25  # Allow some slack for formatting

    def test_format_event_trace_returns_string(self) -> None:
        """format_event_trace_for_llm returns string."""
        from castro.bootstrap_context import BootstrapContextBuilder

        result = _create_enriched_result(sample_idx=0, total_cost=1000)
        builder = BootstrapContextBuilder([result], "BANK_A")

        formatted = builder.format_event_trace_for_llm(result, max_events=50)

        assert isinstance(formatted, str)

    def test_format_empty_event_trace(self) -> None:
        """format_event_trace_for_llm handles empty trace."""
        from castro.bootstrap_context import BootstrapContextBuilder

        result = _create_enriched_result(sample_idx=0, total_cost=1000, events=[])
        builder = BootstrapContextBuilder([result], "BANK_A")

        formatted = builder.format_event_trace_for_llm(result, max_events=50)

        assert isinstance(formatted, str)


class TestBootstrapContextBuilderAgentContext:
    """Tests for build_agent_context method."""

    def test_build_agent_context_returns_context(self) -> None:
        """build_agent_context returns AgentSimulationContext."""
        from castro.bootstrap_context import BootstrapContextBuilder

        results = [
            _create_enriched_result(sample_idx=0, total_cost=1000),
            _create_enriched_result(sample_idx=1, total_cost=500),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        context = builder.build_agent_context()

        # Should have mean_cost and best/worst info
        assert context.mean_cost == 750  # (1000 + 500) / 2
        assert context.best_seed_cost == 500
        assert context.worst_seed_cost == 1000

    def test_build_agent_context_has_output_strings(self) -> None:
        """build_agent_context includes formatted event traces."""
        from castro.bootstrap_context import BootstrapContextBuilder

        results = [_create_enriched_result(sample_idx=0, total_cost=1000)]
        builder = BootstrapContextBuilder(results, "BANK_A")

        context = builder.build_agent_context()

        # Should have best/worst output strings
        assert context.best_seed_output is not None
        assert context.worst_seed_output is not None
        assert isinstance(context.best_seed_output, str)
        assert isinstance(context.worst_seed_output, str)

    def test_build_agent_context_computes_std(self) -> None:
        """build_agent_context computes cost standard deviation."""
        from castro.bootstrap_context import BootstrapContextBuilder

        # Results with known variance
        results = [
            _create_enriched_result(sample_idx=0, total_cost=1000),
            _create_enriched_result(sample_idx=1, total_cost=1000),
            _create_enriched_result(sample_idx=2, total_cost=1000),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        context = builder.build_agent_context()

        # With identical costs, std should be 0
        assert context.cost_std == 0


class TestBootstrapContextBuilderInvariants:
    """Tests for project invariants in BootstrapContextBuilder."""

    def test_mean_cost_is_integer(self) -> None:
        """mean_cost in context is integer (INV-1)."""
        from castro.bootstrap_context import BootstrapContextBuilder

        results = [
            _create_enriched_result(sample_idx=0, total_cost=1001),
            _create_enriched_result(sample_idx=1, total_cost=1002),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        context = builder.build_agent_context()

        # Mean is 1001.5, should be rounded to integer
        assert isinstance(context.mean_cost, int)


def _create_enriched_result(
    sample_idx: int,
    total_cost: int,
    events: list[Any] | None = None,
) -> Any:
    """Create a minimal EnrichedEvaluationResult for testing.

    Args:
        sample_idx: Sample index.
        total_cost: Total cost in cents.
        events: Optional list of events. If None, creates a default event.

    Returns:
        EnrichedEvaluationResult instance.
    """
    from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
        BootstrapEvent,
        CostBreakdown,
        EnrichedEvaluationResult,
    )

    if events is None:
        events = [BootstrapEvent(tick=0, event_type="test", details={})]

    return EnrichedEvaluationResult(
        sample_idx=sample_idx,
        seed=42 + sample_idx,
        total_cost=total_cost,
        settlement_rate=0.95,
        avg_delay=2.5,
        event_trace=tuple(events),
        cost_breakdown=CostBreakdown(
            delay_cost=total_cost // 2,
            overdraft_cost=total_cost // 4,
            deadline_penalty=total_cost // 4,
            eod_penalty=0,
        ),
    )
