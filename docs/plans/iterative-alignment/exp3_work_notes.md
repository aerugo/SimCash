# Exp3 Work Notes

## Session: 2025-12-13

### Starting State

Reading the Three-Period Dummy Example from Castro et al. (2025) Section 7.2.

### Paper Analysis

**Three-Period Dummy Example (Section 7.2):**

```
P^A = P^B = [0.2, 0.2, 0]
```

This means:
- Period 1: Each agent owes 20% of their collateral B to the other
- Period 2: Each agent owes another 20% of their collateral B
- Period 3: No new payment demands (P_3 = 0)

**Total payment demand per agent:** 40% of collateral (0.2 + 0.2 + 0 = 0.4)

**Cost parameters:**
- r_c = 0.1 (initial liquidity cost)
- r_d = 0.2 (delay cost per tick) — when r_c < r_d
- r_b = 0.4 (end-of-day borrowing)

**Paper Results (Figure 8, page 17):**
- When r_c < r_d: ~25% initial liquidity, ~10% delay
- When r_d < r_c: ~20% initial liquidity, ~25% delay

### Critical Issue Identified

Current exp3_joint.yaml uses **stochastic Poisson arrivals** with **LogNormal amounts**, but the paper uses **fixed deterministic payments** of exactly 0.2B per period.

**Impact:** The LLM is trying to learn a policy for a DIFFERENT problem than the paper describes.

### Plan

1. Create a deterministic scenario with scripted transactions
2. Fix the cost parameters to match paper
3. Simplify policy constraints to match paper's action space
4. Run experiment with GPT-5.2 reasoning=high

---

### Investigation: How to Create Scripted Transactions

**FOUND:** SimCash supports `scenario_events` with `CustomTransactionArrival`:

```yaml
scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 20000
    priority: 5
    deadline: 2
    schedule:
      type: OneTime
      tick: 0
```

This is exactly what exp1_2period.yaml uses for deterministic transactions!

---

### Configuration Changes Required

**exp3_joint.yaml needs:**

1. **Remove stochastic arrivals** - Delete `arrival_config` from agents
2. **Add deterministic transactions** via `scenario_events`:
   - Tick 0: A→B 20000, B→A 20000 (20% of 100,000 collateral)
   - Tick 1: A→B 20000, B→A 20000 (another 20%)
   - Tick 2: No new payments (P = 0)
3. **Fix cost parameters** to match paper's r_c < r_d < r_b:
   - r_c = 0.1 (collateral cost)
   - r_d = 0.2 (delay cost)
   - r_b = 0.4 (EOD borrowing)

**exp3.yaml needs:**
1. Change evaluation mode to `deterministic` (no stochastic elements)
2. Simplify `allowed_parameters` to just `initial_liquidity_fraction`
3. Simplify `allowed_fields` to minimal set
4. Add `prompt_customization` for joint learning focus

---

### Implementation

Modified exp3_joint.yaml to use deterministic transactions:
- `scenario_events` with `CustomTransactionArrival`
- P^A = P^B = [0.2, 0.2, 0] matching paper
- Fixed cost parameters for r_c < r_d < r_b

---

## First Run (2025-12-13)

### Observations

First run showed oscillation with costs jumping unexpectedly:
- Iteration 1: Both A and B went to 0.2 initial liquidity (good!)
- Iteration 2: BANK_B went to 0.0 (free-riding attempt)
- Iteration 3: Cost jumped to $266.64 (very bad!)

### Bug Found!

**Root Cause:** In `_evaluate_policy_pair`, after running both old and new policies, the method left `self._policies[agent_id]` set to `new_policy`. When the policy was REJECTED, it was never restored to `old_policy`.

**Fix:** Added policy restoration at the end of `_evaluate_policy_pair`:
```python
# CRITICAL: Restore old policy - caller will set new policy if accepted
self._policies[agent_id] = old_policy
```

### Fix Applied

File: `api/payment_simulator/experiments/runner/optimization.py`
- Lines 1056-1057: Added restoration for deterministic mode
- Lines 1081-1082: Added restoration for bootstrap mode

---

## Second Run (Post-Bug-Fix)

### Convergence Trajectory

| Iteration | Total Cost | BANK_A Policy | BANK_B Policy | Notes |
|-----------|------------|---------------|---------------|-------|
| 1 | $99.90 | 0.5 → 0.2 ✓ | 0.5 → 0.2 ✓ | Both reduce liquidity |
| 2 | $39.96 | 0.2 → 0.0 ✓ | 0.2 → 0.0 ✗ | A reduces, B rejected |
| 3 | $19.98 | 0.0 → 0.0 ✗ | 0.2 → 0.0 ✓ | B reduces after A stable |
| 4 | $13.32 | 0.0 → 0.0 ✗ | 0.0 → 0.0 ✓ | B timing change! |
| 5 | $0.00 | 0.0 ✗ | 0.0 ✗ | Zero cost equilibrium! |
| 6-9 | $0.00 | stable | stable | Converged |

### Key Observations

1. **Zero-Cost Equilibrium Found!** The LLM discovered that with:
   - Both agents at 0.0 initial liquidity
   - Perfect payment timing coordination
   - Payments exactly offset each other

   → Total cost = $0.00 (no collateral cost, no delay cost)

2. **Sequential Convergence:** BANK_A moved first to 0.0, then BANK_B followed after seeing the benefit.

3. **Order-Dependent:** When both tried 0.0 simultaneously, it failed. But sequential adoption worked.

4. **Timing Learning:** The LLM learned not just initial liquidity but also payment timing. The policy change from BANK_B at iteration 4 (0.0 → 0.0 with cost improvement) suggests timing optimization.

### Comparison to Paper

**Paper Prediction (Castro et al. 2025, Section 7.2):**
- When r_c < r_d: ~25% initial liquidity, ~10% delay
- Expected total cost: non-zero (from collateral cost)

**SimCash LLM Result:**
- Both agents: 0.0 initial liquidity
- Total cost: $0.00
- Converged in 5 iterations

### Analysis

The LLM found a **better equilibrium** than the paper's analytical result because:

1. **Perfect Symmetry Exploitation:** With symmetric payments (P^A = P^B = [0.2, 0.2, 0]), incoming payments from counterparty can fund outgoing payments.

2. **Timing Coordination:** The policy decision tree allows Release/Hold per-tick, enabling strategic timing.

3. **Deferred Crediting:** The `deferred_crediting: true` setting means received payments become available for use.

4. **LSM Enabled?** The bilateral offset mechanism may be helping to net payments.

### Next Steps

1. Investigate if this is a valid equilibrium or a simulation artifact
2. Check if LSM bilateral offsetting is occurring
3. Consider if the paper assumes constraints not present in SimCash

---

## Divergence Investigation (2025-12-13)

### Question

Why did the LLM find a zero-cost equilibrium when the paper predicts ~25% initial liquidity with non-zero costs?

### Root Cause Analysis

**IDENTIFIED: The `unsecured_cap: 50000` setting provides FREE credit!**

#### Test 1: With Current Config (unsecured_cap: 50000)

```
💰 Agent Financial Stats
BANK_A
  Balance:            $0.00
  Credit Limit:       $500.00    ← FREE credit line!
  Available Liquidity: $500.00   ← Can make $500 in payments without collateral!
```

With symmetric payments of $200 each (20,000 cents):
- Agent can use $500 credit to pay $200 → balance goes to -$200
- Receives $200 from counterparty → balance returns to $0
- Net cost = $0 (no collateral needed, no delay)

#### Test 2: With unsecured_cap: 0 (Paper-Accurate)

```
💰 Agent Financial Stats
BANK_A
  Balance:            $0.00
  Credit Limit:       None       ← No free credit
  Available Liquidity: $0.00     ← Cannot pay without liquidity!
```

Result:
- **0% settlement rate** - Complete gridlock!
- **Total Cost: $400** from delay penalties
- Payments queued as "Insufficient balance"

### Key Differences from Paper

| Aspect | Paper Assumption | SimCash Config | Impact |
|--------|------------------|----------------|--------|
| **Unsecured credit** | None (agents need collateral) | 50,000 cents ($500) | Agents can pay without posting collateral |
| **Initial liquidity source** | Posted collateral | Free unsecured credit | No collateral cost incurred |
| **Symmetric payment exploit** | Not exploitable without liquidity | Fully exploitable with credit | Zero-cost equilibrium possible |

### Mechanism Explanation

The paper's model assumes agents MUST post collateral to get liquidity:
- Posting collateral incurs cost r_c
- Not posting means delaying, incurring cost r_d
- Optimal balance: ~25% posted (minimize r_c + r_d)

SimCash with `unsecured_cap: 50000`:
- Agents have FREE $500 credit line
- Payments are only $200 → credit is sufficient
- Symmetric payments cancel: A→B $200, B→A $200 = net zero
- No collateral needed, no delay → zero cost

### Fix Required

To match paper conditions:
```yaml
agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0      # ← CRITICAL: No free credit!
    max_collateral_capacity: 100000
```

---

## Result Summary

**Experiment 3 (Three-Period Dummy Example):**
- **Status:** CONVERGED (but with incorrect experimental conditions)
- **Final Total Cost:** $0.00
- **Final Policies:** BANK_A = 0.0, BANK_B = 0.0 initial_liquidity_fraction
- **Iterations to Convergence:** 9 (stable from iteration 5)
- **Comparison to Paper:** LLM found zero-cost equilibrium vs paper's ~25% liquidity prediction
- **Root Cause:** `unsecured_cap: 50000` provided free credit that bypassed collateral requirement

---

## Fix Applied (2025-12-13)

### Changes Made

1. **exp3_joint.yaml:**
   - Changed `unsecured_cap: 50000` → `unsecured_cap: 0` for both agents
   - Added comments explaining the paper requirement

2. **exp3.yaml:**
   - Updated prompt to clarify NO unsecured credit available
   - Emphasized that collateral is the ONLY source of liquidity
   - Added warning about gridlock if no collateral posted

### Expected Behavior After Fix

With `unsecured_cap: 0`:
- Agents MUST post collateral to have any liquidity
- The LLM should learn to set `initial_liquidity_fraction` to ~20-25%
- Zero-cost equilibrium should be impossible (collateral cost is unavoidable)
- Results should match paper's prediction more closely

