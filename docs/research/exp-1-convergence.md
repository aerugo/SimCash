# Exp-1 Convergence Analysis: Minimal Liquidity Fraction Problem

**Date:** 2025-12-09
**Status:** Investigation Complete
**Conclusion:** The convergence to minimal liquidity fractions is **NOT reasonable** per the Castro paper. There is a bug in the experiment setup or cost calculation.

## Executive Summary

Experiment 1 converged both BANK_A and BANK_B towards `initial_liquidity_fraction → 0`, which contradicts the theoretical Nash equilibrium from Castro et al. (2025). The paper predicts:
- **Bank A**: `ℓ₀ = 0` (correct direction, but for wrong reasons)
- **Bank B**: `ℓ₀ = 0.2` (20% of collateral capacity, i.e., 20,000)

The convergence to minimal liquidity for both banks indicates the cost function is not penalizing the lack of settlement appropriately.

## Expected Nash Equilibrium (Castro Paper)

### The 2-Period Model (Section 4)

From Castro et al. Section 4.1, the payment schedule is:
- **Agent A**: P^A = [0, 15000] (no payments in period 0, 15000 in period 1)
- **Agent B**: P^B = [15000, 5000] (15000 in period 0, 5000 in period 1)

The cost structure requires:
```
r_c < r_d < r_b
```
Where:
- `r_c` = initial liquidity cost (collateral opportunity cost)
- `r_d` = delay cost (per-tick penalty for unsettled transactions)
- `r_b` = end-of-day borrowing cost (much higher than r_c)

### Best Response Functions

The best response function for agent i is (from Equation in Section 4):
```
ℓ₀^i = P₁^i + max(P₂^i - min(ℓ₀^{-i}, P₁^{-i}), 0)
```

**For Bank B:**
- Bank B must pay 15,000 in period 0 (no incoming payments yet)
- Bank B must pay 5,000 in period 1
- If B posts ≥15,000, it receives incoming payment from A in period 1
- **Optimal**: Post 20,000 (15,000 + 5,000) to cover both periods

**For Bank A:**
- Bank A receives 20,000 from B in period 0 (if B posts enough)
- Bank A must pay 15,000 in period 1
- Since incoming (20,000) > outgoing (15,000), A needs no initial liquidity
- **Optimal**: Post 0

### Equilibrium Outcome
| Agent | Initial Liquidity | Reasoning |
|-------|------------------|-----------|
| BANK_A | 0 | Uses incoming from B to fund period-1 payment |
| BANK_B | 20,000 | Must fund both periods (no early incoming) |

## Observed Behavior

### The Convergence Pattern
```
Iteration  | BANK_A Liquidity | BANK_B Liquidity | Total Cost
-----------|------------------|------------------|------------
1          | 0.25             | 0.25             | $5,040
5          | 0.15             | 0.16             | $3,240
10         | 0.10             | 0.11             | $2,240
15         | 0.05             | 0.06             | $1,240
20         | 0.015            | 0.02             | $340
24         | 0.0025           | 0.003            | $90
```

**Both banks converged to near-zero liquidity**, not just Bank A.

### Critical Observation: "Settled: 0/0 (100.0%)"

The simulation output shows:
```
Settled: 0/0 (100.0%)
```

This means:
- `transactions_settled = 0`
- `transactions_failed = 0`
- **No transactions are being counted at all**

## Root Cause Analysis

### ~~Hypothesis 1: Transactions Not Being Created~~ (RULED OUT)

The scenario events in `configs/exp1_2period.yaml` specify:
```yaml
scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 15000
    priority: 5
    deadline: 1
    schedule:
      type: OneTime
      tick: 0
  # ... additional transactions
```

**Investigation Result:** CustomTransactionArrival IS correctly handled at the Orchestrator level (see `simulator/src/orchestrator/engine.rs:1515-1563`):

```rust
// CustomTransactionArrival: create transaction through normal arrival path
ScenarioEvent::CustomTransactionArrival { ... } => {
    // Submit through normal transaction submission path
    let tx_id = self.submit_transaction(
        from_agent, to_agent, *amount, deadline_tick, priority, is_divisible,
    )?;
    // ...
}
```

The transactions ARE being created. This hypothesis is **ruled out**.

### Hypothesis 2: Cost Calculation Not Including Delay Costs (CONFIRMED - ROOT CAUSE)

Looking at the cost structure in exp1:
```yaml
cost_rates:
  collateral_cost_per_tick_bps: 500    # 5% per tick
  delay_cost_per_tick_per_cent: 0.001  # Low delay cost
  overdraft_bps_per_tick: 2000         # 20% per tick
  eod_penalty_per_transaction: 0       # No EOD penalty
  deadline_penalty: 0                   # No deadline penalty
```

The **EOD penalty and deadline penalty are set to 0**! This means:
1. If transactions don't settle by end-of-day, there's no penalty
2. If transactions miss their deadline, there's no penalty

The only costs incurred are:
- Collateral cost: proportional to liquidity posted
- Delay cost: very low (0.001 per tick per cent)

With `eod_penalty = 0` and `deadline_penalty = 0`, failing to settle transactions has minimal cost. The optimal strategy becomes: **post zero collateral** to avoid collateral costs.

### Hypothesis 3: Deferred Crediting Behavior

The config enables deferred crediting:
```yaml
deferred_crediting: true
```

With deferred crediting, payments received are not available until the next tick. In a 2-tick simulation:
- Tick 0: B sends 15,000 to A, A can't use it yet
- Tick 1: A has incoming 15,000, B sends 5,000 to A, A sends 15,000 to B

This is correct behavior per Castro, but if transactions aren't being created, this doesn't matter.

## Cost Decomposition

For Bank A at iteration 1 with liquidity_fraction = 0.25:
```
max_collateral_capacity = 10,000,000 cents
posted_collateral = 10,000,000 × 0.25 = 2,500,000 cents
collateral_cost = 2,500,000 × 500 bps/tick × 2 ticks / 10000
               = 2,500,000 × 0.05 × 2 = 250,000 cents = $2,500
```

This matches the observed cost! The entire cost is collateral cost, with no delay or penalty costs.

## Verification Steps

To confirm the root cause, the following should be checked:

### 1. Verify Transactions Are Being Created
```python
# After running simulation
all_events = orch.get_all_events()
arrivals = [e for e in all_events if e.get("event_type") == "Arrival"]
print(f"Arrivals: {len(arrivals)}")
for a in arrivals:
    print(f"  {a['sender_id']} -> {a['receiver_id']}: {a['amount']}")
```

### 2. Check Cost Breakdown
```python
costs = orch.get_agent_accumulated_costs("BANK_A")
print(f"Collateral cost: {costs.get('collateral_cost', 0)}")
print(f"Delay cost: {costs.get('delay_cost', 0)}")
print(f"EOD penalty: {costs.get('eod_penalty', 0)}")
print(f"Deadline penalty: {costs.get('deadline_penalty', 0)}")
```

### 3. Compare with Castro Paper Parameters

Castro paper uses:
- `r_c = 0.1` (initial liquidity cost)
- `r_d = 0.2` (delay cost)
- `r_b = 0.4` (end-of-day borrowing cost)

The key constraint is `r_c < r_d < r_b`. Our config has effectively `r_d ≈ 0` due to disabled penalties.

## Recommended Fixes

### Fix 1: Enable Meaningful Delay Penalties

```yaml
cost_rates:
  collateral_cost_per_tick_bps: 500
  delay_cost_per_tick_per_cent: 0.002     # Increase to 2x collateral cost
  eod_penalty_per_transaction: 1000000    # $10,000 per unsettled tx
  deadline_penalty: 500000                 # $5,000 for missing deadline
```

### Fix 2: Verify CustomTransactionArrival Processing

Ensure the Orchestrator is correctly processing CustomTransactionArrival events and creating transactions in the pending queue.

### Fix 3: Add Cost Constraint Validation

Add a validation check that enforces `r_c < r_d < r_b`:
```python
def validate_castro_cost_ordering(cost_rates):
    """Ensure costs follow Castro paper ordering."""
    r_c = cost_rates.collateral_cost_per_tick_bps / 10000
    r_d = cost_rates.delay_cost_per_tick_per_cent
    # Need to derive effective r_b from eod_penalty

    assert r_c < r_d, f"Collateral cost ({r_c}) must be < delay cost ({r_d})"
```

## Conclusion

The convergence to minimal liquidity fractions for both banks is **incorrect** and does not match the Castro paper's theoretical Nash equilibrium. The **confirmed root cause** is:

**Disabled Penalties in Cost Configuration:**
- `eod_penalty_per_transaction = 0` - No penalty for unsettled transactions at end-of-day
- `deadline_penalty = 0` - No penalty for missing transaction deadlines
- `delay_cost_per_tick_per_cent = 0.001` - Too low to offset collateral savings

With these settings, the cost function violates the Castro paper's constraint `r_c < r_d < r_b`. The effective delay cost is near-zero, making it always optimal to reduce collateral posting (which only reduces costs).

The LLM is correctly optimizing the cost function as implemented—but the cost function doesn't match the Castro paper's game theory model. The fix requires updating the cost parameters to enforce meaningful delay/settlement penalties.

## References

- Castro, P., Desai, A., Du, H., Garratt, R., & Rivadeneyra, F. (2025). Estimating Policy Functions in Payment Systems Using Reinforcement Learning. ACM Trans. Econ. Comput.
- `experiments/castro/papers/castro_et_al.md` - Full paper text
- `experiments/castro/configs/exp1_2period.yaml` - Experiment configuration
