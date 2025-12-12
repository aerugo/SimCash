# Iterative Alignment Work Notes

## Session: 2025-12-12 (Initial Analysis)

### Context
Task: Make policy optimization find Nash equilibrium for Castro 2-period Initial Liquidity Game

### Key Findings

1. **Paper Nash Equilibrium (Section 6.3)**:
   - Agent A: P^A = [0, 0.15] → pays 15000 at tick 1
   - Agent B: P^B = [0.15, 0.05] → pays 15000 at tick 0, 5000 at tick 1
   - Optimal: A posts 0 collateral, B posts 20000 collateral

2. **Current exp1_2period.yaml Transaction Schedule** (correctly maps paper):
   - Bank A → Bank B: 15000 at tick 1, deadline 2
   - Bank B → Bank A: 15000 at tick 0, deadline 1
   - Bank B → Bank A: 5000 at tick 1, deadline 2

3. **Gap Identified**: Too many allowed fields confuse the LLM:
   - Current: 12+ fields including queue metrics
   - Needed: ~6 fields for tick, balance, collateral

4. **Architecture Review**:
   - New optimizer prompt system completed in previous sessions
   - Dynamic system prompt builder has Castro mode
   - Event filtering and agent isolation working

### Plan Created
- Main plan: `docs/plans/iterative-alignment/iteration.md`
- 5 phases identified, starting with minimal field set

---

## Session: 2025-12-12 (Phase 1 Implementation)

### What Was Done
1. **Created TDD test file**: `api/tests/castro/test_castro_equilibrium.py`
   - 17 tests for verifying Nash equilibrium
   - All 17 tests pass
   - Tests cover: transaction schedule, optimal costs, suboptimal penalties, minimal fields

2. **Simplified exp1.yaml policy_constraints**:
   - Reduced from 12+ fields to 6 minimal fields
   - Reduced from 3 parameters to 1 (initial_liquidity_fraction)
   - Fields: system_tick_in_day, balance, remaining_collateral_capacity, posted_collateral, max_collateral_capacity, ticks_to_deadline

3. **Rewrote system prompt for Castro game**:
   - Explicit game setup (Castro et al. 2025, Section 6.3)
   - Clear Nash equilibrium explanation
   - Template policy structure provided
   - Model changed to GPT-5.2 with reasoning_effort: "high"

### Key Observations
- Tests confirm optimal policies:
  - Bank A: initial_liquidity_fraction = 0.0 → zero collateral cost
  - Bank B: initial_liquidity_fraction = 0.002 → posts 20000 collateral
- Deferred crediting allows Bank A to use incoming payment from Bank B
- Cost structure: collateral_cost, delay_cost, deadline_penalty, liquidity_cost

### Issues Encountered
- Policy type had to be "Inline" not "DecisionTree"
- Config needs SimulationConfig.from_dict() conversion for FFI
- Cost key is "deadline_penalty" not "penalty_cost"

### Next Steps
1. Run experiment with GPT-5.2 and observe results
2. Compare to expected Nash equilibrium
3. Document results and iterate if needed

---

## Session: 2025-12-12 (Bug Fixes - Evaluation Loop)

### Context
Investigating why experiment output showed:
1. `Evaluation: $40.00 → $40.00 (+0.0%)` - same cost for old and new
2. In exp1 (deterministic), cost varied wildly: iter2 $30, iter3 $62.50
3. Policies always accepted even when they seemed worse

### Root Cause Analysis

**Bug 1: Seed changes per iteration in deterministic mode**
- Location: `optimization.py:830`
- Code: `seed = self._config.master_seed + self._current_iteration`
- Impact: Each iteration used a DIFFERENT seed, making "deterministic" mode non-deterministic
- The scenario had fixed `scenario_events` but the RNG seed affected other simulation behavior

**Bug 2: New policy never evaluated before acceptance**
- Location: `optimization.py:1196`
- Code logged `new_cost=current_cost` because new policy wasn't evaluated
- Output showed `$40.00 → $40.00` misleadingly

**Bug 3: Deterministic mode always accepts**
- Location: `optimization.py:1383-1386`
- Code: `if eval_mode == "deterministic": return True`
- All policies accepted without comparison, including worse ones

### Fixes Applied

1. **Fixed seed consistency** (`optimization.py:830`):
   ```python
   # Before: seed = self._config.master_seed + self._current_iteration
   # After:
   seed = self._config.master_seed  # Constant seed for deterministic mode
   ```

2. **Fixed acceptance to return actual new cost** (`optimization.py:1362-1412`):
   - Changed `_should_accept_policy()` signature to return `tuple[bool, int]`
   - Now evaluates new policy and returns both decision AND new cost
   - Deterministic mode: accept only if `new_cost <= current_cost`

3. **Fixed `_evaluate_policy_on_samples`** (`optimization.py:979-985`):
   - For deterministic mode, use `master_seed` directly (consistent with `_evaluate_policies`)
   - For bootstrap mode, continue using derived seeds

### Tests Verified
- All 17 `test_castro_equilibrium.py` tests pass
- All 7 `test_bootstrap_paired_comparison.py` tests pass
- Type check passes (`mypy optimization.py`)

### Expected Behavior Now
- Deterministic mode uses constant seed → same policy produces same cost
- Evaluation shows actual before/after costs: `$40.00 → $30.00 (-25%)`
- Policies only accepted if they improve (or equal) cost
- Cost should converge towards optimal Nash equilibrium

### Next Steps
1. Re-run exp1 with fixed code
2. Verify policy converges to optimal (A=0.0, B=0.2)
3. Verify eval output shows meaningful cost comparisons

---

## Session Notes Template

```
## Session: YYYY-MM-DD (Topic)

### What Was Done
-

### Key Observations
-

### Issues Encountered
-

### Next Steps
-
```
