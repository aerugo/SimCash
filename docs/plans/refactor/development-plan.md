# AI Cash Management Architecture Refactor - Development Plan

**Status:** Draft
**Created:** 2025-12-10
**Last Updated:** 2025-12-10
**Author:** Claude
**Related:**
- [Conceptual Plan](./conceptual-plan.md) - Architecture overview
- [Work Notes](./work_notes.md) - Progress tracking

---

## Overview

This document provides the phase-by-phase implementation plan for the AI Cash Management architecture refactor. Each phase includes:

- **Objectives**: What we're trying to achieve
- **TDD Tests**: Tests to write FIRST (TDD principle)
- **Implementation**: Code to write
- **Verification**: How to confirm success
- **Files**: Specific files to create/modify/delete

---

## Phase 0: Fix Bootstrap Paired Comparison Bug (Critical)

**Duration**: 1 day
**Risk**: Low (contained change)
**Breaking Changes**: None (bug fix)

### Problem Analysis

**Current behavior** (BROKEN):
```
Iteration N:
  1. Generate samples S1
  2. Evaluate old_policy on S1 → cost_old
  3. LLM proposes new_policy
  4. Generate samples S2 (DIFFERENT!)
  5. Evaluate new_policy on S2 → cost_new
  6. Accept if cost_new < cost_old
```

**Expected behavior** (CORRECT):
```
Iteration N:
  1. Generate samples S
  2. LLM proposes new_policy
  3. For each sample in S:
     - Evaluate old_policy → cost_old_i
     - Evaluate new_policy → cost_new_i
     - delta_i = cost_new_i - cost_old_i
  4. Accept if mean(delta) < 0
```

**Impact**: The `compute_paired_deltas()` method EXISTS in `BootstrapPolicyEvaluator` but is NEVER called!

### TDD Tests

```python
# tests/experiments/castro/test_bootstrap_paired_comparison.py
"""Tests for paired comparison bug fix."""

import pytest
from unittest.mock import MagicMock


class TestPairedComparison:
    """Tests verifying paired comparison is used."""

    def test_same_samples_used_for_old_and_new_policy(self) -> None:
        """Same bootstrap samples must be used for both policies."""
        # Setup: Create evaluator with deterministic seed
        evaluator = create_test_evaluator(seed=42)

        # Generate samples once
        samples = evaluator.generate_samples(agent_id="BANK_A")

        # Evaluate OLD policy on samples
        old_results = [evaluator.evaluate_sample(s, old_policy) for s in samples]

        # Evaluate NEW policy on SAME samples
        new_results = [evaluator.evaluate_sample(s, new_policy) for s in samples]

        # Verify: sample indices match
        for old, new in zip(old_results, new_results):
            assert old.sample_idx == new.sample_idx
            assert old.seed == new.seed

    def test_acceptance_based_on_paired_delta(self) -> None:
        """Policy acceptance must use paired delta, not absolute costs."""
        # Setup: Mock evaluator where new policy is better on SAME samples
        evaluator = MockEvaluator()
        evaluator.set_paired_results([
            # sample_idx, old_cost, new_cost
            (0, 1000, 900),   # delta = -100 (improvement)
            (1, 1200, 1100),  # delta = -100 (improvement)
            (2, 800, 850),    # delta = +50 (regression)
        ])

        comparison = evaluator.compare(old_policy, new_policy, "BANK_A")

        # Mean delta = (-100 + -100 + 50) / 3 = -50 (improvement)
        assert comparison.delta < 0
        assert comparison.should_accept is True

    def test_compute_paired_deltas_is_called(self) -> None:
        """Verify compute_paired_deltas is actually called during optimization."""
        runner = create_test_runner()
        runner._bootstrap_evaluator = MagicMock()

        # Run one optimization iteration
        asyncio.run(runner._optimize_agent("BANK_A", samples))

        # Verify paired comparison was used
        runner._bootstrap_evaluator.compute_paired_deltas.assert_called_once()
```

### Implementation

**Changes to `experiments/castro/castro/runner.py`**:

```python
# In _evaluate_policies(), return samples for reuse
async def _evaluate_policies(
    self,
    iteration: int,
    ...
) -> tuple[int, dict[str, int], dict[str, Any], list[dict], list[BootstrapSample]]:
    """Evaluate policies and return samples for paired comparison."""
    samples = self._bootstrap_sampler.generate_samples(...)
    results = self._bootstrap_evaluator.evaluate_samples(samples, policy)
    return total_cost, per_agent_costs, context, seed_results, samples

# In optimization loop - use SAME samples for comparison
async def _run_iteration(self, iteration: int) -> None:
    # First evaluation with current policy - CAPTURE SAMPLES
    total_cost, per_agent_costs, context, seed_results, samples = (
        await self._evaluate_policies(iteration, ...)
    )

    # For each agent optimization
    for agent_id in self._experiment.optimized_agents:
        old_policy = self._policies[agent_id]

        # Get LLM proposal
        result = await self._optimize_agent(agent_id, context[agent_id])

        if result.was_accepted and result.new_policy:
            # CRITICAL: Use SAME samples for paired comparison
            deltas = self._bootstrap_evaluator.compute_paired_deltas(
                samples=samples,
                policy_a=old_policy,
                policy_b=result.new_policy,
                agent_id=agent_id,
            )
            mean_delta = sum(deltas) / len(deltas)

            if mean_delta < 0:  # New policy is better
                self._policies[agent_id] = result.new_policy
                self._log_acceptance(agent_id, mean_delta)
            else:
                self._log_rejection(agent_id, mean_delta)
```

### Files to Modify

| File | Change |
|------|--------|
| `experiments/castro/castro/runner.py` | Store and reuse bootstrap samples |
| `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` | Ensure `compute_paired_deltas()` works correctly |

### Verification

```bash
# Run specific test
cd api && .venv/bin/python -m pytest tests/experiments/castro/test_bootstrap_paired_comparison.py -v

# Run full Castro test suite
cd experiments/castro && python -m pytest tests/ -v

# Manual verification: Run experiment and check logs show paired deltas
castro run exp1 --verbose-monte-carlo
```

---

## Phase 0.5: Add Event Tracing to Bootstrap Sandbox

**Duration**: 2-3 days
**Risk**: Medium (modifying core evaluation path)
**Breaking Changes**: None (additive)

### Problem Analysis

**Current Context/Evaluation Mismatch**:
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

**Target Architecture**:
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

### TDD Tests

```python
# tests/ai_cash_mgmt/bootstrap/test_enriched_evaluation.py
"""Tests for enriched bootstrap evaluation."""

import pytest
from payment_simulator.ai_cash_mgmt.bootstrap.models import (
    BootstrapEvent,
    CostBreakdown,
    EnrichedEvaluationResult,
)


class TestBootstrapEvent:
    """Tests for BootstrapEvent dataclass."""

    def test_is_frozen(self) -> None:
        """BootstrapEvent is immutable."""
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
        """All cost values are integers (INV-1)."""
        breakdown = CostBreakdown(
            delay_cost=100,
            overdraft_cost=50,
            deadline_penalty=200,
            eod_penalty=0,
        )
        assert isinstance(breakdown.delay_cost, int)
        assert isinstance(breakdown.overdraft_cost, int)
        assert isinstance(breakdown.total, int)


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


# tests/experiments/castro/test_bootstrap_context.py
"""Tests for BootstrapContextBuilder."""

from castro.bootstrap_context import BootstrapContextBuilder


class TestBootstrapContextBuilder:
    """Tests for BootstrapContextBuilder."""

    def test_get_best_result_returns_lowest_cost(self) -> None:
        """get_best_result returns result with minimum cost."""
        results = [
            create_result(sample_idx=0, total_cost=1000),
            create_result(sample_idx=1, total_cost=500),  # Best
            create_result(sample_idx=2, total_cost=800),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        best = builder.get_best_result()
        assert best.total_cost == 500
        assert best.sample_idx == 1

    def test_get_worst_result_returns_highest_cost(self) -> None:
        """get_worst_result returns result with maximum cost."""
        results = [
            create_result(sample_idx=0, total_cost=1000),  # Worst
            create_result(sample_idx=1, total_cost=500),
            create_result(sample_idx=2, total_cost=800),
        ]
        builder = BootstrapContextBuilder(results, "BANK_A")

        worst = builder.get_worst_result()
        assert worst.total_cost == 1000

    def test_format_event_trace_limits_events(self) -> None:
        """format_event_trace_for_llm limits number of events."""
        result = create_result_with_many_events(100)
        builder = BootstrapContextBuilder([result], "BANK_A")

        formatted = builder.format_event_trace_for_llm(result, max_events=20)

        # Should be limited to 20 events
        assert formatted.count("tick") <= 20
```

### Implementation

**Step 0.5.1: Add enriched models**

```python
# api/payment_simulator/ai_cash_mgmt/bootstrap/models.py

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BootstrapEvent:
    """Event captured during bootstrap evaluation.

    Minimal format optimized for LLM consumption.
    All monetary values in integer cents (INV-1).
    """
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
    event_trace: list[BootstrapEvent]
    cost_breakdown: CostBreakdown
```

**Step 0.5.2: Add evaluate_sample_enriched method**

```python
# api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py

def evaluate_sample_enriched(
    self,
    sample: BootstrapSample,
    policy: dict[str, Any],
) -> EnrichedEvaluationResult:
    """Evaluate with full event capture for LLM context."""
    # Build and run sandbox
    config = self._config_builder.build_config(sample, policy, ...)
    ffi_config = config.to_ffi_dict()
    orchestrator = Orchestrator.new(ffi_config)

    # Run with event capture
    events: list[BootstrapEvent] = []
    for tick in range(sample.total_ticks):
        orchestrator.tick()

        # Capture relevant events from this tick
        tick_events = orchestrator.get_tick_events(tick)
        for event in tick_events:
            if self._is_relevant_event(event, sample.agent_id):
                events.append(self._convert_to_bootstrap_event(event))

    # Extract metrics and cost breakdown
    metrics = self._extract_agent_metrics(orchestrator, sample.agent_id)
    cost_breakdown = self._extract_cost_breakdown(orchestrator, sample.agent_id)

    return EnrichedEvaluationResult(
        sample_idx=sample.sample_idx,
        seed=sample.seed,
        total_cost=int(metrics["total_cost"]),
        settlement_rate=float(metrics["settlement_rate"]),
        avg_delay=float(metrics["avg_delay"]),
        event_trace=events,
        cost_breakdown=cost_breakdown,
    )

def _is_relevant_event(self, event: dict, agent_id: str) -> bool:
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

def _convert_to_bootstrap_event(self, event: dict) -> BootstrapEvent:
    """Convert FFI event dict to BootstrapEvent."""
    return BootstrapEvent(
        tick=event.get("tick", 0),
        event_type=event.get("event_type", "unknown"),
        details={k: v for k, v in event.items() if k not in ("tick", "event_type")},
    )
```

**Step 0.5.3: Create BootstrapContextBuilder**

```python
# experiments/castro/castro/bootstrap_context.py
"""Bootstrap-native context builder for LLM prompts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from payment_simulator.ai_cash_mgmt.bootstrap.models import (
        BootstrapEvent,
        EnrichedEvaluationResult,
    )
    from payment_simulator.ai_cash_mgmt.prompts.context import AgentSimulationContext


class BootstrapContextBuilder:
    """Builds LLM context directly from enriched bootstrap results.

    Unlike MonteCarloContextBuilder, works natively with bootstrap
    evaluation results - no adapters or placeholder data.
    """

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
        """Format event trace for LLM prompt.

        Filters to most informative events:
        - Policy decisions (shows decision points)
        - High-cost events (shows what to optimize)
        - Settlement failures (shows problems)
        """
        # Prioritize events by informativeness
        events = sorted(
            result.event_trace,
            key=lambda e: self._event_priority(e),
            reverse=True,
        )[:max_events]

        # Sort by tick for chronological presentation
        events = sorted(events, key=lambda e: e.tick)

        return self._format_events(events)

    def _event_priority(self, event: BootstrapEvent) -> int:
        """Score event by informativeness for LLM."""
        priority_map = {
            "PolicyDecision": 100,
            "DelayCostAccrual": 80,
            "OverdraftCostAccrual": 90,
            "RtgsImmediateSettlement": 50,
            "Queue2LiquidityRelease": 60,
            "Arrival": 30,
        }
        return priority_map.get(event.event_type, 10)

    def _format_events(self, events: list[BootstrapEvent]) -> str:
        """Format events as readable text."""
        lines = []
        for event in events:
            lines.append(f"Tick {event.tick}: {event.event_type}")
            for key, value in event.details.items():
                if key in ("amount", "cost"):
                    lines.append(f"  {key}: ${value / 100:.2f}")
                else:
                    lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    def build_agent_context(self) -> AgentSimulationContext:
        """Build context matching SingleAgentContext format."""
        from payment_simulator.ai_cash_mgmt.prompts.context import AgentSimulationContext
        import statistics

        best = self.get_best_result()
        worst = self.get_worst_result()
        costs = [r.total_cost for r in self._results]

        return AgentSimulationContext(
            agent_id=self._agent_id,
            best_seed=best.seed,
            best_seed_cost=best.total_cost,
            best_seed_output=self.format_event_trace_for_llm(best),
            worst_seed=worst.seed,
            worst_seed_cost=worst.total_cost,
            worst_seed_output=self.format_event_trace_for_llm(worst),
            mean_cost=int(statistics.mean(costs)),
            cost_std=int(statistics.stdev(costs)) if len(costs) > 1 else 0,
        )
```

**Step 0.5.4: Update runner to use enriched evaluation**

```python
# experiments/castro/castro/runner.py

async def _evaluate_policies(
    self,
    iteration: int,
) -> tuple[int, dict[str, int], dict[str, BootstrapContextBuilder], list[BootstrapSample]]:
    """Evaluate using enriched bootstrap results.

    Returns context builders per agent that have REAL event data,
    not placeholder SimulationResults.
    """
    all_results: dict[str, list[EnrichedEvaluationResult]] = {}
    all_samples: dict[str, list[BootstrapSample]] = {}

    for agent_id in self._experiment.optimized_agents:
        samples = self._bootstrap_sampler.generate_samples(agent_id, ...)
        all_samples[agent_id] = samples

        # Use enriched evaluation
        results = [
            self._bootstrap_evaluator.evaluate_sample_enriched(
                sample, self._policies[agent_id]
            )
            for sample in samples
        ]
        all_results[agent_id] = results

    # Build context builders with REAL data
    context_builders = {
        agent_id: BootstrapContextBuilder(results, agent_id)
        for agent_id, results in all_results.items()
    }

    # Compute costs
    total_cost = sum(
        sum(r.total_cost for r in results) // len(results)
        for results in all_results.values()
    )
    per_agent_costs = {
        agent_id: sum(r.total_cost for r in results) // len(results)
        for agent_id, results in all_results.items()
    }

    # Return samples for paired comparison (Phase 0)
    samples_list = list(all_samples.values())[0]
    return total_cost, per_agent_costs, context_builders, samples_list
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/models.py` | `BootstrapEvent`, `CostBreakdown`, `EnrichedEvaluationResult` |
| `experiments/castro/castro/bootstrap_context.py` | `BootstrapContextBuilder` |
| `api/tests/ai_cash_mgmt/bootstrap/test_enriched_evaluation.py` | Tests for enriched models |
| `api/tests/experiments/castro/test_bootstrap_context.py` | Tests for context builder |

### Files to Modify

| File | Change |
|------|--------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py` | Add `evaluate_sample_enriched()` |
| `experiments/castro/castro/runner.py` | Use enriched evaluation and `BootstrapContextBuilder` |

### Files to Deprecate (Later)

| File | Reason |
|------|--------|
| `experiments/castro/castro/context_builder.py` | Replaced by `bootstrap_context.py` |

### Verification

```bash
# Run enriched evaluation tests
cd api && .venv/bin/python -m pytest tests/ai_cash_mgmt/bootstrap/test_enriched_evaluation.py -v

# Run context builder tests
cd experiments/castro && python -m pytest tests/test_bootstrap_context.py -v

# Manual verification: Check LLM receives real event data
castro run exp1 --verbose-llm
```

---

## Phase 1: Preparation (Pre-Refactor)

**Duration**: 1-2 days
**Risk**: Low
**Breaking Changes**: None

### Objectives

1. Create directory structure for new modules
2. Define protocol interfaces (no implementation)
3. Add comprehensive test fixtures
4. Ensure all existing tests pass

### TDD Tests

```python
# tests/llm/test_protocol.py
"""Tests for LLM protocol - write FIRST, will fail until implemented."""

from payment_simulator.llm.protocol import LLMClientProtocol

def test_llm_client_protocol_has_generate_structured_output():
    """LLMClientProtocol defines generate_structured_output method."""
    assert hasattr(LLMClientProtocol, "generate_structured_output")

def test_llm_client_protocol_has_generate_text():
    """LLMClientProtocol defines generate_text method."""
    assert hasattr(LLMClientProtocol, "generate_text")


# tests/experiments/config/test_experiment_config.py
"""Tests for experiment config loading."""

def test_experiment_config_from_yaml_loads_required_fields():
    """ExperimentConfig.from_yaml loads all required fields."""
    # This test will fail until ExperimentConfig is implemented
    pass  # Placeholder - implement in Phase 2


# tests/fixtures/experiments/test_experiment.yaml
# Create test fixture YAML files for testing
```

### Implementation

1. **Create directory structure**:
```bash
mkdir -p api/payment_simulator/llm
mkdir -p api/payment_simulator/experiments/{config,runner,persistence,orchestrator}
mkdir -p api/tests/llm
mkdir -p api/tests/experiments/{config,runner,persistence}
mkdir -p experiments/castro/experiments
mkdir -p api/tests/fixtures/experiments
```

2. **Create empty `__init__.py` files**

3. **Create protocol stubs**:
```python
# api/payment_simulator/llm/__init__.py
"""LLM integration layer."""

# api/payment_simulator/llm/protocol.py
"""LLM client protocol definitions."""

from typing import Protocol, TypeVar

T = TypeVar("T")

class LLMClientProtocol(Protocol):
    """Protocol for LLM clients."""

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM."""
        ...

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM."""
        ...
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/llm/__init__.py` | LLM module init |
| `api/payment_simulator/llm/protocol.py` | Protocol definitions |
| `api/payment_simulator/experiments/__init__.py` | Experiments module init |
| `api/payment_simulator/experiments/config/__init__.py` | Config submodule |
| `api/payment_simulator/experiments/runner/__init__.py` | Runner submodule |
| `api/payment_simulator/experiments/persistence/__init__.py` | Persistence submodule |
| `api/payment_simulator/experiments/orchestrator/__init__.py` | Orchestrator submodule |
| `api/tests/llm/__init__.py` | LLM tests init |
| `api/tests/llm/test_protocol.py` | Protocol tests |
| `api/tests/experiments/__init__.py` | Experiments tests init |
| `api/tests/fixtures/experiments/test_experiment.yaml` | Test fixture |

### Verification

```bash
# All existing tests pass
cd api && .venv/bin/python -m pytest

# New test file exists (tests will fail - expected)
.venv/bin/python -m pytest tests/llm/test_protocol.py -v

# Imports work
.venv/bin/python -c "from payment_simulator.llm.protocol import LLMClientProtocol"
```

---

## Phase 2: LLM Module Extraction

**Duration**: 2-3 days
**Risk**: Medium
**Breaking Changes**: None (parallel implementation)

### Objectives

1. Create unified LLM configuration (`LLMConfig`)
2. Move `PydanticAILLMClient` to new module
3. Create `AuditCaptureLLMClient` wrapper
4. Add Castro adapter to use new module

### TDD Tests

```python
# tests/llm/test_config.py
"""Tests for LLMConfig."""

import pytest
from payment_simulator.llm.config import LLMConfig


class TestLLMConfig:
    """Tests for LLMConfig dataclass."""

    def test_creates_with_model_string(self) -> None:
        """LLMConfig creates from provider:model string."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.model == "anthropic:claude-sonnet-4-5"

    def test_provider_property_extracts_provider(self) -> None:
        """provider property extracts provider from model string."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.provider == "anthropic"

    def test_model_name_property_extracts_model(self) -> None:
        """model_name property extracts model from string."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        assert config.model_name == "claude-sonnet-4-5"

    def test_defaults_temperature_to_zero(self) -> None:
        """Default temperature is 0.0 for determinism."""
        config = LLMConfig(model="openai:gpt-4o")
        assert config.temperature == 0.0

    def test_anthropic_thinking_budget(self) -> None:
        """Anthropic models support thinking_budget."""
        config = LLMConfig(
            model="anthropic:claude-sonnet-4-5",
            thinking_budget=8000,
        )
        assert config.thinking_budget == 8000

    def test_openai_reasoning_effort(self) -> None:
        """OpenAI models support reasoning_effort."""
        config = LLMConfig(
            model="openai:o1",
            reasoning_effort="high",
        )
        assert config.reasoning_effort == "high"


# tests/llm/test_pydantic_client.py
"""Tests for PydanticAI LLM client."""

import pytest
from pydantic import BaseModel
from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.pydantic_client import PydanticAILLMClient


class PolicyOutput(BaseModel):
    """Test response model."""
    policy_id: str
    parameters: dict[str, float]


class TestPydanticAILLMClient:
    """Tests for PydanticAILLMClient."""

    def test_creates_with_config(self) -> None:
        """Client creates with LLMConfig."""
        config = LLMConfig(model="anthropic:claude-sonnet-4-5")
        client = PydanticAILLMClient(config)
        assert client._config == config

    @pytest.mark.asyncio
    async def test_generate_structured_output_returns_model(self) -> None:
        """generate_structured_output returns parsed model."""
        # This test requires mocking - skip in unit tests, cover in integration
        pytest.skip("Requires LLM mock or integration test")


# tests/llm/test_audit_wrapper.py
"""Tests for audit capture wrapper."""

import pytest
from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)
from payment_simulator.llm.protocol import LLMClientProtocol


class MockLLMClient:
    """Mock LLM client for testing."""

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        return f"Response to: {prompt}"

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type,
        system_prompt: str | None = None,
    ) -> object:
        return response_model()


class TestAuditCaptureLLMClient:
    """Tests for AuditCaptureLLMClient."""

    def test_wraps_delegate_client(self) -> None:
        """Wrapper wraps a delegate client."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper._delegate is mock

    def test_get_last_interaction_returns_none_initially(self) -> None:
        """get_last_interaction returns None before any calls."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)
        assert wrapper.get_last_interaction() is None

    @pytest.mark.asyncio
    async def test_captures_text_interaction(self) -> None:
        """Captures interaction from generate_text call."""
        mock = MockLLMClient()
        wrapper = AuditCaptureLLMClient(mock)

        await wrapper.generate_text("test prompt", "system prompt")

        interaction = wrapper.get_last_interaction()
        assert interaction is not None
        assert interaction.user_prompt == "test prompt"
        assert interaction.system_prompt == "system prompt"


class TestLLMInteraction:
    """Tests for LLMInteraction dataclass."""

    def test_is_frozen(self) -> None:
        """LLMInteraction is immutable (frozen)."""
        interaction = LLMInteraction(
            system_prompt="sys",
            user_prompt="user",
            raw_response="response",
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=100,
            completion_tokens=50,
            latency_seconds=1.5,
        )
        with pytest.raises(AttributeError):
            interaction.user_prompt = "modified"  # type: ignore
```

### Implementation

1. **Create LLMConfig**:

```python
# api/payment_simulator/llm/config.py
"""Unified LLM configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Unified LLM configuration.

    Supports multiple LLM providers with provider-specific options.

    Example:
        >>> config = LLMConfig(
        ...     model="anthropic:claude-sonnet-4-5",
        ...     thinking_budget=8000,
        ... )
        >>> config.provider
        'anthropic'
        >>> config.model_name
        'claude-sonnet-4-5'
    """

    # Model specification in provider:model format
    model: str

    # Common settings
    temperature: float = 0.0
    max_retries: int = 3
    timeout_seconds: int = 120

    # Provider-specific (mutually exclusive)
    thinking_budget: int | None = None  # Anthropic extended thinking
    reasoning_effort: str | None = None  # OpenAI: low, medium, high

    @property
    def provider(self) -> str:
        """Extract provider from model string."""
        return self.model.split(":")[0]

    @property
    def model_name(self) -> str:
        """Extract model name from model string."""
        return self.model.split(":", 1)[1]
```

2. **Move PydanticAILLMClient** (copy from castro, adapt):

```python
# api/payment_simulator/llm/pydantic_client.py
"""PydanticAI-based LLM client implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from pydantic_ai import Agent

from payment_simulator.llm.config import LLMConfig

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T", bound="BaseModel")


class PydanticAILLMClient:
    """LLM client using PydanticAI for structured output.

    Implements LLMClientProtocol.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize with configuration."""
        self._config = config

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output from LLM."""
        agent = Agent(
            model=self._config.model,
            result_type=response_model,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate plain text from LLM."""
        agent = Agent(
            model=self._config.model,
            result_type=str,
            system_prompt=system_prompt or "",
        )
        result = await agent.run(prompt)
        return result.data
```

3. **Create AuditCaptureLLMClient**:

```python
# api/payment_simulator/llm/audit_wrapper.py
"""Audit capture wrapper for LLM clients."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

    from payment_simulator.llm.protocol import LLMClientProtocol

T = TypeVar("T", bound="BaseModel")


@dataclass(frozen=True)
class LLMInteraction:
    """Captured LLM interaction for audit trail.

    Immutable record of a single LLM interaction.
    """

    system_prompt: str
    user_prompt: str
    raw_response: str
    parsed_policy: dict[str, Any] | None
    parsing_error: str | None
    prompt_tokens: int
    completion_tokens: int
    latency_seconds: float


class AuditCaptureLLMClient:
    """Wrapper that captures interactions for audit replay.

    Wraps any LLMClientProtocol implementation and captures
    all interactions for later replay.

    Example:
        >>> base_client = PydanticAILLMClient(config)
        >>> audit_client = AuditCaptureLLMClient(base_client)
        >>> result = await audit_client.generate_text("prompt")
        >>> interaction = audit_client.get_last_interaction()
        >>> interaction.user_prompt
        'prompt'
    """

    def __init__(self, delegate: LLMClientProtocol) -> None:
        """Initialize with delegate client."""
        self._delegate = delegate
        self._last_interaction: LLMInteraction | None = None

    def get_last_interaction(self) -> LLMInteraction | None:
        """Get the most recent interaction."""
        return self._last_interaction

    async def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str:
        """Generate text and capture interaction."""
        start = time.perf_counter()
        result = await self._delegate.generate_text(prompt, system_prompt)
        latency = time.perf_counter() - start

        self._last_interaction = LLMInteraction(
            system_prompt=system_prompt or "",
            user_prompt=prompt,
            raw_response=result,
            parsed_policy=None,
            parsing_error=None,
            prompt_tokens=0,  # Not available from base client
            completion_tokens=0,
            latency_seconds=latency,
        )

        return result

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type[T],
        system_prompt: str | None = None,
    ) -> T:
        """Generate structured output and capture interaction."""
        start = time.perf_counter()
        try:
            result = await self._delegate.generate_structured_output(
                prompt, response_model, system_prompt
            )
            latency = time.perf_counter() - start

            # Try to extract dict representation
            parsed: dict[str, Any] | None = None
            if hasattr(result, "model_dump"):
                parsed = result.model_dump()
            elif hasattr(result, "__dict__"):
                parsed = result.__dict__

            self._last_interaction = LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response=str(result),
                parsed_policy=parsed,
                parsing_error=None,
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
            )

            return result

        except Exception as e:
            latency = time.perf_counter() - start
            self._last_interaction = LLMInteraction(
                system_prompt=system_prompt or "",
                user_prompt=prompt,
                raw_response="",
                parsed_policy=None,
                parsing_error=str(e),
                prompt_tokens=0,
                completion_tokens=0,
                latency_seconds=latency,
            )
            raise
```

4. **Update module `__init__.py`**:

```python
# api/payment_simulator/llm/__init__.py
"""LLM integration layer.

This module provides unified LLM abstraction for all modules
needing LLM capabilities.

Example:
    >>> from payment_simulator.llm import LLMConfig, PydanticAILLMClient
    >>> config = LLMConfig(model="anthropic:claude-sonnet-4-5")
    >>> client = PydanticAILLMClient(config)
"""

from payment_simulator.llm.audit_wrapper import (
    AuditCaptureLLMClient,
    LLMInteraction,
)
from payment_simulator.llm.config import LLMConfig
from payment_simulator.llm.protocol import LLMClientProtocol
from payment_simulator.llm.pydantic_client import PydanticAILLMClient

__all__ = [
    "LLMClientProtocol",
    "LLMConfig",
    "PydanticAILLMClient",
    "AuditCaptureLLMClient",
    "LLMInteraction",
]
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/llm/config.py` | LLMConfig dataclass |
| `api/payment_simulator/llm/pydantic_client.py` | PydanticAI implementation |
| `api/payment_simulator/llm/audit_wrapper.py` | Audit capture wrapper |
| `api/tests/llm/test_config.py` | Config tests |
| `api/tests/llm/test_pydantic_client.py` | Client tests |
| `api/tests/llm/test_audit_wrapper.py` | Wrapper tests |

### Files to Modify (Later)

| File | Change |
|------|--------|
| `experiments/castro/castro/runner.py` | Import from `payment_simulator.llm` |

### Verification

```bash
# All LLM module tests pass
cd api && .venv/bin/python -m pytest tests/llm/ -v

# Type checking passes
.venv/bin/python -m mypy payment_simulator/llm/

# Imports work
.venv/bin/python -c "from payment_simulator.llm import LLMConfig, PydanticAILLMClient"
```

---

## Phase 3: Experiment Configuration Framework

**Duration**: 2-3 days
**Risk**: Medium
**Breaking Changes**: None (new code)

### Objectives

1. Create `ExperimentConfig` YAML loader
2. Create `EvaluationConfig` for bootstrap/deterministic settings
3. Create experiment YAML schema
4. Add validation for experiment configs

### TDD Tests

```python
# tests/experiments/config/test_experiment_config.py
"""Tests for ExperimentConfig YAML loading."""

from pathlib import Path

import pytest

from payment_simulator.experiments.config.experiment_config import (
    ExperimentConfig,
    EvaluationConfig,
    OutputConfig,
)


class TestExperimentConfig:
    """Tests for ExperimentConfig."""

    @pytest.fixture
    def valid_yaml_path(self, tmp_path: Path) -> Path:
        """Create valid experiment YAML."""
        content = """
name: test_experiment
description: "Test experiment for unit tests"
scenario: configs/test_scenario.yaml
evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
optimized_agents:
  - BANK_A
  - BANK_B
constraints: castro.constraints.CASTRO_CONSTRAINTS
output:
  directory: results
  database: test.db
"""
        yaml_path = tmp_path / "experiment.yaml"
        yaml_path.write_text(content)
        return yaml_path

    def test_loads_from_yaml(self, valid_yaml_path: Path) -> None:
        """ExperimentConfig loads from YAML file."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.name == "test_experiment"
        assert config.description == "Test experiment for unit tests"

    def test_loads_scenario_path(self, valid_yaml_path: Path) -> None:
        """Loads scenario path as Path object."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.scenario_path == Path("configs/test_scenario.yaml")

    def test_loads_evaluation_config(self, valid_yaml_path: Path) -> None:
        """Loads nested evaluation config."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.evaluation.mode == "bootstrap"
        assert config.evaluation.num_samples == 10
        assert config.evaluation.ticks == 12

    def test_loads_convergence_config(self, valid_yaml_path: Path) -> None:
        """Loads convergence criteria."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.convergence.max_iterations == 25
        assert config.convergence.stability_threshold == 0.05

    def test_loads_llm_config(self, valid_yaml_path: Path) -> None:
        """Loads LLM configuration."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.llm.model == "anthropic:claude-sonnet-4-5"
        assert config.llm.temperature == 0.0

    def test_loads_optimized_agents(self, valid_yaml_path: Path) -> None:
        """Loads list of optimized agents."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.optimized_agents == ["BANK_A", "BANK_B"]

    def test_loads_constraints_module(self, valid_yaml_path: Path) -> None:
        """Loads constraints module path."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.constraints_module == "castro.constraints.CASTRO_CONSTRAINTS"

    def test_loads_output_config(self, valid_yaml_path: Path) -> None:
        """Loads output configuration."""
        config = ExperimentConfig.from_yaml(valid_yaml_path)
        assert config.output.directory == Path("results")
        assert config.output.database == "test.db"

    def test_raises_on_missing_file(self) -> None:
        """Raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            ExperimentConfig.from_yaml(Path("nonexistent.yaml"))

    def test_raises_on_invalid_yaml(self, tmp_path: Path) -> None:
        """Raises error on invalid YAML."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("{ invalid yaml :::")
        with pytest.raises(Exception):  # yaml.YAMLError
            ExperimentConfig.from_yaml(bad_yaml)

    def test_raises_on_missing_required_field(self, tmp_path: Path) -> None:
        """Raises ValidationError on missing required field."""
        incomplete = tmp_path / "incomplete.yaml"
        incomplete.write_text("name: test\n")  # Missing other fields
        with pytest.raises(Exception):  # pydantic.ValidationError
            ExperimentConfig.from_yaml(incomplete)


class TestEvaluationConfig:
    """Tests for EvaluationConfig."""

    def test_bootstrap_mode_requires_num_samples(self) -> None:
        """Bootstrap mode requires num_samples."""
        config = EvaluationConfig(mode="bootstrap", num_samples=10, ticks=12)
        assert config.num_samples == 10

    def test_deterministic_mode_ignores_samples(self) -> None:
        """Deterministic mode ignores num_samples."""
        config = EvaluationConfig(mode="deterministic", num_samples=None, ticks=12)
        assert config.num_samples is None

    def test_defaults_to_bootstrap(self) -> None:
        """Default mode is bootstrap."""
        config = EvaluationConfig(ticks=12)
        assert config.mode == "bootstrap"
```

### Implementation

```python
# api/payment_simulator/experiments/config/experiment_config.py
"""Experiment configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from payment_simulator.ai_cash_mgmt.config.game_config import ConvergenceCriteria
from payment_simulator.llm.config import LLMConfig


@dataclass
class EvaluationConfig:
    """Evaluation mode configuration.

    Controls how policies are evaluated (bootstrap vs deterministic).
    """

    ticks: int
    mode: str = "bootstrap"
    num_samples: int | None = 10

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.mode not in ("bootstrap", "deterministic"):
            msg = f"Invalid evaluation mode: {self.mode}"
            raise ValueError(msg)


@dataclass
class OutputConfig:
    """Output configuration."""

    directory: Path = field(default_factory=lambda: Path("results"))
    database: str = "experiments.db"
    verbose: bool = True


@dataclass
class ExperimentConfig:
    """Experiment configuration loaded from YAML.

    Defines all settings needed to run an experiment.

    Example YAML:
        name: exp1
        description: "2-Period Deterministic"
        scenario: configs/exp1_2period.yaml
        evaluation:
          mode: bootstrap
          num_samples: 10
          ticks: 12
        convergence:
          max_iterations: 25
        llm:
          model: "anthropic:claude-sonnet-4-5"
        optimized_agents:
          - BANK_A
        constraints: castro.constraints.CASTRO_CONSTRAINTS
        output:
          directory: results
    """

    name: str
    description: str
    scenario_path: Path
    evaluation: EvaluationConfig
    convergence: ConvergenceCriteria
    llm: LLMConfig
    optimized_agents: list[str]
    constraints_module: str
    output: OutputConfig
    master_seed: int = 42

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentConfig:
        """Load experiment config from YAML file.

        Args:
            path: Path to experiment YAML file.

        Returns:
            ExperimentConfig loaded from file.

        Raises:
            FileNotFoundError: If file doesn't exist.
            yaml.YAMLError: If YAML is invalid.
            ValidationError: If required fields missing.
        """
        if not path.exists():
            msg = f"Experiment config not found: {path}"
            raise FileNotFoundError(msg)

        with open(path) as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> ExperimentConfig:
        """Create config from dictionary."""
        # Validate required fields
        required = ["name", "scenario", "evaluation", "convergence", "llm", "optimized_agents"]
        missing = [f for f in required if f not in data]
        if missing:
            msg = f"Missing required fields: {missing}"
            raise ValueError(msg)

        return cls(
            name=data["name"],
            description=data.get("description", ""),
            scenario_path=Path(data["scenario"]),
            evaluation=EvaluationConfig(
                mode=data["evaluation"].get("mode", "bootstrap"),
                num_samples=data["evaluation"].get("num_samples", 10),
                ticks=data["evaluation"]["ticks"],
            ),
            convergence=ConvergenceCriteria(
                max_iterations=data["convergence"].get("max_iterations", 50),
                stability_threshold=data["convergence"].get("stability_threshold", 0.05),
                stability_window=data["convergence"].get("stability_window", 5),
                improvement_threshold=data["convergence"].get("improvement_threshold", 0.01),
            ),
            llm=LLMConfig(
                model=data["llm"]["model"],
                temperature=data["llm"].get("temperature", 0.0),
                max_retries=data["llm"].get("max_retries", 3),
                thinking_budget=data["llm"].get("thinking_budget"),
                reasoning_effort=data["llm"].get("reasoning_effort"),
            ),
            optimized_agents=data["optimized_agents"],
            constraints_module=data.get("constraints", ""),
            output=OutputConfig(
                directory=Path(data.get("output", {}).get("directory", "results")),
                database=data.get("output", {}).get("database", "experiments.db"),
                verbose=data.get("output", {}).get("verbose", True),
            ),
            master_seed=data.get("master_seed", 42),
        )

    def load_constraints(self) -> Any:
        """Dynamically load constraints from module path.

        Returns:
            ScenarioConstraints loaded from constraints_module.
        """
        import importlib

        if not self.constraints_module:
            return None

        # Parse "module.path.VARIABLE"
        parts = self.constraints_module.rsplit(".", 1)
        if len(parts) != 2:
            msg = f"Invalid constraints module format: {self.constraints_module}"
            raise ValueError(msg)

        module_path, variable_name = parts
        module = importlib.import_module(module_path)
        return getattr(module, variable_name)
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/experiments/config/experiment_config.py` | Main config class |
| `api/payment_simulator/experiments/config/evaluation_config.py` | Evaluation settings |
| `api/tests/experiments/config/test_experiment_config.py` | Config tests |

### Verification

```bash
# Config tests pass
cd api && .venv/bin/python -m pytest tests/experiments/config/ -v

# Type checking passes
.venv/bin/python -m mypy payment_simulator/experiments/config/
```

---

## Phase 4: Experiment Runner Framework

**Duration**: 3-4 days
**Risk**: Medium
**Breaking Changes**: None (parallel implementation)

### Objectives

1. Create `ExperimentRunnerProtocol`
2. Create `BaseExperimentRunner` with optimization loop
3. Create `OutputHandlerProtocol` and implementations
4. Create unified experiment persistence

### TDD Tests

```python
# tests/experiments/runner/test_base_runner.py
"""Tests for BaseExperimentRunner."""

import pytest

from payment_simulator.experiments.runner.base_runner import BaseExperimentRunner
from payment_simulator.experiments.runner.output import SilentOutput


class MockEvaluator:
    """Mock policy evaluator for testing."""

    def evaluate(self, policy: dict, agent_id: str) -> int:
        return 1000  # Fixed cost

    def compare(self, old: dict, new: dict, agent_id: str) -> dict:
        return {"delta": -100, "old_cost": 1000, "new_cost": 900}


class MockLLMClient:
    """Mock LLM client for testing."""

    async def generate_structured_output(self, prompt: str, model: type, **kwargs) -> dict:
        return {"policy_id": "test", "parameters": {"threshold": 5.0}}


class TestBaseExperimentRunner:
    """Tests for BaseExperimentRunner."""

    @pytest.fixture
    def runner(self, tmp_path) -> BaseExperimentRunner:
        """Create runner with mock components."""
        from payment_simulator.experiments.config.experiment_config import (
            ExperimentConfig,
            EvaluationConfig,
            OutputConfig,
        )
        from payment_simulator.ai_cash_mgmt.config.game_config import ConvergenceCriteria
        from payment_simulator.llm.config import LLMConfig

        config = ExperimentConfig(
            name="test",
            description="Test experiment",
            scenario_path=tmp_path / "scenario.yaml",
            evaluation=EvaluationConfig(mode="deterministic", ticks=10),
            convergence=ConvergenceCriteria(max_iterations=3),
            llm=LLMConfig(model="mock:test"),
            optimized_agents=["BANK_A"],
            constraints_module="",
            output=OutputConfig(),
        )

        return BaseExperimentRunner(
            config=config,
            evaluator=MockEvaluator(),
            llm_client=MockLLMClient(),
            constraints=None,
            output=SilentOutput(),
        )

    def test_creates_with_config(self, runner: BaseExperimentRunner) -> None:
        """Runner creates with config."""
        assert runner._config.name == "test"

    @pytest.mark.asyncio
    async def test_runs_until_convergence_or_max_iterations(
        self, runner: BaseExperimentRunner
    ) -> None:
        """Runner completes after max iterations."""
        result = await runner.run()
        assert result.num_iterations <= 3
```

### Implementation

See full implementation in conceptual-plan.md Phase 4 section.

Key files:
- `api/payment_simulator/experiments/runner/protocol.py`
- `api/payment_simulator/experiments/runner/base_runner.py`
- `api/payment_simulator/experiments/runner/output.py`

### Verification

```bash
cd api && .venv/bin/python -m pytest tests/experiments/runner/ -v
```

---

## Phase 4.5: Bootstrap Integration Tests with Mocked LLM

**Duration**: 1-2 days
**Risk**: Low
**Breaking Changes**: None (tests only)

### Objectives

1. Create comprehensive integration tests for bootstrap policy evaluation
2. Verify bootstrap samples are processed by both old and new policies
3. Verify delta costs are correctly calculated
4. Verify policies are accepted/rejected based on paired comparison

### TDD Tests

```python
# tests/experiments/integration/test_bootstrap_policy_acceptance.py
"""Integration tests for bootstrap policy acceptance."""

import pytest
from unittest.mock import AsyncMock

from payment_simulator.llm import LLMClientProtocol


class MockLLMClient:
    """Mock LLM that returns deterministic policy updates."""

    def __init__(self, improved_policy: dict) -> None:
        self._improved_policy = improved_policy

    async def generate_structured_output(
        self,
        prompt: str,
        response_model: type,
        system_prompt: str | None = None,
    ) -> dict:
        """Return the improved policy."""
        return self._improved_policy


class TestBootstrapPolicyAcceptance:
    """Tests for policy acceptance based on bootstrap evaluation."""

    @pytest.mark.asyncio
    async def test_samples_evaluated_with_old_policy(self) -> None:
        """Bootstrap samples are evaluated with old policy."""
        # Arrange: Create evaluator with known seed
        # Act: Run evaluation
        # Assert: Verify samples were evaluated with old policy
        ...

    @pytest.mark.asyncio
    async def test_same_samples_used_for_new_policy(self) -> None:
        """Same bootstrap samples are used for new policy evaluation."""
        # This is CRITICAL - samples must be identical for paired comparison
        ...

    @pytest.mark.asyncio
    async def test_paired_delta_computed_correctly(self) -> None:
        """Paired delta = old_cost - new_cost for same sample."""
        ...

    @pytest.mark.asyncio
    async def test_policy_accepted_when_mean_delta_positive(self) -> None:
        """Policy is ACCEPTED when mean_delta > 0 (new policy cheaper)."""
        ...

    @pytest.mark.asyncio
    async def test_policy_rejected_when_mean_delta_negative(self) -> None:
        """Policy is REJECTED when mean_delta <= 0 (old policy better)."""
        ...

    @pytest.mark.asyncio
    async def test_end_to_end_with_mocked_llm(self) -> None:
        """Full experiment run with mocked LLM returning valid policy."""
        ...
```

### Implementation

- Create mock LLM client that returns deterministic policy updates
- Create test scenarios with known cost outcomes
- Verify exact sample reuse between old/new policy evaluation

### Verification

```bash
cd api && .venv/bin/python -m pytest tests/experiments/integration/ -v
```

---

## Phase 4.6: Terminology Cleanup

**Duration**: 0.5 days
**Risk**: Low
**Breaking Changes**: CLI flag rename (`--verbose-monte-carlo` → `--verbose-bootstrap`)

### Objectives

Fix incorrect terminology throughout the codebase:
- Use "bootstrap" or "bootstrap sampling" instead of "Monte Carlo"
- "Bootstrap Monte Carlo" is NOT a valid term and should be removed

### Files to Update

| File | Changes |
|------|---------|
| `api/payment_simulator/ai_cash_mgmt/bootstrap/*.py` | Update docstrings |
| `api/payment_simulator/ai_cash_mgmt/config/*.py` | Rename fields/methods |
| `api/payment_simulator/ai_cash_mgmt/core/*.py` | Update docstrings |
| `api/payment_simulator/ai_cash_mgmt/sampling/*.py` | Update docstrings |
| `api/payment_simulator/cli/commands/ai_game.py` | Rename CLI flags |
| `experiments/castro/castro/runner.py` | Update variable names |
| `api/migrations/*.sql` | Update column names (with migration) |

### Terminology Changes

| Old Term | New Term |
|----------|----------|
| Monte Carlo | bootstrap |
| monte_carlo | bootstrap |
| Bootstrap Monte Carlo | bootstrap |
| `--verbose-monte-carlo` | `--verbose-bootstrap` |
| `MonteCarloContextBuilder` | `BootstrapContextBuilder` |

### Verification

```bash
# Verify no remaining Monte Carlo references (except historical docs)
grep -r "Monte Carlo" api/ --include="*.py" | grep -v "# Historical"
```

---

## Phase 5: CLI Commands

**Duration**: 2 days
**Risk**: Low
**Breaking Changes**: None (new commands)

### Objectives

1. Create `payment-sim experiment` command group
2. Implement `run`, `validate`, `list`, `info` subcommands
3. Create Castro CLI thin wrapper

### New CLI Commands

#### `payment-sim experiment` Command Group

```bash
# Run experiment from YAML
payment-sim experiment run path/to/experiment.yaml [OPTIONS]

Options:
  --model TEXT           Override LLM model (provider:model format)
  --max-iter INT         Override max iterations
  --seed INT             Override master seed
  --output-dir PATH      Override output directory
  --verbose              Enable verbose output
  --quiet                Suppress output
  --dry-run              Validate config without running

# Validate experiment configuration
payment-sim experiment validate path/to/experiment.yaml

# List experiments in directory
payment-sim experiment list --dir experiments/castro/experiments/

# Show experiment info
payment-sim experiment info path/to/experiment.yaml

# Generate experiment template
payment-sim experiment template --output new_experiment.yaml

# Replay experiment from database
payment-sim experiment replay <run_id> --db experiments.db [OPTIONS]

Options:
  --verbose              Enable verbose output
  --audit                Show detailed audit trail
  --start INT            Start iteration (for audit)
  --end INT              End iteration (for audit)

# List experiment results
payment-sim experiment results --db experiments.db [OPTIONS]

Options:
  --experiment TEXT      Filter by experiment name
  --limit INT            Max results to show
```

### Implementation

```python
# api/payment_simulator/cli/commands/experiment.py
"""Experiment CLI commands."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

experiment_app = typer.Typer(
    name="experiment",
    help="Experiment framework commands",
    no_args_is_help=True,
)

console = Console()


@experiment_app.command()
def run(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML configuration"),
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", "-m", help="Override LLM model"),
    ] = None,
    max_iter: Annotated[
        int | None,
        typer.Option("--max-iter", "-i", help="Override max iterations"),
    ] = None,
    seed: Annotated[
        int | None,
        typer.Option("--seed", "-s", help="Override master seed"),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", "-o", help="Override output directory"),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress output"),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Validate config without running"),
    ] = False,
) -> None:
    """Run an experiment from YAML configuration.

    Examples:
        # Run with defaults
        payment-sim experiment run experiments/exp1.yaml

        # Override model and iterations
        payment-sim experiment run exp.yaml --model openai:gpt-4o --max-iter 50

        # Dry run (validate only)
        payment-sim experiment run exp.yaml --dry-run
    """
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig
    from payment_simulator.experiments.runner.base_runner import BaseExperimentRunner
    from payment_simulator.experiments.runner.output import (
        RichConsoleOutput,
        SilentOutput,
    )
    from payment_simulator.llm import PydanticAILLMClient

    # Load config
    try:
        config = ExperimentConfig.from_yaml(config_path)
    except FileNotFoundError:
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Invalid config: {e}[/red]")
        raise typer.Exit(1) from None

    # Apply CLI overrides
    if model:
        config.llm.model = model
    if max_iter:
        config.convergence.max_iterations = max_iter
    if seed:
        config.master_seed = seed
    if output_dir:
        config.output.directory = output_dir

    if dry_run:
        console.print("[green]Configuration valid![/green]")
        console.print(f"  Name: {config.name}")
        console.print(f"  Scenario: {config.scenario_path}")
        console.print(f"  Agents: {config.optimized_agents}")
        return

    # Create components
    llm_client = PydanticAILLMClient(config.llm)
    constraints = config.load_constraints()
    output_handler = SilentOutput() if quiet else RichConsoleOutput(console, verbose)

    # Create and run
    runner = BaseExperimentRunner(
        config=config,
        evaluator=...,  # Create from config
        llm_client=llm_client,
        constraints=constraints,
        output=output_handler,
    )

    try:
        result = asyncio.run(runner.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        raise typer.Exit(130) from None

    # Show results
    table = Table(title=f"Results: {config.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Run ID", result.run_id)
    table.add_row("Final Cost", f"${result.final_cost / 100:.2f}")
    table.add_row("Iterations", str(result.num_iterations))
    table.add_row("Converged", "Yes" if result.converged else "No")
    console.print(table)


@experiment_app.command()
def validate(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML configuration"),
    ],
) -> None:
    """Validate experiment configuration.

    Checks that the config file is valid YAML, has all required fields,
    and references valid scenario and constraint files.
    """
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig

    try:
        config = ExperimentConfig.from_yaml(config_path)
    except FileNotFoundError:
        console.print(f"[red]Config not found: {config_path}[/red]")
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Validation failed: {e}[/red]")
        raise typer.Exit(1) from None

    console.print("[green]Configuration valid![/green]")
    console.print(f"  Name: {config.name}")
    console.print(f"  Description: {config.description}")
    console.print(f"  Scenario: {config.scenario_path}")
    console.print(f"  Mode: {config.evaluation.mode}")
    console.print(f"  Agents: {', '.join(config.optimized_agents)}")


@experiment_app.command("list")
def list_experiments(
    directory: Annotated[
        Path,
        typer.Option("--dir", "-d", help="Directory containing experiment YAMLs"),
    ] = Path("experiments"),
) -> None:
    """List available experiments in a directory."""
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig

    if not directory.exists():
        console.print(f"[red]Directory not found: {directory}[/red]")
        raise typer.Exit(1)

    yamls = list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
    if not yamls:
        console.print(f"[yellow]No experiment files found in {directory}[/yellow]")
        return

    table = Table(title="Available Experiments")
    table.add_column("File", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Description")
    table.add_column("Mode")
    table.add_column("Agents")

    for yaml_path in sorted(yamls):
        try:
            config = ExperimentConfig.from_yaml(yaml_path)
            table.add_row(
                yaml_path.name,
                config.name,
                config.description[:40] + "..." if len(config.description) > 40 else config.description,
                config.evaluation.mode,
                ", ".join(config.optimized_agents),
            )
        except Exception as e:
            table.add_row(yaml_path.name, "[red]Error[/red]", str(e)[:40], "", "")

    console.print(table)


@experiment_app.command()
def info(
    config_path: Annotated[
        Path,
        typer.Argument(help="Path to experiment YAML configuration"),
    ],
) -> None:
    """Show detailed experiment configuration."""
    from payment_simulator.experiments.config.experiment_config import ExperimentConfig

    try:
        config = ExperimentConfig.from_yaml(config_path)
    except Exception as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        raise typer.Exit(1) from None

    console.print(f"[bold cyan]{config.name}[/bold cyan]")
    console.print(f"Description: {config.description}")
    console.print()

    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Scenario Path", str(config.scenario_path))
    table.add_row("Master Seed", str(config.master_seed))
    table.add_row("", "")
    table.add_row("[bold]Evaluation[/bold]", "")
    table.add_row("  Mode", config.evaluation.mode)
    table.add_row("  Samples", str(config.evaluation.num_samples or "N/A"))
    table.add_row("  Ticks", str(config.evaluation.ticks))
    table.add_row("", "")
    table.add_row("[bold]Convergence[/bold]", "")
    table.add_row("  Max Iterations", str(config.convergence.max_iterations))
    table.add_row("  Stability Threshold", f"{config.convergence.stability_threshold:.1%}")
    table.add_row("", "")
    table.add_row("[bold]LLM[/bold]", "")
    table.add_row("  Model", config.llm.model)
    table.add_row("  Temperature", str(config.llm.temperature))
    table.add_row("", "")
    table.add_row("[bold]Agents[/bold]", ", ".join(config.optimized_agents))

    console.print(table)


@experiment_app.command()
def template(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
) -> None:
    """Generate experiment configuration template."""
    template = """# Experiment Configuration
name: my_experiment
description: "Description of the experiment"

# Scenario configuration file (relative to experiment file)
scenario: configs/scenario.yaml

# Evaluation settings
evaluation:
  mode: bootstrap  # or "deterministic"
  num_samples: 10  # Number of bootstrap samples
  ticks: 12        # Ticks per evaluation

# Convergence criteria
convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01

# LLM configuration
llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3
  # thinking_budget: 8000  # For Anthropic extended thinking
  # reasoning_effort: high  # For OpenAI o1/o3 models

# Agents to optimize
optimized_agents:
  - BANK_A
  - BANK_B

# Constraints module (Python import path)
constraints: castro.constraints.CASTRO_CONSTRAINTS

# Output settings
output:
  directory: results
  database: experiments.db
  verbose: true

# Master seed for determinism
master_seed: 42
"""

    if output:
        output.write_text(template)
        console.print(f"[green]Template written to {output}[/green]")
    else:
        console.print(template)
```

### Files to Create

| File | Purpose |
|------|---------|
| `api/payment_simulator/cli/commands/experiment.py` | CLI commands |
| `api/tests/cli/test_experiment_commands.py` | CLI tests |

### Verification

```bash
# CLI help works
payment-sim experiment --help
payment-sim experiment run --help

# Template generation works
payment-sim experiment template

# Validation works
payment-sim experiment validate tests/fixtures/experiment.yaml
```

---

## Phase 6: Castro Migration

**Duration**: 2-3 days
**Risk**: Medium
**Breaking Changes**: Castro CLI changes (backwards compatible)

### Objectives

1. Create experiment YAML files from Python dataclasses
2. Update Castro CLI to use experiment framework
3. Keep backwards compatibility with existing commands

### Tasks

1. **Create YAML experiment definitions**:
   - `experiments/castro/experiments/exp1.yaml`
   - `experiments/castro/experiments/exp2.yaml`
   - `experiments/castro/experiments/exp3.yaml`

2. **Simplify Castro CLI**:
   - Import from experiment framework
   - Keep existing command signatures
   - Map `castro run exp1` → `payment-sim experiment run experiments/exp1.yaml`

3. **Remove duplicated code**:
   - `castro/pydantic_llm_client.py` (use `payment_simulator.llm`)
   - `castro/model_config.py` (merged into `payment_simulator.llm`)
   - Simplify `castro/runner.py` to use `BaseExperimentRunner`

### Example YAML (exp2.yaml)

```yaml
# experiments/castro/experiments/exp2.yaml
name: exp2
description: "12-Period Stochastic LVTS-Style"

scenario: configs/exp2_12period.yaml

evaluation:
  mode: bootstrap
  num_samples: 10
  ticks: 12

convergence:
  max_iterations: 25
  stability_threshold: 0.05
  stability_window: 5
  improvement_threshold: 0.01

llm:
  model: "anthropic:claude-sonnet-4-5"
  temperature: 0.0
  max_retries: 3

optimized_agents:
  - BANK_A
  - BANK_B

constraints: castro.constraints.CASTRO_CONSTRAINTS

output:
  directory: results
  database: castro.db
  verbose: true

master_seed: 42
```

---

## Phase 7: Documentation

**Duration**: 2-3 days
**Risk**: Low

### Documentation Structure

```
docs/reference/
├── llm/
│   ├── index.md
│   ├── configuration.md
│   ├── protocols.md
│   ├── providers.md
│   └── audit.md
├── experiments/
│   ├── index.md
│   ├── configuration.md
│   ├── runner.md
│   ├── cli.md
│   ├── persistence.md
│   └── extending.md
├── ai_cash_mgmt/
│   ├── index.md (updated)
│   └── ... (existing, trimmed)
└── castro/
    ├── index.md (simplified)
    ├── constraints.md
    └── experiments.md
```

### Documentation Tasks

1. **Create `docs/reference/llm/`**:
   - Protocol reference
   - Configuration options
   - Provider-specific settings
   - Audit capture guide

2. **Create `docs/reference/experiments/`**:
   - YAML configuration reference
   - Runner API reference
   - CLI command reference
   - How to create new experiments

3. **Update `docs/reference/ai_cash_mgmt/`**:
   - Remove sections moved to experiments/llm
   - Focus on bootstrap, constraints, optimization

4. **Replace `docs/reference/castro/`**:
   - Simplify to Castro-specific content only
   - Reference experiment framework docs

5. **Add architecture doc**:
   - `docs/reference/architecture/XX-experiment-framework.md`

---

## Verification Checklist

Before each phase is complete:

- [ ] All new tests pass
- [ ] All existing tests pass
- [ ] Type checking passes (mypy)
- [ ] Linting passes (ruff)
- [ ] Documentation updated
- [ ] Changes committed with clear messages

Before final merge:

- [ ] Full test suite passes
- [ ] Performance benchmarks acceptable
- [ ] Documentation complete
- [ ] Castro experiments still work
- [ ] Determinism verified (same seed = same result)
- [ ] Replay identity maintained

---

## Files to Delete (After Migration Complete)

After all phases are complete, the following files can be safely deleted:

### Castro Files (Moved to Core Modules)

| File | Reason | Replacement |
|------|--------|-------------|
| `experiments/castro/castro/pydantic_llm_client.py` | Moved to `payment_simulator.llm` | `llm/pydantic_client.py` |
| `experiments/castro/castro/model_config.py` | Merged into LLM config | `llm/config.py` |
| `experiments/castro/castro/context_builder.py` | Replaced by bootstrap context | `castro/bootstrap_context.py` |
| `experiments/castro/castro/simulation.py` | No longer needed (bootstrap replaces full sim) | Bootstrap evaluation |

### Castro Persistence (Unified into Core)

| File | Reason | Replacement |
|------|--------|-------------|
| `experiments/castro/castro/persistence/models.py` | Merged into core persistence | `experiments/persistence/events.py` |
| `experiments/castro/castro/persistence/repository.py` | Merged into core persistence | `experiments/persistence/repository.py` |

### Deprecated Python Factories

| File | Reason | Replacement |
|------|--------|-------------|
| `experiments/castro/castro/experiments.py` | Replaced by YAML configs | `experiments/castro/experiments/*.yaml` |

**Important**: Do NOT delete these files until:
1. All tests pass with the new implementations
2. Castro CLI works with YAML configs
3. Replay functionality verified

---

---

## Phase 9: Castro Module Slimming

**Duration**: 1-2 days
**Risk**: Low
**Breaking Changes**: None (internal cleanup)

### Objectives

Reduce Castro module complexity by removing redundant code and leveraging core SimCash modules.

### Current State Analysis

After meticulous review of every file in `experiments/castro/`, the following issues were identified:

| Issue | Severity | File(s) |
|-------|----------|---------|
| Terminology bug (monte_carlo → bootstrap) | High | `events.py` |
| Duplicate VerboseConfig classes | High | `verbose_logging.py`, `display.py` |
| Redundant experiments.py | High | `experiments.py` |
| Obsolete context_builder.py | Medium | `context_builder.py` |
| Complex runner.py | Medium | `runner.py` |

### Tasks

#### 9.1: Fix Terminology Bug in events.py

**File**: `experiments/castro/castro/events.py`

| Old | New |
|-----|-----|
| `EVENT_MONTE_CARLO_EVALUATION` | `EVENT_BOOTSTRAP_EVALUATION` |
| `create_monte_carlo_event()` | `create_bootstrap_evaluation_event()` |

#### 9.2: Consolidate VerboseConfig

**Problem**: Two different VerboseConfig classes with different field names:
- `verbose_logging.py`: `policy`, `bootstrap`, `llm`, `rejections`, `debug`
- `display.py`: `show_iterations`, `show_bootstrap`, `show_llm_calls`, `show_policy_changes`, `show_rejections`

**Solution**:
1. Keep `verbose_logging.py` VerboseConfig as the single source of truth
2. Update `display.py` to import from `verbose_logging.py`
3. Align field names to be consistent

#### 9.3: Delete experiments.py

**Problem**: `experiments.py` contains:
- `CastroExperiment` dataclass (~50 lines)
- `create_exp1()`, `create_exp2()`, `create_exp3()` factories (~100 lines each)
- `EXPERIMENTS` dict

**Solution**:
1. Already have `experiments/exp1.yaml`, `exp2.yaml`, `exp3.yaml`
2. Create YAML loader to replace Python factories
3. Delete `experiments.py`

**Migration**:
```python
# OLD (experiments.py)
from castro.experiments import EXPERIMENTS
exp = EXPERIMENTS["exp1"](model="anthropic:claude-sonnet-4-5")

# NEW (YAML-based)
from castro.experiment_loader import load_experiment
exp = load_experiment("exp1", model_override="anthropic:claude-sonnet-4-5")
```

#### 9.4: Delete context_builder.py

**Problem**: `context_builder.py` contains `BootstrapContextBuilder` that works with `SimulationResult` objects (old pattern).

**Reason to delete**: `bootstrap_context.py` contains `EnrichedBootstrapContextBuilder` that works with `EnrichedEvaluationResult` (new pattern from Phase 0.5).

**Verification before deletion**:
```bash
grep -r "from castro.context_builder import" experiments/castro/
grep -r "BootstrapContextBuilder" experiments/castro/ --include="*.py"
```

#### 9.5: Simplify runner.py

**Current**: 936 lines with many responsibilities.

**Target changes**:
- Extract experiment loading to separate module
- Use YAML configs instead of `CastroExperiment` dataclass
- Remove any unused helper methods
- Target: < 700 lines

#### 9.6: Update cli.py

**Current**: Imports from `experiments.py` EXPERIMENTS dict.

**Change**: Import from YAML-based experiment loader.

### Files Summary

| Action | File | Reason |
|--------|------|--------|
| DELETE | `experiments.py` | Redundant with YAML configs |
| DELETE | `context_builder.py` | Replaced by `bootstrap_context.py` |
| MODIFY | `events.py` | Fix terminology |
| MODIFY | `display.py` | Remove duplicate VerboseConfig |
| MODIFY | `verbose_logging.py` | Keep as single VerboseConfig source |
| MODIFY | `runner.py` | Simplify, use YAML loading |
| MODIFY | `cli.py` | Update imports |
| MODIFY | `__init__.py` | Update exports |
| CREATE | `experiment_loader.py` | YAML experiment loading (~50 lines) |

### TDD Tests

```python
# tests/test_experiment_loader.py
"""Tests for YAML experiment loading."""

import pytest
from pathlib import Path
from castro.experiment_loader import load_experiment, list_experiments


class TestExperimentLoader:
    """Tests for experiment loading from YAML."""

    def test_load_experiment_from_yaml(self) -> None:
        """load_experiment loads config from YAML file."""
        exp = load_experiment("exp1")
        assert exp.name == "exp1"
        assert exp.description == "2-Period Deterministic Nash Equilibrium"

    def test_load_experiment_with_model_override(self) -> None:
        """load_experiment allows model override."""
        exp = load_experiment("exp1", model_override="openai:gpt-4o")
        assert exp.get_model_config().model == "openai:gpt-4o"

    def test_list_experiments_returns_available(self) -> None:
        """list_experiments returns all YAML experiment names."""
        exps = list_experiments()
        assert "exp1" in exps
        assert "exp2" in exps
        assert "exp3" in exps

    def test_load_nonexistent_experiment_raises(self) -> None:
        """load_experiment raises for unknown experiment."""
        with pytest.raises(FileNotFoundError):
            load_experiment("nonexistent")
```

### Verification

```bash
# Run Castro tests
cd experiments/castro && uv run pytest tests/ -v

# Verify no remaining Monte Carlo terminology
grep -r "monte_carlo" experiments/castro/castro/ --include="*.py"
grep -r "MONTE_CARLO" experiments/castro/castro/ --include="*.py"

# Verify experiments still work
uv run castro run exp1 --max-iter 1 --verbose

# Verify replay still works
uv run castro replay <run_id> --verbose
```

### Expected Outcome

**Lines of code removed**: ~400
- `experiments.py`: ~350 lines
- `context_builder.py`: ~100 lines
- Duplicate VerboseConfig: ~50 lines

**Lines of code added**: ~100
- `experiment_loader.py`: ~50 lines
- Tests: ~50 lines

**Net reduction**: ~300 lines

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 0: Bootstrap Bug Fix | 1 day | None |
| Phase 0.5: Event Tracing | 2-3 days | Phase 0 |
| Phase 1: Preparation | 1-2 days | Phase 0.5 |
| Phase 2: LLM Module | 2-3 days | Phase 1 |
| Phase 3: Experiment Config | 2-3 days | Phase 1 |
| Phase 4: Experiment Runner | 3-4 days | Phases 2, 3 |
| Phase 4.5: Bootstrap Integration Tests | 1-2 days | Phase 4 |
| Phase 4.6: Terminology Cleanup | 0.5 days | Phase 4.5 |
| Phase 5: CLI Commands | 2 days | Phase 4.6 |
| Phase 6: Castro Migration | 2-3 days | Phase 5 |
| Phase 7: Documentation | 2-3 days | Phase 6 |
| Phase 8: LLMConfig Migration | 1 day | Phase 7 |
| **Phase 9: Castro Slimming** | **1-2 days** | **Phase 8** |

**Total: ~20-28 days**

---

## Phase 10: Deep Integration - Core Module Consolidation

**Duration**: 2-3 days
**Risk**: Medium-High
**Breaking Changes**: None (internal refactoring)
**Dependencies**: Phase 9

### Objectives

Move remaining Castro components to core SimCash modules where they can be reused:

1. **EnrichedBootstrapContextBuilder** → `ai_cash_mgmt/bootstrap/`
2. **PydanticAILLMClient (policy-specific)** → `llm/` with custom prompt support
3. **run_id.py** → `experiments/` module
4. **StateProvider pattern** → `experiments/runner/` (DEFERRED due to high complexity)
5. **Persistence unification** → `experiments/persistence/` (DEFERRED due to migration risk)

### Tasks

#### 10.1: Move EnrichedBootstrapContextBuilder to Core (Low Risk)

**Impact:** ~200 lines moved
**TDD Test File:** `api/tests/ai_cash_mgmt/bootstrap/test_context_builder_core.py`

**Steps:**
1. Write TDD tests for core location import
2. Write TDD tests for functionality preservation
3. Write TDD tests for Castro backward compatibility
4. Run tests → FAIL
5. Copy `EnrichedBootstrapContextBuilder` to `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`
6. Update `api/payment_simulator/ai_cash_mgmt/bootstrap/__init__.py` to export
7. Update Castro's `bootstrap_context.py` to re-export from core
8. Run tests → PASS

#### 10.2: Extend PydanticAILLMClient with Custom Prompt (Medium Risk)

**Impact:** ~150 lines reduced from Castro
**TDD Test File:** `api/tests/llm/test_pydantic_client_custom_prompt.py`

**Steps:**
1. Write TDD tests for custom system prompt support
2. Write TDD tests for default system prompt
3. Write TDD tests for Castro migration path
4. Run tests → FAIL
5. Modify `api/payment_simulator/llm/pydantic_client.py`:
   - Add `default_system_prompt` parameter to `__init__`
   - Use `default_system_prompt` when `system_prompt=None` in methods
6. Update Castro's `pydantic_llm_client.py` to use core client with custom prompt
7. Run tests → PASS

#### 10.3: Move run_id.py to Core (Very Low Risk)

**Impact:** ~30 lines moved
**TDD Test File:** `api/tests/experiments/test_run_id_core.py`

**Steps:**
1. Write TDD tests for core location import
2. Write TDD tests for run ID generation
3. Write TDD tests for Castro backward compatibility
4. Run tests → FAIL
5. Move `run_id.py` to `api/payment_simulator/experiments/run_id.py`
6. Update `api/payment_simulator/experiments/__init__.py` to export `generate_run_id`
7. Update Castro's `run_id.py` to re-export from core
8. Run tests → PASS

#### 10.4: Generalize StateProvider to Core (DEFERRED - High Risk)

**Rationale for deferral:**
- High complexity
- Touches many files
- Requires careful protocol design
- Can be done in a future phase

#### 10.5: Unify Persistence (DEFERRED - High Risk)

**Rationale for deferral:**
- Database schema changes required
- High migration risk
- Can be done independently later

### Expected Outcome

| Category | Before Phase 10 | After Phase 10 | Delta |
|----------|-----------------|----------------|-------|
| Core ai_cash_mgmt | existing | +200 | +200 |
| Core experiments | existing | +30 | +30 |
| Core llm | existing | +20 | +20 |
| Castro bootstrap_context.py | ~200 | ~50 (re-export) | -150 |
| Castro pydantic_llm_client.py | ~200 | ~100 (wrapper) | -100 |
| Castro run_id.py | ~30 | ~5 (re-export) | -25 |
| **Net Castro Reduction** | | | **-275** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_context_builder_core.py | 8 |
| test_run_id_core.py | 8 |
| test_pydantic_client_custom_prompt.py | 6 |
| **Total** | **22** |

### Verification Checklist

- [ ] All API tests pass: `cd api && .venv/bin/python -m pytest`
- [ ] All Castro tests pass: `cd experiments/castro && uv run pytest tests/`
- [ ] Type checking passes: `mypy payment_simulator/`
- [ ] Castro CLI still works: `uv run castro run exp1 --max-iter 1 --dry-run`
- [ ] Net Castro reduction of ~275 lines

See [phases/phase_10.md](./phases/phase_10.md) for full TDD test specifications.

---

## Phase 11: Infrastructure Generalization - StateProvider and Persistence

**Duration**: 4-5 days
**Risk**: High
**Dependencies**: Phase 10
**Breaking Changes**: Potentially (database migration required for 11.2)

### Objectives

Phase 11 addresses the high-risk tasks deferred from Phase 10:

1. **Task 11.1: StateProvider Protocol** - Generalize for experiment replay identity
2. **Task 11.2: Unified Persistence** - Consolidate experiment persistence

### Task 11.1: Generalize StateProvider Protocol (High Risk)

**Impact:** ~250 lines abstracted to core
**TDD Test File:** `api/tests/experiments/runner/test_state_provider_core.py`

**Protocol Definition:**
```python
@runtime_checkable
class ExperimentStateProviderProtocol(Protocol):
    """Protocol for accessing experiment state."""
    def get_experiment_info(self) -> dict[str, Any]: ...
    def get_total_iterations(self) -> int: ...
    def get_iteration_events(self, iteration: int) -> list[dict[str, Any]]: ...
    def get_iteration_policies(self, iteration: int) -> dict[str, Any]: ...
    def get_iteration_costs(self, iteration: int) -> dict[str, int]: ...
    def get_iteration_accepted_changes(self, iteration: int) -> dict[str, bool]: ...
```

**Steps:**
1. Write TDD tests for protocol definition
2. Write TDD tests for `DatabaseStateProvider`
3. Write TDD tests for `LiveStateProvider`
4. Run tests → FAIL
5. Create `api/payment_simulator/experiments/runner/state_provider.py`
6. Update exports in `__init__.py`
7. Run tests → PASS
8. Update Castro to use or implement core protocol

### Task 11.2: Unify Persistence Layer (High Risk)

**Impact:** ~300 lines unified
**TDD Test File:** `api/tests/experiments/persistence/test_experiment_repository.py`

**Database Schema:**
```sql
CREATE TABLE experiments (
    run_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    experiment_type VARCHAR NOT NULL,
    config JSON NOT NULL,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    num_iterations INTEGER,
    converged BOOLEAN,
    convergence_reason VARCHAR
);

CREATE TABLE experiment_iterations (
    run_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    costs_per_agent JSON NOT NULL,
    accepted_changes JSON NOT NULL,
    policies JSON NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    PRIMARY KEY (run_id, iteration)
);
```

**Steps:**
1. Write TDD tests for `ExperimentRepository`
2. Write TDD tests for record classes
3. Write TDD tests for StateProvider integration
4. Run tests → FAIL
5. Create `api/payment_simulator/experiments/persistence/repository.py`
6. Update exports in `__init__.py`
7. Run tests → PASS
8. Create migration script for existing Castro databases
9. Update Castro to use core repository (optional - can be phased)

### Risk Mitigation

**StateProvider:**
- Start with minimal protocol, extend as needed
- Fallback: Castro keeps its own provider, imports core for type hints only

**Persistence:**
- New tables alongside old (don't modify existing schema)
- Migration script with dry-run mode
- Backup before migration
- Fallback: Castro keeps own persistence, core repository is optional

### Expected Outcome

| Category | Change |
|----------|--------|
| Core experiments/runner | +150 lines |
| Core experiments/persistence | +300 lines |
| Castro state_provider.py | -200 lines |
| Castro persistence/ | -200 lines |
| **Net Castro Reduction** | **~400 lines** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_state_provider_core.py | ~15 |
| test_experiment_repository.py | ~20 |
| **Total** | **~35** |

### Verification Checklist

- [ ] All API tests pass: `cd api && .venv/bin/python -m pytest`
- [ ] All Castro tests pass: `cd experiments/castro && uv run pytest tests/`
- [ ] Type checking passes: `mypy payment_simulator/`
- [ ] Replay identity works: Same input produces same output
- [ ] Migration script succeeds on test database

See [phases/phase_11.md](./phases/phase_11.md) for full TDD test specifications.

---

## Timeline Summary

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 0: Bootstrap Bug Fix | 1 day | None |
| Phase 0.5: Event Tracing | 2-3 days | Phase 0 |
| Phase 1: Preparation | 1-2 days | Phase 0.5 |
| Phase 2: LLM Module | 2-3 days | Phase 1 |
| Phase 3: Experiment Config | 2-3 days | Phase 1 |
| Phase 4: Experiment Runner | 3-4 days | Phases 2, 3 |
| Phase 4.5: Bootstrap Integration Tests | 1-2 days | Phase 4 |
| Phase 4.6: Terminology Cleanup | 0.5 days | Phase 4.5 |
| Phase 5: CLI Commands | 2 days | Phase 4.6 |
| Phase 6: Castro Migration | 2-3 days | Phase 5 |
| Phase 7: Documentation | 2-3 days | Phase 6 |
| Phase 8: LLMConfig Migration | 1 day | Phase 7 |
| Phase 9: Castro Slimming | 1-2 days | Phase 8 |
| Phase 10: Deep Integration | 2-3 days | Phase 9 |
| **Phase 11: Infrastructure Generalization** | **4-5 days** | **Phase 10** |
| **Phase 12: Castro Migration** | **2-3 days** | **Phase 11** |

**Total: ~28-39 days**

---

## Phase 12: Castro Migration to Core Infrastructure

**Status:** Planned
**Dependencies:** Phase 11 (StateProvider Protocol and Unified Persistence)
**Risk:** Medium (backward compatibility, replay identity preservation)

Phase 12 migrates Castro experiments to use the core infrastructure created in Phase 11.

### Tasks

#### Task 12.1: Adapt Castro StateProvider to Core Protocol
- Make `LiveExperimentProvider` implement core `ExperimentStateProviderProtocol`
- Make `DatabaseExperimentProvider` use core methods
- Keep Castro's `ExperimentEvent` for event-specific features
- Maintain backward compatibility with existing API

#### Task 12.2: Migrate Castro Persistence to Core Repository
- `ExperimentEventRepository` wraps core `ExperimentRepository` internally
- Castro keeps `ExperimentRunRecord` as facade over `ExperimentRecord`
- Add conversion methods: `ExperimentEvent <-> EventRecord`

#### Task 12.3: Event System Alignment
- Add `to_event_record()` method to `ExperimentEvent`
- Add `from_event_record()` class method to `ExperimentEvent`
- Keep all event creation helpers (domain-specific)

### Expected Outcomes
- ~330 lines removed from Castro
- ~32 new tests added
- Full backward compatibility
- Replay identity preserved

See `phases/phase_12.md` for detailed TDD specifications.

---

## Phase 13: Complete Experiment StateProvider Migration

**Status:** COMPLETED
**Dependencies:** Phase 12
**Risk:** Medium (API changes, test migrations)

Phase 13 completes the StateProvider pattern migration by extending core protocol with audit methods and deleting Castro's redundant infrastructure.

### Tasks

#### Task 13.1: Extend Core Protocol with Audit Methods
- Add `run_id` property to protocol
- Add `get_run_metadata()` method
- Add `get_all_events()` iterator
- Add `get_final_result()` method
- Implement in both `LiveStateProvider` and `DatabaseStateProvider`

#### Task 13.2: Update Castro Display to Use Core Protocol
- Update `display.py` to import from core
- Update `audit_display.py` to import from core
- Events are now dicts with `event_type` key, not objects

#### Task 13.3: Update CLI Replay to Use Core
- CLI `replay` command uses `ExperimentRepository.as_state_provider()`
- Remove import of `DatabaseExperimentProvider` from castro

#### Task 13.4: Delete Castro Infrastructure
- Delete `castro/state_provider.py`
- Delete `castro/persistence/` directory
- Delete `castro/event_compat.py`

#### Task 13.5: Update All Test Imports
- Update all test files to import from core
- Delete obsolete test files

### Expected Outcomes
- ~800+ lines removed from Castro
- ~60 new tests added
- Full replay identity preserved

See [phases/phase_13.md](./phases/phase_13.md) for detailed TDD specifications.

---

## Phase 14: Verbose Logging, Audit Display, and CLI Integration to Core

**Status:** PLANNED
**Dependencies:** Phase 13
**Risk:** Medium (Castro needs to stay functional during migration)

Phase 14 completes the extraction of reusable experiment infrastructure to core SimCash modules, making Castro a truly thin experiment-specific layer.

### Objectives

1. Move `VerboseConfig` and `VerboseLogger` to core `experiments/runner/verbose.py`
2. Move `display_experiment_output()` to core `experiments/runner/display.py`
3. Move `display_audit_output()` to core `experiments/runner/audit.py`
4. Create generic experiment CLI commands in core `experiments/cli/`
5. Update Castro to be a thin wrapper using core infrastructure
6. Update documentation

### Task 14.1: Move VerboseConfig and VerboseLogger to Core (Low Risk)

**TDD Tests First:**
```python
# api/tests/experiments/runner/test_verbose_core.py
"""Tests for core verbose logging infrastructure."""

import pytest
from payment_simulator.experiments.runner.verbose import (
    VerboseConfig,
    VerboseLogger,
)


class TestVerboseConfig:
    """Tests for VerboseConfig dataclass."""

    def test_default_all_disabled(self) -> None:
        """Default config has all flags disabled."""
        config = VerboseConfig()
        assert config.iterations is False
        assert config.policy is False
        assert config.bootstrap is False
        assert config.llm is False
        assert config.rejections is False

    def test_all_enabled_factory(self) -> None:
        """all_enabled() creates config with all flags True."""
        config = VerboseConfig.all_enabled()
        assert config.iterations is True
        assert config.policy is True

    def test_from_cli_flags_verbose_enables_all(self) -> None:
        """from_cli_flags(verbose=True) enables all flags."""
        config = VerboseConfig.from_cli_flags(verbose=True)
        assert config.iterations is True

    def test_any_property_detects_any_enabled(self) -> None:
        """any property returns True if any flag is enabled."""
        config = VerboseConfig(policy=True)
        assert config.any is True


class TestVerboseLogger:
    """Tests for VerboseLogger class."""

    def test_creates_with_config(self) -> None:
        """VerboseLogger creates with VerboseConfig."""
        config = VerboseConfig(policy=True)
        logger = VerboseLogger(config)
        assert logger.config.policy is True

    def test_log_iteration_start_when_enabled(self) -> None:
        """log_iteration_start outputs when iterations flag is True."""
        from io import StringIO
        from rich.console import Console

        config = VerboseConfig(iterations=True)
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        logger = VerboseLogger(config, console=console)

        logger.log_iteration_start(1, 10000)  # costs in cents

        assert "Iteration" in output.getvalue()

    def test_log_policy_change_when_disabled(self) -> None:
        """log_policy_change is silent when policy flag is False."""
        from io import StringIO
        from rich.console import Console

        config = VerboseConfig(policy=False)
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        logger = VerboseLogger(config, console=console)

        logger.log_policy_change("BANK_A", {}, {})

        assert output.getvalue() == ""
```

**Steps:**
1. Write TDD tests for `VerboseConfig` and `VerboseLogger`
2. Run tests → FAIL
3. Create `api/payment_simulator/experiments/runner/verbose.py`
4. Copy implementation from Castro with modifications
5. Update `__init__.py` exports
6. Run tests → PASS
7. Update Castro to import from core

### Task 14.2: Move display_experiment_output() to Core (Low Risk)

**TDD Tests First:**
```python
# api/tests/experiments/runner/test_display_core.py
"""Tests for core experiment display functions."""

import pytest
from payment_simulator.experiments.runner.display import display_experiment_output
from payment_simulator.experiments.runner import LiveStateProvider


class TestDisplayExperimentOutput:
    """Tests for display_experiment_output function."""

    def test_displays_header_with_run_id(self) -> None:
        """Display includes run ID in header."""
        from io import StringIO
        from rich.console import Console

        provider = LiveStateProvider(
            experiment_name="exp1",
            experiment_type="castro",
            config={},
            run_id="exp1-123",
        )
        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_experiment_output(provider, console)

        assert "exp1-123" in output.getvalue()

    def test_displays_events_from_provider(self) -> None:
        """Display iterates over events from provider."""
        from io import StringIO
        from rich.console import Console

        provider = LiveStateProvider(...)
        provider.record_event(0, "experiment_start", {"experiment_name": "exp1"})

        output = StringIO()
        console = Console(file=output, force_terminal=True)

        display_experiment_output(provider, console)

        assert "exp1" in output.getvalue()

    def test_respects_verbose_config(self) -> None:
        """Display respects VerboseConfig settings."""
        # Test that verbose flags control output visibility
        ...
```

**Steps:**
1. Write TDD tests for `display_experiment_output`
2. Run tests → FAIL
3. Create `api/payment_simulator/experiments/runner/display.py`
4. Copy implementation from Castro
5. Update to use core `VerboseConfig`
6. Run tests → PASS
7. Update Castro to re-export from core

### Task 14.3: Move display_audit_output() to Core (Low Risk)

**TDD Tests First:**
```python
# api/tests/experiments/runner/test_audit_core.py
"""Tests for core audit display functions."""

import pytest
from payment_simulator.experiments.runner.audit import display_audit_output


class TestDisplayAuditOutput:
    """Tests for display_audit_output function."""

    def test_displays_llm_interaction_events(self) -> None:
        """Audit display shows LLM interaction details."""
        ...

    def test_filters_by_iteration_range(self) -> None:
        """Audit respects start_iteration and end_iteration params."""
        ...

    def test_displays_prompts_and_responses(self) -> None:
        """Audit shows full prompts and responses."""
        ...
```

**Steps:**
1. Write TDD tests for `display_audit_output`
2. Run tests → FAIL
3. Create `api/payment_simulator/experiments/runner/audit.py`
4. Copy implementation from Castro
5. Update to use core imports
6. Run tests → PASS
7. Delete Castro's `audit_display.py`

### Task 14.4: Create Generic Experiment CLI in Core (Medium Risk)

**TDD Tests First:**
```python
# api/tests/experiments/cli/test_cli_core.py
"""Tests for core experiment CLI commands."""

import pytest
from typer.testing import CliRunner
from payment_simulator.experiments.cli import experiment_app

runner = CliRunner()


class TestRunCommand:
    """Tests for experiment run command."""

    def test_run_requires_config_path(self) -> None:
        """Run command requires config path argument."""
        result = runner.invoke(experiment_app, ["run"])
        assert result.exit_code != 0

    def test_run_validates_config(self) -> None:
        """Run validates experiment config."""
        result = runner.invoke(experiment_app, ["run", "nonexistent.yaml"])
        assert "not found" in result.output.lower() or result.exit_code != 0


class TestReplayCommand:
    """Tests for experiment replay command."""

    def test_replay_requires_run_id(self) -> None:
        """Replay command requires run ID argument."""
        result = runner.invoke(experiment_app, ["replay"])
        assert result.exit_code != 0


class TestResultsCommand:
    """Tests for experiment results command."""

    def test_results_lists_experiments(self, tmp_path) -> None:
        """Results command lists experiments from database."""
        # Create test database with experiments
        ...
```

**Steps:**
1. Write TDD tests for CLI commands
2. Run tests → FAIL
3. Create `api/payment_simulator/experiments/cli/` package:
   - `__init__.py` - exports `experiment_app`
   - `run.py` - run command
   - `replay.py` - replay command
   - `results.py` - results listing
   - `common.py` - shared utilities
4. Implement generic commands that work with any experiment type
5. Run tests → PASS

### Task 14.5: Update Castro CLI to Use Core (Low Risk)

**Steps:**
1. Update Castro `cli.py` to be a thin wrapper:
   - Import commands from core
   - Add Castro-specific defaults (DEFAULT_MODEL, experiments directory)
   - Keep Castro-specific argument handling
2. Verify all Castro CLI tests pass
3. Castro `cli.py` should be ~100 lines (down from ~500)

### Task 14.6: Update Castro Runner to Import from Core (Low Risk)

**Steps:**
1. Update `runner.py` to import `VerboseConfig` from core
2. Update `runner.py` to import `VerboseLogger` from core
3. Verify all runner tests pass

### Task 14.7: Delete Redundant Castro Files (Low Risk)

**Files to Delete:**
- `castro/verbose_logging.py` (~430 lines)
- `castro/audit_display.py` (~200 lines)

**Files to Reduce:**
- `castro/display.py` - becomes thin re-export (~30 lines, -170)
- `castro/cli.py` - becomes thin wrapper (~100 lines, -400)

### Task 14.8: Update Documentation (Low Risk)

**Steps:**
1. Create `docs/reference/experiments/verbose.md` - verbose logging reference
2. Create `docs/reference/experiments/display.md` - display functions reference
3. Create `docs/reference/experiments/cli.md` - CLI commands reference (replaces existing)
4. Update `docs/reference/castro/index.md` - note Castro uses core infrastructure
5. Update `docs/reference/experiments/index.md` - add new modules

### Expected Outcomes

| Category | Before | After | Delta |
|----------|--------|-------|-------|
| Core experiments/runner | existing | +650 lines | +650 |
| Core experiments/cli | 0 | +500 lines | +500 |
| Castro verbose_logging.py | 430 | 0 (deleted) | -430 |
| Castro display.py | 200 | 30 (re-export) | -170 |
| Castro audit_display.py | 200 | 0 (deleted) | -200 |
| Castro cli.py | 500 | 100 (wrapper) | -400 |
| **Net Core Addition** | | | **+1150** |
| **Net Castro Reduction** | | | **-1200** |

### New Tests Added

| Test File | Test Count |
|-----------|------------|
| test_verbose_core.py | ~20 |
| test_display_core.py | ~15 |
| test_audit_core.py | ~10 |
| test_cli_core.py | ~25 |
| **Total** | **~70** |

### Verification Checklist

- [ ] All API tests pass: `cd api && .venv/bin/python -m pytest`
- [ ] All Castro tests pass: `cd experiments/castro && uv run pytest tests/`
- [ ] Type checking passes: `mypy payment_simulator/experiments/`
- [ ] Castro CLI still works: `castro run exp1 --max-iter 1 --dry-run`
- [ ] Castro replay works: `castro replay <run_id> --verbose`
- [ ] Core CLI works: `payment-sim experiment run experiments/castro/experiments/exp1.yaml --dry-run`
- [ ] Documentation complete and accurate

See [phases/phase_14.md](./phases/phase_14.md) for full TDD test specifications.

---

## Timeline Summary (Updated)

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 0: Bootstrap Bug Fix | 1 day | ✅ COMPLETED |
| Phase 0.5: Event Tracing | 2-3 days | ✅ COMPLETED |
| Phase 1: Preparation | 1-2 days | ✅ COMPLETED |
| Phase 2: LLM Module | 2-3 days | ✅ COMPLETED |
| Phase 3: Experiment Config | 2-3 days | ✅ COMPLETED |
| Phase 4: Experiment Runner | 3-4 days | ✅ COMPLETED |
| Phase 4.5: Bootstrap Integration Tests | 1-2 days | ✅ COMPLETED |
| Phase 4.6: Terminology Cleanup | 0.5 days | ✅ COMPLETED |
| Phase 5: CLI Commands | 2 days | ✅ COMPLETED |
| Phase 6: Castro Migration | 2-3 days | ✅ COMPLETED |
| Phase 7: Documentation | 2-3 days | ✅ COMPLETED |
| Phase 8: LLMConfig Migration | 1 day | ✅ COMPLETED |
| Phase 9: Castro Slimming | 1-2 days | ✅ COMPLETED |
| Phase 10: Deep Integration | 2-3 days | ✅ COMPLETED |
| Phase 11: Infrastructure Generalization | 4-5 days | ✅ COMPLETED |
| Phase 12: Castro Migration | 2-3 days | ✅ COMPLETED |
| Phase 13: StateProvider Migration | 2-3 days | ✅ COMPLETED |
| **Phase 14: Verbose/Audit/CLI to Core** | **3-4 days** | **PLANNED** |

**Phases 0-13 Complete. Phase 14 remaining.**

---

*Document Version 1.6 - Added Phases 13 and 14*
