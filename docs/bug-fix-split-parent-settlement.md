# Bug Fix: Split Parent Settlement Tracking

**Date**: 2025-11-05
**Bug**: Settlement rate discrepancy when transactions are split
**Status**: Root cause identified, fix in progress

---

## Problem Summary

Settlement rate calculation shows discrepancy between:
- **Official metric**: 1063 settlements (via `is_effectively_settled()`)
- **Debug count**: 1042 fully settled arrivals (via `is_fully_settled()`)
- **Difference**: 21 transactions

### Root Cause

When a transaction is split into children:
1. **Children are created** with `parent_id` set to parent's ID
2. **Children settle independently** and their `remaining_amount` → 0
3. **Parent's `remaining_amount` is NEVER updated** - stays at original value
4. **Result**: Parent shows `remaining_amount = amount` even though all children settled

This causes:
- `is_effectively_settled(parent)` → `TRUE` (all children settled)
- `is_fully_settled(parent)` → `FALSE` (remaining_amount != 0)

## Evidence

Investigated 5_agent_lsm_collateral_scenario.yaml:
- **21 split parents identified**
- **84 total children** (4 children per parent)
- **All 84 children fully settled** ($116,153.48 total)
- **All 21 parents show $0.00 settled** (remaining_amount unchanged)

### Example Parent Transaction

```
Parent: 2ac0aa7c-beb5-4599-af5e-a56ecc991420
Amount: $7,887.16
Parent remaining_amount: $7,887.16  ← SHOULD BE $0.00
Children: 4 (all settled)
Total child settled: $7,887.16
```

## Transaction Split Flow (Current - BUGGY)

```rust
// 1. Parent created
let parent = Transaction::new("A", "B", 100_000, 0, 10);
// parent.amount = 100_000
// parent.remaining_amount = 100_000

// 2. Policy decides to split into 4 children
for child_amount in [25_000, 25_000, 25_000, 25_000] {
    let child = Transaction::new_split(
        "A", "B", child_amount, 0, 10,
        parent.id().to_string()
    );
    // child.parent_id = Some(parent_id)
    // child.amount = 25_000
    // child.remaining_amount = 25_000
}

// 3. Children settle
child1.settle(25_000, tick)?;  // child1.remaining_amount = 0
child2.settle(25_000, tick)?;  // child2.remaining_amount = 0
child3.settle(25_000, tick)?;  // child3.remaining_amount = 0
child4.settle(25_000, tick)?;  // child4.remaining_amount = 0

// 4. Parent state UNCHANGED (BUG!)
// parent.remaining_amount = 100_000  ← WRONG! Should be 0
```

## Expected Behavior

When a child settles, the parent's `remaining_amount` should be reduced:

```rust
// When child settles
child.settle(amount, tick)?;

// SHOULD ALSO DO:
if let Some(parent_id) = child.parent_id() {
    if let Some(parent) = state.get_transaction_mut(parent_id) {
        parent.remaining_amount -= amount;

        // Update parent status if fully settled
        if parent.remaining_amount == 0 {
            parent.status = TransactionStatus::Settled { tick };
        }
    }
}
```

## Fix Location

Need to update RTGS settlement code in `backend/src/settlement/rtgs.rs`:

1. **`try_settle()` function** (line 104-135)
2. **`submit_transaction()` function** (line 211-270)
3. **`process_queue()` function** (line 322-392)

After calling `transaction.settle(amount, tick)`, add logic to update parent.

## Implementation Plan

### Step 1: Add helper function to Transaction

Add method to reduce parent's remaining amount:

```rust
// In backend/src/models/transaction.rs
impl Transaction {
    /// Reduce remaining amount by settled child amount
    /// Used when a child transaction settles
    pub(crate) fn reduce_remaining(&mut self, amount: i64) -> Result<(), TransactionError> {
        if amount > self.remaining_amount {
            return Err(TransactionError::AmountExceedsRemaining {
                amount,
                remaining: self.remaining_amount,
            });
        }

        self.remaining_amount -= amount;
        Ok(())
    }
}
```

### Step 2: Update RTGS settlement functions

Add parent update logic after each `transaction.settle()` call:

```rust
// After transaction.settle(amount, tick)?;
if let Some(parent_id) = transaction.parent_id() {
    if let Some(parent) = state.get_transaction_mut(parent_id) {
        parent.reduce_remaining(amount)?;

        // If parent now fully settled, update status
        if parent.remaining_amount() == 0 {
            // Parent is now fully settled via all children
            // Mark it as settled (INTERNAL - don't trigger events)
            parent.status = TransactionStatus::Settled { tick };
        }
    }
}
```

### Step 3: Write comprehensive tests

```rust
#[test]
fn test_split_parent_settlement_tracking() {
    // Create parent and split into children
    // Settle all children
    // Verify parent's remaining_amount reduced to 0
    // Verify parent is marked as fully settled
}

#[test]
fn test_partial_child_settlement() {
    // Create parent with 4 children
    // Settle 2 children
    // Verify parent's remaining_amount reduced by 50%
    // Verify parent is NOT yet fully settled
}
```

## Testing Strategy

1. **Unit test**: Split parent settlement in `backend/tests/`
2. **Integration test**: Run 5_agent_lsm_collateral_scenario.yaml
3. **Verify metrics**:
   - Settlement rate should be ≤ 100%
   - Official and debug counts should match
   - `is_effectively_settled()` and `is_fully_settled()` should agree

## Expected Results After Fix

Running 5_agent_lsm_collateral_scenario.yaml:
```
Official metrics:
  total_arrivals:    1078
  total_settlements: 1042  ← Should match debug count
  settlement_rate:   0.9666 (96.7%)

Debug counts:
  arrivals:          1078
  settled_arrivals:  1042  ← Should match official count

MATCH! ✅
```

---

## Related Files

- `backend/src/settlement/rtgs.rs` - Settlement engine (FIX HERE)
- `backend/src/models/transaction.rs` - Transaction model (add helper)
- `backend/src/orchestrator/engine.rs` - Split creation (lines 2150-2169)
- `docs/evaluation-issues-summary.md` - Original bug report
- `api/tests/integration/test_settlement_rate_debug.py` - Debug investigation
- `api/tests/integration/test_split_parent_investigation.py` - Split analysis

---

**Next Step**: Implement fix in rtgs.rs
