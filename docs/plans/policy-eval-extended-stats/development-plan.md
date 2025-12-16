# Extended Policy Evaluation Statistics - Development Plan

**Status**: Planning
**Created**: 2025-12-16
**Branch**: `claude/document-policy-eval-stats-WkXVB`

## Summary

Extend the `PolicyEvaluationRecord` to capture additional evaluation metrics that are currently computed but not persisted: settlement rate, average delay, cost breakdown, standard deviation, and confidence intervals - all at both total and per-agent granularity.

## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All costs stored as integer cents
- **INV-2**: Determinism is Sacred - Seeds stored for reproducibility; statistics computed deterministically
- **INV-5**: Replay Identity - Extended stats should not break existing replay functionality (additive change only)

## Current State Analysis

The `PolicyEvaluationRecord` currently stores:
- `old_cost`, `new_cost` (mean costs in cents)
- `delta_sum`, `num_samples`
- `sample_details` (bootstrap only: per-sample costs and deltas)
- `scenario_seed` (deterministic only)

**What's computed but NOT persisted:**

| Metric | Where Computed | Currently Stored? |
|--------|----------------|-------------------|
| Settlement rate (total) | `optimization.py:555` via `orch.get_system_metrics()` | No |
| Average delay (total) | `optimization.py:556` via `orch.get_system_metrics()` | No |
| Cost breakdown | `optimization.py:591-599` as `CostBreakdown` | No |
| Per-agent costs | `optimization.py:547` in `per_agent_costs` dict | No |
| Cost std dev | `context_builder.py:236` for LLM context | No |
| Confidence intervals | Not computed | No |

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `api/payment_simulator/experiments/persistence/repository.py` | `PolicyEvaluationRecord` with basic fields | Add extended fields for stats |
| `api/payment_simulator/experiments/runner/optimization.py` | `_save_policy_evaluation()` with basic fields | Capture and pass extended stats |
| `api/payment_simulator/experiments/analysis/charting.py` | Uses basic cost data | Expose extended stats via queries |

## Solution Design

### Data Model Extension

```
PolicyEvaluationRecord (extended)
├── Core fields (existing)
│   ├── run_id, iteration, agent_id
│   ├── evaluation_mode, proposed_policy
│   ├── old_cost, new_cost, context_simulation_cost
│   ├── accepted, acceptance_reason
│   ├── delta_sum, num_samples
│   ├── sample_details, scenario_seed
│   └── timestamp
│
└── Extended Stats (NEW)
    ├── System-wide metrics
    │   ├── settlement_rate: float
    │   ├── avg_delay: float
    │   ├── cost_breakdown: JSON {delay, overdraft, deadline_penalty, eod_penalty}
    │   ├── cost_std_dev: int | None (bootstrap only)
    │   └── confidence_interval_95: [int, int] | None (bootstrap only)
    │
    └── Per-agent metrics
        └── agent_stats: JSON {
              "AGENT_ID": {
                "cost": int,
                "settlement_rate": float,
                "avg_delay": float,
                "cost_breakdown": {...}
              }
            }
```

### Key Design Decisions

1. **Store aggregate stats at record level, not per-sample**: User explicitly requested NOT to capture settlement rates and delays per sample - only totals and per-agent aggregates.

2. **JSON columns for complex structures**: Use JSON for `cost_breakdown` and `agent_stats` to avoid schema proliferation while maintaining queryability (DuckDB supports JSON extraction).

3. **Nullable stats fields**: `cost_std_dev` and `confidence_interval_95` are only meaningful for bootstrap mode (N > 1 samples).

4. **Per-agent stats keyed by agent_id**: Allows flexible multi-agent analysis without fixed schema.

5. **Compute CI at 95% level using t-distribution**: Standard statistical practice for sample sizes.

## Test Matrix Reference

See **`test-matrix.md`** for the complete 94-test matrix covering all combinations of:
- Evaluation mode (deterministic vs bootstrap)
- Metric type (settlement_rate, avg_delay, cost_breakdown, std_dev, CI)
- Granularity (total vs per-agent)
- Agent count (single vs multi-agent)

## Phase Overview

| Phase | Description | TDD Focus | Tests (from matrix) |
|-------|-------------|-----------|---------------------|
| 1 | Extend `PolicyEvaluationRecord` and DB schema | Schema validation, round-trip persistence | 18 tests (PR-*) |
| 2 | Capture metrics during evaluation | All mode × metric × granularity combinations | 56 tests (DT-*, DA-*, DM-*, BT-*, BA-*, BM-*) |
| 3 | Compute derived statistics (std dev, CI) | Statistical correctness, edge cases | 12 tests (EC-*) |
| 4 | Queries and cross-validation | End-to-end, cross-validation | 8 tests (CV-*) |

---

## Phase 1: Schema Extension

**Goal**: Extend `PolicyEvaluationRecord` dataclass and database schema with new fields.

### Deliverables
1. Extended `PolicyEvaluationRecord` dataclass
2. Updated database schema with new columns
3. Updated `_row_to_policy_evaluation_record()` mapping

### TDD Approach
1. Write tests verifying new fields can be persisted and retrieved
2. Add columns and update dataclass
3. Verify backward compatibility with existing data

### Success Criteria
- [ ] `PolicyEvaluationRecord` has all new fields with correct types
- [ ] Database schema includes new columns (nullable for backward compat)
- [ ] Existing records without extended stats load correctly (null handling)
- [ ] New records with extended stats round-trip correctly

---

## Phase 2: Metrics Capture

**Goal**: Capture extended metrics during policy evaluation simulations.

### Deliverables
1. Extended `SimulationResult` or new struct to carry metrics
2. Updated `_run_single_simulation()` to capture system metrics
3. Updated `_evaluate_policy_pair()` to aggregate metrics

### TDD Approach
1. Write tests verifying metrics are captured from orchestrator
2. Update simulation code to extract and return metrics
3. Verify metrics are correct for both deterministic and bootstrap modes

### Success Criteria
- [ ] `settlement_rate` and `avg_delay` captured from `orch.get_system_metrics()`
- [ ] `cost_breakdown` captured from per-agent cost queries
- [ ] Per-agent metrics captured for all agents in evaluation
- [ ] Metrics propagate through to `_save_policy_evaluation()`

---

## Phase 3: Derived Statistics

**Goal**: Compute standard deviation and confidence intervals for bootstrap evaluations.

### Deliverables
1. `compute_cost_statistics()` function for std dev and CI
2. Integration into `_evaluate_policy_pair()` for bootstrap mode
3. Handle edge cases (N=1, N=0)

### TDD Approach
1. Write tests with known sample data to verify statistical calculations
2. Implement statistics computation
3. Verify edge cases handled gracefully

### Success Criteria
- [ ] `cost_std_dev` computed correctly for bootstrap samples
- [ ] 95% CI computed using t-distribution formula
- [ ] Deterministic mode returns `None` for these fields
- [ ] Edge cases (single sample, zero samples) handled

---

## Phase 4: Queries and Integration

**Goal**: Expose extended stats via repository queries and update charting.

### Deliverables
1. Updated query methods to include extended stats
2. Optional: charting enhancements to use new data
3. Documentation of new fields

### TDD Approach
1. Write tests for query methods returning extended stats
2. Update queries
3. Verify integration with charting

### Success Criteria
- [ ] `get_policy_evaluations()` returns records with extended stats
- [ ] Extended stats accessible for analysis
- [ ] No regression in existing charting functionality

---

## Testing Strategy

### Unit Tests
- Schema validation: Field types, nullable handling
- Statistics computation: Known inputs produce expected outputs
- Persistence round-trip: Save and load with extended fields

### Integration Tests
- Full experiment run captures extended stats
- Bootstrap vs deterministic mode differences
- Multi-agent scenarios

### Identity/Invariant Tests
- INV-1: All costs remain integer cents
- INV-2: Same seed produces same stats

---

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - No new invariants expected
- [ ] `docs/requests/persist-policy-evaluation-metrics.md` - Mark extended stats as implemented

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | Schema extension |
| Phase 2 | Pending | Metrics capture |
| Phase 3 | Pending | Statistics computation |
| Phase 4 | Pending | Queries and integration |
