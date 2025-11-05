# Overdue Transaction Handling

**Implementation Status**: ✅ Complete (Phases 1-5)
**Created**: 2025-11-04
**Last Updated**: 2025-11-04

## Overview

The payment simulator implements realistic overdue transaction handling that mirrors real-world payment systems. When a transaction passes its deadline, it is marked as **overdue** rather than dropped, and remains in the system with escalating costs until eventually settled.

## Problem Statement

In real payment systems:
- Transactions cannot simply be "dropped" - all obligations must eventually settle
- Delayed transactions incur escalating penalties and regulatory scrutiny
- Banks must actively manage overdue transactions to minimize costs
- Cash managers need ability to prioritize overdue transactions urgently

The previous "dropped" status was unrealistic and prevented accurate simulation of real-world payment system dynamics.

## Design Rationale

### Terminology: "Overdue" vs "Dropped"

**Why "Overdue"?**
- Industry-standard banking term for late payments
- Conveys the transaction must still be processed (not abandoned)
- Matches real-world payment system terminology (TARGET2, Fedwire, etc.)
- Aligns with regulatory frameworks that track overdue obligations

**Why not "Dropped"?**
- Implies permanent removal/abandonment
- Doesn't exist in real payment systems
- Misrepresents the obligation to settle

### System-Enforced Transitions

Deadline transitions are **system-enforced**, not policy-driven:

```
┌─────────┐
│ Pending │
└────┬────┘
     │
     │ (tick > deadline)
     │ SYSTEM-ENFORCED
     │
     ▼
┌─────────┐           ┌─────────┐
│ Overdue │ ────────> │ Settled │
└─────────┘           └─────────┘
     │
     └─────────────────────> (with escalated costs)
```

**Critical**: This happens automatically in both Queue 1 (agent internal) and Queue 2 (RTGS central queue).

**Why system-enforced?**
- Queue 2 has no policy - system must handle transitions
- Deadline is a system invariant, not a policy decision
- Ensures consistent behavior across all queues
- Prevents policy bugs from breaking fundamental system rules

## Cost Model

### Base Delay Cost (Pending Transactions)

```
delay_cost = delay_cost_per_tick_per_cent × remaining_amount
```

Applied every tick a transaction remains unsettled.

### Overdue Cost Structure

When a transaction becomes overdue, two costs apply:

#### 1. One-Time Deadline Penalty

```rust
// Charged exactly once when transaction first becomes overdue
deadline_penalty: i64  // Default: $1,000 (100_000 cents)
```

**Purpose**: Immediate regulatory/compliance penalty for missing deadline.

#### 2. Escalated Delay Cost (Per Tick)

```rust
overdue_delay_cost = overdue_delay_multiplier
                   × delay_cost_per_tick_per_cent
                   × remaining_amount
```

**Default multiplier**: `5.0` (5x normal delay cost)

**Rationale**:
- Models regulatory scrutiny for overdue payments
- Creates strong incentive to settle overdue transactions
- Reflects real-world penalties (e.g., TARGET2 penalty rates)
- Makes cost-benefit analysis more realistic for cash managers

### Configuration

Add to `CostRates` struct:

```rust
pub struct CostRates {
    // ... existing fields ...

    /// Multiplier for delay cost when transaction is overdue (default: 5.0)
    pub overdue_delay_multiplier: f64,

    /// One-time penalty when transaction first becomes overdue (default: 100_000)
    pub deadline_penalty: i64,
}
```

### Cost Example

**Scenario**: $10,000 transaction overdue for 10 ticks

**Parameters**:
- `delay_cost_per_tick_per_cent = 0.0001` (1 bp per tick)
- `overdue_delay_multiplier = 5.0`
- `deadline_penalty = 100_000` ($1,000)

**Calculation**:
```
# When pending (ticks 1-5 before deadline):
pending_cost_per_tick = 0.0001 × 1_000_000 = 100 cents ($1.00)
total_pending_cost = 100 × 5 = 500 cents ($5.00)

# One-time penalty at deadline (tick 6):
deadline_penalty = 100_000 cents ($1,000.00)

# When overdue (ticks 6-15):
overdue_cost_per_tick = 5.0 × 0.0001 × 1_000_000 = 500 cents ($5.00)
total_overdue_cost = 500 × 10 = 5,000 cents ($50.00)

# Grand total:
total_cost = $5.00 + $1,000.00 + $50.00 = $1,055.00
```

## Priority Reprioritization

### Context Fields

Policies have access to overdue status via context fields:

```rust
// Available in policy evaluation context
is_overdue: f64          // 1.0 if overdue, 0.0 otherwise
overdue_duration: f64    // Number of ticks since becoming overdue
```

### Reprioritize Action

Policies can adjust transaction priority using the `Reprioritize` action:

```rust
ReleaseDecision::Reprioritize {
    tx_id: String,
    new_priority: u8,  // 0-10, capped at 255 in implementation
}
```

**Key characteristics**:
- Transaction remains in Queue 1 (not submitted)
- Independent of submission decision
- Can be called multiple times as conditions change
- Priority is capped at 10 for standard use (255 for special cases)

### Policy DSL Support

The tree-based policy DSL supports reprioritize actions:

```yaml
release_policy:
  # Escalate overdue transactions to maximum priority
  - if: is_overdue == 1
    then:
      action: reprioritize
      new_priority: 10
      reason: "Urgent: past deadline"

  # Gradual escalation based on duration
  - if: overdue_duration > 20
    then:
      action: reprioritize
      new_priority: 10

  - if: overdue_duration > 10
    then:
      action: reprioritize
      new_priority: 8

  # Separate decision: submit if liquidity available
  - if: available_liquidity >= amount
    then:
      action: submit_full
```

## Implementation Details

### Transaction Model Changes

```rust
pub enum TransactionStatus {
    Pending,
    PartiallySettled { tick: usize, amount: i64 },
    Settled { tick: usize },
    Overdue { missed_deadline_tick: usize },  // NEW
}

impl Transaction {
    /// Check if transaction is overdue
    pub fn is_overdue(&self) -> bool;

    /// Get tick when transaction became overdue
    pub fn overdue_since_tick(&self) -> Option<usize>;

    /// Mark transaction as overdue (idempotent)
    pub fn mark_overdue(&mut self, tick: usize) -> Result<(), String>;

    /// Set transaction priority (0-10)
    pub fn set_priority(&mut self, priority: u8);
}
```

**Idempotency**: `mark_overdue()` can be called multiple times safely - only the first call records the transition.

### RTGS Settlement Changes

Queue processing logic updated to mark overdue but keep in queue:

```rust
// Old behavior (REMOVED):
if transaction.is_past_deadline(tick) {
    transaction.drop_transaction(tick);
    continue;  // Remove from queue
}

// New behavior (CURRENT):
if transaction.is_past_deadline(tick) && !transaction.is_overdue() {
    transaction.mark_overdue(tick)?;
    // Transaction remains in queue, continues to settlement attempt
}

// Attempt settlement for ALL transactions (including overdue)
match try_settle(&mut state, &tx_id, tick) {
    Ok(()) => { /* settled */ }
    Err(InsufficientLiquidity) => {
        // Re-queue (including overdue transactions)
        still_pending.push(tx_id);
    }
}
```

### Event Logging

New event type for tracking reprioritization:

```rust
Event::TransactionReprioritized {
    tick: usize,
    agent_id: String,
    tx_id: String,
    old_priority: u8,
    new_priority: u8,
}
```

## Example Policies

### Aggressive Overdue Handling

See: [`examples/policies/overdue_handling.yaml`](../examples/policies/overdue_handling.yaml)

**Strategy**:
- Immediately reprioritize any overdue transaction to priority 10
- Submit high-priority transactions (≥8) when liquidity available
- Hold lower-priority during EOD rush to preserve liquidity
- Post collateral aggressively for imminent deadlines

**Use case**: Risk-averse bank that must avoid overdue transactions at all costs.

### Gradual Escalation

See: [`examples/policies/overdue_moderate.yaml`](../examples/policies/overdue_moderate.yaml)

**Strategy**:
- Gradual priority escalation based on overdue duration:
  - \>20 ticks overdue → priority 10
  - \>10 ticks overdue → priority 8
  - \>0 ticks overdue → priority 7
- Submit when liquidity available

**Use case**: Balanced approach that escalates priority proportionally to how late the transaction is.

## Testing

### Unit Tests

**Transaction Model** (`backend/src/models/transaction.rs`):
- `test_transaction_mark_overdue` - Marks transaction as overdue
- `test_transaction_mark_overdue_idempotent` - Multiple calls safe
- `test_transaction_settle_overdue` - Overdue transactions can settle
- `test_overdue_since_tick_none_when_not_overdue` - Returns None when pending

**RTGS Settlement** (`backend/tests/test_rtgs_settlement.rs`):
- `test_mark_transaction_overdue_past_deadline` - System-enforced marking
- Tests verify transactions remain in queue after deadline
- Tests verify overdue transactions can settle when liquidity arrives

**Cost Model** (`backend/src/models/costs.rs`):
- `test_overdue_delay_cost_applied` - 5x multiplier applied
- `test_deadline_penalty_charged_once` - One-time penalty
- `test_overdue_and_pending_costs_separate` - Independent calculations

**Policy Interpreter** (`backend/src/policy/tree/interpreter.rs`):
- `test_build_reprioritize_decision_*` - 5 comprehensive tests
- Tests cover literal values, computed expressions, field references, capping, errors

### Integration Tests

**Python FFI Tests** (`api/tests/integration/test_overdue_transactions.py`):
- 7 integration tests covering full lifecycle
- Configuration parsing tests
- Default value tests
- Multi-agent overdue scenarios

**Result**: 481/481 Rust tests passing, 3/7 Python tests passing (remaining need additional FFI query methods)

## Breaking Changes

### API Changes

1. **TransactionStatus enum**: `Dropped` → `Overdue`
2. **CostRates struct**: Added `overdue_delay_multiplier` field (default: 5.0)
3. **ReleaseDecision enum**: Added `Reprioritize` variant
4. **ActionType enum**: Added `Reprioritize` variant

### Migration Path

**For existing simulations**:
1. Update all transaction status checks from `Dropped` to `Overdue`
2. Add `overdue_delay_multiplier: 5.0` to cost configuration (or omit for default)
3. Update policy DSL to use `is_overdue` and `overdue_duration` fields
4. Consider adding reprioritize actions to policies for better overdue management

**Backward compatibility**:
- FFI layer provides default value (5.0) for `overdue_delay_multiplier`
- Old configs without the field will work with default behavior
- All policies continue to work without reprioritize actions

## Future Enhancements

### Potential Extensions

1. **Regulatory reporting**: Track overdue transaction counts and durations for compliance
2. **Dynamic multiplier**: Increase multiplier over time (e.g., 5x at deadline, 10x after 50 ticks)
3. **Overdue categories**: Different penalty tiers based on transaction characteristics
4. **Settlement guarantees**: Collateral requirements specifically for overdue transactions
5. **Inter-bank penalties**: Sender pays penalty to receiver for late settlement

### Research Questions

- What is the optimal `overdue_delay_multiplier` to match real-world behavior?
- How do overdue transactions affect system-wide gridlock?
- What policies minimize overdue costs while maintaining liquidity?
- How does overdue handling interact with LSM (Liquidity-Saving Mechanism)?

## References

- Implementation plan: [`docs/plans/realistic-dropped-transactions.md`](plans/realistic-dropped-transactions.md)
- Example policies: [`examples/policies/`](../examples/policies/)
- Transaction model: [`backend/src/models/transaction.rs`](../backend/src/models/transaction.rs)
- RTGS settlement: [`backend/src/settlement/rtgs.rs`](../backend/src/settlement/rtgs.rs)
- Policy interpreter: [`backend/src/policy/tree/interpreter.rs`](../backend/src/policy/tree/interpreter.rs)

---

*Last updated: 2025-11-04*
*Implementation: Phases 1-5 complete (481/481 Rust tests passing)*
