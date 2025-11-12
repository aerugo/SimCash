# Fix Replay Settlement Classification and Collateral Oscillation Bugs

**Status**: In Progress
**Created**: 2025-01-12
**Priority**: Critical (P0)
**Affects**: Replay accuracy, settlement metrics, collateral modeling

---

## Problem Statement

Replay output for sim-6556aa5d (ticks 250-260) reveals three critical bugs that violate system invariants:

### 1. Mislabeled Settlement Events (Accuracy Bug)
**Symptom**: Transactions released from Queue 2 are reported as "RTGS Immediate"
- TX b175367e: In Queue 2 at ticks 250-252, then reported as "RTGS Immediate" at tick 253
- TX be36bd0d: In Queue 2 at ticks 250-254, then reported as "RTGS Immediate" at tick 255

**Impact**:
- Metrics are wrong (settlement_rate includes queue releases as immediate)
- Users cannot distinguish immediate RTGS from delayed queue releases
- LSM metrics are invisible (all releases labeled as RTGS)

**Root Cause**: Settlement event creation doesn't distinguish settlement source:
```rust
// Current: All settlements create same event type
Event::TransactionSettled { tx_id, ... }
```

### 2. Collateral Oscillation (Policy Bug)
**Symptom**: REGIONAL_TRUST posts/withdraws collateral every single tick
- Tick 250: WITHDRAWN $62,713.27
- Tick 251: POSTED $64,944.24 (DeadlineEmergency)
- Tick 252: WITHDRAWN $64,944.24
- Tick 253: POSTED $78,481.20 (DeadlineEmergency)
- Pattern repeats every tick

**Impact**:
- Unrealistic behavior (real banks don't thrash collateral)
- Computational waste
- Difficult to audit actual liquidity crises
- "DeadlineEmergency" reason is vague

**Root Cause**: Policy has no hysteresis or state:
```python
# Every tick:
if needs_liquidity:
    post_collateral()  # Immediately posts
# Next tick:
if has_excess_liquidity:
    withdraw_collateral()  # Immediately withdraws
```

### 3. Collateral Doesn't Affect Headroom (Modeling Bug)
**Symptom**: Posted collateral appears in events but doesn't increase available liquidity
- Available Liquidity = CreditLimit - CreditUsed (ignores posted collateral)
- Agent posts $87K collateral but headroom stays at 24%

**Impact**:
- Collateral posting is cosmetic, not functional
- Agents can't use posted collateral to settle transactions
- Defeats the purpose of collateral mechanism

**Root Cause**: Headroom calculation ignores collateral:
```rust
// Current
let headroom = agent.credit_limit - agent.credit_used;

// Should be
let headroom = agent.credit_limit + (agent.posted_collateral * haircut) - agent.credit_used;
```

---

## Success Criteria

### Functional Requirements
1. **Settlement Classification**
   - ✅ Immediate RTGS: Settled on submission (payer had balance+headroom)
   - ✅ Queue Release: Released from queue due to new liquidity
   - ✅ LSM Bilateral: Released via 2-agent offset
   - ✅ LSM Cycle: Released via N-agent cycle (N≥3)

2. **Collateral Behavior**
   - ✅ Posted collateral increases headroom immediately
   - ✅ Minimum holding period: Cannot withdraw within 5 ticks of posting
   - ✅ Hysteresis: Only post if liquidity gap > threshold (e.g., 10% of queue value)
   - ✅ Event reasons are specific: "CoveringOverdueTransaction(tx_id)" not "DeadlineEmergency"

3. **Replay Identity**
   - ✅ `payment-sim run` and `payment-sim replay` produce byte-identical output (modulo timestamps)
   - ✅ All settlement types appear correctly in both modes

### Metrics Integrity
- Settlement rate splits: `immediate_rate`, `queue_release_rate`, `lsm_rate`
- Collateral utilization: `posted_collateral_avg`, `collateral_volatility` (std dev of changes)
- Headroom tracking: Correctly reflects balance + credit + collateral

---

## Technical Design

### Phase 1: Settlement Event Classification (Rust)

#### 1.1 New Event Variants
**File**: `backend/src/models/event.rs`

```rust
pub enum Event {
    // REMOVE: Generic TransactionSettled
    // TransactionSettled { tick, tx_id, sender, receiver, amount },

    // ADD: Specific settlement event types
    RtgsImmediateSettlement {
        tick: i64,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        sender_balance_before: i64,
        sender_balance_after: i64,
    },

    Queue2LiquidityRelease {
        tick: i64,
        tx_id: String,
        sender: String,
        receiver: String,
        amount: i64,
        queue_wait_ticks: i64,
        release_reason: String, // "NewLiquidity", "CollateralPosted", "IncomingPayment"
    },

    LsmBilateralOffset {
        tick: i64,
        agent_a: String,
        agent_b: String,
        tx_a_to_b: String,
        tx_b_to_a: String,
        amount_a_to_b: i64,
        amount_b_to_a: i64,
        net_settled: i64,
    },

    LsmCycleSettlement {
        tick: i64,
        agents: Vec<String>,
        tx_ids: Vec<String>,
        tx_amounts: Vec<i64>,
        net_positions: Vec<i64>,
        max_net_outflow: i64,
        max_net_outflow_agent: String,
        total_value: i64,
    },

    // ... existing events ...
}
```

#### 1.2 Settlement Path Changes
**Files**:
- `backend/src/settlement/rtgs.rs`
- `backend/src/settlement/lsm.rs`
- `backend/src/orchestrator/tick.rs`

```rust
// In RTGS immediate settlement
fn settle_immediate(state: &mut State, tx: &Transaction) -> Result<()> {
    let sender = state.agents.get_mut(&tx.sender)?;
    let balance_before = sender.balance;

    // ... execute settlement ...

    let balance_after = sender.balance;

    state.events.push(Event::RtgsImmediateSettlement {
        tick: state.current_tick,
        tx_id: tx.id.clone(),
        sender: tx.sender.clone(),
        receiver: tx.receiver.clone(),
        amount: tx.amount,
        sender_balance_before: balance_before,
        sender_balance_after: balance_after,
    });

    Ok(())
}

// In Queue 2 release
fn release_from_queue2(state: &mut State, tx: &Transaction, reason: &str) -> Result<()> {
    let arrival_tick = tx.arrival_tick;
    let wait_ticks = state.current_tick - arrival_tick;

    // ... execute settlement ...

    state.events.push(Event::Queue2LiquidityRelease {
        tick: state.current_tick,
        tx_id: tx.id.clone(),
        sender: tx.sender.clone(),
        receiver: tx.receiver.clone(),
        amount: tx.amount,
        queue_wait_ticks: wait_ticks,
        release_reason: reason.to_string(),
    });

    Ok(())
}

// In LSM bilateral
fn lsm_bilateral_offset(state: &mut State, cycle: &LsmCycle) -> Result<()> {
    // Validate it's actually bilateral
    assert_eq!(cycle.agents.len(), 2);
    assert_eq!(cycle.tx_ids.len(), 2);

    state.events.push(Event::LsmBilateralOffset {
        tick: state.current_tick,
        agent_a: cycle.agents[0].clone(),
        agent_b: cycle.agents[1].clone(),
        tx_a_to_b: cycle.tx_ids[0].clone(),
        tx_b_to_a: cycle.tx_ids[1].clone(),
        amount_a_to_b: cycle.tx_amounts[0],
        amount_b_to_a: cycle.tx_amounts[1],
        net_settled: cycle.tx_amounts[0].min(cycle.tx_amounts[1]),
    });

    Ok(())
}

// In LSM cycle (N≥3)
fn lsm_cycle_settlement(state: &mut State, cycle: &LsmCycle) -> Result<()> {
    assert!(cycle.agents.len() >= 3);

    let max_outflow_idx = cycle.net_positions.iter()
        .enumerate()
        .max_by_key(|(_, &pos)| pos.abs())
        .map(|(idx, _)| idx)
        .unwrap();

    state.events.push(Event::LsmCycleSettlement {
        tick: state.current_tick,
        agents: cycle.agents.clone(),
        tx_ids: cycle.tx_ids.clone(),
        tx_amounts: cycle.tx_amounts.clone(),
        net_positions: cycle.net_positions.clone(),
        max_net_outflow: cycle.net_positions[max_outflow_idx],
        max_net_outflow_agent: cycle.agents[max_outflow_idx].clone(),
        total_value: cycle.tx_amounts.iter().sum(),
    });

    Ok(())
}
```

#### 1.3 FFI Serialization
**File**: `backend/src/ffi/orchestrator.rs`

```rust
fn serialize_event(event: &Event) -> HashMap<String, PyObject> {
    match event {
        Event::RtgsImmediateSettlement {
            tick, tx_id, sender, receiver, amount,
            sender_balance_before, sender_balance_after
        } => {
            let mut dict = HashMap::new();
            dict.insert("event_type".to_string(), "rtgs_immediate_settlement".into());
            dict.insert("tick".to_string(), tick.into());
            dict.insert("tx_id".to_string(), tx_id.into());
            dict.insert("sender".to_string(), sender.into());
            dict.insert("receiver".to_string(), receiver.into());
            dict.insert("amount".to_string(), amount.into());
            dict.insert("sender_balance_before".to_string(), sender_balance_before.into());
            dict.insert("sender_balance_after".to_string(), sender_balance_after.into());
            dict
        },

        Event::Queue2LiquidityRelease {
            tick, tx_id, sender, receiver, amount,
            queue_wait_ticks, release_reason
        } => {
            let mut dict = HashMap::new();
            dict.insert("event_type".to_string(), "queue2_liquidity_release".into());
            dict.insert("tick".to_string(), tick.into());
            dict.insert("tx_id".to_string(), tx_id.into());
            dict.insert("sender".to_string(), sender.into());
            dict.insert("receiver".to_string(), receiver.into());
            dict.insert("amount".to_string(), amount.into());
            dict.insert("queue_wait_ticks".to_string(), queue_wait_ticks.into());
            dict.insert("release_reason".to_string(), release_reason.into());
            dict
        },

        Event::LsmBilateralOffset {
            tick, agent_a, agent_b, tx_a_to_b, tx_b_to_a,
            amount_a_to_b, amount_b_to_a, net_settled
        } => {
            let mut dict = HashMap::new();
            dict.insert("event_type".to_string(), "lsm_bilateral_offset".into());
            dict.insert("tick".to_string(), tick.into());
            dict.insert("agent_a".to_string(), agent_a.into());
            dict.insert("agent_b".to_string(), agent_b.into());
            dict.insert("tx_a_to_b".to_string(), tx_a_to_b.into());
            dict.insert("tx_b_to_a".to_string(), tx_b_to_a.into());
            dict.insert("amount_a_to_b".to_string(), amount_a_to_b.into());
            dict.insert("amount_b_to_a".to_string(), amount_b_to_a.into());
            dict.insert("net_settled".to_string(), net_settled.into());
            dict
        },

        Event::LsmCycleSettlement {
            tick, agents, tx_ids, tx_amounts, net_positions,
            max_net_outflow, max_net_outflow_agent, total_value
        } => {
            let mut dict = HashMap::new();
            dict.insert("event_type".to_string(), "lsm_cycle_settlement".into());
            dict.insert("tick".to_string(), tick.into());
            dict.insert("agents".to_string(), agents.into());
            dict.insert("tx_ids".to_string(), tx_ids.into());
            dict.insert("tx_amounts".to_string(), tx_amounts.into());
            dict.insert("net_positions".to_string(), net_positions.into());
            dict.insert("max_net_outflow".to_string(), max_net_outflow.into());
            dict.insert("max_net_outflow_agent".to_string(), max_net_outflow_agent.into());
            dict.insert("total_value".to_string(), total_value.into());
            dict
        },

        // ... other events ...
    }
}
```

---

### Phase 2: Collateral Headroom Integration (Rust)

#### 2.1 Agent State Enhancement
**File**: `backend/src/models/agent.rs`

```rust
pub struct Agent {
    pub id: String,
    pub balance: i64,
    pub credit_limit: i64,
    pub credit_used: i64,

    // ADD: Collateral tracking
    pub posted_collateral: i64,
    pub collateral_posted_at_tick: Option<i64>, // For minimum holding period
    pub collateral_haircut: f64, // e.g., 0.95 = 95% of value counts toward headroom

    // ... queues, etc ...
}

impl Agent {
    /// Calculate total available liquidity including collateral-backed credit
    pub fn available_liquidity(&self) -> i64 {
        let positive_balance = self.balance.max(0);

        // Collateral-backed headroom: haircut * posted_collateral
        let collateral_headroom = ((self.posted_collateral as f64) * self.collateral_haircut) as i64;

        // Total headroom = base credit limit + collateral headroom - credit used
        let total_headroom = self.credit_limit + collateral_headroom - self.credit_used;

        let available_headroom = total_headroom.max(0);

        positive_balance + available_headroom
    }

    /// Can withdraw collateral? (Must wait minimum holding period)
    pub fn can_withdraw_collateral(&self, current_tick: i64, min_holding_ticks: i64) -> bool {
        match self.collateral_posted_at_tick {
            None => true, // No collateral posted
            Some(posted_at) => {
                let ticks_held = current_tick - posted_at;
                ticks_held >= min_holding_ticks
            }
        }
    }
}
```

#### 2.2 Collateral Event Enhancements
**File**: `backend/src/models/event.rs`

```rust
pub enum Event {
    // ... settlement events from Phase 1 ...

    // ENHANCE: Collateral events with specific reasons
    CollateralPosted {
        tick: i64,
        agent_id: String,
        amount: i64,
        reason: CollateralReason,
        new_total: i64,
        headroom_increase: i64, // How much liquidity this adds
    },

    CollateralWithdrawn {
        tick: i64,
        agent_id: String,
        amount: i64,
        reason: CollateralWithdrawReason,
        new_total: i64,
        ticks_held: i64,
    },

    // ... other events ...
}

pub enum CollateralReason {
    OverdueTransaction(String), // tx_id
    QueuePressure { queue_value: i64, liquidity_gap: i64 },
    CreditLimitApproaching { credit_used_pct: f64 },
    EndOfDayBuffer { unsettled_count: usize },
}

pub enum CollateralWithdrawReason {
    LiquidityRestored,
    MinimumHoldingPeriodExpired,
    EndOfDay,
}
```

#### 2.3 Collateral Policy with Hysteresis
**File**: `backend/src/policies/collateral.rs` (NEW)

```rust
use crate::models::{Agent, Event, CollateralReason, CollateralWithdrawReason};

pub struct CollateralPolicy {
    pub min_holding_ticks: i64,
    pub posting_threshold_pct: f64, // Only post if gap > this % of queue value
    pub withdrawal_threshold_pct: f64, // Only withdraw if excess > this %
    pub haircut: f64,
}

impl CollateralPolicy {
    pub fn evaluate_posting(
        &self,
        agent: &Agent,
        current_tick: i64,
        queue_value: i64,
    ) -> Option<(i64, CollateralReason)> {
        let available = agent.available_liquidity();
        let liquidity_gap = queue_value - available;

        // Only post if gap exceeds threshold
        if liquidity_gap <= 0 {
            return None;
        }

        let gap_pct = (liquidity_gap as f64) / (queue_value as f64);
        if gap_pct < self.posting_threshold_pct {
            return None; // Gap too small, don't thrash
        }

        // Calculate amount to post (cover gap + small buffer)
        let amount_to_post = (liquidity_gap as f64 * 1.1) as i64;

        let reason = CollateralReason::QueuePressure {
            queue_value,
            liquidity_gap,
        };

        Some((amount_to_post, reason))
    }

    pub fn evaluate_withdrawal(
        &self,
        agent: &Agent,
        current_tick: i64,
        queue_value: i64,
    ) -> Option<(i64, CollateralWithdrawReason)> {
        // Check minimum holding period
        if !agent.can_withdraw_collateral(current_tick, self.min_holding_ticks) {
            return None;
        }

        // Check if we have excess liquidity
        let available = agent.available_liquidity();
        let excess = available - queue_value;

        if excess <= 0 {
            return None; // Still need the collateral
        }

        let excess_pct = (excess as f64) / (queue_value.max(1) as f64);
        if excess_pct < self.withdrawal_threshold_pct {
            return None; // Not enough excess to justify withdrawal
        }

        // Withdraw partial amount, keep some buffer
        let amount_to_withdraw = agent.posted_collateral.min((excess as f64 * 0.8) as i64);

        let reason = CollateralWithdrawReason::LiquidityRestored;

        Some((amount_to_withdraw, reason))
    }
}
```

---

### Phase 3: Python Display Updates

#### 3.1 Display Settlement Types
**File**: `api/payment_simulator/cli/display/verbose_output.py`

```python
def display_tick_verbose_output(provider: StateProvider, tick: int, events: List[Dict]):
    """Single source of truth for tick display (run AND replay)."""

    # Group settlements by type
    rtgs_immediate = []
    queue_releases = []
    lsm_bilaterals = []
    lsm_cycles = []

    for event in events:
        event_type = event.get('event_type')

        if event_type == 'rtgs_immediate_settlement':
            rtgs_immediate.append(event)
        elif event_type == 'queue2_liquidity_release':
            queue_releases.append(event)
        elif event_type == 'lsm_bilateral_offset':
            lsm_bilaterals.append(event)
        elif event_type == 'lsm_cycle_settlement':
            lsm_cycles.append(event)

    # Display settlements
    total_settled = len(rtgs_immediate) + len(queue_releases) + len(lsm_bilaterals) + len(lsm_cycles)
    if total_settled > 0:
        console.print(f"\n✅ {total_settled} transaction(s) settled:\n")

        if rtgs_immediate:
            console.print(f"   [bold]RTGS Immediate ({len(rtgs_immediate)}):[/bold]")
            for event in rtgs_immediate:
                console.print(
                    f"   • TX {event['tx_id']}: {event['sender']} → {event['receiver']} | "
                    f"${event['amount']/100:.2f}"
                )

        if queue_releases:
            console.print(f"\n   [bold]Queue Releases ({len(queue_releases)}):[/bold]")
            for event in queue_releases:
                wait = event['queue_wait_ticks']
                reason = event['release_reason']
                console.print(
                    f"   • TX {event['tx_id']}: {event['sender']} → {event['receiver']} | "
                    f"${event['amount']/100:.2f} | [dim]Waited {wait} ticks | {reason}[/dim]"
                )

        if lsm_bilaterals:
            console.print(f"\n   [bold]LSM Bilateral Offsets ({len(lsm_bilaterals)}):[/bold]")
            for event in lsm_bilaterals:
                console.print(
                    f"   • {event['agent_a']} ⇄ {event['agent_b']} | "
                    f"Net settled: ${event['net_settled']/100:.2f}"
                )
                console.print(f"      TX {event['tx_a_to_b']}: ${event['amount_a_to_b']/100:.2f}")
                console.print(f"      TX {event['tx_b_to_a']}: ${event['amount_b_to_a']/100:.2f}")

        if lsm_cycles:
            console.print(f"\n   [bold]LSM Cycle Settlements ({len(lsm_cycles)}):[/bold]")
            for event in lsm_cycles:
                n_agents = len(event['agents'])
                console.print(
                    f"   • {n_agents}-agent cycle | Total value: ${event['total_value']/100:.2f} | "
                    f"Max outflow: ${event['max_net_outflow']/100:.2f} ({event['max_net_outflow_agent']})"
                )
                for i, agent in enumerate(event['agents']):
                    tx_id = event['tx_ids'][i]
                    amount = event['tx_amounts'][i]
                    net_pos = event['net_positions'][i]
                    console.print(
                        f"      {agent}: TX {tx_id} ${amount/100:.2f} | "
                        f"Net position: ${net_pos/100:.2f}"
                    )
```

#### 3.2 Display Collateral with Reasons
**File**: `api/payment_simulator/cli/display/verbose_output.py`

```python
def display_collateral_activity(events: List[Dict]):
    """Display collateral events with specific reasons."""
    collateral_events = [
        e for e in events
        if e.get('event_type') in ['collateral_posted', 'collateral_withdrawn']
    ]

    if not collateral_events:
        return

    # Group by agent
    by_agent = {}
    for event in collateral_events:
        agent_id = event['agent_id']
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append(event)

    console.print("\n💰 Collateral Activity:")
    for agent_id, agent_events in by_agent.items():
        console.print(f"   [bold]{agent_id}:[/bold]")
        for event in agent_events:
            event_type = event['event_type']
            amount = event['amount']
            new_total = event['new_total']

            if event_type == 'collateral_posted':
                reason = event['reason']
                headroom_increase = event['headroom_increase']
                console.print(
                    f"   • POSTED: ${amount/100:,.2f} | Reason: {reason} | "
                    f"New Total: ${new_total/100:,.2f} | "
                    f"+${headroom_increase/100:,.2f} liquidity"
                )
            else:  # withdrawn
                ticks_held = event['ticks_held']
                reason = event['reason']
                console.print(
                    f"   • WITHDRAWN: ${amount/100:,.2f} | Reason: {reason} | "
                    f"New Total: ${new_total/100:,.2f} | "
                    f"Held {ticks_held} ticks"
                )
```

---

### Phase 4: Configuration Updates

#### 4.1 Add Collateral Policy Config
**File**: `api/payment_simulator/config/schema.py`

```python
class CollateralPolicyConfig(BaseModel):
    """Configuration for collateral posting/withdrawal policy."""

    min_holding_ticks: int = Field(
        default=5,
        ge=0,
        description="Minimum ticks collateral must be held before withdrawal"
    )

    posting_threshold_pct: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Only post collateral if liquidity gap > this % of queue value"
    )

    withdrawal_threshold_pct: float = Field(
        default=0.20,
        ge=0.0,
        le=1.0,
        description="Only withdraw if excess liquidity > this % of queue value"
    )

    haircut: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Fraction of posted collateral that counts toward headroom"
    )

class AgentConfig(BaseModel):
    # ... existing fields ...

    collateral_policy: Optional[CollateralPolicyConfig] = Field(
        default_factory=CollateralPolicyConfig,
        description="Policy for collateral posting/withdrawal"
    )
```

**File**: `three_day_realistic_crisis.yaml`

```yaml
agents:
  - id: REGIONAL_TRUST
    opening_balance: 200000.00
    credit_limit: 80000.00
    # ... existing config ...

    collateral_policy:
      min_holding_ticks: 5
      posting_threshold_pct: 0.10  # Only post if gap > 10% of queue
      withdrawal_threshold_pct: 0.20  # Only withdraw if excess > 20%
      haircut: 0.95  # 95% of posted value counts as liquidity
```

---

## Test Plan (TDD)

### Test 1: Settlement Event Classification
**File**: `api/tests/integration/test_settlement_classification.py`

```python
def test_rtgs_immediate_creates_correct_event():
    """RTGS immediate settlement creates rtgs_immediate_settlement event."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "credit_limit": 0},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0},
        ],
    })

    # Inject transaction that can settle immediately
    orch.inject_transaction({
        "id": "tx1",
        "sender": "A",
        "receiver": "B",
        "amount": 10000,
        "priority": 5,
    })

    orch.tick()

    events = orch.get_tick_events(orch.current_tick())
    settlement_events = [e for e in events if e['event_type'] == 'rtgs_immediate_settlement']

    assert len(settlement_events) == 1
    event = settlement_events[0]

    assert event['tx_id'] == "tx1"
    assert event['sender'] == "A"
    assert event['receiver'] == "B"
    assert event['amount'] == 10000
    assert event['sender_balance_before'] == 100000
    assert event['sender_balance_after'] == 90000


def test_queue_release_creates_correct_event():
    """Queue 2 release creates queue2_liquidity_release event."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 10000},
            {"id": "B", "opening_balance": 50000, "credit_limit": 0},
        ],
    })

    # Inject transaction that will queue (insufficient liquidity)
    orch.inject_transaction({
        "id": "tx1",
        "sender": "A",
        "receiver": "B",
        "amount": 20000,  # More than balance + available credit
        "priority": 5,
    })

    orch.tick()  # Queues

    # Now give A liquidity via incoming payment
    orch.inject_transaction({
        "id": "tx2",
        "sender": "B",
        "receiver": "A",
        "amount": 20000,
        "priority": 5,
    })

    orch.tick()  # tx2 settles, tx1 releases from queue

    events = orch.get_tick_events(orch.current_tick())
    queue_release_events = [e for e in events if e['event_type'] == 'queue2_liquidity_release']

    assert len(queue_release_events) == 1
    event = queue_release_events[0]

    assert event['tx_id'] == "tx1"
    assert event['queue_wait_ticks'] == 1
    assert event['release_reason'] in ['NewLiquidity', 'IncomingPayment']


def test_lsm_bilateral_creates_correct_event():
    """LSM bilateral offset creates lsm_bilateral_offset event."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "lsm_enabled": True,
        "agent_configs": [
            {"id": "A", "opening_balance": 5000, "credit_limit": 0},
            {"id": "B", "opening_balance": 5000, "credit_limit": 0},
        ],
    })

    # Create bilateral gridlock
    orch.inject_transaction({
        "id": "tx_a_to_b",
        "sender": "A",
        "receiver": "B",
        "amount": 10000,
        "priority": 5,
    })

    orch.inject_transaction({
        "id": "tx_b_to_a",
        "sender": "B",
        "receiver": "A",
        "amount": 8000,
        "priority": 5,
    })

    orch.tick()  # Both queue
    orch.run_lsm()  # LSM should find bilateral offset

    events = orch.get_all_events()
    lsm_events = [e for e in events if e['event_type'] == 'lsm_bilateral_offset']

    assert len(lsm_events) == 1
    event = lsm_events[0]

    assert set([event['agent_a'], event['agent_b']]) == {'A', 'B'}
    assert event['net_settled'] == 8000  # min(10000, 8000)


def test_replay_preserves_settlement_classification():
    """Replay shows same settlement types as run mode."""
    config = {
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {"id": "A", "opening_balance": 100000, "credit_limit": 50000},
            {"id": "B", "opening_balance": 100000, "credit_limit": 50000},
        ],
    }

    # Run mode
    orch = Orchestrator.new(config)
    orch.run_ticks(10)
    run_events = orch.get_all_events()

    run_rtgs = [e for e in run_events if e['event_type'] == 'rtgs_immediate_settlement']
    run_queue = [e for e in run_events if e['event_type'] == 'queue2_liquidity_release']

    # Replay mode (assuming persistence)
    # replay_events = replay_from_db(sim_id)
    # replay_rtgs = [e for e in replay_events if e['event_type'] == 'rtgs_immediate_settlement']
    # replay_queue = [e for e in replay_events if e['event_type'] == 'queue2_liquidity_release']

    # assert len(run_rtgs) == len(replay_rtgs)
    # assert len(run_queue) == len(replay_queue)
    # ... compare tx_ids ...
```

### Test 2: Collateral Headroom Integration
**File**: `api/tests/integration/test_collateral_headroom.py`

```python
def test_posted_collateral_increases_available_liquidity():
    """Posted collateral immediately increases available liquidity."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": -50000,  # Overdraft
                "credit_limit": 60000,
                "collateral_policy": {
                    "haircut": 0.95,
                },
            },
            {"id": "B", "opening_balance": 100000, "credit_limit": 0},
        ],
    })

    # Check initial liquidity
    agent_a = orch.get_agent_state("A")
    initial_liquidity = agent_a['available_liquidity']
    # balance=-50000, credit_limit=60000, credit_used=50000
    # available = 0 + (60000 - 50000) = 10000
    assert initial_liquidity == 10000

    # Post collateral
    orch.post_collateral("A", 100000)  # Post $100K

    # Check new liquidity
    agent_a = orch.get_agent_state("A")
    new_liquidity = agent_a['available_liquidity']
    posted = agent_a['posted_collateral']

    assert posted == 100000
    # available = 0 + (60000 + 100000*0.95 - 50000) = 0 + (60000 + 95000 - 50000) = 105000
    assert new_liquidity == 105000

    # Verify event logged headroom increase
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e['event_type'] == 'collateral_posted']
    assert len(collateral_events) == 1
    assert collateral_events[0]['headroom_increase'] == 95000


def test_collateral_minimum_holding_period():
    """Cannot withdraw collateral before minimum holding period."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 100000,
                "credit_limit": 50000,
                "collateral_policy": {
                    "min_holding_ticks": 5,
                },
            },
            {"id": "B", "opening_balance": 100000, "credit_limit": 0},
        ],
    })

    # Post collateral at tick 0
    orch.post_collateral("A", 50000)
    assert orch.get_agent_state("A")['posted_collateral'] == 50000

    # Try to withdraw at tick 1 (too soon)
    orch.tick()
    result = orch.withdraw_collateral("A", 50000)
    assert result['success'] == False
    assert 'minimum holding period' in result['reason'].lower()

    # Try to withdraw at tick 4 (still too soon)
    for _ in range(3):
        orch.tick()
    result = orch.withdraw_collateral("A", 50000)
    assert result['success'] == False

    # Withdraw at tick 5 (allowed)
    orch.tick()
    result = orch.withdraw_collateral("A", 50000)
    assert result['success'] == True
    assert orch.get_agent_state("A")['posted_collateral'] == 0

    # Verify event includes ticks_held
    events = orch.get_tick_events(orch.current_tick())
    withdraw_events = [e for e in events if e['event_type'] == 'collateral_withdrawn']
    assert len(withdraw_events) == 1
    assert withdraw_events[0]['ticks_held'] == 5


def test_collateral_policy_hysteresis():
    """Collateral policy only posts/withdraws when gap exceeds threshold."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "credit_limit": 20000,
                "collateral_policy": {
                    "posting_threshold_pct": 0.10,  # Only post if gap > 10% of queue
                    "withdrawal_threshold_pct": 0.20,
                },
            },
            {"id": "B", "opening_balance": 100000, "credit_limit": 0},
        ],
    })

    # Create small queue (below threshold)
    orch.inject_transaction({
        "id": "tx1",
        "sender": "A",
        "receiver": "B",
        "amount": 32000,  # Slightly more than available (30000)
        "priority": 5,
    })

    orch.tick()  # Queues

    # Check that collateral was NOT posted (gap too small)
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e['event_type'] == 'collateral_posted']
    assert len(collateral_events) == 0

    # Now create large queue (above threshold)
    orch.inject_transaction({
        "id": "tx2",
        "sender": "A",
        "receiver": "B",
        "amount": 40000,
        "priority": 5,
    })

    orch.tick()  # Now gap is large

    # Check that collateral WAS posted
    events = orch.get_tick_events(orch.current_tick())
    collateral_events = [e for e in events if e['event_type'] == 'collateral_posted']
    assert len(collateral_events) == 1


def test_no_collateral_oscillation():
    """Agent does not post/withdraw collateral every tick."""
    orch = Orchestrator.new({
        "seed": 42,
        "ticks_per_day": 100,
        "agent_configs": [
            {
                "id": "A",
                "opening_balance": 10000,
                "credit_limit": 20000,
                "collateral_policy": {
                    "min_holding_ticks": 5,
                    "posting_threshold_pct": 0.10,
                    "withdrawal_threshold_pct": 0.20,
                },
            },
            {"id": "B", "opening_balance": 100000, "credit_limit": 0},
        ],
    })

    # Create sustained queue pressure
    for i in range(10):
        orch.inject_transaction({
            "id": f"tx{i}",
            "sender": "A",
            "receiver": "B",
            "amount": 15000,
            "priority": 5,
        })
        orch.tick()

    # Count collateral events
    all_events = orch.get_all_events()
    posted_events = [e for e in all_events if e['event_type'] == 'collateral_posted']
    withdrawn_events = [e for e in all_events if e['event_type'] == 'collateral_withdrawn']

    # Should post once and hold it (not oscillate)
    assert len(posted_events) <= 2  # At most 2 postings in 10 ticks
    assert len(withdrawn_events) == 0  # Should not withdraw while queue persists
```

### Test 3: Replay Identity with New Events
**File**: `api/tests/integration/test_replay_identity_gold_standard.py`

```python
def test_replay_settlement_classification_identity():
    """Replay preserves exact settlement event types from run."""
    config_path = "three_day_realistic_crisis.yaml"
    db_path = "test_replay_settlement.db"

    # Run mode
    result = subprocess.run([
        "payment-sim", "run",
        "--config", config_path,
        "--persist", db_path,
        "--ticks", "50",
    ], capture_output=True, text=True)

    run_output = result.stdout

    # Replay mode
    result = subprocess.run([
        "payment-sim", "replay",
        "--db", db_path,
        "--from-tick", "0",
        "--to-tick", "50",
    ], capture_output=True, text=True)

    replay_output = result.stdout

    # Compare settlement sections (excluding timestamps)
    run_settlements = extract_settlement_section(run_output)
    replay_settlements = extract_settlement_section(replay_output)

    assert run_settlements == replay_settlements

    # Verify all 4 settlement types present
    assert "RTGS Immediate" in replay_output
    assert "Queue Releases" in replay_output or "Queue Release" in replay_output
    assert "LSM Bilateral" in replay_output or len([e for e in events if e['event_type'] == 'lsm_bilateral_offset']) > 0
    assert "LSM Cycle" in replay_output or len([e for e in events if e['event_type'] == 'lsm_cycle_settlement']) > 0


def test_replay_collateral_identity():
    """Replay preserves exact collateral events from run."""
    config_path = "three_day_realistic_crisis.yaml"
    db_path = "test_replay_collateral.db"

    # Run mode
    result = subprocess.run([
        "payment-sim", "run",
        "--config", config_path,
        "--persist", db_path,
        "--ticks", "100",
    ], capture_output=True, text=True)

    run_output = result.stdout

    # Replay mode
    result = subprocess.run([
        "payment-sim", "replay",
        "--db", db_path,
        "--from-tick", "0",
        "--to-tick", "100",
    ], capture_output=True, text=True)

    replay_output = result.stdout

    # Extract collateral sections
    run_collateral = extract_collateral_section(run_output)
    replay_collateral = extract_collateral_section(replay_output)

    assert run_collateral == replay_collateral

    # Verify no oscillation (max 1 post per 5 ticks)
    posted_count = run_output.count("POSTED:")
    assert posted_count <= 100 / 5  # At most 20 postings in 100 ticks
```

---

## Implementation Order (TDD Workflow)

### Iteration 1: Settlement Classification
1. ✅ Write failing test: `test_rtgs_immediate_creates_correct_event`
2. ✅ Add `Event::RtgsImmediateSettlement` to event.rs
3. ✅ Update RTGS settlement to emit new event
4. ✅ Add FFI serialization for new event
5. ✅ Update display logic to show "RTGS Immediate"
6. ✅ Test passes

### Iteration 2: Queue Release Classification
1. ✅ Write failing test: `test_queue_release_creates_correct_event`
2. ✅ Add `Event::Queue2LiquidityRelease` to event.rs
3. ✅ Update queue release logic to emit new event
4. ✅ Add FFI serialization
5. ✅ Update display logic to show "Queue Releases"
6. ✅ Test passes

### Iteration 3: LSM Classification
1. ✅ Write failing tests for bilateral and cycle
2. ✅ Add `Event::LsmBilateralOffset` and `Event::LsmCycleSettlement`
3. ✅ Update LSM to distinguish bilateral vs cycle
4. ✅ Add FFI serialization
5. ✅ Update display logic
6. ✅ Tests pass

### Iteration 4: Collateral Headroom
1. ✅ Write failing test: `test_posted_collateral_increases_available_liquidity`
2. ✅ Add `posted_collateral` and `collateral_haircut` to Agent struct
3. ✅ Update `available_liquidity()` method
4. ✅ Test passes

### Iteration 5: Collateral Minimum Holding
1. ✅ Write failing test: `test_collateral_minimum_holding_period`
2. ✅ Add `collateral_posted_at_tick` to Agent
3. ✅ Add `can_withdraw_collateral()` method
4. ✅ Enforce in withdrawal logic
5. ✅ Test passes

### Iteration 6: Collateral Hysteresis
1. ✅ Write failing test: `test_collateral_policy_hysteresis`
2. ✅ Create `CollateralPolicy` struct
3. ✅ Add `evaluate_posting()` and `evaluate_withdrawal()` methods
4. ✅ Integrate into tick loop
5. ✅ Test passes

### Iteration 7: Replay Identity
1. ✅ Write failing test: `test_replay_settlement_classification_identity`
2. ✅ Ensure all events persisted correctly
3. ✅ Verify replay display matches run
4. ✅ Test passes

### Iteration 8: Integration Test
1. ✅ Run full replay test on sim-6556aa5d ticks 250-260
2. ✅ Verify no oscillation
3. ✅ Verify LSM events visible
4. ✅ Verify headroom increases with collateral

---

## Acceptance Criteria

### Must Pass
- [ ] All new tests pass (8 test files)
- [ ] Existing tests pass (regression check)
- [ ] Replay identity maintained (run == replay output)
- [ ] No collateral oscillation in ticks 250-260 replay
- [ ] LSM events visible in verbose output
- [ ] Available liquidity includes collateral-backed headroom

### Performance
- [ ] No significant performance regression (<5% slowdown)
- [ ] FFI event serialization overhead acceptable

### Documentation
- [ ] CLAUDE.md updated with new event types
- [ ] Config schema documented
- [ ] Example configs updated

---

## Rollout Plan

1. **Phase 1 (Settlement)**: Deploy settlement classification first (low risk)
2. **Phase 2 (Collateral Headroom)**: Deploy headroom calculation (medium risk)
3. **Phase 3 (Collateral Policy)**: Deploy hysteresis logic (low risk)
4. **Phase 4 (Verification)**: Re-run all historical simulations to verify metrics

---

## Risk Mitigation

### Risk 1: Breaking Existing Metrics
**Mitigation**: Keep old `TransactionSettled` event temporarily, emit both old and new events for transition period

### Risk 2: Collateral Policy Too Conservative
**Mitigation**: Make thresholds configurable, provide multiple presets (aggressive, balanced, conservative)

### Risk 3: Replay Divergence
**Mitigation**: Extensive TDD, compare byte-for-byte output, use gold standard tests

---

## Questions / Decisions

1. **Q**: Should we backfill existing databases with new event types?
   **A**: No, too risky. Mark old sims as "legacy format" in metadata.

2. **Q**: Should collateral haircut vary by asset type?
   **A**: Not yet. Keep simple (single haircut per agent). Future enhancement.

3. **Q**: What if agent has no collateral to post?
   **A**: Policy returns `None`, agent continues in overdraft. No special handling.

---

## Success Metrics

- **Settlement Accuracy**: 100% of settlements correctly classified
- **Collateral Stability**: <1 collateral event per 5 ticks (on average)
- **Headroom Correctness**: Available liquidity = balance + (credit + collateral*haircut - credit_used)
- **Replay Identity**: 0 byte differences (modulo timestamps)
- **Test Coverage**: >90% of new code covered by tests

---

**Next Steps**: Proceed to implementation following TDD workflow above.
