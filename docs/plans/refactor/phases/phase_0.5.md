# Phase 0.5: Add Event Tracing to Bootstrap Sandbox

**Status:** In Progress
**Created:** 2025-12-10
**Risk:** Medium (modifying core evaluation path)
**Breaking Changes:** None (additive)

---

## Problem Analysis

### Current Context/Evaluation Mismatch

The current system has a critical mismatch between what produces costs and what context the LLM receives:

```
┌─────────────────────────────────────────────────────────────────┐
│  Evaluation Path                   Context Path                 │
│                                                                 │
│  BootstrapSampler                  Full Simulation              │
│       ↓                                 ↓                       │
│  3-Agent Sandbox                   VerboseOutputCapture         │
│       ↓                                 ↓                       │
│  EvaluationResult                  MonteCarloContextBuilder     │
│  (actual costs)                    (placeholder data!)          │
│       ↓                                 ↓                       │
│  Accept/Reject Decision       →    LLM Prompt                   │
│                                                                 │
│  PROBLEM: Context doesn't match what produced the costs!        │
└─────────────────────────────────────────────────────────────────┘
```

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Single Evaluation + Context Path                               │
│                                                                 │
│  BootstrapSampler                                               │
│       ↓                                                         │
│  3-Agent Sandbox (with event capture)                           │
│       ↓                                                         │
│  EnrichedEvaluationResult                                       │
│  ├── total_cost (for accept/reject)                             │
│  ├── event_trace (for LLM context)                              │
│  └── cost_breakdown (for LLM learning)                          │
│       ↓                                                         │
│  BootstrapContextBuilder                                        │
│       ↓                                                         │
│  LLM Prompt (context matches costs!)                            │
│                                                                 │
│  GOAL: Single source of truth for both evaluation and context   │
└─────────────────────────────────────────────────────────────────┘
```

---

## TDD Test Specifications

### Test File 1: `api/tests/ai_cash_mgmt/unit/bootstrap/test_enriched_evaluation.py`

```python
"""Tests for enriched bootstrap evaluation models and methods."""

import pytest
from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
    BootstrapEvent,
    CostBreakdown,
    EnrichedEvaluationResult,
)


class TestBootstrapEvent:
    """Tests for BootstrapEvent dataclass."""

    def test_is_frozen(self) -> None:
        """BootstrapEvent is immutable (project convention)."""
        event = BootstrapEvent(tick=0, event_type="arrival", details={})
        with pytest.raises(AttributeError):
            event.tick = 1  # type: ignore

    def test_stores_all_fields(self) -> None:
        """BootstrapEvent stores tick, type, and details."""
        event = BootstrapEvent(
            tick=5,
            event_type="PolicyDecision",
            details={"action": "release", "tx_id": "tx-001"},
        )
        assert event.tick == 5
        assert event.event_type == "PolicyDecision"
        assert event.details["action"] == "release"


class TestCostBreakdown:
    """Tests for CostBreakdown dataclass."""

    def test_total_property_sums_all_costs(self) -> None:
        """total property returns sum of all cost types."""
        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        assert breakdown.total == 350

    def test_all_costs_are_integer_cents(self) -> None:
        """All cost values are integers (INV-1: money is always i64)."""
        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        assert isinstance(breakdown.delay_cost, int)
        assert isinstance(breakdown.overdraft_cost, int)
        assert isinstance(breakdown.total, int)

    def test_is_frozen(self) -> None:
        """CostBreakdown is immutable."""
        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        with pytest.raises(AttributeError):
            breakdown.delay_cost = 200  # type: ignore


class TestEnrichedEvaluationResult:
    """Tests for EnrichedEvaluationResult dataclass."""

    def test_contains_event_trace(self) -> None:
        """EnrichedEvaluationResult includes event trace for LLM context."""
        result = EnrichedEvaluationResult(
            sample_idx=0,
            seed=42,
            total_cost=1000,
            settlement_rate=0.95,
            avg_delay=2.5,
            event_trace=[
                BootstrapEvent(tick=0, event_type="arrival", details={}),
                BootstrapEvent(tick=1, event_type="settlement", details={}),
            ],
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
```

### Test File 2: `api/tests/experiments/castro/test_bootstrap_context.py`

```python
"""Tests for BootstrapContextBuilder."""

import pytest
from castro.bootstrap_context import BootstrapContextBuilder


class TestBootstrapContextBuilder:
    """Tests for BootstrapContextBuilder."""

    def test_get_best_result_returns_lowest_cost(self) -> None:
        """get_best_result returns result with minimum cost."""
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
        results = [
            _create_enriched_result(sample_idx=0, total_cost=1000),  # Worst
            _create_enriched_result(sample_idx=1, total_cost=500),
            _create_enriched_result(sample_idx=2, total_cost=800),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        worst = builder.get_worst_result()
        assert worst.total_cost == 1000

    def test_format_event_trace_limits_events(self) -> None:
        """format_event_trace_for_llm limits number of events."""
        events = [
            BootstrapEvent(tick=i, event_type="arrival", details={})
            for i in range(100)
        ]
        result = _create_enriched_result(sample_idx=0, total_cost=1000, events=events)
        builder = BootstrapContextBuilder([result], "BANK_A")

        formatted = builder.format_event_trace_for_llm(result, max_events=20)

        # Output should contain at most 20 tick references
        assert formatted.count("tick") <= 20

    def test_build_agent_context_returns_context(self) -> None:
        """build_agent_context returns AgentSimulationContext."""
        results = [_create_enriched_result(sample_idx=0, total_cost=1000)]
        builder = BootstrapContextBuilder(results, "BANK_A")

        context = builder.build_agent_context()

        assert context.mean_cost == 1000
        assert context.best_seed_output is not None
```

---

## Implementation Plan

### Step 0.5.1: Add enriched models

**File:** `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` (NEW)

Create new dataclasses:

```python
@dataclass(frozen=True)
class BootstrapEvent:
    """Event captured during bootstrap evaluation."""
    tick: int
    event_type: str  # "arrival", "decision", "settlement", "cost"
    details: dict[str, Any]


@dataclass(frozen=True)
class CostBreakdown:
    """Breakdown of costs by type (integer cents)."""
    delay_cost: int
    overdraft_cost: int
    deadline_penalty: int
    eod_penalty: int

    @property
    def total(self) -> int:
        return self.delay_cost + self.overdraft_cost + self.deadline_penalty + self.eod_penalty


@dataclass(frozen=True)
class EnrichedEvaluationResult:
    """Evaluation result with context for LLM prompts."""
    sample_idx: int
    seed: int
    total_cost: int  # Integer cents (INV-1)
    settlement_rate: float
    avg_delay: float
    event_trace: tuple[BootstrapEvent, ...]  # Use tuple for immutability
    cost_breakdown: CostBreakdown
```

### Step 0.5.2: Add evaluate_sample_enriched method

**File:** `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py`

Add new method to `BootstrapPolicyEvaluator`:

```python
def evaluate_sample_enriched(
    self,
    sample: BootstrapSample,
    policy: dict[str, Any],
) -> EnrichedEvaluationResult:
    """Evaluate with full event capture for LLM context.

    Like evaluate_sample() but also captures event trace and
    cost breakdown for building LLM prompts.
    """
    # Build and run sandbox
    config = self._config_builder.build_config(...)
    ffi_config = config.to_ffi_dict()
    orchestrator = Orchestrator.new(ffi_config)

    # Run with event capture
    events: list[BootstrapEvent] = []
    for tick in range(sample.total_ticks):
        orchestrator.tick()
        tick_events = orchestrator.get_tick_events(tick)
        for event in tick_events:
            if self._is_relevant_event(event, sample.agent_id):
                events.append(self._convert_to_bootstrap_event(event))

    # Extract metrics
    metrics = self._extract_agent_metrics(orchestrator, sample.agent_id)
    cost_breakdown = self._extract_cost_breakdown(orchestrator, sample.agent_id)

    return EnrichedEvaluationResult(
        sample_idx=sample.sample_idx,
        seed=sample.seed,
        total_cost=int(metrics["total_cost"]),
        settlement_rate=float(metrics["settlement_rate"]),
        avg_delay=float(metrics["avg_delay"]),
        event_trace=tuple(events),
        cost_breakdown=cost_breakdown,
    )
```

Add helper methods:

```python
def _is_relevant_event(self, event: dict[str, Any], agent_id: str) -> bool:
    """Filter for events relevant to the target agent."""
    relevant_types = {
        "Arrival", "PolicyDecision", "RtgsImmediateSettlement",
        "Queue2LiquidityRelease", "DelayCostAccrual", "OverdraftCostAccrual",
    }
    if event.get("event_type") not in relevant_types:
        return False
    return (
        event.get("sender_id") == agent_id
        or event.get("receiver_id") == agent_id
        or event.get("agent_id") == agent_id
    )

def _convert_to_bootstrap_event(self, event: dict[str, Any]) -> BootstrapEvent:
    """Convert FFI event dict to BootstrapEvent."""
    return BootstrapEvent(
        tick=event.get("tick", 0),
        event_type=event.get("event_type", "unknown"),
        details={k: v for k, v in event.items() if k not in ("tick", "event_type")},
    )

def _extract_cost_breakdown(
    self,
    orchestrator: Orchestrator,
    agent_id: str,
) -> CostBreakdown:
    """Extract cost breakdown from completed simulation."""
    try:
        costs = orchestrator.get_agent_accumulated_costs(agent_id)
        return CostBreakdown(
            delay_cost=int(costs.get("delay_cost", 0)),
            overdraft_cost=int(costs.get("overdraft_cost", 0)),
            deadline_penalty=int(costs.get("deadline_penalty", 0)),
            eod_penalty=int(costs.get("eod_penalty", 0)),
        )
    except Exception:
        return CostBreakdown(
            delay_cost=0, overdraft_cost=0, deadline_penalty=0, eod_penalty=0
        )
```

### Step 0.5.3: Create BootstrapContextBuilder

**File:** `experiments/castro/castro/bootstrap_context.py` (NEW)

```python
"""Bootstrap-native context builder for LLM prompts."""

from __future__ import annotations

import statistics
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.enriched_models import (
        BootstrapEvent,
        EnrichedEvaluationResult,
    )
    from payment_simulator.ai_cash_mgmt.prompts.context import AgentSimulationContext


class BootstrapContextBuilder:
    """Builds LLM context directly from enriched bootstrap results."""

    def __init__(
        self,
        results: list[EnrichedEvaluationResult],
        agent_id: str,
    ) -> None:
        self._results = results
        self._agent_id = agent_id

    def get_best_result(self) -> EnrichedEvaluationResult:
        """Get result with lowest cost."""
        return min(self._results, key=lambda r: r.total_cost)

    def get_worst_result(self) -> EnrichedEvaluationResult:
        """Get result with highest cost."""
        return max(self._results, key=lambda r: r.total_cost)

    def format_event_trace_for_llm(
        self,
        result: EnrichedEvaluationResult,
        max_events: int = 50,
    ) -> str:
        """Format event trace for LLM prompt."""
        # Prioritize informative events
        events = sorted(
            result.event_trace,
            key=lambda e: self._event_priority(e),
            reverse=True,
        )[:max_events]

        # Sort chronologically
        events = sorted(events, key=lambda e: e.tick)
        return self._format_events(events)

    def build_agent_context(self) -> AgentSimulationContext:
        """Build context compatible with existing prompt system."""
        costs = [r.total_cost for r in self._results]
        mean_cost = int(statistics.mean(costs))
        std_cost = int(statistics.stdev(costs)) if len(costs) > 1 else 0

        best = self.get_best_result()
        worst = self.get_worst_result()

        return AgentSimulationContext(
            mean_cost=mean_cost,
            cost_std=std_cost,
            best_seed=best.seed,
            worst_seed=worst.seed,
            best_seed_cost=best.total_cost,
            worst_seed_cost=worst.total_cost,
            best_seed_output=self.format_event_trace_for_llm(best),
            worst_seed_output=self.format_event_trace_for_llm(worst),
        )
```

### Step 0.5.4: Update runner.py (Optional - can defer)

This step can be deferred as Phase 0.5 is additive and doesn't break existing functionality.

---

## Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` | New dataclasses |
| `experiments/castro/castro/bootstrap_context.py` | Bootstrap-native context builder |
| `api/tests/ai_cash_mgmt/unit/bootstrap/test_enriched_evaluation.py` | Model tests |
| `api/tests/experiments/castro/test_bootstrap_context.py` | Context builder tests |

## Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` | Add `evaluate_sample_enriched()` |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/__init__.py` | Export new models |

---

## Verification Checklist

### Unit Tests
- [ ] `test_bootstrap_event_is_frozen` passes
- [ ] `test_cost_breakdown_total_sums_all_costs` passes
- [ ] `test_all_costs_are_integer_cents` passes
- [ ] `test_enriched_result_contains_event_trace` passes
- [ ] `test_get_best_result_returns_lowest_cost` passes
- [ ] `test_format_event_trace_limits_events` passes

### Integration Tests
```bash
cd api && uv run pytest tests/ai_cash_mgmt/unit/bootstrap/ -v
cd api && uv run pytest tests/experiments/castro/ -v
```

### Type Checking
```bash
cd api && uv run mypy payment_simulator/ai_cash_mgmt/bootstrap/
```

---

## Notes

### Why This Phase Matters

1. **LLM Context Accuracy**: The LLM currently receives context from full simulation that doesn't match the bootstrap evaluation. This means the LLM is optimizing based on misleading information.

2. **Cost Attribution**: The `CostBreakdown` allows the LLM to understand which cost types are contributing most to the total cost, enabling more targeted policy improvements.

3. **Event Trace**: The event trace shows the LLM what actually happened during evaluation, helping it understand cause-and-effect relationships between policy decisions and costs.

### Design Decisions

1. **Separate `enriched_models.py` file**: Keep new models separate from existing `models.py` to avoid modifying existing import paths.

2. **Immutable dataclasses**: All new models use `frozen=True` to match project conventions and ensure thread safety.

3. **Optional integration with runner**: The enriched evaluation is additive - existing evaluation path continues to work, and we can gradually migrate to enriched evaluation.

---

*Phase 0.5 Plan v1.0 - 2025-12-10*
