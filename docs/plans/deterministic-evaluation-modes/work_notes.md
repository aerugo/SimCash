# Deterministic Evaluation Modes - Work Notes

**Project**: Implement deterministic-temporal and deterministic-pairwise evaluation modes
**Started**: 2025-12-16
**Branch**: claude/clarify-simcash-rtgs-dHZAS

---

## Session Log

### 2025-12-16 - Initial Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-2, INV-9
- Read `api/payment_simulator/experiments/runner/optimization.py` - understood seed usage inconsistency
- Read `api/payment_simulator/experiments/config/experiment_config.py` - understood current mode validation

**Applicable Invariants**:
- INV-2: Determinism is Sacred - Both modes must be reproducible with same seed
- INV-9: Policy Evaluation Identity - Seed used for display must match seed used for acceptance

**Key Insights**:
- `_evaluate_policies()` uses `master_seed` (constant across iterations)
- `_evaluate_policy_pair()` uses `get_iteration_seed()` (varies per iteration)
- This causes displayed cost ≠ acceptance decision cost
- Solution: Always use iteration-varying seed for consistency

**Completed**:
- [x] Analyzed current state of optimization.py
- [x] Identified the seed inconsistency bug
- [x] Created development plan
- [x] Created work notes

**Next Steps**:
1. Create Phase 1 detailed plan
2. Write failing tests for seed consistency
3. Fix seed inconsistency in `_evaluate_policies()`

---

## Phase Progress

### Phase 1: Fix Seed Inconsistency
**Status**: Pending
**Started**:
**Completed**:

#### Results
- TBD

#### Notes
- TBD

---

## Key Decisions

### Decision 1: Always Use Iteration-Varying Seed
**Rationale**: The comment in `_evaluate_policies()` claims using master_seed "ensures policy changes are the ONLY variable affecting cost". However, this is wrong because `_evaluate_policy_pair()` uses a different seed, so the cost displayed doesn't match the cost used for acceptance. Using iteration-varying seed everywhere maintains consistency.

### Decision 2: Backward Compatibility for `deterministic`
**Rationale**: Existing experiment configs use `mode: deterministic`. Rather than breaking them, we'll treat plain `deterministic` as an alias for `deterministic-pairwise`.

### Decision 3: Temporal Mode Skips Paired Evaluation
**Rationale**: In temporal mode, we don't need to run both old and new policy on the same seed. We simply run the current policy, compare to previous iteration's cost, and decide. This is simpler and matches the "game-like" mental model where agents only see historical outcomes.

---

## Issues Encountered

*None yet*

---

## Files Modified

### Created
- `docs/plans/deterministic-evaluation-modes/development-plan.md` - Development plan
- `docs/plans/deterministic-evaluation-modes/work_notes.md` - This file

### Modified
- *TBD during implementation*

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] No new invariants expected

### Other Documentation
- [ ] `docs/reference/experiments/configuration.md` - Document new evaluation modes
