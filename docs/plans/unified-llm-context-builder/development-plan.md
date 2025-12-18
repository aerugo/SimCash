# Unified LLM Context Builder - Development Plan

**Status**: In Progress (Simplified)
**Created**: 2025-12-18
**Branch**: claude/simcash-paper-draft-6AIrp

## Summary

Unify the LLM context building across all evaluation modes (bootstrap, deterministic-pairwise, deterministic-temporal) so that the LLM receives **identical simulation output** regardless of mode. Only evaluation statistics (metadata) may differ.

## Problem Statement (UPDATED)

### Original Issues (Now Fixed)

| Issue | Status | Commit |
|-------|--------|--------|
| Temporal mode passed `None` for all context | ✅ Fixed | `ba70321` |
| Bootstrap showed extra "initial simulation" stream | ✅ Fixed | `19e537d` |

### Remaining Issue

Bootstrap mode still shows **two simulation traces** (best + worst), while deterministic modes show **one trace**. For true INV-12 compliance, ALL modes should show exactly ONE simulation trace.

### Target State

| Mode | Simulation Output | Evaluation Metadata |
|------|-------------------|---------------------|
| `bootstrap` | 1 trace (best sample) | mean_cost, cost_std, num_samples |
| `deterministic-pairwise` | 1 trace (single sim) | scenario_seed |
| `deterministic-temporal` | 1 trace (single sim) | scenario_seed |

## Critical Invariants

- **INV-11**: Agent Isolation - LLM prompts must only contain Agent X's data
- **INV-12**: LLM Context Identity - All modes provide identical simulation output format. Only evaluation metadata differs.

## Solution Design (Simplified)

Instead of creating a full Protocol abstraction, we simplify the existing code:

### What Changes

1. **Remove `worst_seed_output` from prompts** - Don't show two traces
2. **Remove `worst_seed_*` parameters** - Not passed to PolicyOptimizer.optimize()
3. **Rename conceptually** - Think "simulation_output" not "best_seed_output"

### What Stays the Same

- `AgentSimulationContext` dataclass (keeps `best_seed_output` field name for compatibility)
- `_optimize_agent()` and `_optimize_agent_temporal()` (both already work)
- Existing test infrastructure

### Unified Context (Target)

```
ALL MODES:
┌────────────────────────────────────────────────────┐
│  SIMULATION OUTPUT (identical format)              │
│  - Tick-by-tick events from evaluation             │
│  - Agent-isolated (INV-11)                         │
│  - ONE trace only                                  │
└────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────┐
│  EVALUATION METADATA (mode-specific)               │
│  Bootstrap: mean=$X, std=$Y, N=50 samples          │
│  Deterministic: seed=42, single evaluation         │
└────────────────────────────────────────────────────┘
```

## Implementation Plan

### Phase 1: Remove worst_seed_output from Prompt ✅ DONE

**Files**: `single_agent_context.py`
**Change**: Don't render the "Worst Performing Bootstrap Sample" section

### Phase 2: Stop Passing worst_seed_output

**Files**: `optimization.py`
**Change**: Pass `worst_seed_output=None` in all modes

### Phase 3: Verify with Experiments

**Action**: Run 1 iteration of exp1 (temporal) and exp2 (bootstrap)
**Verify**: LLM receives identical simulation output format

## TDD Test Cases

### test_unified_context.py (Already Created)

- `test_bootstrap_mode_does_not_include_initial_simulation_header` ✅
- `test_all_modes_produce_same_output_format` ✅

### New Tests Needed

- `test_no_worst_seed_output_in_prompt` - Verify worst sample not shown
- `test_evaluation_metadata_differs_by_mode` - Verify stats are mode-specific

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Fix temporal context | ✅ Complete | Commit `ba70321` |
| Remove initial simulation | ✅ Complete | Commit `19e537d` |
| Remove worst_seed_output | 🔄 In Progress | TDD implementation |
| Verify experiments | ⏳ Pending | Run exp1 + exp2 |

## Verification Checklist

After implementation:

- [ ] `pytest tests/experiments/runner/test_unified_context.py` passes
- [ ] `pytest tests/experiments/runner/test_temporal_context.py` passes
- [ ] exp1 (temporal) shows simulation output to LLM
- [ ] exp2 (bootstrap) shows ONE simulation trace (not two)
- [ ] Both experiments show identical output FORMAT
- [ ] mypy type check passes
