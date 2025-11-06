# Plan: Fix LSM Cycle Display and Add Offset/Liquidity Breakdown

**Status**: Planning
**Priority**: Medium
**Created**: 2025-11-05

---

## Problem Statement

The LSM cycle visualization in CLI output has two major issues:

### Issue 1: Displaying "unknown" agent names and "$0.00" amounts

**Current output:**
```
🔄 LSM Cycles (3):

   Cycle 1 (Bilateral):
   unknown ⇄ unknown
   • unknown→unknown: TX 4b292c96 ($0.00)
   • unknown→unknown: TX fb82211a ($0.00)
```

**Root cause**:
- The `output.py` code calls `orch.get_transaction_details(tx_id)` to look up agent names
- In full-replay mode (from database), the orchestrator doesn't have transaction details loaded
- The lookup returns `None`, resulting in "unknown" and 0 amounts

### Issue 2: Not showing offset vs. liquidity breakdown

**Current behavior**:
- Only shows individual transaction amounts
- Doesn't distinguish between:
  - Amount settled via bilateral/multilateral offset (netting)
  - Amount requiring actual liquidity flow

**Desired behavior** (per T2 implementation plan):
- Show how much was offset (netted out)
- Show how much required liquidity (net flow)
- Show direction of net liquidity flow between agents

---

## Root Cause Analysis

### Data Flow

1. **Rust Settlement** (`backend/src/settlement/lsm.rs`):
   - `settle_bilateral_offsets()` settles A↔B pairs
   - `settle_cycle()` settles multilateral cycles with net positions
   - Logs `Event::LsmBilateralOffset` and `Event::LsmCycleSettlement`
   - Creates `LsmCycleEvent` for persistence

2. **Event Structure** (`backend/src/models/event.rs`):
   ```rust
   LsmBilateralOffset {
       tick: usize,
       tx_id_a: String,  // Only TX IDs, no agent names!
       tx_id_b: String,
       amount: i64,      // Offset amount (min of both directions)
   }

   LsmCycleSettlement {
       tick: usize,
       tx_ids: Vec<String>,  // Only TX IDs
       cycle_value: i64,     // Total value
   }
   ```

3. **LsmCycleEvent** (for persistence):
   ```rust
   pub struct LsmCycleEvent {
       tick: usize,
       day: usize,
       cycle_type: String,  // "bilateral" or "multilateral"
       cycle_length: usize,
       agents: Vec<String>,        // ✓ Has agent names!
       transactions: Vec<String>,   // ✓ Has TX IDs
       settled_value: i64,          // Net settled value
       total_value: i64,            // Gross total

       // MISSING:
       // - Individual transaction amounts
       // - Net positions per agent
       // - Liquidity flows (direction + amount)
   }
   ```

4. **Python Display** (`api/payment_simulator/cli/output.py`):
   - Receives events via FFI
   - Tries to look up transaction details with `orch.get_transaction_details()`
   - In full-replay mode, this fails → "unknown"

---

## Solution Design

### Approach: Enhance Event Data (Not Database Lookups)

**Principle**: Events should be **self-contained** for display. Don't rely on lookups.

### Phase 1: Enhance Event Structures

#### 1.1 Add Agent Info to Events

**Modify `Event` enum** (`backend/src/models/event.rs`):

```rust
/// Transaction settled via LSM bilateral offset
LsmBilateralOffset {
    tick: usize,
    agent_a: String,         // NEW: First agent ID
    agent_b: String,         // NEW: Second agent ID
    tx_id_a: String,
    tx_id_b: String,
    amount_a_to_b: i64,      // NEW: A→B total amount
    amount_b_to_a: i64,      // NEW: B→A total amount
    offset_amount: i64,      // Renamed from 'amount' (min of both)
    net_liquidity: i64,      // NEW: abs(amount_a - amount_b)
    net_direction: String,   // NEW: "A_to_B" or "B_to_A"
},

/// Transaction settled via LSM cycle detection
LsmCycleSettlement {
    tick: usize,
    agents: Vec<String>,            // NEW: Agent IDs in cycle
    tx_ids: Vec<String>,
    tx_amounts: Vec<i64>,           // NEW: Individual tx amounts
    net_positions: HashMap<String, i64>,  // NEW: Net per agent
    cycle_value: i64,               // Total gross value
    max_net_outflow: i64,          // NEW: Largest net requiring liquidity
},
```

**Benefits**:
- Events are self-contained (no lookups needed)
- Supports replay from DB without orchestrator
- Provides all data for rich visualization

**Drawbacks**:
- Larger event size
- Breaking change to Event enum

#### 1.2 Enhance LsmCycleEvent

**Modify `LsmCycleEvent`** (`backend/src/settlement/lsm.rs`):

```rust
#[derive(Debug, Clone, PartialEq, serde::Serialize, serde::Deserialize)]
pub struct LsmCycleEvent {
    pub tick: usize,
    pub day: usize,
    pub cycle_type: String,
    pub cycle_length: usize,
    pub agents: Vec<String>,
    pub transactions: Vec<String>,

    // NEW: Individual transaction details
    pub tx_amounts: Vec<i64>,
    pub tx_senders: Vec<String>,
    pub tx_receivers: Vec<String>,

    // NEW: Net position analysis
    pub net_positions: HashMap<String, i64>,
    pub max_net_outflow: i64,
    pub max_net_outflow_agent: String,

    // Existing
    pub settled_value: i64,
    pub total_value: i64,
}
```

**This structure will be used**:
- For persistence to `lsm_cycles` table
- For CLI display (convert from Event → LsmCycleEvent)

---

### Phase 2: Update Settlement Code to Populate Events

#### 2.1 Bilateral Offsetting

**In `settle_bilateral_offsets()`** (lsm.rs ~line 880):

```rust
// When creating bilateral events
for pair in &bilateral_result.offset_pairs {
    let offset_amount = pair.amount_a_to_b.min(pair.amount_b_to_a);
    let net_liquidity = (pair.amount_a_to_b - pair.amount_b_to_a).abs();
    let net_direction = if pair.amount_a_to_b > pair.amount_b_to_a {
        format!("{}_to_{}", pair.agent_a, pair.agent_b)
    } else {
        format!("{}_to_{}", pair.agent_b, pair.agent_a)
    };

    // Log event with full details
    self.log_event(Event::LsmBilateralOffset {
        tick,
        agent_a: pair.agent_a.clone(),
        agent_b: pair.agent_b.clone(),
        tx_id_a: pair.txs_a_to_b[0].clone(),  // Representative TX
        tx_id_b: pair.txs_b_to_a[0].clone(),
        amount_a_to_b: pair.amount_a_to_b,
        amount_b_to_a: pair.amount_b_to_a,
        offset_amount,
        net_liquidity,
        net_direction,
    });
}
```

#### 2.2 Cycle Settlement

**In `settle_cycle()`** (lsm.rs ~line 723):

```rust
// After calculating net_positions (line 747)
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

// Build transaction details vectors
let mut tx_amounts = Vec::new();
let mut tx_senders = Vec::new();
let mut tx_receivers = Vec::new();

for tx_id in &cycle.transactions {
    if let Some(tx) = state.get_transaction(tx_id) {
        tx_amounts.push(tx.remaining_amount());
        tx_senders.push(tx.sender_id().to_string());
        tx_receivers.push(tx.receiver_id().to_string());
    }
}

// Log enhanced event
self.log_event(Event::LsmCycleSettlement {
    tick,
    agents: cycle.agents.clone(),
    tx_ids: cycle.transactions.clone(),
    tx_amounts,
    net_positions: net_positions.clone(),
    cycle_value: cycle.total_value,
    max_net_outflow,
});
```

---

### Phase 3: Update FFI to Serialize Enhanced Events

**Modify `get_tick_events()`** (`backend/src/ffi/orchestrator.rs` ~line 985):

```rust
Event::LsmBilateralOffset {
    tick,
    agent_a,
    agent_b,
    tx_id_a,
    tx_id_b,
    amount_a_to_b,
    amount_b_to_a,
    offset_amount,
    net_liquidity,
    net_direction,
} => {
    json!({
        "tick": tick,
        "event_type": "LsmBilateralOffset",
        "agent_a": agent_a,
        "agent_b": agent_b,
        "tx_id_a": tx_id_a,
        "tx_id_b": tx_id_b,
        "amount_a_to_b": amount_a_to_b,
        "amount_b_to_a": amount_b_to_a,
        "offset_amount": offset_amount,
        "net_liquidity": net_liquidity,
        "net_direction": net_direction,
    })
}

Event::LsmCycleSettlement {
    tick,
    agents,
    tx_ids,
    tx_amounts,
    net_positions,
    cycle_value,
    max_net_outflow,
} => {
    json!({
        "tick": tick,
        "event_type": "LsmCycleSettlement",
        "agents": agents,
        "tx_ids": tx_ids,
        "tx_amounts": tx_amounts,
        "net_positions": net_positions,
        "cycle_value": cycle_value,
        "max_net_outflow": max_net_outflow,
    })
}
```

---

### Phase 4: Update Python Display Logic

**Enhance `log_lsm_cycle_visualization()`** (`api/payment_simulator/cli/output.py` ~line 907):

```python
def log_lsm_cycle_visualization(orch, events, quiet=False):
    """Visualize LSM cycles with offset/liquidity breakdown."""
    if quiet:
        return

    lsm_bilateral = [e for e in events if e.get("event_type") == "LsmBilateralOffset"]
    lsm_cycles = [e for e in events if e.get("event_type") == "LsmCycleSettlement"]

    total_cycles = len(lsm_bilateral) + len(lsm_cycles)
    if total_cycles == 0:
        return

    console.print()
    console.print(f"🔄 [magenta]LSM Cycles ({total_cycles}):[/magenta]")
    console.print()

    cycle_num = 1

    # Bilateral offsets
    for event in lsm_bilateral:
        console.print(f"   Cycle {cycle_num} (Bilateral):")

        agent_a = event["agent_a"]
        agent_b = event["agent_b"]
        amount_a_to_b = event["amount_a_to_b"]
        amount_b_to_a = event["amount_b_to_a"]
        offset = event["offset_amount"]
        net_liquidity = event["net_liquidity"]
        net_dir = event["net_direction"]

        console.print(f"   {agent_a} ⇄ {agent_b}")
        console.print(f"   • {agent_a}→{agent_b}: TX {event['tx_id_a'][:8]} (${amount_a_to_b / 100:,.2f})")
        console.print(f"   • {agent_b}→{agent_a}: TX {event['tx_id_b'][:8]} (${amount_b_to_a / 100:,.2f})")
        console.print()
        console.print(f"   💫 [cyan]Offset: ${offset / 100:,.2f}[/cyan] (netted out)")

        if net_liquidity > 0:
            direction_arrow = "→" if "to" in net_dir else "←"
            from_agent, to_agent = net_dir.split("_to_")
            console.print(
                f"   💰 [yellow]Net Liquidity: ${net_liquidity / 100:,.2f}[/yellow] "
                f"({from_agent} {direction_arrow} {to_agent})"
            )

        console.print()
        cycle_num += 1

    # Multilateral cycles
    for event in lsm_cycles:
        agents = event["agents"]
        tx_ids = event["tx_ids"]
        tx_amounts = event["tx_amounts"]
        net_positions = event["net_positions"]
        cycle_value = event["cycle_value"]
        max_net_outflow = event["max_net_outflow"]

        num_agents = len(agents) - 1  # Exclude duplicate
        console.print(f"   Cycle {cycle_num} (Multilateral - {num_agents} agents):")

        # Show cycle chain: A → B → C → A
        cycle_str = " → ".join(agents)
        console.print(f"   {cycle_str}")

        # Show each transaction
        for i, tx_id in enumerate(tx_ids):
            sender = event.get("tx_senders", [])[i] if i < len(event.get("tx_senders", [])) else agents[i]
            receiver = event.get("tx_receivers", [])[i] if i < len(event.get("tx_receivers", [])) else agents[i+1]
            amount = tx_amounts[i]
            console.print(f"   • {sender}→{receiver}: TX {tx_id[:8]} (${amount / 100:,.2f})")

        console.print()
        console.print(f"   💰 [cyan]Gross Value: ${cycle_value / 100:,.2f}[/cyan]")
        console.print(f"   💫 [yellow]Max Liquidity Used: ${max_net_outflow / 100:,.2f}[/yellow]")

        liquidity_saved = cycle_value - max_net_outflow
        if liquidity_saved > 0:
            efficiency = (liquidity_saved / cycle_value) * 100
            console.print(f"   ✨ [green]Liquidity Saved: ${liquidity_saved / 100:,.2f} ({efficiency:.1f}%)[/green]")

        # Show net positions
        console.print()
        console.print("   Net Positions:")
        for agent, net_pos in sorted(net_positions.items()):
            if net_pos > 0:
                console.print(f"   • {agent}: [green]+${net_pos / 100:,.2f}[/green] (inflow)")
            elif net_pos < 0:
                console.print(f"   • {agent}: [red]-${abs(net_pos) / 100:,.2f}[/red] (outflow)")
            else:
                console.print(f"   • {agent}: [dim]$0.00[/dim] (net zero)")

        console.print()
        cycle_num += 1
```

**Example Output**:

```
🔄 LSM Cycles (3):

   Cycle 1 (Bilateral):
   BANK_A ⇄ BANK_B
   • BANK_A→BANK_B: TX 4b292c96 ($340.11)
   • BANK_B→BANK_A: TX fb82211a ($326.17)

   💫 Offset: $326.17 (netted out)
   💰 Net Liquidity: $13.94 (BANK_A → BANK_B)

   Cycle 2 (Multilateral - 3 agents):
   BANK_A → BANK_B → BANK_C → BANK_A
   • BANK_A→BANK_B: TX c8c3e739 ($462.51)
   • BANK_B→BANK_C: TX (unknown) ($500.00)
   • BANK_C→BANK_A: TX 5b9b863e ($463.07)

   💰 Gross Value: $1,425.58
   💫 Max Liquidity Used: $38.56
   ✨ Liquidity Saved: $1,387.02 (97.3%)

   Net Positions:
   • BANK_A: -$0.56 (outflow)
   • BANK_B: -$37.49 (outflow)
   • BANK_C: +$38.05 (inflow)
```

---

## Migration Strategy

### Breaking Changes

1. **Event enum**: New fields added to `LsmBilateralOffset` and `LsmCycleSettlement`
2. **LsmCycleEvent**: New fields for tx details and net positions
3. **FFI serialization**: New JSON fields in event output

### Backward Compatibility

**Option 1: Non-breaking (Recommended)**
- Keep old event fields, add new ones as optional
- Python code checks for new fields first, falls back to old behavior
- Gradual migration

**Option 2: Breaking**
- Replace old fields entirely
- Requires updating all consumers
- Faster, cleaner

**Recommendation**: Use Option 1 initially, clean up in next major version.

---

## Testing Strategy

### Unit Tests (Rust)

```rust
#[test]
fn test_lsm_bilateral_event_includes_agents() {
    // Setup bilateral offset scenario
    // Verify Event::LsmBilateralOffset has agent_a, agent_b
    // Verify net_liquidity calculation
}

#[test]
fn test_lsm_cycle_event_includes_net_positions() {
    // Setup 3-agent cycle with unequal amounts
    // Verify Event::LsmCycleSettlement has net_positions
    // Verify max_net_outflow calculation
}
```

### Integration Tests (Python)

```python
def test_lsm_display_shows_agent_names():
    """Verify CLI output shows actual agent names, not 'unknown'."""
    # Run simulation with LSM
    # Capture output
    # Assert "BANK_A" appears (not "unknown")

def test_lsm_display_shows_offset_vs_liquidity():
    """Verify offset and net liquidity are displayed."""
    # Run simulation with bilateral offset
    # Assert "Offset:" appears in output
    # Assert "Net Liquidity:" appears
```

---

## Implementation Checklist

- [ ] Phase 1.1: Enhance `Event` enum with agent info
- [ ] Phase 1.2: Enhance `LsmCycleEvent` with tx details
- [ ] Phase 2.1: Update bilateral offsetting to populate events
- [ ] Phase 2.2: Update cycle settlement to populate events
- [ ] Phase 3: Update FFI serialization
- [ ] Phase 4: Update Python display logic
- [ ] Write Rust unit tests
- [ ] Write Python integration tests
- [ ] Update documentation
- [ ] Test with real simulation scenarios

---

## Success Criteria

✅ Agent names display correctly (no "unknown")
✅ Transaction amounts display correctly (no "$0.00")
✅ Bilateral offsets show:
   - Individual transaction amounts
   - Offset amount (netted)
   - Net liquidity direction and amount

✅ Multilateral cycles show:
   - Individual transaction amounts
   - Gross total value
   - Net positions per agent
   - Max liquidity used
   - Liquidity saved percentage

✅ Works in both live and full-replay modes
✅ No database lookups needed for display
✅ Events are self-contained

---

## Timeline Estimate

- Phase 1: Enhance data structures (2 hours)
- Phase 2: Update settlement code (3 hours)
- Phase 3: Update FFI (1 hour)
- Phase 4: Update Python display (2 hours)
- Testing (2 hours)

**Total**: ~10 hours (1.5 days)

---

**Next Steps**:
1. Review this plan
2. Get approval for Event enum changes
3. Implement Phase 1 (data structures)
4. Iterate through remaining phases
