# Recover Sophisticated Optimizer Prompt for Experiments

**Date**: 2025-12-12
**Status**: ✅ Completed
**Priority**: High
**Completion Date**: 2025-12-12

> **Implementation**: Completed in commit `4ddaf8b`. See [Optimizer Prompt Architecture](../reference/ai_cash_mgmt/optimizer-prompt.md) for full documentation.

## Executive Summary

The Castro experiment module contained a sophisticated optimizer prompt system that was deleted in commit `286eb52`. This plan documents what was deleted, what already exists in core modules (much of which is unused), and proposes a recovery strategy that wires up existing components rather than recreating deleted code.

**Key Finding**: Most of the sophisticated functionality already exists in unused core modules. The primary work is **integration**, not reimplementation.

---

## Table of Contents

1. [What Was Deleted](#1-what-was-deleted)
2. [What Already Exists in Core](#2-what-already-exists-in-core)
3. [Gap Analysis](#3-gap-analysis)
4. [Integration Plan](#4-integration-plan)
5. [Implementation Phases](#5-implementation-phases)
6. [File Locations Reference](#6-file-locations-reference)

---

## 1. What Was Deleted

The following files were deleted in commit `286eb52` (Phase 18: Delete Castro Python code):

### 1.1 `verbose_capture.py`
Captured tick-by-tick events from simulations with per-agent filtering.

```python
# Key classes (deleted):
class VerboseOutput:
    """Stores events by tick with filter_for_agent() method."""
    events_by_tick: dict[int, list[dict]]
    def filter_for_agent(self, agent_id: str) -> str: ...

class VerboseOutputCapture:
    """Captures events during simulation."""
    def run_and_capture(self, orch, ticks) -> VerboseOutput: ...
```

**Git retrieval**: `git show 286eb52^:experiments/castro/castro/verbose_capture.py`

### 1.2 `context_builder.py`
Built per-agent context from Monte Carlo bootstrap results.

```python
# Key classes (deleted):
class AgentSimulationContext:
    """Per-agent statistics with best/worst seed outputs."""
    best_seed: int
    best_seed_cost: int
    best_seed_output: str | None  # Filtered verbose output
    worst_seed: int
    worst_seed_cost: int
    worst_seed_output: str | None
    mean_cost: float
    cost_std: float

class BootstrapContextBuilder:
    """Builds context from bootstrap results."""
    def get_best_seed_for_agent(self, agent_id: str) -> tuple[int, int]: ...
    def get_worst_seed_for_agent(self, agent_id: str) -> tuple[int, int]: ...
    def get_best_seed_verbose_output(self, agent_id: str) -> str | None: ...
    def build_context_for_agent(self, ...) -> SingleAgentContext: ...
```

**Git retrieval**: `git show 286eb52^:experiments/castro/castro/context_builder.py`

### 1.3 `runner.py` (Integration)
Wired everything together in the experiment runner.

**Key integration points (deleted)**:
1. Created `VerboseOutputCapture` during simulation
2. Stored verbose outputs with `SimulationResult`
3. Created `BootstrapContextBuilder` from results
4. Called `builder.get_agent_simulation_context(agent_id)` for each agent
5. Passed `best_seed_output`, `worst_seed_output` to `PolicyOptimizer.optimize()`

**Git retrieval**: `git show 286eb52^:experiments/castro/castro/runner.py`

---

## 2. What Already Exists in Core

### 2.1 `EnrichedBootstrapContextBuilder` ✅ EXISTS
**File**: `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py`

This is essentially the same as the deleted `BootstrapContextBuilder`, but works with `EnrichedEvaluationResult` objects:

```python
class EnrichedBootstrapContextBuilder:
    """Builds LLM context directly from enriched bootstrap results."""

    def get_best_result(self) -> EnrichedEvaluationResult: ...
    def get_worst_result(self) -> EnrichedEvaluationResult: ...
    def build_agent_context(self) -> AgentSimulationContext: ...
    def format_event_trace_for_llm(self, result, max_events=500) -> str: ...

@dataclass
class AgentSimulationContext:  # Also exists here!
    agent_id: str
    best_seed: int
    best_seed_cost: int
    best_seed_output: str | None
    worst_seed: int
    worst_seed_cost: int
    worst_seed_output: str | None
    mean_cost: int
    cost_std: int
```

**Status**: Fully implemented but **UNUSED** by `OptimizationLoop`

### 2.2 `EnrichedEvaluationResult` ✅ EXISTS
**File**: `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py`

Contains event traces for LLM context:

```python
@dataclass(frozen=True)
class EnrichedEvaluationResult:
    sample_idx: int
    seed: int
    total_cost: int
    settlement_rate: float
    avg_delay: float
    event_trace: tuple[BootstrapEvent, ...]  # Event capture!
    cost_breakdown: CostBreakdown

@dataclass(frozen=True)
class BootstrapEvent:
    tick: int
    event_type: str
    details: dict[str, Any]

@dataclass(frozen=True)
class CostBreakdown:
    delay_cost: int
    overdraft_cost: int
    deadline_penalty: int
    eod_penalty: int
```

**Status**: Defined but **NOT POPULATED** during evaluation

### 2.3 `PolicyOptimizer` ✅ EXISTS & SUPPORTS EXTENDED CONTEXT
**File**: `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py`

Already accepts all extended context parameters:

```python
async def optimize(
    self,
    agent_id: str,
    current_policy: dict[str, Any],
    current_iteration: int,
    current_metrics: dict[str, Any],
    llm_client: LLMClientProtocol,
    llm_model: str,
    current_cost: float = 0.0,
    iteration_history: list[SingleAgentIterationRecord] | None = None,
    best_seed_output: str | None = None,      # ← Extended context
    worst_seed_output: str | None = None,     # ← Extended context
    best_seed: int = 0,                        # ← Extended context
    worst_seed: int = 0,                       # ← Extended context
    best_seed_cost: int = 0,                   # ← Extended context
    worst_seed_cost: int = 0,                  # ← Extended context
    cost_breakdown: dict[str, int] | None = None,  # ← Extended context
    cost_rates: dict[str, Any] | None = None,      # ← Extended context
    debug_callback: DebugCallback | None = None,
) -> OptimizationResult: ...
```

**Status**: Fully implemented, already uses `build_single_agent_context()`, but **NEVER CALLED** by `OptimizationLoop`

### 2.4 `SingleAgentContextBuilder` ✅ EXISTS
**File**: `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py`

The sophisticated 50k+ token prompt builder with:
- Cost breakdown analysis
- Optimization guidance
- Simulation output sections (best/worst seed)
- Iteration history with BEST/KEPT/REJECTED status
- Parameter trajectories

**Status**: Fully implemented, used by `PolicyOptimizer`, but `PolicyOptimizer` is **NOT USED** by `OptimizationLoop`

### 2.5 `EventFilter` ✅ EXISTS
**File**: `api/payment_simulator/cli/filters.py`

Per-agent event filtering with comprehensive agent matching:

```python
class EventFilter:
    def __init__(self, agent_id: str | None = None, ...): ...
    def matches(self, event: dict, tick: int) -> bool: ...
```

Handles:
- `agent_id`, `sender_id`, `sender` fields
- `agent_a`, `agent_b` for LSM bilateral
- `agents` list for LSM cycle
- Receiver matching for settlement events (incoming liquidity)

**Status**: Fully implemented, used by replay/run CLI

### 2.6 `VerboseConfig` & `VerboseLogger` ✅ EXISTS
**File**: `api/payment_simulator/experiments/runner/verbose.py`

Already migrated from Castro:

```python
@dataclass
class VerboseConfig:
    iterations: bool = False
    policy: bool = False
    bootstrap: bool = False
    llm: bool = False
    rejections: bool = False
    debug: bool = False

class VerboseLogger:
    def log_iteration_start(self, iteration, total_cost): ...
    def log_policy_change(self, agent_id, old_policy, new_policy, ...): ...
    def log_bootstrap_evaluation(self, seed_results, mean_cost, std_cost, ...): ...
    def log_llm_call(self, metadata): ...
    def log_rejection(self, rejection): ...
```

**Status**: Fully implemented, used by `OptimizationLoop`

---

## 3. Gap Analysis

### 3.1 Current `OptimizationLoop` Issues
**File**: `api/payment_simulator/experiments/runner/optimization.py`

| Missing Feature | Status | Root Cause |
|----------------|--------|------------|
| Rich LLM prompts | ❌ | Uses inline prompt, not `PolicyOptimizer` |
| Best/worst seed outputs | ❌ | Doesn't use `EnrichedBootstrapContextBuilder` |
| Event capture | ❌ | `_run_single_simulation()` discards events |
| Cost breakdown | ❌ | Not extracted from simulation |
| Iteration history tracking | ❌ | Not building `SingleAgentIterationRecord` |
| Per-agent filtering | ❌ | Not using `EventFilter` |

### 3.2 Current `_run_single_simulation()` vs Required

**Current** (line ~455):
```python
def _run_single_simulation(self, seed: int) -> tuple[int, dict[str, int]]:
    # Runs simulation, extracts only total cost and per-agent costs
    # DISCARDS all events
    for _ in range(total_ticks):
        orch.tick()
    # No event capture!
```

**Required**:
```python
def _run_single_simulation(self, seed: int, capture_events: bool = False) -> SimulationResult:
    # Run simulation
    for tick in range(total_ticks):
        orch.tick()
        if capture_events:
            events_by_tick[tick] = orch.get_tick_events(tick)

    # Return rich result with events
    return SimulationResult(
        total_cost=total_cost,
        per_agent_costs=per_agent_costs,
        event_trace=events_by_tick if capture_events else None,
        cost_breakdown=cost_breakdown,
    )
```

### 3.3 Current `_optimize_agent()` vs Required

**Current** (line ~635):
```python
async def _optimize_agent(self, agent_id: str, current_cost: int) -> None:
    # Uses inline prompt - NOT the sophisticated context builder
    prompt = f"""Optimize policy for agent {agent_id}.
    Current cost: ${current_cost / 100:.2f}
    Iteration: {self._current_iteration}
    ..."""

    new_policy = await self._llm_client.generate_policy(prompt, ...)
```

**Required**:
```python
async def _optimize_agent(self, agent_id: str, agent_context: AgentSimulationContext) -> None:
    # Use core PolicyOptimizer with rich context
    result = await self._policy_optimizer.optimize(
        agent_id=agent_id,
        current_policy=self._policies[agent_id],
        current_iteration=self._current_iteration,
        current_metrics=current_metrics,
        llm_client=self._llm_client,
        llm_model=self._config.llm.model,
        current_cost=agent_context.mean_cost,
        iteration_history=self._iteration_history.get(agent_id, []),
        best_seed_output=agent_context.best_seed_output,
        worst_seed_output=agent_context.worst_seed_output,
        best_seed=agent_context.best_seed,
        worst_seed=agent_context.worst_seed,
        best_seed_cost=agent_context.best_seed_cost,
        worst_seed_cost=agent_context.worst_seed_cost,
        cost_breakdown=self._cost_breakdown,
        cost_rates=self._cost_rates,
        debug_callback=self._debug_callback,
    )
```

---

## 4. Integration Plan

### Strategy: Wire Up Existing Components

Instead of recreating deleted code, we will:

1. **Enhance `_run_single_simulation()`** to optionally capture events
2. **Create `EnrichedEvaluationResult`** objects during evaluation
3. **Use `EnrichedBootstrapContextBuilder`** to build agent contexts
4. **Replace inline prompt with `PolicyOptimizer`** calls
5. **Track `SingleAgentIterationRecord`** history

### Data Flow (Proposed)

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OptimizationLoop.run()                          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  _evaluate_policies() with event capture                            │
│    for sample in samples:                                           │
│      result = _run_simulation_with_events(seed)                     │
│      enriched_results.append(EnrichedEvaluationResult(              │
│        seed=seed,                                                   │
│        total_cost=result.total_cost,                                │
│        event_trace=result.events,                                   │
│        cost_breakdown=result.cost_breakdown,                        │
│      ))                                                             │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  For each agent_id in optimized_agents:                             │
│    builder = EnrichedBootstrapContextBuilder(enriched_results,      │
│                                               agent_id)             │
│    agent_context = builder.build_agent_context()                    │
│      ↳ Computes best/worst seed per agent                          │
│      ↳ Formats event traces for LLM                                │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PolicyOptimizer.optimize()                                         │
│    ↳ build_single_agent_context()                                   │
│      ↳ Cost analysis with breakdown                                │
│      ↳ Optimization guidance                                       │
│      ↳ Best/worst seed verbose outputs                             │
│      ↳ Iteration history with ACCEPTED/REJECTED status             │
│      ↳ Parameter trajectories                                      │
│    ↳ LLM call with rich 50k+ token prompt                          │
│    ↳ Validation with retry on errors                               │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 5. Implementation Phases

### Phase 1: Add Event Capture to Simulation
**File**: `api/payment_simulator/experiments/runner/optimization.py`

**Changes**:
1. Add `_run_simulation_with_events()` method that captures tick events
2. Create `BootstrapEvent` objects from FFI events
3. Extract `CostBreakdown` from agent accumulated costs
4. Return `EnrichedEvaluationResult` objects

**Effort**: ~2-3 hours

### Phase 2: Integrate EnrichedBootstrapContextBuilder
**File**: `api/payment_simulator/experiments/runner/optimization.py`

**Changes**:
1. Import `EnrichedBootstrapContextBuilder` from `ai_cash_mgmt.bootstrap`
2. In `_evaluate_policies()`:
   - Collect `EnrichedEvaluationResult` objects
   - Create builder for each agent
   - Store `AgentSimulationContext` for use in optimization
3. Add per-agent event filtering using `EventFilter`

**Effort**: ~2 hours

### Phase 3: Replace Inline Prompt with PolicyOptimizer
**File**: `api/payment_simulator/experiments/runner/optimization.py`

**Changes**:
1. Import and initialize `PolicyOptimizer` from `ai_cash_mgmt.optimization`
2. Track `SingleAgentIterationRecord` history per agent
3. Replace `_optimize_agent()` implementation:
   - Remove inline prompt
   - Call `PolicyOptimizer.optimize()` with full context
   - Track iteration history with acceptance status

**Effort**: ~3-4 hours

### Phase 4: Add Iteration History Tracking
**Files**:
- `api/payment_simulator/experiments/runner/optimization.py`

**Changes**:
1. Create `SingleAgentIterationRecord` after each iteration
2. Track policy changes via `compute_policy_diff()`
3. Mark iterations as `is_best_so_far` when cost improves
4. Store `cost_breakdown` per iteration

**Effort**: ~2 hours

### Phase 5: Tests
**Files**:
- `api/tests/experiments/test_enriched_context_integration.py`
- `api/tests/experiments/test_optimization_with_events.py`

**Test coverage**:
1. Event capture during simulation
2. EnrichedBootstrapContextBuilder integration
3. PolicyOptimizer produces rich prompts
4. Iteration history tracking
5. End-to-end with mock LLM

**Effort**: ~3-4 hours

---

## 6. File Locations Reference

### Existing Core Components (to use)

| Component | File | Status |
|-----------|------|--------|
| `EnrichedBootstrapContextBuilder` | `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` | ✅ Unused |
| `AgentSimulationContext` | `api/payment_simulator/ai_cash_mgmt/bootstrap/context_builder.py` | ✅ Unused |
| `EnrichedEvaluationResult` | `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` | ✅ Unused |
| `BootstrapEvent` | `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` | ✅ Unused |
| `CostBreakdown` | `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` | ✅ Unused |
| `PolicyOptimizer` | `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py` | ✅ Unused |
| `SingleAgentContextBuilder` | `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` | ✅ Used by PolicyOptimizer |
| `SingleAgentContext` | `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` | ✅ Used |
| `SingleAgentIterationRecord` | `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` | ✅ Unused |
| `EventFilter` | `api/payment_simulator/cli/filters.py` | ✅ Used by CLI |
| `VerboseConfig` | `api/payment_simulator/experiments/runner/verbose.py` | ✅ Used |
| `VerboseLogger` | `api/payment_simulator/experiments/runner/verbose.py` | ✅ Used |

### Files to Modify

| File | Changes |
|------|---------|
| `api/payment_simulator/experiments/runner/optimization.py` | Main integration work |

### Deleted Files (for reference only)

| File | Git Command |
|------|-------------|
| `verbose_capture.py` | `git show 286eb52^:experiments/castro/castro/verbose_capture.py` |
| `context_builder.py` | `git show 286eb52^:experiments/castro/castro/context_builder.py` |
| `runner.py` | `git show 286eb52^:experiments/castro/castro/runner.py` |

---

## Summary

**Total Estimated Effort**: 12-15 hours

**Key Insight**: The sophisticated optimizer prompt functionality is ~80% already implemented in unused core modules. The primary work is wiring up existing components in `OptimizationLoop`, not reimplementing deleted code.

**Benefits of this approach**:
1. Leverages battle-tested core components
2. Maintains single source of truth (no duplication)
3. All experiments benefit from improvements
4. Cleaner architecture than deleted Castro code
