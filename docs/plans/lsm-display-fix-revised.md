# Revised Plan: LSM Display Enhancement - Offset/Liquidity Breakdown

**Status**: Bug Investigation in Progress
**Priority**: HIGH (Duplicate Transaction Bug Found)
**Created**: 2025-11-05
**Updated**: 2025-11-05 (after duplicate transaction investigation)

---

## ⚠️ CRITICAL BUG DISCOVERED

**Issue**: Transaction `c6979dfa` appears in TWO different LSM bilateral cycles:
```
Cycle 1 (Bilateral):
CORRESPONDENT_HUB ⇄ REGIONAL_TRUST
• CORRESPONDENT_HUB→REGIONAL_TRUST: TX c6979dfa ($4,203.00)
• REGIONAL_TRUST→CORRESPONDENT_HUB: TX 4b6bb32c ($5,317.63)

Cycle 2 (Bilateral):
REGIONAL_TRUST ⇄ CORRESPONDENT_HUB
• REGIONAL_TRUST→CORRESPONDENT_HUB: TX d073dd61 ($4,333.87)
• CORRESPONDENT_HUB→REGIONAL_TRUST: TX c6979dfa ($4,203.00)
```

**This should be impossible** - a transaction can only be settled once and removed from the queue.

See [Investigation Findings](#investigation-findings) below for root cause analysis.

---

## Executive Summary

After reviewing the current implementation, **agent names and amounts are already working correctly**! The display shows proper agent names and transaction amounts via the `LsmCycleEvent` struct stored in the database.

**What's DONE**:
- ✅ Agent names display correctly (not "unknown")
- ✅ Transaction amounts display correctly (not "$0.00")
- ✅ Cycle chain visualization works (A → B → C → A)
- ✅ `LsmCycleEvent` has `agents` and `transactions` fields
- ✅ Database persistence of LSM cycles works
- ✅ Replay mode reconstruction works

**What's MISSING** (from T2 implementation plan):
- ❌ Offset vs. liquidity breakdown for bilateral offsets
- ❌ Net positions per agent for multilateral cycles
- ❌ Gross value vs. max liquidity used
- ❌ Liquidity saved percentage
- ❌ Net settlement direction display

**New Bugs Found**:
- 🐛 Duplicate transaction in multiple cycles (CRITICAL)
- 🐛 `tx_amounts` / `transactions` vector length mismatch
- 🐛 Event conversion discards transactions beyond first 2

---

## Current Implementation Status

### What's Working

**Data Flow**:
1. Rust `LsmCycleEvent` captures cycle data with agent IDs (✅)
2. Events stored in `lsm_cycles` database table (✅)
3. Replay reconstructs events with `agent_ids` and `tx_ids` (✅)
4. Display uses `event.get("agent_ids")` for visualization (✅)

**Current Output**:
```
🔄 LSM Cycles (1):

   Cycle 1 (Multilateral - 3 agents):
   BANK_C → BANK_B → BANK_A → BANK_C
   • TX d7a5618a ($750.23)
   • TX c9a76643 ($332.46)
   • TX c18c8669 ($539.31)
```

### What's Missing

**No offset/liquidity analysis**:
- Doesn't show how much was offset (netted) vs. actual liquidity flow
- Doesn't show net positions per agent
- Doesn't show liquidity efficiency

**Desired Output** (from plan):
```
🔄 LSM Cycles (1):

   Cycle 1 (Multilateral - 3 agents):
   BANK_C → BANK_B → BANK_A → BANK_C
   • BANK_C→BANK_B: TX d7a5618a ($750.23)
   • BANK_B→BANK_A: TX c9a76643 ($332.46)
   • BANK_A→BANK_C: TX c18c8669 ($539.31)

   💰 Gross Value: $1,621.92
   💫 Max Liquidity Used: $217.77
   ✨ Liquidity Saved: $1,404.15 (86.6%)

   Net Positions:
   • BANK_A: -$210.92 (outflow - needed liquidity!)
   • BANK_B: +$303.77 (inflow)
   • BANK_C: -$92.85 (outflow)
```

---

## What Needs to Be Added

### Phase 1: Enhance `LsmCycleEvent` Structure

**Current structure** (`backend/src/settlement/lsm.rs:167`):
```rust
pub struct LsmCycleEvent {
    pub tick: usize,
    pub day: usize,
    pub cycle_type: String,
    pub cycle_length: usize,
    pub agents: Vec<String>,        // ✅ Has this
    pub transactions: Vec<String>,   // ✅ Has this
    pub settled_value: i64,          // Net settled value
    pub total_value: i64,            // Gross total
}
```

**Add these fields**:
```rust
pub struct LsmCycleEvent {
    // ... existing fields ...

    // NEW: Individual transaction amounts (for display)
    pub tx_amounts: Vec<i64>,

    // NEW: Net position analysis (T2-compliant)
    pub net_positions: HashMap<String, i64>,

    // NEW: Liquidity metrics
    pub max_net_outflow: i64,         // Largest net requiring liquidity
    pub max_net_outflow_agent: String, // Who needed the liquidity
}
```

### Phase 2: Populate New Fields in Settlement Code

**Location**: `backend/src/settlement/lsm.rs`, around line 890 (bilateral) and 927 (cycle)

**For bilateral offsets**:
```rust
cycle_events.push(LsmCycleEvent {
    // ... existing fields ...
    tx_amounts: vec![pair.amount_a_to_b, pair.amount_b_to_a],
    net_positions: {
        let mut map = HashMap::new();
        let net_a = pair.amount_b_to_a as i64 - pair.amount_a_to_b as i64;
        let net_b = pair.amount_a_to_b as i64 - pair.amount_b_to_a as i64;
        map.insert(pair.agent_a.clone(), net_a);
        map.insert(pair.agent_b.clone(), net_b);
        map
    },
    max_net_outflow: (pair.amount_a_to_b - pair.amount_b_to_a).abs().max(
        (pair.amount_b_to_a - pair.amount_a_to_b).abs()
    ),
    max_net_outflow_agent: if pair.amount_a_to_b > pair.amount_b_to_a {
        pair.agent_a.clone()
    } else {
        pair.agent_b.clone()
    },
});
```

**For multilateral cycles** (after line 747 where net_positions is calculated):
```rust
// Already calculating net_positions for feasibility check!
let net_positions = calculate_cycle_net_positions(state, cycle);

// Find max net outflow
let max_net_outflow = net_positions.values()
    .filter(|&&v| v < 0)
    .map(|v| v.abs())
    .max()
    .unwrap_or(0);

let max_net_outflow_agent = net_positions.iter()
    .filter(|(_, &v)| v < 0)
    .max_by_key(|(_, v)| v.abs())
    .map(|(agent, _)| agent.clone())
    .unwrap_or_default();

// Build tx_amounts vector
let tx_amounts: Vec<i64> = cycle.transactions.iter()
    .filter_map(|tx_id| state.get_transaction(tx_id))
    .map(|tx| tx.remaining_amount())
    .collect();

// Add to event
let event = LsmCycleEvent {
    tick,
    day,
    cycle_type,
    cycle_length,
    agents: cycle.agents.clone(),
    transactions: cycle.transactions.clone(),
    settled_value: result.settled_value,
    total_value: cycle.total_value,
    tx_amounts,              // NEW
    net_positions: net_positions.clone(),  // NEW
    max_net_outflow,         // NEW
    max_net_outflow_agent,   // NEW
};
```

### Phase 3: Update Database Schema

**Location**: `api/payment_simulator/persistence/schema.py`

**Add columns to `lsm_cycles` table**:
```python
CREATE TABLE lsm_cycles (
    # ... existing columns ...
    tx_amounts TEXT,              -- JSON array of transaction amounts
    net_positions TEXT,           -- JSON object {agent_id: net_value}
    max_net_outflow INTEGER,      -- Largest net outflow in cents
    max_net_outflow_agent TEXT,   -- Agent ID requiring most liquidity
    # ...
)
```

**Migration strategy**:
- Make new columns optional (allow NULL)
- Existing data won't have these fields
- New simulations will populate them

### Phase 4: Update Display Logic

**Location**: `api/payment_simulator/cli/output.py`

**Enhance multilateral cycle display** (around line 473-486):

```python
# LSM cycles
if lsm_cycles:
    console.print(f"   [magenta]LSM Cycle ({len(lsm_cycles)}):[/magenta]")
    for event in lsm_cycles:
        agent_ids = event.get("agent_ids", [])
        tx_amounts = event.get("tx_amounts", [])
        net_positions = event.get("net_positions", {})
        total_value = event.get("total_value", 0)
        max_net_outflow = event.get("max_net_outflow", 0)

        if agent_ids:
            cycle_str = " → ".join(agent_ids) + f" → {agent_ids[0]}"
            console.print(f"   • Cycle: {cycle_str}")

            # Show each transaction with sender/receiver
            tx_ids = event.get("tx_ids", [])
            for i, tx_id in enumerate(tx_ids):
                if i < len(agent_ids) and i < len(tx_amounts):
                    sender = agent_ids[i]
                    receiver = agent_ids[(i + 1) % len(agent_ids)]
                    amount = tx_amounts[i]
                    console.print(
                        f"     - {sender}→{receiver}: TX {tx_id[:8]} (${amount / 100:,.2f})"
                    )

            console.print()

            # Show liquidity analysis
            console.print(f"     [cyan]💰 Gross Value: ${total_value / 100:,.2f}[/cyan]")

            if max_net_outflow > 0:
                console.print(
                    f"     [yellow]💫 Max Liquidity Used: ${max_net_outflow / 100:,.2f}[/yellow]"
                )

                liquidity_saved = total_value - max_net_outflow
                if liquidity_saved > 0:
                    efficiency = (liquidity_saved / total_value) * 100
                    console.print(
                        f"     [green]✨ Liquidity Saved: ${liquidity_saved / 100:,.2f} "
                        f"({efficiency:.1f}%)[/green]"
                    )

            # Show net positions
            if net_positions:
                console.print()
                console.print("     Net Positions:")
                for agent_id in agent_ids:  # Preserve cycle order
                    if agent_id in net_positions:
                        net_pos = net_positions[agent_id]
                        if net_pos > 0:
                            console.print(
                                f"     • {agent_id}: [green]+${net_pos / 100:,.2f}[/green] (inflow)"
                            )
                        elif net_pos < 0:
                            console.print(
                                f"     • {agent_id}: [red]-${abs(net_pos) / 100:,.2f}[/red] "
                                "(outflow - used liquidity)"
                            )
                        else:
                            console.print(f"     • {agent_id}: [dim]$0.00[/dim] (net zero)")

            console.print()
```

---

## Implementation Checklist

### Phase 1: Rust Data Structures
- [ ] Add fields to `LsmCycleEvent` struct
- [ ] Update Serde serialization for new fields

### Phase 2: Settlement Code
- [ ] Populate `tx_amounts` in bilateral offset events
- [ ] Populate `net_positions` in bilateral offset events
- [ ] Populate `tx_amounts` in cycle settlement events
- [ ] Populate `net_positions` in cycle settlement events
- [ ] Calculate `max_net_outflow` and `max_net_outflow_agent`

### Phase 3: Database
- [ ] Add columns to `lsm_cycles` table schema
- [ ] Update persistence code to write new fields
- [ ] Update query code to read new fields
- [ ] Test migration for existing databases

### Phase 4: Display
- [ ] Update `log_settlement_details()` to show offset/liquidity breakdown
- [ ] Add liquidity metrics display
- [ ] Add net positions display
- [ ] Format for readability

### Phase 5: Testing
- [ ] Test with bilateral offsets
- [ ] Test with multilateral cycles
- [ ] Test with varying amounts
- [ ] Test replay mode with new data
- [ ] Test replay mode with old data (missing fields)

---

## Example Output Comparison

### Before (Current)
```
🔄 LSM Cycles (1):

   Cycle 1 (Multilateral - 3 agents):
   BANK_C → BANK_B → BANK_A → BANK_C
   • TX d7a5618a ($750.23)
   • TX c9a76643 ($332.46)
   • TX c18c8669 ($539.31)
```

### After (With Enhancement)
```
🔄 LSM Cycles (1):

   Cycle 1 (Multilateral - 3 agents):
   BANK_C → BANK_B → BANK_A → BANK_C
   • BANK_C→BANK_B: TX d7a5618a ($750.23)
   • BANK_B→BANK_A: TX c9a76643 ($332.46)
   • BANK_A→BANK_C: TX c18c8669 ($539.31)

   💰 Gross Value: $1,622.00
   💫 Max Liquidity Used: $217.77
   ✨ Liquidity Saved: $1,404.23 (86.6%)

   Net Positions:
   • BANK_C: -$210.92 (outflow - used liquidity)
   • BANK_B: +$303.77 (inflow)
   • BANK_A: -$92.85 (outflow - used liquidity)
```

---

## Timeline Estimate

- **Phase 1** (Data structures): 1 hour
- **Phase 2** (Settlement code): 2 hours
- **Phase 3** (Database): 1 hour
- **Phase 4** (Display): 2 hours
- **Phase 5** (Testing): 2 hours

**Total**: ~8 hours (1 day)

---

## Success Criteria

✅ `LsmCycleEvent` contains all needed fields
✅ Bilateral offsets show offset vs. net liquidity
✅ Multilateral cycles show gross vs. net liquidity
✅ Net positions displayed per agent
✅ Liquidity saved percentage calculated
✅ Works in both live and replay modes
✅ Backward compatible with existing databases

---

## Notes

- Original plan called for changing Event enum, but that's NOT needed
- `LsmCycleEvent` already has agent names, just needs enhancement
- Settlement code already calculates `net_positions` for feasibility checks, just need to capture it
- Display logic already working, just needs to use additional fields

**Key insight**: Most of the hard work is already done! We just need to:
1. Capture net_positions that are already being calculated
2. Add a few derived metrics (max_net_outflow, liquidity_saved)
3. Display them nicely

---

---

## INVESTIGATION UPDATE (2025-11-05)

### Bug Confirmed

Transaction duplicates confirmed via debug output:
```
[LSM DEBUG] Logging 3 LSM cycle events
[LSM DEBUG] Logging bilateral event with 5 transactions: [29ea7cfb..., fa562ec6..., ...]
[LSM DEBUG] Logging bilateral event with 5 transactions: [29ea7cfb..., fa562ec6..., ...]
[LSM DEBUG] Logging bilateral event with 5 transactions: [29ea7cfb..., fa562ec6..., ...]
```

### Root Cause

The `run_lsm_pass()` function runs up to 3 iterations (MAX_ITERATIONS=3). Each iteration creates cycle events that get accumulated in `cycle_events` vector, leading to duplicates.

### Fixes Applied

1. ✅ Fixed `tx_amounts`/`transactions` length mismatch ([lsm.rs:903-916](backend/src/settlement/lsm.rs#L903-L916))
2. ✅ Added early `continue` check for processed pairs ([lsm.rs:294-300](backend/src/settlement/lsm.rs#L294-L300))
3. ⏭️ **TODO**: Prevent duplicate cycle events across iterations

### Next Fix Needed

Modify `run_lsm_pass()` to track which transactions have been settled and avoid creating duplicate cycle events.

---

**Next Steps**:
1. ✅ Complete TDD test for duplicate transactions
2. ✅ Fix vector length mismatch
3. ⏭️ Fix duplicate cycle events across iterations
4. ⏭️ Run full simulation to verify all fixes
5. Review this revised plan
6. Implement Phase 1 (add fields to LsmCycleEvent)
7. Implement Phase 2 (populate in settlement code)
8. Test with current simulation
9. Add database schema changes
10. Update display logic
