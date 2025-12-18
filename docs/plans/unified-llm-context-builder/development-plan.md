# Unified LLM Context Builder - Development Plan

**Status**: In Progress
**Created**: 2025-12-18
**Branch**: claude/simcash-paper-draft-6AIrp

## Summary

Unify the LLM context building across all evaluation modes (bootstrap, deterministic-pairwise, deterministic-temporal) so that the LLM receives identical context EXCEPT for mode-specific evaluation differences. Currently, `deterministic-temporal` mode provides NO simulation output to the LLM, causing it to optimize blindly.

## Problem Statement

### Current Behavior

| Mode | Context Building | Simulation Output | LLM Visibility |
|------|------------------|-------------------|----------------|
| `bootstrap` | `BootstrapLLMContext` + `AgentSimulationContext` | 3 streams (initial, best, worst) | ✅ Full |
| `deterministic-pairwise` | `AgentSimulationContext.best_seed_output` | 1 stream (single sim events) | ✅ Works |
| `deterministic-temporal` | `_optimize_agent_temporal()` bypasses all | `None` for everything | ❌ Broken |

### Root Cause (Single Issue)

**`_optimize_agent_temporal()` bypasses context building entirely** (line 2356-2365):
```python
opt_result = await self._policy_optimizer.optimize(
    ...
    events=None,  # Temporal mode doesn't use event trace
    best_seed_output=None,
    worst_seed_output=None,
    ...
)
```

Note: `deterministic-pairwise` works correctly. It uses `AgentSimulationContext.best_seed_output` via the fallback in `_optimize_agent()` (lines 1950-1951):
```python
elif agent_context and agent_context.best_seed_output:
    combined_best_output = agent_context.best_seed_output
```

`bootstrap` mode adds additional streams via `BootstrapLLMContext` (initial simulation + best/worst comparison), but deterministic-pairwise provides adequate simulation visibility for LLM optimization.

### Impact

The LLM cannot learn strategic dynamics (e.g., incoming payments can cover outgoing) without seeing simulation output. This explains:
- Exp2 (bootstrap): A=11%, B=11% → Matches Castro ✅
- Exp1 (temporal): A=80%, B=40% → Inverted from Castro ❌

## Critical Invariants to Respect

- **INV-9**: Policy Evaluation Identity - Policy parameter extraction must be identical across all paths
- **INV-10**: Scenario Config Interpretation Identity - Scenario extraction must be identical across all paths
- **INV-11**: Agent Isolation - LLM prompts must only contain Agent X's data

### NEW INV Proposed

- **INV-12**: LLM Context Identity - For any agent A and simulation result R, the LLM context MUST contain identical simulation output formatting regardless of evaluation mode. Only mode-specific evaluation metadata may differ.

## Current State Analysis

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `experiments/runner/optimization.py` | Temporal mode passes `None` for outputs | Use unified context builder for all modes |
| `ai_cash_mgmt/prompts/llm_context_protocol.py` | Does not exist | CREATE: Protocol definition |
| `ai_cash_mgmt/prompts/unified_context_builder.py` | Does not exist | CREATE: Single implementation |
| `experiments/runner/optimization.py` | Bootstrap-specific context building | Refactor to use unified builder |

### Current Architecture

```
Bootstrap Mode:
  _run_initial_simulation() → InitialSimulationResult
  _create_bootstrap_samples() → list[BootstrapSample]
  _build_agent_contexts() → dict[str, AgentSimulationContext]
  _optimize_agent() receives: best_seed_output, worst_seed_output ✅

Deterministic-Temporal Mode:
  _evaluate_policies() → single simulation result
  _optimize_agent_temporal() receives: None, None ❌
```

## Solution Design

### Unified Context Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      LLMContextBuilderProtocol                          │
│  build_context(agent_id, enriched_results, iteration) → LLMAgentContext │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│  Bootstrap      │    │  Deterministic       │    │  Deterministic       │
│  ContextBuilder │    │  Pairwise Builder    │    │  Temporal Builder    │
│  (N samples)    │    │  (1 sample)          │    │  (1 sample)          │
└────────┬────────┘    └──────────┬───────────┘    └──────────┬───────────┘
         │                        │                           │
         │ ┌──────────────────────┴───────────────────────────┘
         │ │
         ▼ ▼
┌───────────────────────────────────────────────────────────────┐
│                      LLMAgentContext                          │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  SHARED (identical across modes):                       │  │
│  │  - simulation_output: str  ← format_filtered_output()   │  │
│  │  - cost_breakdown: dict[str, int]                       │  │
│  │  - iteration_history: list[IterationRecord]             │  │
│  │  - current_cost: int                                    │  │
│  └─────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  MODE-SPECIFIC (evaluation metadata):                   │  │
│  │  Bootstrap:                                             │  │
│  │    - best_seed, worst_seed, best_seed_output, ...       │  │
│  │    - num_samples, mean_cost, cost_std                   │  │
│  │  Deterministic-Pairwise:                                │  │
│  │    - scenario_seed, policy_accepted, delta_cost         │  │
│  │  Deterministic-Temporal:                                │  │
│  │    - scenario_seed, iteration_cost_history              │  │
│  └─────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────┘
```

### What Each Mode Provides (Target State)

| Field | Bootstrap | Det-Pairwise | Det-Temporal |
|-------|-----------|--------------|--------------|
| `simulation_output` | ✅ best sample events | ✅ single sim events | ✅ single sim events |
| `cost_breakdown` | ✅ averaged | ✅ single | ✅ single |
| `iteration_history` | ✅ full | ✅ full | ✅ full |
| `mode_metadata.best_seed` | ✅ | - | - |
| `mode_metadata.worst_seed` | ✅ | - | - |
| `mode_metadata.num_samples` | ✅ N | ✅ 1 | ✅ 1 |
| `mode_metadata.scenario_seed` | - | ✅ | ✅ |
| `mode_metadata.policy_accepted` | - | ✅ (per iteration) | - |

### Key Design Decisions

1. **Protocol-based abstraction**: Define `LLMContextBuilderProtocol` that all modes implement
2. **Shared formatting**: All modes use the same `format_filtered_output()` for simulation events
3. **Simulation output is NEVER None**: All modes must provide simulation visibility
4. **Mode-specific metadata only**: Bootstrap adds best/worst comparison; pairwise adds acceptance; temporal adds cross-iteration
5. **Single entry point**: Remove `_optimize_agent_temporal()` - use unified `_optimize_agent()` for all modes

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Define Protocol and data types | Type safety | 3 tests |
| 2 | Implement unified builder | Context equality | 5 tests |
| 3 | Integrate into optimization loop | End-to-end | 4 tests |
| 4 | Verify Castro experiments | Regression | 3 tests |

## Phase 1: Protocol and Data Types

**Goal**: Define the contract for unified LLM context building

### Deliverables
1. `LLMContextBuilderProtocol` in `ai_cash_mgmt/prompts/llm_context_protocol.py`
2. `LLMAgentContext` dataclass with all required fields
3. Unit tests for data structure validation

### TDD Approach
1. Write tests for `LLMAgentContext` creation and validation
2. Define Protocol with required methods
3. Verify type checking passes

### Success Criteria
- [ ] Protocol defined with `build_context()` method
- [ ] `LLMAgentContext` contains: simulation_output, cost_breakdown, iteration_history
- [ ] Type checking passes
- [ ] INV-11 (Agent Isolation) enforced in Protocol docstring

## Phase 2: Unified Context Builder Implementation

**Goal**: Single implementation that works for all evaluation modes

### Deliverables
1. `UnifiedLLMContextBuilder` class
2. Mode-specific adapters (if needed)
3. Tests verifying context identity across modes

### TDD Approach
1. Write test: same simulation result → same context output
2. Implement builder with mode detection
3. Verify format_filtered_output used consistently

### Success Criteria
- [ ] Bootstrap mode produces same simulation_output format
- [ ] Deterministic modes produce same simulation_output format
- [ ] Only mode-specific metadata differs
- [ ] INV-12 (LLM Context Identity) verified by tests

## Phase 3: Integration into Optimization Loop

**Goal**: Replace mode-specific context building with unified builder

### Deliverables
1. Refactored `_optimize_agent()` to use unified builder
2. Refactored `_optimize_agent_temporal()` to use unified builder
3. Integration tests verifying no behavior change for bootstrap mode

### TDD Approach
1. Write test: bootstrap mode behavior unchanged
2. Write test: deterministic-temporal now receives simulation output
3. Refactor optimization loop
4. Verify all tests pass

### Success Criteria
- [ ] Bootstrap mode behavior unchanged (regression test)
- [ ] Deterministic-temporal receives full simulation context
- [ ] All existing tests pass
- [ ] New INV-12 tests pass

## Phase 4: Verify Castro Experiments

**Goal**: Confirm fix improves experiment results

### Deliverables
1. Re-run Exp1 with fixed context builder
2. Document results compared to Castro predictions
3. Update experiment configs if needed

### Success Criteria
- [ ] Exp1 converges closer to Castro prediction (A≈0%, B≈20%)
- [ ] Exp2 remains stable (already works)
- [ ] Exp3 shows improved stability

## Testing Strategy

### Unit Tests
- `test_llm_agent_context_creation`: Verify dataclass fields
- `test_protocol_compliance`: Verify implementations satisfy protocol
- `test_format_identity`: Same events → same formatted output

### Integration Tests
- `test_bootstrap_context_unchanged`: Regression for bootstrap mode
- `test_temporal_receives_output`: Temporal mode now gets simulation output
- `test_context_agent_isolation`: INV-11 compliance

### Identity/Invariant Tests
- `test_inv12_context_identity`: Same simulation → same context (except metadata)

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - Add INV-12: LLM Context Identity
- [ ] `api/CLAUDE.md` - Document unified context builder pattern
- [ ] Docstrings in new files

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | Protocol and data types |
| Phase 2 | Pending | Unified builder implementation |
| Phase 3 | Pending | Integration |
| Phase 4 | Pending | Verification |
