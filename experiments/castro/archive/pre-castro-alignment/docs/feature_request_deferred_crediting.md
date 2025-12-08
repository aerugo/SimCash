# Feature Request: Deferred Crediting Mode (Castro-Compatible Settlement)

**Date**: 2025-12-02
**Requested by**: Castro et al. replication study
**Priority**: High (blocks accurate Castro comparison)

---

## Summary

Add a configuration option to defer crediting receivers until the end of a tick, matching Castro et al. (2025)'s assumption that incoming payments (R_t) only become available in period t+1.

---

## Background

### Current Behavior

SimCash credits receivers **immediately** during RTGS queue processing:

```rust
// simulator/src/settlement/rtgs.rs - process_queue()
for tx_id in tx_ids {
    if can_pay {
        sender.debit(amount)?;
        receiver.credit(amount);  // Immediate!
    }
}
```

When A pays B, B can use those funds for its own transactions processed later in the **same tick**.

### Castro's Model (Section 3)

> "At the end of each period, the agent receives incoming payments R_t from other agents."
> "Liquidity evolves as: ℓ_t = ℓ_{t-1} - P_t x_t + R_t"

Incoming payments received in period t only become available in period t+1.

### Impact on Research

This difference enables equilibrium strategies in SimCash that are impossible in Castro's model:

| Model | Can both banks post zero initial liquidity? |
|-------|---------------------------------------------|
| Castro | No - gridlock occurs |
| SimCash | Yes - "within-tick recycling" works |

The LLM optimization study found a "symmetric near-zero liquidity equilibrium" that exploits SimCash's immediate crediting. This is a valid equilibrium in SimCash but **not in Castro's model**.

---

## Proposed Solution

### Configuration Option

Add a new top-level configuration field:

```yaml
# Deferred crediting mode (Castro-compatible)
# When true, credits are batched and applied at end of tick
deferred_crediting: true  # Default: false (current behavior)
```

### Implementation Approach

**Option A: Batch Credits (Recommended)**

Accumulate credits during queue processing, apply at end of tick:

```rust
struct DeferredCredits {
    pending: HashMap<String, i64>,  // agent_id -> accumulated credits
}

fn process_queue(state: &mut SimulationState, tick: usize) -> QueueProcessingResult {
    let mut deferred = DeferredCredits::default();

    for tx_id in tx_ids {
        if can_pay {
            sender.debit(amount)?;
            if state.config.deferred_crediting {
                deferred.pending.entry(receiver_id).or_default() += amount;
            } else {
                receiver.credit(amount);  // Current behavior
            }
        }
    }

    // Apply deferred credits at end of tick
    if state.config.deferred_crediting {
        for (agent_id, amount) in deferred.pending {
            state.get_agent_mut(&agent_id).credit(amount);
        }
    }
}
```

**Option B: Shadow Balances**

Track "available balance" vs "pending credits" separately. More complex but allows finer control.

### Events

New event type for visibility:

```rust
Event::DeferredCreditApplied {
    tick: usize,
    agent_id: String,
    amount: i64,
    source_transactions: Vec<String>,
}
```

---

## Acceptance Criteria

1. [ ] New config field `deferred_crediting: bool` (default false)
2. [ ] When enabled, credits accumulate during tick and apply at end
3. [ ] Balance checks during tick use pre-credit balances only
4. [ ] Event emitted when deferred credits are applied
5. [ ] Existing behavior unchanged when `deferred_crediting: false`
6. [ ] Determinism maintained (credits applied in sorted agent order)
7. [ ] Documentation updated

---

## Testing

### Test Case 1: Gridlock Without Credit

```yaml
deferred_crediting: true
agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0  # No credit
  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 0

scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 10000
    tick: 0
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 10000
    tick: 0
```

**Expected**: Neither transaction settles in tick 0 (gridlock).
**With current behavior**: One settles, then the other uses incoming funds.

### Test Case 2: Castro 2-Period Replication

Run Castro's 2-period scenario with deferred crediting. Verify:
- LLM cannot find symmetric near-zero equilibrium
- Optimal solution matches Castro's asymmetric equilibrium (A=0, B=$200)

---

## Alternatives Considered

### 1. Per-Period Settlement Windows

Run RTGS once per "period" with credits applied between periods. Rejected: Too invasive, changes tick semantics.

### 2. Transaction Ordering Controls

Guarantee specific agent ordering. Rejected: Doesn't solve the fundamental issue - credits still immediate.

### 3. Document as Known Difference

Accept SimCash differs from Castro. Rejected: Undermines research validity.

---

## References

- Castro et al. (2025), Section 3 - Payment System Environment
- SimCash issue: Accurate Castro replication
- `experiments/castro/RESEARCH_PAPER.md` - Documents the discrepancy
