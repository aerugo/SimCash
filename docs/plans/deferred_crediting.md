# Deferred Crediting Implementation Plan

**Date**: 2025-12-02
**Priority**: High

---

## 1. Feature Overview

### 1.1 Current Behavior (Immediate Crediting)

When a payment settles in SimCash, the receiver's balance is credited **immediately** during queue processing:

```rust
// simulator/src/settlement/rtgs.rs:130-131
sender.debit(amount)?;
receiver.credit(amount);  // Immediate!
```

This allows "within-tick recycling": when A pays B, B can use those funds for its own transactions processed later in the **same tick**.

### 1.2 Academic Model (Deferred Crediting)

In academic payment models, incoming payments received in period t only become available in period t+1:
> "Liquidity evolves as: ℓ_t = ℓ_{t-1} - P_t x_t + R_t"

### 1.3 Implementation Goal

Add a configuration option `deferred_crediting: bool` (default: false) that:
- When **false**: Current behavior (immediate crediting)
- When **true**: Credits accumulate during tick, applied at end of tick

---

## 2. Edge Case Analysis

### 2.1 RTGS Immediate Settlement

**Scenario**: Transaction settles immediately on submission (sender has liquidity).

| Mode | Behavior |
|------|----------|
| Immediate | Receiver can use funds immediately |
| Deferred | Receiver credit is accumulated, applied at tick end |

**Edge Case**: A settles 3 transactions to B in same tick
- Immediate: B's balance increases after each settlement
- Deferred: B's accumulated_credits += each amount; balance updates once at tick end

### 2.2 RTGS Queue-2 Settlement

**Scenario**: Queued transaction settles when sender gains liquidity.

The sender gains liquidity from incoming payments. With deferred crediting:
- Those incoming payments don't immediately increase sender's balance
- Sender must rely on *opening balance* + *credit headroom* only

**Edge Case**: Circular payment with zero balances
```
Config:
  deferred_crediting: true
  BANK_A: balance=0, credit=0
  BANK_B: balance=0, credit=0

  Tick 0:
    A→B: $100 (arrives)
    B→A: $100 (arrives)
```

| Mode | Result |
|------|--------|
| Immediate | One settles (A→B), then other settles (B→A using incoming $100) |
| Deferred | **GRIDLOCK** - Neither can settle (both have $0 available) |

This is the **core behavioral difference** that matches academic payment models.

### 2.3 LSM Bilateral Offset

**Scenario**: A↔B bilateral offset.

```
A→B: $500
B→A: $300
Net: A→B $200
```

With LSM, both transactions settle atomically. The question: does the net receiver (B) get credited immediately?

| Mode | Behavior |
|------|----------|
| Immediate | B receives $200 net immediately (can use same tick) |
| Deferred | B's credit is deferred until tick end |

**Note**: LSM uses `adjust_balance()` which directly modifies balance. We need to intercept this.

### 2.4 LSM Cycle Settlement

**Scenario**: A→B→C→A cycle with net positions.

```
A→B: $500 (A net: -$300)
B→C: $800 (B net: +$100)
C→A: $700 (C net: +$200)
```

With LSM:
- A debited $300 (net payer)
- B credited $100 (net receiver)
- C credited $200 (net receiver)

With deferred crediting:
- Net payers (A): debits still apply immediately (reduces balance)
- Net receivers (B, C): credits deferred until tick end

**Critical**: Debits must still apply immediately, only credits are deferred.

### 2.5 Multiple Settlement Types in Same Tick

**Scenario**: Mix of RTGS immediate, Queue-2 release, LSM in one tick.

All credit operations across all settlement types should:
1. Accumulate in `DeferredCredits` during tick processing
2. Apply atomically at end of tick (in sorted agent order for determinism)

### 2.6 End-of-Day with Deferred Credits

**Scenario**: EOD processing happens with pending deferred credits.

**Order of operations**:
1. All tick processing (arrivals, policies, settlements)
2. Deferred credits applied
3. Cost accrual (uses final balances)
4. EOD processing (penalties for unsettled)
5. Tick advances

This ensures costs are calculated on actual balances after credits applied.

### 2.7 Collateral and Credit Limit Interactions

**Scenario**: Agent B needs posted collateral for credit headroom.

With deferred crediting:
- B cannot count incoming payments as available liquidity
- B must have sufficient opening balance + credit headroom
- This may cause more transactions to queue or fail

**Edge Case**: Policy posts collateral expecting incoming payments
- With immediate: Post collateral, receive payments, have headroom
- With deferred: Post collateral, incoming payments NOT available yet, may still lack headroom

### 2.8 Overdue Transaction Settlement

**Scenario**: Overdue transaction settles via RTGS or LSM.

The receiver credit behavior is identical to non-overdue:
- Deferred mode: Credit accumulated, applied at tick end
- Cost calculations use final balance after credits applied

### 2.9 Child Transaction Settlement (Split Payments)

**Scenario**: Parent transaction split into children, children settle.

Each child settlement credits the receiver. With deferred:
- All child credits accumulated
- Applied at tick end
- Parent marked fully settled when all children settle

### 2.10 Determinism Requirements

Credits must be applied in deterministic order to maintain replay identity.

**Solution**: Apply deferred credits in sorted agent ID order:
```rust
let mut agent_ids: Vec<_> = deferred_credits.pending.keys().collect();
agent_ids.sort();  // Deterministic order
for agent_id in agent_ids {
    // Apply credit
}
```

---

## 3. TDD Strategy

### 3.1 Test-First Development Phases

#### Phase 1: Core Gridlock Test (Acceptance Criterion)
```rust
#[test]
fn test_deferred_crediting_causes_gridlock_with_zero_balances() {
    // This is THE defining test - if this passes, feature is fundamentally correct
    let config = OrchestratorConfig {
        deferred_crediting: true,
        agents: vec![
            AgentConfig { id: "A", opening_balance: 0, unsecured_cap: 0, .. },
            AgentConfig { id: "B", opening_balance: 0, unsecured_cap: 0, .. },
        ],
        scenario_events: vec![
            CustomTransactionArrival { from: "A", to: "B", amount: 10000, tick: 0 },
            CustomTransactionArrival { from: "B", to: "A", amount: 10000, tick: 0 },
        ],
        ..
    };

    let mut orch = Orchestrator::new(config)?;
    orch.tick()?;

    // Both transactions should be queued (gridlock)
    assert_eq!(orch.queue_size(), 2);
    assert_eq!(orch.settlements_count(), 0);
}
```

#### Phase 2: Immediate Mode Unchanged
```rust
#[test]
fn test_immediate_crediting_allows_recycling() {
    // Same scenario but with deferred_crediting: false
    let config = OrchestratorConfig {
        deferred_crediting: false,  // Default
        // ... same agents and events ...
    };

    let mut orch = Orchestrator::new(config)?;
    orch.tick()?;

    // Both should settle (one enables the other)
    assert_eq!(orch.queue_size(), 0);
    assert_eq!(orch.settlements_count(), 2);
}
```

#### Phase 3: Deferred Credit Event Emission
```rust
#[test]
fn test_deferred_credit_event_emitted() {
    let config = OrchestratorConfig {
        deferred_crediting: true,
        agents: vec![
            AgentConfig { id: "A", opening_balance: 100000, .. },
            AgentConfig { id: "B", opening_balance: 0, .. },
        ],
        scenario_events: vec![
            CustomTransactionArrival { from: "A", to: "B", amount: 50000, tick: 0 },
        ],
        ..
    };

    let mut orch = Orchestrator::new(config)?;
    orch.tick()?;

    // Check for DeferredCreditApplied event
    let events = orch.get_tick_events(0)?;
    let deferred_events: Vec<_> = events.iter()
        .filter(|e| e.event_type == "DeferredCreditApplied")
        .collect();

    assert_eq!(deferred_events.len(), 1);
    assert_eq!(deferred_events[0].agent_id, "B");
    assert_eq!(deferred_events[0].amount, 50000);
}
```

#### Phase 4: Balance Timing Test
```rust
#[test]
fn test_balance_not_available_during_tick_in_deferred_mode() {
    // Setup: A has 100k, B has 0
    // Tick 0: A→B 50k (settles), B→C 30k (should queue because B has 0)
    let config = OrchestratorConfig {
        deferred_crediting: true,
        agents: vec![
            AgentConfig { id: "A", opening_balance: 100000, .. },
            AgentConfig { id: "B", opening_balance: 0, .. },
            AgentConfig { id: "C", opening_balance: 0, .. },
        ],
        // Inject transactions in specific order
        ..
    };

    // Verify B→C queued even though A→B settled in same tick
}
```

#### Phase 5: LSM with Deferred Credits
```rust
#[test]
fn test_lsm_bilateral_with_deferred_credits() {
    // A→B 500, B→A 300 (LSM bilateral offset)
    // Net: B receives 200
    // With deferred: B's credit deferred until tick end
}

#[test]
fn test_lsm_cycle_with_deferred_credits() {
    // A→B→C→A cycle
    // Net receivers should have deferred credits
}
```

#### Phase 6: Determinism Tests
```rust
#[test]
fn test_deferred_crediting_determinism() {
    // Run same scenario twice with same seed
    // Verify identical results
}

#[test]
fn test_deferred_credit_order_determinism() {
    // Multiple agents receive credits in same tick
    // Verify credits applied in sorted agent ID order
}
```

#### Phase 7: Integration with Cost Calculations
```rust
#[test]
fn test_cost_calculation_uses_final_balance() {
    // Verify overdraft costs calculated AFTER deferred credits applied
}
```

#### Phase 8: Replay Identity
```rust
#[test]
fn test_replay_identity_with_deferred_crediting() {
    // Run with persistence, replay
    // Verify output identical
}
```

### 3.2 Python Integration Tests

```python
def test_deferred_crediting_gridlock_via_ffi():
    """Verify gridlock scenario works through FFI."""
    config = {
        "deferred_crediting": True,
        "agents": [
            {"id": "A", "opening_balance": 0, "unsecured_cap": 0, ...},
            {"id": "B", "opening_balance": 0, "unsecured_cap": 0, ...},
        ],
        ...
    }
    orch = Orchestrator.new(config)
    orch.tick()
    assert orch.queue_size() == 2

def test_deferred_crediting_config_default_false():
    """Verify default is False (backward compatible)."""
    config = {...}  # No deferred_crediting field
    orch = Orchestrator.new(config)
    # Should behave as immediate crediting
```

---

## 4. Implementation Phases

### Phase 1: Configuration (Rust + Python)

**Rust (`simulator/src/orchestrator/engine.rs`):**
```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct OrchestratorConfig {
    // ... existing fields ...

    /// Deferred crediting mode (deferred crediting)
    /// When true, credits are batched and applied at end of tick
    #[serde(default)]
    pub deferred_crediting: bool,
}
```

**Python (`api/payment_simulator/config/schemas.py`):**
```python
class SimulationConfig(BaseModel):
    # ... existing fields ...

    deferred_crediting: bool = Field(
        False,
        description="When true, credits are batched and applied at end of tick (deferred crediting)"
    )
```

### Phase 2: DeferredCredits Accumulator

**New struct (`simulator/src/settlement/deferred.rs`):**
```rust
/// Accumulator for deferred credits during a tick
#[derive(Debug, Default)]
pub struct DeferredCredits {
    /// agent_id -> (total_credits, source_transactions)
    pending: BTreeMap<String, (i64, Vec<String>)>,
}

impl DeferredCredits {
    pub fn new() -> Self {
        Self { pending: BTreeMap::new() }
    }

    /// Accumulate credit for an agent
    pub fn accumulate(&mut self, agent_id: &str, amount: i64, tx_id: &str) {
        let entry = self.pending.entry(agent_id.to_string()).or_insert((0, Vec::new()));
        entry.0 += amount;
        entry.1.push(tx_id.to_string());
    }

    /// Apply all deferred credits to agents (sorted order for determinism)
    pub fn apply_all(&mut self, state: &mut SimulationState, tick: usize) -> Vec<Event> {
        let mut events = Vec::new();

        // Sorted iteration for determinism
        let agent_ids: Vec<_> = self.pending.keys().cloned().collect();

        for agent_id in agent_ids {
            if let Some((amount, tx_ids)) = self.pending.remove(&agent_id) {
                if let Some(agent) = state.get_agent_mut(&agent_id) {
                    agent.credit(amount);

                    events.push(Event::DeferredCreditApplied {
                        tick,
                        agent_id: agent_id.clone(),
                        amount,
                        source_transactions: tx_ids,
                    });
                }
            }
        }

        events
    }

    pub fn clear(&mut self) {
        self.pending.clear();
    }
}
```

### Phase 3: Event Definition

**Rust (`simulator/src/models/event.rs`):**
```rust
pub enum Event {
    // ... existing variants ...

    /// Deferred credits applied at end of tick (deferred crediting mode)
    DeferredCreditApplied {
        tick: usize,
        agent_id: String,
        amount: i64,
        source_transactions: Vec<String>,
    },
}
```

### Phase 4: RTGS Settlement Modification

**Modify `try_settle()` and `process_queue()` in `rtgs.rs`:**

```rust
pub fn try_settle_with_deferred(
    sender: &mut Agent,
    receiver_id: &str,  // Only need ID, not mutable ref
    transaction: &mut Transaction,
    tick: usize,
    deferred_credits: &mut Option<DeferredCredits>,
) -> Result<(), SettlementError> {
    // ... validation ...

    sender.debit(amount)?;

    // Credit handling
    match deferred_credits {
        Some(dc) => {
            // Deferred mode: accumulate credit
            dc.accumulate(receiver_id, amount, transaction.id());
        }
        None => {
            // Immediate mode: credit directly (requires receiver ref)
            // This path needs the actual receiver agent
            // Consider restructuring to always use state lookup
        }
    }

    transaction.settle(amount, tick)?;
    Ok(())
}
```

**Alternative approach (cleaner):**
Modify `process_queue()` to accept a `deferred_crediting: bool` flag and handle credits conditionally:

```rust
pub fn process_queue(
    state: &mut SimulationState,
    tick: usize,
    deferred_credits: Option<&mut DeferredCredits>,
) -> QueueProcessingResult {
    // ... existing logic ...

    for tx_id in tx_ids {
        // ... can_pay check ...

        if can_pay && bilateral_ok && multilateral_ok {
            // Debit sender
            sender.debit(amount)?;

            // Credit handling
            if let Some(dc) = deferred_credits {
                dc.accumulate(&receiver_id, amount, &tx_id);
            } else {
                receiver.credit(amount);
            }

            // ... rest of settlement ...
        }
    }
}
```

### Phase 5: LSM Settlement Modification

**Modify bilateral offset and cycle settlement in `lsm.rs`:**

```rust
fn settle_bilateral_pair_with_deferred(
    state: &mut SimulationState,
    txs_ab: &[String],
    txs_ba: &[String],
    tick: usize,
    to_remove: &mut BTreeMap<String, ()>,
    deferred_credits: Option<&mut DeferredCredits>,
) -> usize {
    // ... existing logic ...

    // For each transaction in A→B direction
    for tx_id in txs_ab {
        let sender = state.get_agent_mut(&sender_id).unwrap();
        sender.adjust_balance(-(amount as i64));  // Debit is immediate

        // Credit handling
        if let Some(dc) = deferred_credits {
            dc.accumulate(&receiver_id, amount, tx_id);
        } else {
            state.get_agent_mut(&receiver_id).unwrap().adjust_balance(amount as i64);
        }

        // ... settle transaction ...
    }
}
```

### Phase 6: Orchestrator Integration

**Modify `tick()` in `engine.rs`:**

```rust
pub fn tick(&mut self) -> Result<TickResult, SimulationError> {
    // ... existing steps 1-3 ...

    // Initialize deferred credits if enabled
    let mut deferred_credits = if self.config.deferred_crediting {
        Some(DeferredCredits::new())
    } else {
        None
    };

    // STEP 4: RTGS Queue-2 Processing
    let queue_result = rtgs::process_queue(
        &mut self.state,
        current_tick,
        deferred_credits.as_mut(),
    );

    // STEP 5: LSM
    let lsm_result = lsm::run_lsm_pass(
        &mut self.state,
        &self.lsm_config,
        current_tick,
        self.time_manager.ticks_per_day(),
        self.config.entry_disposition_offsetting,
        deferred_credits.as_mut(),
    );

    // STEP 5.9: APPLY DEFERRED CREDITS (new step!)
    if let Some(mut dc) = deferred_credits {
        let credit_events = dc.apply_all(&mut self.state, current_tick);
        for event in credit_events {
            self.log_event(event);
        }
    }

    // STEP 6: Cost accrual (now uses final balances)
    // ... existing cost calculation ...

    // ... rest of tick ...
}
```

### Phase 7: FFI Serialization

**Add event serialization in `lib.rs`:**

```rust
Event::DeferredCreditApplied { tick, agent_id, amount, source_transactions } => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "DeferredCreditApplied".into());
    dict.insert("tick".to_string(), (*tick).into());
    dict.insert("agent_id".to_string(), agent_id.clone().into());
    dict.insert("amount".to_string(), (*amount).into());
    dict.insert("source_transactions".to_string(), source_transactions.clone().into());
    dict
}
```

---

## 5. Testing Checklist

### 5.1 Unit Tests (Rust)

- [ ] `test_deferred_credits_new_empty` - DeferredCredits starts empty
- [ ] `test_deferred_credits_accumulate_single` - Single accumulation works
- [ ] `test_deferred_credits_accumulate_multiple` - Multiple accumulations sum correctly
- [ ] `test_deferred_credits_apply_all_order` - Applied in sorted agent order
- [ ] `test_deferred_credits_apply_all_clears` - Pending cleared after apply

### 5.2 RTGS Tests (Rust)

- [ ] `test_rtgs_immediate_mode_credits_immediately` - Receiver balance updates immediately
- [ ] `test_rtgs_deferred_mode_accumulates` - Credits go to accumulator
- [ ] `test_rtgs_deferred_gridlock` - Zero-balance gridlock scenario

### 5.3 LSM Tests (Rust)

- [ ] `test_lsm_bilateral_deferred_mode` - Bilateral credits deferred
- [ ] `test_lsm_cycle_deferred_mode` - Cycle credits deferred
- [ ] `test_lsm_debits_still_immediate` - Debits are not deferred

### 5.4 Orchestrator Tests (Rust)

- [ ] `test_tick_applies_deferred_credits` - Credits applied at end of tick
- [ ] `test_tick_cost_calculation_after_credits` - Costs use final balance
- [ ] `test_tick_events_include_deferred_credit` - Event logged

### 5.5 Integration Tests (Python)

- [ ] `test_deferred_crediting_config_passed_via_ffi` - Config reaches Rust
- [ ] `test_deferred_crediting_gridlock_scenario` - Full gridlock test
- [ ] `test_deferred_crediting_event_in_output` - Event returned via FFI
- [ ] `test_deferred_crediting_replay_identity` - Run == Replay

### 5.6 Edge Case Tests

- [ ] `test_deferred_with_split_payments` - Child transactions work
- [ ] `test_deferred_with_overdue` - Overdue settlements work
- [ ] `test_deferred_with_collateral` - Collateral interactions work
- [ ] `test_deferred_eod_processing` - EOD processing order correct
- [ ] `test_deferred_multi_day` - Works across multiple days

### 5.7 Determinism Tests

- [ ] `test_deferred_determinism_same_seed` - Same seed = same output
- [ ] `test_deferred_credit_order_determinism` - Credits in sorted order

---

## 6. Documentation Updates

### 6.1 Files to Update

- [ ] `CLAUDE.md` - Add deferred_crediting to config documentation
- [ ] `docs/architecture.md` - Document new settlement mode
- [ ] `docs/game-design.md` - Document behavioral difference
- [ ] `docs/reference/patterns-and-conventions.md` - Add to config patterns
- [ ] Document deferred crediting mode in relevant locations

### 6.2 Example Configuration

```yaml
simulation:
  ticks_per_day: 100
  num_days: 1
  rng_seed: 12345

# Enable deferred crediting settlement mode
deferred_crediting: true

agents:
  - id: BANK_A
    opening_balance: 0
    unsecured_cap: 0
    policy:
      type: Fifo
  - id: BANK_B
    opening_balance: 0
    unsecured_cap: 0
    policy:
      type: Fifo

scenario_events:
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 100000
    schedule:
      type: OneTime
      tick: 0
  - type: CustomTransactionArrival
    from_agent: BANK_B
    to_agent: BANK_A
    amount: 100000
    schedule:
      type: OneTime
      tick: 0

# Expected: Both transactions queue (gridlock)
# With deferred_crediting: false, one would enable the other
```

---

## 7. Risk Assessment

### 7.1 Backward Compatibility

- **Risk**: Existing simulations change behavior
- **Mitigation**: Default is `false` (immediate crediting)

### 7.2 Performance Impact

- **Risk**: Additional data structure overhead
- **Mitigation**: DeferredCredits uses BTreeMap, O(log n) operations
- **Mitigation**: Only created when `deferred_crediting: true`

### 7.3 Determinism

- **Risk**: Non-deterministic credit order
- **Mitigation**: BTreeMap provides sorted iteration; explicit sort before apply

### 7.4 Replay Identity

- **Risk**: Events differ between run and replay
- **Mitigation**: DeferredCreditApplied event contains all needed fields

---

## 8. Success Criteria

1. **Gridlock Test Passes**: Zero-balance agents with mutual payments gridlock
2. **Immediate Mode Unchanged**: Default behavior identical to current
3. **Event Emitted**: DeferredCreditApplied events visible in output
4. **Determinism Maintained**: Same seed = same output
5. **Replay Identity**: Run == Replay for verbose output
6. **All Tests Pass**: Both Rust and Python test suites green
7. **Documentation Complete**: Config option documented with examples
