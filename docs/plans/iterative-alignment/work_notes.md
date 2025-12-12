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
