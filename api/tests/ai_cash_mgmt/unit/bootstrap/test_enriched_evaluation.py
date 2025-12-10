"""Tests for enriched bootstrap evaluation models and methods.

These tests verify the new dataclasses that support event tracing:
- BootstrapEvent: Captures events during evaluation
- CostBreakdown: Itemized cost breakdown
- EnrichedEvaluationResult: Full evaluation result with event trace

All models are immutable (frozen dataclasses) and use integer cents
for money (project invariant INV-1).
"""

from __future__ import annotations

from typing import Any

import pytest


class TestBootstrapEvent:
    """Tests for BootstrapEvent dataclass."""

    def test_is_frozen(self) -> None:
        """BootstrapEvent is immutable (project convention)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
        )

        event = BootstrapEvent(tick=0, event_type="arrival", details={})
        with pytest.raises(AttributeError):
            event.tick = 1  # type: ignore

    def test_stores_all_fields(self) -> None:
        """BootstrapEvent stores tick, type, and details."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
        )

        event = BootstrapEvent(
            tick=5,
            event_type="PolicyDecision",
            details={"action": "release", "tx_id": "tx-001"},
        )
        assert event.tick == 5
        assert event.event_type == "PolicyDecision"
        assert event.details["action"] == "release"
        assert event.details["tx_id"] == "tx-001"

    def test_tick_is_integer(self) -> None:
        """tick is an integer (time is discrete)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
        )

        event = BootstrapEvent(tick=10, event_type="arrival", details={})
        assert isinstance(event.tick, int)


class TestCostBreakdown:
    """Tests for CostBreakdown dataclass."""

    def test_total_property_sums_all_costs(self) -> None:
        """total property returns sum of all cost types."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )

        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        assert breakdown.total == 350

    def test_all_costs_are_integer_cents(self) -> None:
        """All cost values are integers (INV-1: money is always i64)."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )

        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        assert isinstance(breakdown.delay_cost, int)
        assert isinstance(breakdown.overdraft_cost, int)
        assert isinstance(breakdown.deadline_penalty, int)
        assert isinstance(breakdown.eod_penalty, int)
        assert isinstance(breakdown.total, int)

    def test_is_frozen(self) -> None:
        """CostBreakdown is immutable."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )

        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        with pytest.raises(AttributeError):
            breakdown.delay_cost = 200  # type: ignore

    def test_total_with_all_zeros(self) -> None:
        """total returns 0 when all costs are zero."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            CostBreakdown,
        )

        breakdown = CostBreakdown(
            delay_cost=0,
            overdraft_cost=0,
            deadline_penalty=0,
            eod_penalty=0,
        )
        assert breakdown.total == 0


class TestEnrichedEvaluationResult:
    """Tests for EnrichedEvaluationResult dataclass."""

    def test_contains_event_trace(self) -> None:
        """EnrichedEvaluationResult includes event trace for LLM context."""
        from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
            BootstrapEvent,
            CostBreakdown,
            EnrichedEvaluationResult,
        )

        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=42,
            total_cost=1000,
            settlement_rate=0.95,
            avg_delay=2.5,
            event_trace=(
                BootstrapEvent(tick=0, event_type="arrival", details={}),
                BootstrapEvent(tick=1, event_type="settlement", details={}),
            ),
            cost_breakdown=CostBreakdown(
                delay_cost=100, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
            ),
        )
        assert len(result.event_trace) == 2
        assert result.cost_breakdown.total == 100

    def test_is_frozen(self) -> None:
        """EnrichedEvaluationResult is immutable."""
        result = _create_enriched_result(sample_idx=0, total_cost=1000)
        with pytest.raises(AttributeError):
            result.total_cost = 2000  # type: ignore

    def test_total_cost_is_integer(self) -> None:
        """total_cost is integer cents (INV-1)."""
        result = _create_enriched_result(sample_idx=0, total_cost=1000)
        assert isinstance(result.total_cost, int)

    def test_event_trace_is_tuple(self) -> None:
        """event_trace is a tuple (immutable)."""
        result = _create_enriched_result(sample_idx=0, total_cost=1000)
        assert isinstance(result.event_trace, tuple)

    def test_settlement_rate_is_float(self) -> None:
        """settlement_rate is a float between 0 and 1."""
        result = _create_enriched_result(sample_idx=0, total_cost=1000)
        assert isinstance(result.settlement_rate, float)
        assert 0.0 <= result.settlement_rate <= 1.0


def _create_enriched_result(
    sample_idx: int,
    total_cost: int,
    events: list[Any] | None = None,
) -> Any:
    """Create a minimal EnrichedEvaluationResult for testing."""
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
