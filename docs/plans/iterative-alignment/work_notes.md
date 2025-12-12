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

## Session: 2025-12-12 (Phase 2 - Running Experiment & Fixes)

### What Was Done

1. **Ran experiment with GPT-5.2**:
   - Initial run showed costs bouncing between $27.50 and $65.00
   - Both banks converged to initial_liquidity_fraction = 0.0 (wrong for Bank B!)
   - Bank A: 0.0 is CORRECT (optimal)
   - Bank B: 0.0 is WRONG - should be 0.2 (20000/100000)

2. **Identified Root Cause - Broken Default Policy**:
   - The `_create_default_policy()` in `optimization.py` had a broken collateral tree
   - It defined `initial_liquidity_fraction: 0.5` in parameters
   - BUT the `strategic_collateral_tree` just did `HoldCollateral` with amount 0
   - The parameter was NEVER used! The LLM saw it but couldn't understand its purpose

3. **Fixed Default Policy** (`optimization.py:1401-1455`):
   - Changed `strategic_collateral_tree` from simple `HoldCollateral` to proper conditional tree:
     - At tick 0: Post collateral = initial_liquidity_fraction * remaining_collateral_capacity
     - At other ticks: Hold collateral
   - Removed unused parameters (urgency_threshold, liquidity_buffer_factor)
   - All 17 Castro tests still pass

4. **Re-ran experiment with fix**:
   - Iteration 1: Total cost $140.00 (both at 0.5 → lots of collateral)
   - Both banks reduced to 0.0 → cost dropped to $25.00
   - BUT then Bank A went to 1.0 while Bank B stayed at 0.0
   - Cost bounced back to $140.00

### Key Observations

1. **Collateral tree now works**: The fix was correct - policies now properly post collateral
   based on initial_liquidity_fraction parameter.

2. **LLM still not finding optimal**: The LLM is:
   - Correctly moving Bank A towards 0.0 initially
   - Incorrectly keeping Bank B at 0.0 (should be 0.2)
   - Then overshooting Bank A to 1.0

3. **Deterministic mode always accepts**: In deterministic mode, all policy changes
   are accepted regardless of cost impact. The LLM doesn't get rejection feedback.

4. **Cost display may confuse LLM**: Audit shows "$4,000" for 4000 cents (should be "$40.00")

### Issues Identified for Next Phase

1. **Bank B doesn't learn it needs collateral**: Even with verbose output showing
   overdraft costs, Bank B thinks reducing collateral is good because total cost drops.

2. **No rejection signal in deterministic mode**: The LLM always gets "ACCEPTED"
   even when changes make things worse. Need paired comparison.

3. **Asymmetric equilibrium is hard**: Bank A and Bank B need different optimal values
   but they're being optimized with the same prompts/incentives.

### Next Steps
1. Consider switching to bootstrap mode with paired comparison for better feedback
2. Improve prompt to better explain the asymmetric game dynamics
3. Maybe add per-agent cost breakdown more prominently
4. Consider starting Bank B at a higher initial value (0.3 instead of 0.5)

---

## Session: 2025-12-12 (Phase 2 Continued - Acceptance Logic Fix)

### What Was Done

1. **Fixed Acceptance Logic** (`optimization.py:1361-1403`):
   - Changed deterministic mode from "always accept" to "accept only if cost reduces"
   - Now compares old vs new policy costs before accepting
   - Uses `<= ` comparison to allow equal costs (enables exploration)
   - This prevents the LLM from getting stuck with bad changes

2. **Verified all tests still pass**: 17/17 Castro equilibrium tests passing

3. **Attempted re-run**: OpenAI API has TLS certificate issues (infrastructure problem)
   - Error: `SSL routines:OPENSSL_internal:CERTIFICATE_VERIFY_FAILED`
   - Cannot test the fixes until network issue is resolved

### Code Changes Summary

1. `optimization.py` - `_create_default_policy()`:
   - Added proper collateral tree that posts `initial_liquidity_fraction * remaining_collateral_capacity` at tick 0
   - Removed unused parameters (urgency_threshold, liquidity_buffer_factor)

2. `optimization.py` - `_should_accept_policy()`:
   - Changed from `return True` in deterministic mode to actual cost comparison
   - Now evaluates both old and new policies and accepts only if new <= old

### What Needs Testing

When OpenAI API is available:
1. Run experiment and verify rejections work
2. Check if Bank B starts exploring higher collateral values
3. Verify Bank A stays at/near 0 (optimal)
4. Verify Bank B converges towards 0.2 (optimal)

### Expected Behavior After Fixes

- LLM proposes changes
- If change increases cost → REJECTED (shown in output)
- If change reduces/maintains cost → ACCEPTED
- This feedback should guide the LLM toward optimal policies

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
