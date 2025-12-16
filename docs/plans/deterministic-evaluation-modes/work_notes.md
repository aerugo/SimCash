# Deterministic Evaluation Modes - Work Notes

**Project**: Implement deterministic-temporal and deterministic-pairwise evaluation modes
**Started**: 2025-12-16
**Completed**: 2025-12-16
**Branch**: claude/clarify-simcash-rtgs-dHZAS

---

## Session Log

### 2025-12-16 - Implementation Complete

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-2, INV-9
- Read `api/payment_simulator/experiments/runner/optimization.py` - understood seed usage inconsistency
- Read `api/payment_simulator/experiments/config/experiment_config.py` - understood current mode validation

**Applicable Invariants**:
- INV-2: Determinism is Sacred - Both modes must be reproducible with same seed
- INV-9: Policy Evaluation Identity - Seed used for display must match seed used for acceptance

**All Phases Completed**:
- [x] Phase 1: Fixed seed inconsistency bug
- [x] Phase 2: Added evaluation mode parsing
- [x] Phase 3: Implemented temporal evaluation logic
- [x] Phase 4: Created integration tests

---

## Phase Progress

### Phase 1: Fix Seed Inconsistency
**Status**: Complete
**Started**: 2025-12-16
**Completed**: 2025-12-16

#### Results
- Fixed `_evaluate_policies()` to use `_seed_matrix.get_iteration_seed()` instead of `master_seed`
- Created 7 unit tests in `test_seed_consistency.py`

### Phase 2: Add Evaluation Mode Parsing
**Status**: Complete
**Started**: 2025-12-16
**Completed**: 2025-12-16

#### Results
- Added 4 valid modes: bootstrap, deterministic, deterministic-pairwise, deterministic-temporal
- Added helper properties: is_bootstrap, is_deterministic, is_deterministic_pairwise, is_deterministic_temporal
- Created 18 unit tests in `test_evaluation_modes.py`

### Phase 3: Deterministic-Temporal Logic
**Status**: Complete
**Started**: 2025-12-16
**Completed**: 2025-12-16

#### Results
- Added `_previous_iteration_costs` tracking dict
- Added `_previous_policies` tracking dict for revert capability
- Added `_evaluate_temporal_acceptance()` method
- Created 8 unit tests in `test_temporal_evaluation.py`

### Phase 4: Integration Tests
**Status**: Complete
**Started**: 2025-12-16
**Completed**: 2025-12-16

#### Results
- Created 9 integration tests in `test_evaluation_modes_integration.py`
- Tests verify mode initialization, determinism (INV-2), state tracking

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
