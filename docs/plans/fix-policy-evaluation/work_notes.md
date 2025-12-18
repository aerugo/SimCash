# Fix Policy Evaluation - Work Notes

**Project**: Fix deterministic-temporal policy evaluation for multi-agent convergence
**Started**: 2025-12-18
**Branch**: claude/fix-policy-evaluation-JFl5g

---

## Session Log

### 2025-12-18 - Initial Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-2 (Determinism), INV-9 (Policy Evaluation Identity)
- Read `api/payment_simulator/experiments/runner/optimization.py` - understood current temporal evaluation logic
- Read `api/payment_simulator/ai_cash_mgmt/optimization/convergence_detector.py` - understood current convergence detection
- Read `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - understood deterministic-temporal design
- Read `docs/plans/deterministic-evaluation-modes/development-plan.md` - understood prior implementation

**Applicable Invariants**:
- INV-2: Determinism - convergence detection must be deterministic (same seed = same iteration count)
- INV-9: Policy Evaluation Identity - parameter extraction must be consistent across code paths

**Key Insights**:
1. Current `_optimize_agent_temporal()` rejects policies when cost increases vs previous iteration
2. This "greedy hill climbing" doesn't account for counterparty policy changes
3. In multi-agent games, optimal fraction for Agent A depends on Agent B's policy
4. Solution: Track `initial_liquidity_fraction` stability instead of cost-based acceptance
5. Convergence = ALL agents unchanged for `stability_window` iterations

**Problem Analysis**:
- The issue is in `_evaluate_temporal_acceptance()` at line ~2569 of optimization.py
- It compares `current_cost <= previous_cost` and rejects if cost increased
- When counterparty policy changes, cost can increase even with same fraction
- This causes the agent to revert to a suboptimal policy

**Solution Design**:
- Create `PolicyStabilityTracker` class to track fraction history
- Modify `_optimize_agent_temporal()` to always accept LLM's policy
- Check convergence based on fraction stability, not cost stability
- Preserve cost logging for analysis purposes

**Completed**:
- [x] Analyzed current implementation
- [x] Identified root cause of the issue
- [x] Designed solution approach
- [x] Created development plan

**Next Steps**:
1. Create Phase 1 detailed plan
2. Implement PolicyStabilityTracker with TDD
3. Write unit tests first, then implementation

---

## Phase Progress

### Phase 1: Create PolicyStabilityTracker
**Status**: Pending
**Started**: -
**Completed**: -

#### Results
- (pending)

#### Notes
- (pending)

---

## Key Decisions

### Decision 1: Track `initial_liquidity_fraction` specifically
**Rationale**: In Castro-style experiments, this is THE key parameter being optimized. Other policy tree parameters (thresholds, actions) are less relevant for convergence detection because they don't have the same continuous optimization characteristic.

### Decision 2: Always accept LLM's policy in temporal mode
**Rationale**: The LLM is the "optimizer" - it decides when to stop changing. By tracking what it outputs (not rejecting based on cost), we get true policy stability detection. If the LLM keeps outputting the same fraction, it has converged on its "best guess."

### Decision 3: Use floating-point tolerance for fraction comparison
**Rationale**: Fractions may have minor floating-point representation differences (e.g., 0.5 vs 0.50000001). Use epsilon=0.001 for comparison to avoid false instability detection.

---

## Issues Encountered

(No issues yet - planning phase)

---

## Files Modified

### Created
- `docs/plans/fix-policy-evaluation/development-plan.md` - Main development plan
- `docs/plans/fix-policy-evaluation/work_notes.md` - This file

### To Be Created (Phase 1)
- `api/payment_simulator/experiments/runner/policy_stability.py` - PolicyStabilityTracker
- `api/tests/experiments/runner/test_policy_stability.py` - Unit tests

### To Be Modified (Phase 2)
- `api/payment_simulator/experiments/runner/optimization.py` - _optimize_agent_temporal()

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] No new invariants needed (existing INV-2 and INV-9 cover this)

### Other Documentation
- [ ] `docs/reference/ai_cash_mgmt/evaluation-methodology.md` - Update deterministic-temporal section
- [ ] `docs/reference/experiments/configuration.md` - Document convergence behavior
