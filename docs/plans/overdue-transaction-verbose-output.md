# Implementation Plan: Comprehensive Overdue Transaction Verbose Output

## Overview
Enhance verbose output to provide complete visibility into transactions approaching and exceeding their deadlines, including cost breakdowns and timing information.

## Requirements

1. **Near-Deadline Warnings**: Show transactions that will go overdue within 2 ticks
2. **Overdue Events**: Log when transactions become overdue with penalty cost
3. **Overdue Status Display**: Each tick, show all overdue transactions with duration and accumulated costs
4. **Settlement Logging**: When overdue transactions settle, log with full cost breakdown

## Current State Analysis

### What Exists ✅
- `TransactionStatus::Overdue { missed_deadline_tick }` tracks overdue state
- Two-tier cost structure:
  - One-time `deadline_penalty` (default $500)
  - Ongoing delay cost with 5x multiplier
- FFI exposes: `status`, `overdue_since_tick`, `deadline_tick`
- Events: `CostAccrual` (includes penalties), `TransactionReprioritized`

### What's Missing ❌
- No dedicated "TransactionWentOverdue" event
- No "OverdueTransactionSettled" event with cost summary
- No StateProvider methods for near-deadline/overdue queries
- Verbose output doesn't highlight overdue status

## Implementation Plan (TDD Approach)

### Phase 1: Add New Event Types (Rust)

#### Step 1.1: Define Events in `backend/src/models/event.rs`

Add two new event variants:

```rust
pub enum Event {
    // ... existing variants ...

    /// Emitted when a transaction crosses its deadline
    TransactionWentOverdue {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,                    // Total transaction amount
        remaining_amount: i64,          // Unsettled amount
        deadline_tick: usize,           // Original deadline
        ticks_overdue: usize,           // How many ticks late
        deadline_penalty_cost: i64,     // One-time penalty charged
    },

    /// Emitted when an overdue transaction is finally settled
    OverdueTransactionSettled {
        tick: usize,
        tx_id: String,
        sender_id: String,
        receiver_id: String,
        amount: i64,                    // Total transaction amount
        settled_amount: i64,            // Amount settled this tick
        deadline_tick: usize,           // Original deadline
        overdue_since_tick: usize,      // When it became overdue
        total_ticks_overdue: usize,     // Duration overdue
        deadline_penalty_cost: i64,     // One-time penalty (already paid)
        estimated_delay_cost: i64,      // Accumulated delay costs while overdue
    },
}
```

**Test 1.1**: Write Rust unit test that creates these events and verifies all fields.

---

#### Step 1.2: Emit `TransactionWentOverdue` Event

**Location**: `backend/src/orchestrator/engine.rs` in `accrue_costs()` method (around line 2585)

**Current code** (simplified):
```rust
// Mark transactions as overdue
for tx_id in &newly_overdue_txs {
    if let Some(tx_mut) = self.state.get_transaction_mut(tx_id) {
        tx_mut.mark_overdue(tick).ok();
    }
}

// Calculate penalty
let penalty_cost = (newly_overdue_txs.len() as i64) * self.cost_rates.deadline_penalty;
```

**New code**:
```rust
// Mark transactions as overdue and emit events
for tx_id in &newly_overdue_txs {
    if let Some(tx_mut) = self.state.get_transaction_mut(tx_id) {
        let amount = tx_mut.amount();
        let remaining = tx_mut.remaining_amount();
        let sender = tx_mut.sender_id().to_string();
        let receiver = tx_mut.receiver_id().to_string();
        let deadline = tx_mut.deadline_tick();

        tx_mut.mark_overdue(tick).ok();

        // Emit event
        self.events.push(Event::TransactionWentOverdue {
            tick,
            tx_id: tx_id.clone(),
            sender_id: sender,
            receiver_id: receiver,
            amount,
            remaining_amount: remaining,
            deadline_tick: deadline,
            ticks_overdue: tick - deadline,
            deadline_penalty_cost: self.cost_rates.deadline_penalty,
        });
    }
}

let penalty_cost = (newly_overdue_txs.len() as i64) * self.cost_rates.deadline_penalty;
```

**Test 1.2**: Integration test that:
- Creates transaction with deadline at tick 10
- Advances to tick 11
- Verifies `TransactionWentOverdue` event emitted with correct costs

---

#### Step 1.3: Emit `OverdueTransactionSettled` Event

**Locations**: Multiple settlement points need modification

##### A. RTGS Immediate Settlement
**File**: `backend/src/settlement/rtgs.rs` in `attempt_immediate_settlement()`

After successful settlement (around line 111), check if was overdue:

```rust
if result.amount_settled > 0 {
    // ... existing balance updates ...

    // Check if this was an overdue transaction being settled
    if let TransactionStatus::Overdue { missed_deadline_tick } = tx.status() {
        let total_ticks_overdue = tick - missed_deadline_tick;

        // Estimate accumulated delay cost (simplified)
        let estimated_delay_cost = (tx.amount() as f64
            * cost_rates.delay_cost_per_tick_per_cent
            * cost_rates.overdue_delay_multiplier
            * total_ticks_overdue as f64).round() as i64;

        events.push(Event::OverdueTransactionSettled {
            tick,
            tx_id: tx_id.clone(),
            sender_id: tx.sender_id().to_string(),
            receiver_id: tx.receiver_id().to_string(),
            amount: tx.amount(),
            settled_amount: result.amount_settled,
            deadline_tick: tx.deadline_tick(),
            overdue_since_tick: missed_deadline_tick,
            total_ticks_overdue,
            deadline_penalty_cost: cost_rates.deadline_penalty,
            estimated_delay_cost,
        });
    }
}
```

**Challenge**: Cost rates not currently passed to RTGS. Need to add to function signatures.

##### B. LSM Settlement
**File**: `backend/src/settlement/lsm.rs`

Similar logic in `settle_cycle()` after applying settlements.

**Test 1.3**: Integration test that:
- Creates overdue transaction
- Settles it
- Verifies `OverdueTransactionSettled` event with cost breakdown

---

### Phase 2: FFI Serialization

#### Step 2.1: Serialize New Events

**File**: `backend/src/ffi/orchestrator.rs` in `serialize_event()`

```rust
Event::TransactionWentOverdue {
    tick, tx_id, sender_id, receiver_id, amount, remaining_amount,
    deadline_tick, ticks_overdue, deadline_penalty_cost
} => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "transaction_went_overdue".into());
    dict.insert("tick".to_string(), (*tick as i64).into());
    dict.insert("tx_id".to_string(), tx_id.into());
    dict.insert("sender_id".to_string(), sender_id.into());
    dict.insert("receiver_id".to_string(), receiver_id.into());
    dict.insert("amount".to_string(), amount.into());
    dict.insert("remaining_amount".to_string(), remaining_amount.into());
    dict.insert("deadline_tick".to_string(), (*deadline_tick as i64).into());
    dict.insert("ticks_overdue".to_string(), (*ticks_overdue as i64).into());
    dict.insert("deadline_penalty_cost".to_string(), deadline_penalty_cost.into());
    dict
}

Event::OverdueTransactionSettled {
    tick, tx_id, sender_id, receiver_id, amount, settled_amount,
    deadline_tick, overdue_since_tick, total_ticks_overdue,
    deadline_penalty_cost, estimated_delay_cost
} => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "overdue_transaction_settled".into());
    dict.insert("tick".to_string(), (*tick as i64).into());
    dict.insert("tx_id".to_string(), tx_id.into());
    dict.insert("sender_id".to_string(), sender_id.into());
    dict.insert("receiver_id".to_string(), receiver_id.into());
    dict.insert("amount".to_string(), amount.into());
    dict.insert("settled_amount".to_string(), settled_amount.into());
    dict.insert("deadline_tick".to_string(), (*deadline_tick as i64).into());
    dict.insert("overdue_since_tick".to_string(), (*overdue_since_tick as i64).into());
    dict.insert("total_ticks_overdue".to_string(), (*total_ticks_overdue as i64).into());
    dict.insert("deadline_penalty_cost".to_string(), deadline_penalty_cost.into());
    dict.insert("estimated_delay_cost".to_string(), estimated_delay_cost.into());
    dict
}
```

**Test 2.1**: Python integration test verifying event dicts have all fields.

---

### Phase 3: StateProvider Methods

#### Step 3.1: Add Query Methods to Orchestrator

**File**: `backend/src/ffi/orchestrator.rs`

```rust
#[pymethods]
impl Orchestrator {
    /// Get transactions approaching their deadline
    pub fn get_transactions_near_deadline(&self, within_ticks: usize) -> Vec<HashMap<String, PyObject>> {
        Python::with_gil(|py| {
            let current_tick = self.engine.current_tick();
            let threshold = current_tick + within_ticks;

            let mut near_deadline = Vec::new();

            // Check all pending transactions
            for tx in self.engine.state().all_transactions() {
                if !tx.is_settled() && !tx.is_overdue() {
                    if tx.deadline_tick() <= threshold {
                        near_deadline.push(serialize_transaction(py, tx));
                    }
                }
            }

            near_deadline
        })
    }

    /// Get all currently overdue transactions with cost data
    pub fn get_overdue_transactions(&self) -> Vec<HashMap<String, PyObject>> {
        Python::with_gil(|py| {
            let current_tick = self.engine.current_tick();
            let cost_rates = self.engine.cost_rates();

            let mut overdue = Vec::new();

            for tx in self.engine.state().all_transactions() {
                if tx.is_overdue() && !tx.is_settled() {
                    let mut dict = serialize_transaction(py, tx);

                    // Add cost calculations
                    if let Some(overdue_since) = tx.overdue_since_tick() {
                        let ticks_overdue = current_tick - overdue_since;
                        dict.insert("ticks_overdue".to_string(), (ticks_overdue as i64).into());

                        // Estimate accumulated delay cost
                        let delay_cost = (tx.remaining_amount() as f64
                            * cost_rates.delay_cost_per_tick_per_cent
                            * cost_rates.overdue_delay_multiplier
                            * ticks_overdue as f64).round() as i64;

                        dict.insert("estimated_delay_cost".to_string(), delay_cost.into());
                        dict.insert("deadline_penalty_cost".to_string(), cost_rates.deadline_penalty.into());

                        let total_cost = cost_rates.deadline_penalty + delay_cost;
                        dict.insert("total_overdue_cost".to_string(), total_cost.into());
                    }

                    overdue.push(dict);
                }
            }

            overdue
        })
    }
}
```

**Test 3.1**: Python test verifying these methods return correct data.

---

#### Step 3.2: Add to StateProvider Protocol

**File**: `api/payment_simulator/cli/execution/state_provider.py`

```python
class StateProvider(Protocol):
    """Protocol for accessing simulation state (live or replayed)."""

    # ... existing methods ...

    def get_transactions_near_deadline(self, within_ticks: int) -> List[Dict[str, Any]]:
        """Get transactions that will go overdue within N ticks."""
        ...

    def get_overdue_transactions(self) -> List[Dict[str, Any]]:
        """Get all currently overdue transactions with cost data."""
        ...
```

**Implementations**:

```python
class OrchestratorStateProvider(StateProvider):
    """Live state from Rust FFI."""

    def get_transactions_near_deadline(self, within_ticks: int) -> List[Dict[str, Any]]:
        return self.orchestrator.get_transactions_near_deadline(within_ticks)

    def get_overdue_transactions(self) -> List[Dict[str, Any]]:
        return self.orchestrator.get_overdue_transactions()


class DatabaseStateProvider(StateProvider):
    """Replayed state from database."""

    def get_transactions_near_deadline(self, within_ticks: int) -> List[Dict[str, Any]]:
        """Query transactions table for near-deadline txs."""
        current_tick = self.current_tick
        threshold = current_tick + within_ticks

        query = """
            SELECT
                t.tx_id,
                t.sender_id,
                t.receiver_id,
                t.amount,
                t.deadline_tick,
                t.status,
                COALESCE(SUM(s.amount_settled), 0) as total_settled
            FROM transactions t
            LEFT JOIN settlements s ON t.tx_id = s.tx_id AND s.tick <= ?
            WHERE t.simulation_id = ?
                AND t.deadline_tick <= ?
                AND t.deadline_tick >= ?
                AND t.status != 'settled'
            GROUP BY t.tx_id
        """

        rows = self.conn.execute(query, [
            current_tick, self.simulation_id, threshold, current_tick
        ]).fetchall()

        # Convert to dict format matching FFI
        return [self._row_to_transaction_dict(row) for row in rows]

    def get_overdue_transactions(self) -> List[Dict[str, Any]]:
        """Query for overdue transactions with cost calculations."""
        # Implementation using simulation_events and transactions tables
        # Calculate costs based on overdue_since_tick
        ...
```

**Test 3.2**: Test both implementations return same data for same state.

---

### Phase 4: Display Logic

#### Step 4.1: Add Display Functions

**File**: `api/payment_simulator/cli/display/verbose_output.py`

```python
def log_transactions_near_deadline(
    transactions: List[Dict[str, Any]],
    current_tick: int,
    console: Console
) -> None:
    """Display transactions approaching deadline."""
    if not transactions:
        return

    console.print("\n[yellow]⚠️  Transactions Near Deadline (within 2 ticks):[/yellow]")

    for tx in sorted(transactions, key=lambda t: t['deadline_tick']):
        ticks_until = tx['deadline_tick'] - current_tick
        remaining = tx.get('remaining_amount', tx['amount'])

        warning = "🔴 NEXT TICK!" if ticks_until <= 1 else "⚠️"

        console.print(
            f"  {warning} TX {tx['tx_id'][:8]} | "
            f"{tx['sender_id']} → {tx['receiver_id']} | "
            f"${remaining / 100:,.2f} | "
            f"Deadline: Tick {tx['deadline_tick']} ({ticks_until} tick{'s' if ticks_until != 1 else ''} away)"
        )


def log_overdue_transactions_summary(
    overdue_txs: List[Dict[str, Any]],
    console: Console
) -> None:
    """Display summary of all overdue transactions."""
    if not overdue_txs:
        return

    console.print("\n[red]🔥 Overdue Transactions:[/red]")

    total_overdue_cost = 0

    for tx in sorted(overdue_txs, key=lambda t: t.get('ticks_overdue', 0), reverse=True):
        ticks_overdue = tx.get('ticks_overdue', 0)
        total_cost = tx.get('total_overdue_cost', 0)
        deadline_penalty = tx.get('deadline_penalty_cost', 0)
        delay_cost = tx.get('estimated_delay_cost', 0)
        remaining = tx.get('remaining_amount', tx['amount'])

        total_overdue_cost += total_cost

        console.print(
            f"  🔥 TX {tx['tx_id'][:8]} | "
            f"{tx['sender_id']} → {tx['receiver_id']} | "
            f"${remaining / 100:,.2f} | "
            f"Overdue: {ticks_overdue} tick{'s' if ticks_overdue != 1 else ''}"
        )
        console.print(
            f"     💸 Costs: Penalty ${deadline_penalty / 100:,.2f} + "
            f"Delay ${delay_cost / 100:,.2f} = "
            f"[bold red]${total_cost / 100:,.2f}[/bold red]"
        )

    console.print(f"\n  [bold red]Total Overdue Cost: ${total_overdue_cost / 100:,.2f}[/bold red]")


def log_transaction_went_overdue_event(event: Dict[str, Any], console: Console) -> None:
    """Log when a transaction becomes overdue."""
    console.print(
        f"\n[red]❌ Transaction Went Overdue:[/red] TX {event['tx_id'][:8]}"
    )
    console.print(
        f"   {event['sender_id']} → {event['receiver_id']} | "
        f"${event['remaining_amount'] / 100:,.2f}"
    )
    console.print(
        f"   Deadline: Tick {event['deadline_tick']} | "
        f"Current: Tick {event['tick']} | "
        f"[red]{event['ticks_overdue']} tick{'s' if event['ticks_overdue'] != 1 else ''} late[/red]"
    )
    console.print(
        f"   💸 Deadline Penalty Charged: [bold red]${event['deadline_penalty_cost'] / 100:,.2f}[/bold red]"
    )


def log_overdue_transaction_settled_event(event: Dict[str, Any], console: Console) -> None:
    """Log when an overdue transaction is finally settled."""
    console.print(
        f"\n[green]✅ Overdue Transaction Settled:[/green] TX {event['tx_id'][:8]}"
    )
    console.print(
        f"   {event['sender_id']} → {event['receiver_id']} | "
        f"${event['settled_amount'] / 100:,.2f}"
    )
    console.print(
        f"   Was overdue for: [red]{event['total_ticks_overdue']} tick{'s' if event['total_ticks_overdue'] != 1 else ''}[/red] "
        f"(Deadline: {event['deadline_tick']}, Overdue since: {event['overdue_since_tick']})"
    )

    total_cost = event['deadline_penalty_cost'] + event['estimated_delay_cost']
    console.print(
        f"   💸 Total Cost: Penalty ${event['deadline_penalty_cost'] / 100:,.2f} + "
        f"Delay ${event['estimated_delay_cost'] / 100:,.2f} = "
        f"[bold red]${total_cost / 100:,.2f}[/bold red]"
    )
```

**Test 4.1**: Verify display functions render correctly with mock data.

---

#### Step 4.2: Integrate into Main Display Function

**File**: `api/payment_simulator/cli/display/verbose_output.py`

Modify `display_tick_verbose_output()`:

```python
def display_tick_verbose_output(
    provider: StateProvider,
    tick: int,
    events: List[Dict[str, Any]],
    console: Console
) -> None:
    """Display comprehensive tick output."""

    # ... existing header ...

    # NEW: Near-deadline warnings (before events)
    near_deadline = provider.get_transactions_near_deadline(within_ticks=2)
    log_transactions_near_deadline(near_deadline, tick, console)

    # Process events
    for event in events:
        event_type = event.get('event_type')

        # NEW: Handle overdue events
        if event_type == 'transaction_went_overdue':
            log_transaction_went_overdue_event(event, console)
        elif event_type == 'overdue_transaction_settled':
            log_overdue_transaction_settled_event(event, console)
        # ... existing event handlers ...

    # NEW: Overdue summary (after events, before queues)
    overdue_txs = provider.get_overdue_transactions()
    log_overdue_transactions_summary(overdue_txs, console)

    # ... existing queue displays ...
```

**Test 4.2**: End-to-end test with full scenario.

---

### Phase 5: Testing Strategy

#### Test 5.1: Rust Unit Tests

**File**: `backend/tests/test_overdue_events.rs`

```rust
#[test]
fn test_transaction_went_overdue_event_emitted() {
    let mut orch = create_test_orchestrator();

    // Create transaction with deadline at tick 5
    let tx_id = create_transaction_with_deadline(&mut orch, 5);

    // Advance to tick 6 (past deadline)
    orch.tick();  // tick 6

    // Verify event emitted
    let events = orch.get_tick_events(6);
    let overdue_events: Vec<_> = events.iter()
        .filter(|e| e.event_type == "transaction_went_overdue")
        .collect();

    assert_eq!(overdue_events.len(), 1);
    assert_eq!(overdue_events[0].tx_id, tx_id);
    assert_eq!(overdue_events[0].ticks_overdue, 1);
    assert_eq!(overdue_events[0].deadline_penalty_cost, 50_000); // $500
}

#[test]
fn test_overdue_transaction_settled_event_emitted() {
    // Similar test for settlement event
}
```

---

#### Test 5.2: Python Integration Tests

**File**: `api/tests/integration/test_overdue_verbose_output.py`

```python
def test_near_deadline_transactions_displayed():
    """Test that transactions near deadline are shown."""
    config = {
        "ticks_per_day": 100,
        "seed": 12345,
        "agent_configs": [
            {"id": "A", "opening_balance": 100_000},
            {"id": "B", "opening_balance": 100_000},
        ],
        "cost_config": {
            "deadline_penalty": 50_000,
        }
    }

    orch = Orchestrator.new(config)

    # Create transaction with deadline at tick 5
    orch.submit_transaction({
        "tx_id": "tx1",
        "sender_id": "A",
        "receiver_id": "B",
        "amount": 10_000,
        "deadline_tick": 5,
    })

    # Advance to tick 3
    orch.tick()
    orch.tick()
    orch.tick()

    # Check near-deadline query
    near_deadline = orch.get_transactions_near_deadline(within_ticks=2)
    assert len(near_deadline) == 1
    assert near_deadline[0]['tx_id'] == "tx1"


def test_overdue_cost_calculation():
    """Test that overdue costs are calculated correctly."""
    # Create overdue transaction
    # Verify cost breakdown matches formula
    pass


def test_overdue_events_in_replay():
    """Test that overdue events persist and replay correctly."""
    # Run simulation with overdue transactions
    # Persist to database
    # Replay and verify events match
    pass
```

---

#### Test 5.3: Replay Identity Test

**File**: `api/tests/integration/test_replay_identity_gold_standard.py`

Add new test:

```python
def test_overdue_events_replay_identity():
    """Verify overdue events have replay identity."""

    # Create scenario with overdue transactions
    config = create_overdue_scenario_config()

    # Run and persist
    run_output = run_simulation_with_persistence(config, "test_overdue.db")

    # Replay
    replay_output = replay_simulation("test_overdue.db")

    # Compare outputs (strip timing info)
    assert normalize_output(run_output) == normalize_output(replay_output)

    # Verify events persisted
    events = get_simulation_events("test_overdue.db")
    overdue_events = [e for e in events if e['event_type'] in [
        'transaction_went_overdue',
        'overdue_transaction_settled'
    ]]

    assert len(overdue_events) > 0, "Overdue events should be persisted"

    # Verify all fields present
    for event in overdue_events:
        if event['event_type'] == 'transaction_went_overdue':
            assert 'deadline_penalty_cost' in event
            assert 'ticks_overdue' in event
        elif event['event_type'] == 'overdue_transaction_settled':
            assert 'total_ticks_overdue' in event
            assert 'estimated_delay_cost' in event
```

---

## Implementation Checklist

### Rust Backend
- [ ] Add `TransactionWentOverdue` event variant
- [ ] Add `OverdueTransactionSettled` event variant
- [ ] Emit `TransactionWentOverdue` in `accrue_costs()`
- [ ] Emit `OverdueTransactionSettled` in RTGS settlement
- [ ] Emit `OverdueTransactionSettled` in LSM settlement
- [ ] Add `get_transactions_near_deadline()` FFI method
- [ ] Add `get_overdue_transactions()` FFI method
- [ ] Add cost rates parameter to settlement functions
- [ ] Write Rust unit tests

### FFI Layer
- [ ] Serialize `TransactionWentOverdue` event
- [ ] Serialize `OverdueTransactionSettled` event
- [ ] Test event serialization

### Python StateProvider
- [ ] Add protocol methods to `StateProvider`
- [ ] Implement in `OrchestratorStateProvider`
- [ ] Implement in `DatabaseStateProvider` (for replay)
- [ ] Test both implementations

### Display Layer
- [ ] Add `log_transactions_near_deadline()`
- [ ] Add `log_overdue_transactions_summary()`
- [ ] Add `log_transaction_went_overdue_event()`
- [ ] Add `log_overdue_transaction_settled_event()`
- [ ] Integrate into `display_tick_verbose_output()`
- [ ] Test display functions

### Testing
- [ ] Rust unit tests for events
- [ ] Python integration tests for queries
- [ ] Python integration tests for display
- [ ] Replay identity test
- [ ] End-to-end scenario test

---

## Success Criteria

1. ✅ Transactions within 2 ticks of deadline shown with warning
2. ✅ Event logged when transaction becomes overdue with penalty cost
3. ✅ Each tick shows all overdue transactions with duration and costs
4. ✅ Overdue settlements logged separately with full breakdown
5. ✅ All events persist correctly for replay
6. ✅ Replay produces identical output to run
7. ✅ All costs calculated correctly (penalty + delay)
8. ✅ Display is clear, informative, and well-formatted

---

## Estimated Effort

- Rust implementation: ~2-3 hours
- FFI serialization: ~30 minutes
- StateProvider methods: ~1 hour
- Display logic: ~1 hour
- Testing: ~2 hours
- **Total: ~6-7 hours**

---

## Risk Assessment

### Low Risk ✅
- Event addition (follows established pattern)
- FFI serialization (straightforward)
- Display logic (isolated)

### Medium Risk ⚠️
- Cost calculation accuracy (need to match existing formula)
- DatabaseStateProvider replay queries (complex SQL)
- Passing cost rates to settlement functions (signature changes)

### Mitigation
- Write tests first (TDD)
- Reference existing cost calculation code
- Test replay identity thoroughly
- Start with simple cases, add complexity incrementally

---

*Plan created: 2025-11-09*
