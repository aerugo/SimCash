# Extended Policy Evaluation Statistics - Work Notes

**Project**: Extend policy evaluation persistence with settlement rate, delay, cost breakdown, std dev, and CI
**Started**: 2025-12-16
**Branch**: `claude/document-policy-eval-stats-WkXVB`

---

## Session Log

### 2025-12-16 - Initial Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-1, INV-2, INV-5
- Read `docs/plans/CLAUDE.md` - understood planning format
- Read `api/payment_simulator/experiments/persistence/repository.py` - understood current schema
- Read `api/payment_simulator/experiments/runner/optimization.py` - understood where metrics are computed
- Read `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py` - understood CostBreakdown model
- Read `docs/requests/persist-policy-evaluation-metrics.md` - understood original feature request

**Applicable Invariants**:
- INV-1: All costs must be integer cents
- INV-2: Statistics computed from seeded simulations must be deterministic
- INV-5: Changes are additive, should not break replay

**Key Insights**:
- `orch.get_system_metrics()` already returns `settlement_rate` and `avg_delay_ticks`
- `CostBreakdown` model exists in `enriched_models.py` and `SimulationResult`
- Per-agent costs already collected in `per_agent_costs` dict
- User explicitly does NOT want per-sample settlement rates/delays (only aggregate)
- Std dev and CI only meaningful for bootstrap mode (N > 1)

**Completed**:
- [x] Created development plan
- [x] Created work notes
- [ ] Create phase plans

**Next Steps**:
1. Create detailed phase 1 plan
2. Create detailed phase 2 plan
3. Create detailed phase 3 plan
4. Create detailed phase 4 plan

---

## Phase Progress

### Phase 1: Schema Extension
**Status**: Pending
**Started**:
**Completed**:

#### Results
- (pending)

#### Notes
- (pending)

---

## Key Decisions

### Decision 1: JSON columns for complex nested data
**Rationale**: Using JSON columns for `cost_breakdown` and `agent_stats` avoids schema proliferation while maintaining flexibility. DuckDB supports efficient JSON extraction for queries.

### Decision 2: Nullable extended stats fields
**Rationale**: Bootstrap-only stats (`cost_std_dev`, `confidence_interval_95`) should be NULL for deterministic mode rather than storing meaningless zeros.

### Decision 3: Per-agent stats in single JSON column
**Rationale**: Allows any number of agents without schema changes. Each agent's stats stored under their ID key.

### Decision 4: 95% confidence interval using t-distribution
**Rationale**: Standard statistical practice. With N samples: CI = mean ± t_{N-1,0.975} * (std / sqrt(N))

---

## Issues Encountered

(None yet)

---

## Files Modified

### Created
- `docs/plans/policy-eval-extended-stats/development-plan.md` - Main development plan
- `docs/plans/policy-eval-extended-stats/work_notes.md` - This file
- `docs/plans/policy-eval-extended-stats/phases/phase_1.md` - Schema extension
- `docs/plans/policy-eval-extended-stats/phases/phase_2.md` - Metrics capture
- `docs/plans/policy-eval-extended-stats/phases/phase_3.md` - Derived statistics
- `docs/plans/policy-eval-extended-stats/phases/phase_4.md` - Queries and integration

### Modified
- (pending implementation)

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] No new invariants expected (this is additive data capture)

### Other Documentation
- [ ] `docs/requests/persist-policy-evaluation-metrics.md` - Update status of extended stats
