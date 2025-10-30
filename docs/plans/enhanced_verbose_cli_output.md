# Enhanced Verbose CLI Output Implementation Plan

**Status**: PLANNING
**Priority**: HIGH
**Goal**: Transform CLI verbose mode into a comprehensive real-time simulation monitoring system

---

## Executive Summary

**Current State**: Verbose mode shows basic tick summaries with arrival/settlement counts and agent balance changes. Missing granular transaction details, settlement mechanisms, queue contents, and comprehensive statistics.

**Goal**: Create a detailed, real-time monitoring system that shows:
- Every transaction that arrives (with full details)
- Every settlement (with mechanism: RTGS immediate, RTGS queued, LSM bilateral, LSM cycle)
- Queue contents for each agent (Queue 1 and Queue 2)
- Collateral activity per agent
- Policy decisions with reasoning
- Balance utilization metrics
- Cost breakdowns by type
- End-of-day comprehensive statistics

**Approach**: Three-phase implementation (Rust FFI → Python helpers → CLI integration) following TDD principles.

---

## Current Implementation Analysis

### What We Have Now ([run.py:226-289](api/payment_simulator/cli/commands/run.py#L226-L289))

```python
# Verbose tick loop (simplified)
for tick_num in range(total_ticks):
    log_tick_start(tick_num)  # "═══ Tick 42 ═══"
    result = orch.tick()

    # Basic counts only
    log_arrivals(result["num_arrivals"])  # "📥 5 transaction(s) arrived"
    log_settlements(result["num_settlements"])  # "✅ 3 transaction(s) settled"
    log_lsm_activity(bilateral=result["num_lsm_releases"])
    log_costs(result["total_cost"])

    # Agent states (balance changes only, no queue details)
    for agent_id in agent_ids:
        balance = orch.get_agent_balance(agent_id)
        queue_size = orch.get_queue1_size(agent_id)
        log_agent_state(agent_id, balance, queue_size, balance_change)

    log_tick_summary(...)  # Simple summary line
```

### What's Missing

1. **Transaction-level detail**: No info about which transactions arrived/settled
2. **Settlement mechanisms**: Don't know if RTGS immediate, queued, or LSM
3. **Queue contents**: Only sizes, not actual transaction IDs
4. **Queue 2 visibility**: RTGS queue completely invisible
5. **Policy decisions**: No visibility into submit/hold/drop reasoning
6. **Collateral activity**: Events not shown per agent
7. **Balance utilization**: Not showing credit limit usage %
8. **Cost breakdown**: Only totals, not by type (overdraft, delay, split)
9. **LSM cycle details**: No cycle visualization (A→B→C→A)
10. **End-of-day stats**: No daily rollup statistics

---

## Architecture: Three-Layer Approach

```
┌─────────────────────────────────────────────────────┐
│  Layer 3: CLI Verbose Mode (run.py)                │
│  - Orchestrates display logic                      │
│  - Queries Rust state via FFI                      │
│  - Formats output using helpers                    │
└────────────────┬────────────────────────────────────┘
                 │ Calls
┌────────────────▼────────────────────────────────────┐
│  Layer 2: Output Helpers (output.py)               │
│  - log_transaction_details()                       │
│  - log_settlement_details()                        │
│  - log_agent_queues_detailed()                     │
│  - log_policy_decisions()                          │
│  - log_cost_breakdown()                            │
│  - log_lsm_cycle_visualization()                   │
│  - log_end_of_day_stats()                          │
└────────────────┬────────────────────────────────────┘
                 │ Queries via FFI
┌────────────────▼────────────────────────────────────┐
│  Layer 1: Rust FFI Methods (orchestrator.rs)      │
│  - get_tick_events(tick)                           │
│  - get_transaction_details(tx_id)                  │
│  - get_rtgs_queue_contents()                       │
│  - get_agent_credit_limit(agent_id)                │
│  - get_agent_collateral_posted(agent_id)           │
│  - get_lsm_cycle_details(tick)                     │
└─────────────────────────────────────────────────────┘
```

---

## Phase 1: Rust FFI Extensions (RED-GREEN)

### Task 1.1: Expose Event Log via FFI

**File**: `backend/src/ffi/orchestrator.rs`

**Add Method**:
```rust
/// Get all events that occurred during a specific tick
///
/// Returns detailed event log entries for arrivals, settlements,
/// policy decisions, collateral actions, and LSM cycles.
///
/// # Arguments
/// * `tick` - Tick number to query
///
/// # Returns
/// List of event dictionaries with structure:
/// - "type": str - Event type (Arrival, Settlement, PolicySubmit, etc.)
/// - "tick": int - Tick number
/// - "data": dict - Event-specific data
///
/// # Example (from Python)
/// ```python
/// events = orch.get_tick_events(42)
/// for event in events:
///     if event["type"] == "Arrival":
///         print(f"TX {event['tx_id']}: {event['sender']} → {event['receiver']}")
/// ```
fn get_tick_events(&self, py: Python, tick: usize) -> PyResult<Py<PyList>> {
    // Implementation calls self.inner.event_log().events_at_tick(tick)
    // Converts Event enum to Python dicts
}
```

**Rust Engine Method** (`backend/src/orchestrator/engine.rs`):
```rust
pub fn get_tick_events(&self, tick: usize) -> Vec<&Event> {
    self.event_log.events_at_tick(tick)
}
```

**Test** (`backend/tests/test_event_log_ffi.rs`):
```rust
#[test]
fn test_get_tick_events_returns_all_events_for_tick() {
    // Create orchestrator, run 10 ticks
    // Query events for tick 5
    // Verify all events present
}
```

### Task 1.2: Transaction Detail Query

**Add FFI Method**:
```rust
/// Get full details for a specific transaction
///
/// # Returns
/// Dictionary with:
/// - id: str
/// - sender_id: str
/// - receiver_id: str
/// - amount: int (cents)
/// - remaining_amount: int (cents)
/// - arrival_tick: int
/// - deadline_tick: int
/// - priority: int (0-10)
/// - status: str (Pending, Settled, etc.)
/// - parent_id: Optional[str]
fn get_transaction_details(&self, tx_id: &str) -> PyResult<Py<PyDict>> {
    // Calls self.inner.get_transaction(tx_id)
}
```

**Rust Engine Method**:
```rust
pub fn get_transaction(&self, tx_id: &str) -> Option<&Transaction> {
    self.state.get_transaction(tx_id)
}
```

### Task 1.3: RTGS Queue Contents

**Add FFI Method**:
```rust
/// Get list of transaction IDs in RTGS queue (Queue 2)
///
/// Returns transaction IDs in the central RTGS queue waiting
/// for liquidity to become available.
///
/// # Returns
/// List of transaction IDs (strings) in queue order
fn get_rtgs_queue_contents(&self) -> Vec<String> {
    self.inner.get_rtgs_queue_contents()
}
```

**Rust Engine Method**:
```rust
pub fn get_rtgs_queue_contents(&self) -> Vec<String> {
    self.state.get_rtgs_queue().clone()
}
```

### Task 1.4: Agent Credit Limit Query

**Add FFI Method**:
```rust
/// Get agent's credit limit
fn get_agent_credit_limit(&self, agent_id: &str) -> Option<i64> {
    self.inner.get_agent_credit_limit(agent_id)
}
```

**Rust Engine Method**:
```rust
pub fn get_agent_credit_limit(&self, agent_id: &str) -> Option<i64> {
    self.state.agents.get(agent_id).map(|a| a.credit_limit())
}
```

### Task 1.5: Agent Collateral Query

**Add FFI Method**:
```rust
/// Get agent's currently posted collateral
fn get_agent_collateral_posted(&self, agent_id: &str) -> Option<i64> {
    self.inner.get_agent_collateral_posted(agent_id)
}
```

### Task 1.6: Cost Breakdown Query

**Add FFI Method**:
```rust
/// Get detailed cost breakdown for an agent
///
/// # Returns
/// Dictionary with:
/// - overdraft_cost: int (cents)
/// - delay_penalty: int (cents)
/// - split_fee: int (cents)
/// - total: int (cents)
fn get_agent_cost_breakdown(&self, agent_id: &str) -> PyResult<Py<PyDict>> {
    // Calls self.inner.get_costs(agent_id)
}
```

**Existing Rust Method**: Already exists as `get_costs()` returning `CostAccumulator`

**Test Coverage**: 6 new integration tests in `backend/tests/test_verbose_cli_ffi.rs`

---

## Phase 2: Python Output Helpers

### Task 2.1: Transaction Arrival Details

**File**: `api/payment_simulator/cli/output.py`

**Add Function**:
```python
def log_transaction_arrivals(orch: Orchestrator, events: List[Dict], quiet: bool = False):
    """Log detailed transaction arrivals (verbose mode).

    For each arrival event, shows:
    - Transaction ID (truncated to 8 chars)
    - Sender → Receiver
    - Amount (formatted as currency)
    - Priority level (with color coding)
    - Deadline tick

    Args:
        orch: Orchestrator instance (for querying transaction details)
        events: List of arrival events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        📥 3 transaction(s) arrived:
           • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00 | P:8 [red]HIGH[/red] | ⏰ Tick 50
           • TX e5f6g7h8: BANK_B → BANK_C | $250.50 | P:5 MED | ⏰ Tick 55
           • TX i9j0k1l2: BANK_C → BANK_A | $5,000.00 | P:3 LOW | ⏰ Tick 60
    """
    if quiet:
        return

    arrival_events = [e for e in events if e["type"] == "Arrival"]
    if not arrival_events:
        return

    console.print(f"📥 [cyan]{len(arrival_events)} transaction(s) arrived:[/cyan]")

    for event in arrival_events:
        tx_id = event["tx_id"][:8]  # Truncate for readability
        sender = event["sender_id"]
        receiver = event["receiver_id"]
        amount = event["amount"]

        # Get full transaction details for priority/deadline
        tx_details = orch.get_transaction_details(event["tx_id"])
        priority = tx_details["priority"]
        deadline = tx_details["deadline_tick"]

        # Color code priority
        if priority >= 7:
            priority_str = f"P:{priority} [red]HIGH[/red]"
        elif priority >= 4:
            priority_str = f"P:{priority} MED"
        else:
            priority_str = f"P:{priority} LOW"

        amount_str = f"${amount / 100:,.2f}"

        console.print(
            f"   • TX {tx_id}: {sender} → {receiver} | "
            f"{amount_str} | {priority_str} | ⏰ Tick {deadline}"
        )
```

### Task 2.2: Settlement Details with Mechanism

**Add Function**:
```python
def log_settlement_details(orch: Orchestrator, events: List[Dict], tick: int, quiet: bool = False):
    """Log detailed settlements showing how each transaction settled.

    Categorizes settlements by mechanism:
    - RTGS Immediate: Settled immediately upon submission
    - RTGS Queued: Settled after waiting in Queue 2
    - LSM Bilateral: Paired with offsetting transaction
    - LSM Cycle: Part of multilateral netting cycle

    Args:
        orch: Orchestrator instance
        events: List of events from get_tick_events()
        tick: Current tick number
        quiet: Suppress output if True

    Example Output:
        ✅ 5 transaction(s) settled:

           [green]RTGS Immediate (2):[/green]
           • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00
           • TX e5f6g7h8: BANK_C → BANK_D | $500.00

           [magenta]LSM Bilateral Offset (2):[/magenta]
           • TX i9j0k1l2 ⟷ TX m3n4o5p6: BANK_A ⇄ BANK_B | $750.00

           [magenta]LSM Cycle (1):[/magenta]
           • Cycle: BANK_A → BANK_B → BANK_C → BANK_A | Net: $200.00
             - TX q7r8s9t0: $500.00
             - TX u1v2w3x4: $450.00
             - TX y5z6a7b8: $250.00
    """
    if quiet:
        return

    # Categorize settlements by mechanism
    settlement_events = [e for e in events if e["type"] == "Settlement"]
    queued_rtgs = [e for e in events if e["type"] == "QueuedRtgs"]
    lsm_bilateral = [e for e in events if e["type"] == "LsmBilateralOffset"]
    lsm_cycles = [e for e in events if e["type"] == "LsmCycleSettlement"]

    total_settlements = len(settlement_events)
    if total_settlements == 0:
        return

    console.print(f"✅ [green]{total_settlements} transaction(s) settled:[/green]")
    console.print()

    # RTGS immediate (settlement events without prior queuing)
    rtgs_immediate = [
        e for e in settlement_events
        if not any(q["tx_id"] == e["tx_id"] for q in queued_rtgs)
    ]

    if rtgs_immediate:
        console.print(f"   [green]RTGS Immediate ({len(rtgs_immediate)}):[/green]")
        for event in rtgs_immediate:
            tx_details = orch.get_transaction_details(event["tx_id"])
            console.print(
                f"   • TX {event['tx_id'][:8]}: {event['sender_id']} → "
                f"{event['receiver_id']} | ${event['amount'] / 100:,.2f}"
            )
        console.print()

    # LSM bilateral offsets
    if lsm_bilateral:
        console.print(f"   [magenta]LSM Bilateral Offset ({len(lsm_bilateral)}):[/magenta]")
        for event in lsm_bilateral:
            console.print(
                f"   • TX {event['tx_id_a'][:8]} ⟷ TX {event['tx_id_b'][:8]}: "
                f"${event['amount'] / 100:,.2f}"
            )
        console.print()

    # LSM cycles
    if lsm_cycles:
        console.print(f"   [magenta]LSM Cycle ({len(lsm_cycles)}):[/magenta]")
        for event in lsm_cycles:
            # Get cycle details
            cycle_details = orch.get_lsm_cycle_details(tick, event["cycle_id"])
            agents_str = " → ".join(cycle_details["agents"])
            console.print(
                f"   • Cycle: {agents_str} | Net: ${event['cycle_value'] / 100:,.2f}"
            )
            for tx_id in event["tx_ids"]:
                tx = orch.get_transaction_details(tx_id)
                console.print(f"     - TX {tx_id[:8]}: ${tx['amount'] / 100:,.2f}")
        console.print()
```

### Task 2.3: Agent Queue Details (Nested Display)

**Add Function**:
```python
def log_agent_queues_detailed(
    orch: Orchestrator,
    agent_id: str,
    balance: int,
    balance_change: int,
    quiet: bool = False
):
    """Log agent state with detailed queue contents (verbose mode).

    Shows:
    - Agent balance with color coding (overdraft = red, negative change = yellow)
    - Queue 1 (internal) contents with transaction details
    - Queue 2 (RTGS) contents for this agent's transactions
    - Total queued value
    - Credit utilization percentage
    - Collateral posted (if any)

    Args:
        orch: Orchestrator instance
        agent_id: Agent identifier
        balance: Current balance in cents
        balance_change: Balance change since last tick
        quiet: Suppress output if True

    Example Output:
        BANK_A: $5,000.00 (+$500.00) | Credit: 25% used
           Queue 1 (3 transactions, $2,500.00 total):
           • TX a1b2c3d4 → BANK_B: $1,000.00 | P:8 | ⏰ Tick 50
           • TX e5f6g7h8 → BANK_C: $750.00 | P:5 | ⏰ Tick 55
           • TX i9j0k1l2 → BANK_D: $750.00 | P:3 | ⏰ Tick 60

           Queue 2 - RTGS (1 transaction, $500.00):
           • TX m3n4o5p6 → BANK_E: $500.00 | P:7 | ⏰ Tick 45

           Collateral Posted: $1,000,000.00
    """
    if quiet:
        return

    # Format balance with color coding
    balance_str = f"${balance / 100:,.2f}"
    if balance < 0:
        balance_str = f"[red]{balance_str} (overdraft)[/red]"
    elif balance_change < 0:
        balance_str = f"[yellow]{balance_str}[/yellow]"
    else:
        balance_str = f"[green]{balance_str}[/green]"

    # Balance change indicator
    change_str = ""
    if balance_change != 0:
        sign = "+" if balance_change > 0 else ""
        change_str = f" ({sign}${balance_change / 100:,.2f})"

    # Credit utilization
    credit_limit = orch.get_agent_credit_limit(agent_id)
    if credit_limit > 0:
        # Utilization = (credit_limit - balance) / credit_limit
        used = max(0, credit_limit - balance)
        utilization_pct = (used / credit_limit) * 100

        if utilization_pct > 80:
            util_str = f"[red]{utilization_pct:.0f}% used[/red]"
        elif utilization_pct > 50:
            util_str = f"[yellow]{utilization_pct:.0f}% used[/yellow]"
        else:
            util_str = f"[green]{utilization_pct:.0f}% used[/green]"

        credit_str = f" | Credit: {util_str}"
    else:
        credit_str = ""

    console.print(f"  {agent_id}: {balance_str}{change_str}{credit_str}")

    # Queue 1 (internal)
    queue1_contents = orch.get_agent_queue1_contents(agent_id)
    if queue1_contents:
        total_value = sum(
            orch.get_transaction_details(tx_id)["remaining_amount"]
            for tx_id in queue1_contents
        )
        console.print(
            f"     Queue 1 ({len(queue1_contents)} transactions, "
            f"${total_value / 100:,.2f} total):"
        )
        for tx_id in queue1_contents:
            tx = orch.get_transaction_details(tx_id)
            priority_str = f"P:{tx['priority']}"
            console.print(
                f"     • TX {tx_id[:8]} → {tx['receiver_id']}: "
                f"${tx['remaining_amount'] / 100:,.2f} | {priority_str} | "
                f"⏰ Tick {tx['deadline_tick']}"
            )
        console.print()

    # Queue 2 (RTGS) - filter for this agent's transactions
    rtgs_queue = orch.get_rtgs_queue_contents()
    agent_rtgs_txs = [
        tx_id for tx_id in rtgs_queue
        if orch.get_transaction_details(tx_id)["sender_id"] == agent_id
    ]

    if agent_rtgs_txs:
        total_value = sum(
            orch.get_transaction_details(tx_id)["remaining_amount"]
            for tx_id in agent_rtgs_txs
        )
        console.print(
            f"     Queue 2 - RTGS ({len(agent_rtgs_txs)} transactions, "
            f"${total_value / 100:,.2f}):"
        )
        for tx_id in agent_rtgs_txs:
            tx = orch.get_transaction_details(tx_id)
            console.print(
                f"     • TX {tx_id[:8]} → {tx['receiver_id']}: "
                f"${tx['remaining_amount'] / 100:,.2f} | P:{tx['priority']} | "
                f"⏰ Tick {tx['deadline_tick']}"
            )
        console.print()

    # Collateral
    collateral = orch.get_agent_collateral_posted(agent_id)
    if collateral and collateral > 0:
        console.print(f"     Collateral Posted: ${collateral / 100:,.2f}")
        console.print()
```

### Task 2.4: Policy Decision Tracking

**Add Function**:
```python
def log_policy_decisions(events: List[Dict], quiet: bool = False):
    """Log policy decisions made this tick (verbose mode).

    Shows submit/hold/drop/split decisions with reasoning.

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🎯 Policy Decisions (5):
           BANK_A:
           • SUBMIT: TX a1b2c3d4 → BANK_B ($1,000.00) - Sufficient liquidity
           • HOLD: TX e5f6g7h8 → BANK_C ($5,000.00) - Preserving buffer

           BANK_B:
           • SPLIT: TX i9j0k1l2 → 3 children - Amount exceeds threshold
           • DROP: TX m3n4o5p6 → BANK_D - Past deadline
    """
    if quiet:
        return

    policy_events = [
        e for e in events
        if e["type"] in ["PolicySubmit", "PolicyHold", "PolicyDrop", "PolicySplit"]
    ]

    if not policy_events:
        return

    console.print(f"🎯 [blue]Policy Decisions ({len(policy_events)}):[/blue]")

    # Group by agent
    by_agent = {}
    for event in policy_events:
        agent_id = event["agent_id"]
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append(event)

    for agent_id, agent_events in by_agent.items():
        console.print(f"   {agent_id}:")
        for event in agent_events:
            if event["type"] == "PolicySubmit":
                console.print(
                    f"   • [green]SUBMIT[/green]: TX {event['tx_id'][:8]}"
                )
            elif event["type"] == "PolicyHold":
                console.print(
                    f"   • [yellow]HOLD[/yellow]: TX {event['tx_id'][:8]} - "
                    f"{event['reason']}"
                )
            elif event["type"] == "PolicyDrop":
                console.print(
                    f"   • [red]DROP[/red]: TX {event['tx_id'][:8]} - "
                    f"{event['reason']}"
                )
            elif event["type"] == "PolicySplit":
                console.print(
                    f"   • [magenta]SPLIT[/magenta]: TX {event['tx_id'][:8]} → "
                    f"{event['num_splits']} children"
                )
        console.print()
```

### Task 2.5: Collateral Activity

**Add Function**:
```python
def log_collateral_activity(events: List[Dict], quiet: bool = False):
    """Log collateral post/withdraw events (verbose mode).

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        💰 Collateral Activity (2):
           BANK_A:
           • POSTED: $1,000,000.00 - Strategic decision | New Total: $5,000,000.00

           BANK_B:
           • WITHDRAWN: $500,000.00 - Reduce opportunity cost | New Total: $2,500,000.00
    """
    if quiet:
        return

    collateral_events = [
        e for e in events
        if e["type"] in ["CollateralPost", "CollateralWithdraw"]
    ]

    if not collateral_events:
        return

    console.print(f"💰 [yellow]Collateral Activity ({len(collateral_events)}):[/yellow]")

    # Group by agent
    by_agent = {}
    for event in collateral_events:
        agent_id = event["agent_id"]
        if agent_id not in by_agent:
            by_agent[agent_id] = []
        by_agent[agent_id].append(event)

    for agent_id, agent_events in by_agent.items():
        console.print(f"   {agent_id}:")
        for event in agent_events:
            if event["type"] == "CollateralPost":
                console.print(
                    f"   • [green]POSTED[/green]: ${event['amount'] / 100:,.2f} - "
                    f"{event['reason']} | New Total: ${event['new_total'] / 100:,.2f}"
                )
            else:
                console.print(
                    f"   • [yellow]WITHDRAWN[/yellow]: ${event['amount'] / 100:,.2f} - "
                    f"{event['reason']} | New Total: ${event['new_total'] / 100:,.2f}"
                )
        console.print()
```

### Task 2.6: Cost Breakdown Display

**Add Function**:
```python
def log_cost_breakdown(orch: Orchestrator, agent_ids: List[str], quiet: bool = False):
    """Log detailed cost breakdown by agent and type (verbose mode).

    Shows costs accrued this tick broken down by:
    - Overdraft cost (borrowing fees)
    - Delay penalty (time-based for unsettled transactions)
    - Split fee (cost of splitting transactions)

    Args:
        orch: Orchestrator instance
        agent_ids: List of agent identifiers
        quiet: Suppress output if True

    Example Output:
        💰 Costs Accrued This Tick: $125.50

           BANK_A: $75.25
           • Overdraft: $50.00
           • Delay: $25.00
           • Split: $0.25

           BANK_B: $50.25
           • Overdraft: $0.00
           • Delay: $50.00
           • Split: $0.25
    """
    if quiet:
        return

    total_cost = 0
    agent_costs = []

    for agent_id in agent_ids:
        costs = orch.get_agent_cost_breakdown(agent_id)
        if costs and costs["total"] > 0:
            agent_costs.append((agent_id, costs))
            total_cost += costs["total"]

    if total_cost == 0:
        return

    console.print(f"💰 [yellow]Costs Accrued This Tick: ${total_cost / 100:,.2f}[/yellow]")
    console.print()

    for agent_id, costs in agent_costs:
        console.print(f"   {agent_id}: ${costs['total'] / 100:,.2f}")
        console.print(f"   • Overdraft: ${costs['overdraft_cost'] / 100:,.2f}")
        console.print(f"   • Delay: ${costs['delay_penalty'] / 100:,.2f}")
        console.print(f"   • Split: ${costs['split_fee'] / 100:,.2f}")
        console.print()
```

### Task 2.7: LSM Cycle Visualization

**Add Function**:
```python
def log_lsm_cycle_visualization(events: List[Dict], quiet: bool = False):
    """Visualize LSM cycles showing circular payment chains (verbose mode).

    Args:
        events: List of events from get_tick_events()
        quiet: Suppress output if True

    Example Output:
        🔄 LSM Cycles (2):

           Cycle 1 (Bilateral):
           BANK_A ⇄ BANK_B
           • A→B: TX a1b2c3d4 ($1,000.00)
           • B→A: TX e5f6g7h8 ($750.00)
           Net Settlement: $250.00 (A pays B)

           Cycle 2 (Multilateral - 3 agents):
           BANK_A → BANK_B → BANK_C → BANK_A
           • A→B: TX i9j0k1l2 ($500.00)
           • B→C: TX m3n4o5p6 ($450.00)
           • C→A: TX q7r8s9t0 ($300.00)
           Net Settlement: $50.00 (minimal net transfers)
    """
    if quiet:
        return

    lsm_bilateral = [e for e in events if e["type"] == "LsmBilateralOffset"]
    lsm_cycles = [e for e in events if e["type"] == "LsmCycleSettlement"]

    total_cycles = len(lsm_bilateral) + len(lsm_cycles)
    if total_cycles == 0:
        return

    console.print(f"🔄 [magenta]LSM Cycles ({total_cycles}):[/magenta]")
    console.print()

    cycle_num = 1

    # Bilateral offsets
    for event in lsm_bilateral:
        console.print(f"   Cycle {cycle_num} (Bilateral):")
        # Extract agent IDs from transaction details
        # Show bidirectional arrow: A ⇄ B
        console.print(f"   {event['agent_a']} ⇄ {event['agent_b']}")
        console.print(f"   • {event['agent_a']}→{event['agent_b']}: TX {event['tx_id_a'][:8]} (${event['amount_a'] / 100:,.2f})")
        console.print(f"   • {event['agent_b']}→{event['agent_a']}: TX {event['tx_id_b'][:8]} (${event['amount_b'] / 100:,.2f})")
        net = abs(event['amount_a'] - event['amount_b'])
        direction = event['agent_a'] if event['amount_a'] > event['amount_b'] else event['agent_b']
        console.print(f"   Net Settlement: ${net / 100:,.2f} ({direction} pays more)")
        console.print()
        cycle_num += 1

    # Multilateral cycles
    for event in lsm_cycles:
        num_agents = len(event['agent_ids'])
        console.print(f"   Cycle {cycle_num} (Multilateral - {num_agents} agents):")

        # Show cycle: A → B → C → A
        cycle_str = " → ".join(event['agent_ids']) + f" → {event['agent_ids'][0]}"
        console.print(f"   {cycle_str}")

        # Show each transaction in cycle
        for i, tx_id in enumerate(event['tx_ids']):
            sender = event['agent_ids'][i]
            receiver = event['agent_ids'][(i + 1) % num_agents]
            amount = event['amounts'][i]
            console.print(f"   • {sender}→{receiver}: TX {tx_id[:8]} (${amount / 100:,.2f})")

        console.print(f"   Net Settlement: ${event['cycle_value'] / 100:,.2f} (minimal net transfers)")
        console.print()
        cycle_num += 1
```

### Task 2.8: End-of-Day Statistics

**Add Function**:
```python
def log_end_of_day_statistics(
    day: int,
    total_arrivals: int,
    total_settlements: int,
    total_lsm_releases: int,
    total_costs: int,
    agent_stats: List[Dict],
    quiet: bool = False
):
    """Log comprehensive end-of-day statistics (verbose mode).

    Args:
        day: Day number (0-indexed)
        total_arrivals: Total arrivals for the day
        total_settlements: Total settlements for the day
        total_lsm_releases: Total LSM releases for the day
        total_costs: Total costs accrued for the day
        agent_stats: Per-agent statistics
        quiet: Suppress output if True

    Example Output:
        ════════════════════════════════════════════════════════════════
                             END OF DAY 0 SUMMARY
        ════════════════════════════════════════════════════════════════

        📊 SYSTEM-WIDE METRICS:
        • Total Transactions: 10,000
        • Settled: 9,500 (95.0%)
        • Unsettled: 500 (5.0%)
        • LSM Releases: 1,200 (12.6% of settlements)
        • Settlement Rate: 95.0%
        • Total Value Processed: $50,000,000.00

        💰 COSTS:
        • Total: $12,500.00
        • Overdraft: $8,000.00 (64.0%)
        • Delay: $4,000.00 (32.0%)
        • Split: $500.00 (4.0%)

        👥 AGENT PERFORMANCE:

        BANK_A:
        • Final Balance: $5,000,000.00
        • Credit Utilization: 25%
        • Sent: 2,500 ($12,500,000.00) | Received: 2,400 ($12,000,000.00)
        • Settled: 2,450/2,500 (98.0%)
        • Queue 1: 50 transactions ($500,000.00)
        • Queue 2: 0 transactions
        • Peak Queue Size: 120 (at tick 45)
        • Total Costs: $3,200.00

        BANK_B:
        • Final Balance: $3,500,000.00
        • Credit Utilization: 45%
        • Sent: 2,400 ($11,500,000.00) | Received: 2,450 ($11,800,000.00)
        • Settled: 2,350/2,400 (97.9%)
        • Queue 1: 30 transactions ($300,000.00)
        • Queue 2: 20 transactions ($200,000.00)
        • Peak Queue Size: 150 (at tick 52)
        • Total Costs: $4,100.00

        ⚡ PERFORMANCE:
        • Ticks per Second: 1,234.5
        • Total Simulation Time: 0.081s

        ════════════════════════════════════════════════════════════════
    """
    if quiet:
        return

    console.print()
    console.print("═" * 64)
    console.print(f"[bold cyan]{'END OF DAY ' + str(day) + ' SUMMARY':^64}[/bold cyan]")
    console.print("═" * 64)
    console.print()

    # System-wide metrics
    settlement_rate = (total_settlements / total_arrivals * 100) if total_arrivals > 0 else 0
    unsettled = total_arrivals - total_settlements
    lsm_pct = (total_lsm_releases / total_settlements * 100) if total_settlements > 0 else 0

    console.print("[bold]📊 SYSTEM-WIDE METRICS:[/bold]")
    console.print(f"• Total Transactions: {total_arrivals:,}")
    console.print(f"• Settled: {total_settlements:,} ({settlement_rate:.1f}%)")
    console.print(f"• Unsettled: {unsettled:,} ({(unsettled/total_arrivals*100):.1f}%)")
    console.print(f"• LSM Releases: {total_lsm_releases:,} ({lsm_pct:.1f}% of settlements)")
    console.print(f"• Settlement Rate: {settlement_rate:.1f}%")
    console.print()

    # Costs
    console.print("[bold]💰 COSTS:[/bold]")
    console.print(f"• Total: ${total_costs / 100:,.2f}")
    # Cost breakdown would come from summing agent costs
    console.print()

    # Agent performance
    console.print("[bold]👥 AGENT PERFORMANCE:[/bold]")
    console.print()

    for agent in agent_stats:
        console.print(f"[bold]{agent['id']}:[/bold]")
        console.print(f"• Final Balance: ${agent['final_balance'] / 100:,.2f}")
        console.print(f"• Credit Utilization: {agent['credit_utilization']:.0f}%")
        console.print(
            f"• Sent: {agent['sent_count']:,} (${agent['sent_value'] / 100:,.2f}) | "
            f"Received: {agent['received_count']:,} (${agent['received_value'] / 100:,.2f})"
        )
        console.print(
            f"• Settled: {agent['settled_count']}/{agent['sent_count']} "
            f"({agent['settlement_rate']:.1f}%)"
        )
        console.print(
            f"• Queue 1: {agent['queue1_size']} transactions "
            f"(${agent['queue1_value'] / 100:,.2f})"
        )
        console.print(
            f"• Queue 2: {agent['queue2_size']} transactions "
            f"(${agent['queue2_value'] / 100:,.2f})"
        )
        console.print(f"• Peak Queue Size: {agent['peak_queue']} (at tick {agent['peak_tick']})")
        console.print(f"• Total Costs: ${agent['total_costs'] / 100:,.2f}")
        console.print()

    console.print("═" * 64)
    console.print()
```

---

## Phase 3: CLI Integration

### Task 3.1: Enhanced Verbose Tick Loop

**File**: `api/payment_simulator/cli/commands/run.py`

**Replace Verbose Loop** (lines 226-284):

```python
# Verbose mode: show detailed events in real-time
log_info(f"Running {total_ticks} ticks (verbose mode)...", True)

# Get agent IDs for state tracking
agent_ids = orch.get_agent_ids()

# Track previous balances for change detection
prev_balances = {agent_id: orch.get_agent_balance(agent_id) for agent_id in agent_ids}

# Track daily statistics
daily_stats = {
    "arrivals": 0,
    "settlements": 0,
    "lsm_releases": 0,
    "costs": 0,
}

tick_results = []
sim_start = time.time()

for tick_num in range(total_ticks):
    # ═══════════════════════════════════════════════════════════
    # TICK HEADER
    # ═══════════════════════════════════════════════════════════
    log_tick_start(tick_num)

    # Execute tick
    result = orch.tick()
    tick_results.append(result)

    # Update daily stats
    daily_stats["arrivals"] += result["num_arrivals"]
    daily_stats["settlements"] += result["num_settlements"]
    daily_stats["lsm_releases"] += result["num_lsm_releases"]
    daily_stats["costs"] += result["total_cost"]

    # ═══════════════════════════════════════════════════════════
    # SECTION 1: ARRIVALS (detailed)
    # ═══════════════════════════════════════════════════════════
    if result["num_arrivals"] > 0:
        events = orch.get_tick_events(tick_num)
        log_transaction_arrivals(orch, events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 2: POLICY DECISIONS
    # ═══════════════════════════════════════════════════════════
    events = orch.get_tick_events(tick_num)
    log_policy_decisions(events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 3: SETTLEMENTS (detailed with mechanisms)
    # ═══════════════════════════════════════════════════════════
    if result["num_settlements"] > 0:
        log_settlement_details(orch, events, tick_num)

    # ═══════════════════════════════════════════════════════════
    # SECTION 4: LSM CYCLE VISUALIZATION
    # ═══════════════════════════════════════════════════════════
    if result["num_lsm_releases"] > 0:
        log_lsm_cycle_visualization(events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 5: COLLATERAL ACTIVITY
    # ═══════════════════════════════════════════════════════════
    log_collateral_activity(events)

    # ═══════════════════════════════════════════════════════════
    # SECTION 6: AGENT STATES (detailed queues)
    # ═══════════════════════════════════════════════════════════
    console.print("[bold]Agent States:[/bold]")
    for agent_id in agent_ids:
        current_balance = orch.get_agent_balance(agent_id)
        balance_change = current_balance - prev_balances[agent_id]

        # Only show agents with activity or queued transactions
        queue1_size = orch.get_queue1_size(agent_id)
        rtgs_queue = orch.get_rtgs_queue_contents()
        has_rtgs = any(
            orch.get_transaction_details(tx_id)["sender_id"] == agent_id
            for tx_id in rtgs_queue
        )

        if balance_change != 0 or queue1_size > 0 or has_rtgs:
            log_agent_queues_detailed(orch, agent_id, current_balance, balance_change)

        prev_balances[agent_id] = current_balance

    # ═══════════════════════════════════════════════════════════
    # SECTION 7: COST BREAKDOWN
    # ═══════════════════════════════════════════════════════════
    if result["total_cost"] > 0:
        log_cost_breakdown(orch, agent_ids)

    # ═══════════════════════════════════════════════════════════
    # SECTION 8: TICK SUMMARY
    # ═══════════════════════════════════════════════════════════
    total_queued = sum(orch.get_queue1_size(aid) for aid in agent_ids)
    log_tick_summary(
        result["num_arrivals"],
        result["num_settlements"],
        result["num_lsm_releases"],
        total_queued
    )

    # ═══════════════════════════════════════════════════════════
    # END-OF-DAY PROCESSING
    # ═══════════════════════════════════════════════════════════
    if (tick_num + 1) % ticks_per_day == 0:
        # Calculate day number
        day = tick_num // ticks_per_day

        # Gather agent statistics for day summary
        agent_stats = []
        for agent_id in agent_ids:
            # Query metrics (would need FFI methods for detailed stats)
            stats = {
                "id": agent_id,
                "final_balance": orch.get_agent_balance(agent_id),
                "credit_utilization": 0,  # Calculate from credit_limit and balance
                "sent_count": 0,  # Would need tracking
                "sent_value": 0,
                "received_count": 0,
                "received_value": 0,
                "settled_count": 0,
                "settlement_rate": 0,
                "queue1_size": orch.get_queue1_size(agent_id),
                "queue1_value": 0,  # Sum of transaction amounts
                "queue2_size": 0,  # Count of agent's txs in RTGS queue
                "queue2_value": 0,
                "peak_queue": 0,  # Would need tracking
                "peak_tick": 0,
                "total_costs": 0,  # Would need cumulative tracking
            }
            agent_stats.append(stats)

        # Display end-of-day summary
        log_end_of_day_statistics(
            day=day,
            total_arrivals=daily_stats["arrivals"],
            total_settlements=daily_stats["settlements"],
            total_lsm_releases=daily_stats["lsm_releases"],
            total_costs=daily_stats["costs"],
            agent_stats=agent_stats,
        )

        # Reset daily stats
        daily_stats = {
            "arrivals": 0,
            "settlements": 0,
            "lsm_releases": 0,
            "costs": 0,
        }

sim_duration = time.time() - sim_start
ticks_per_second = total_ticks / sim_duration if sim_duration > 0 else 0

log_success(
    f"\nSimulation complete: {total_ticks} ticks in {sim_duration:.2f}s "
    f"({ticks_per_second:.1f} ticks/s)",
    False
)

# ... (rest of final output remains the same)
```

### Task 3.2: Additional FFI Methods for Statistics

For end-of-day statistics, we need additional FFI methods:

```rust
// In backend/src/ffi/orchestrator.rs

/// Get agent transaction statistics
fn get_agent_transaction_stats(&self, agent_id: &str) -> PyResult<Py<PyDict>> {
    // Returns:
    // - sent_count
    // - sent_value
    // - received_count
    // - received_value
    // - settled_count
    // - peak_queue_size
    // - peak_queue_tick
}

/// Get cumulative agent costs for current day
fn get_agent_cumulative_costs(&self, agent_id: &str) -> PyResult<Py<PyDict>> {
    // Returns cost breakdown accumulated since start of day
}
```

---

## Testing Strategy

### Unit Tests (Python)

**File**: `api/tests/cli/test_verbose_output.py`

```python
def test_log_transaction_arrivals_formats_correctly():
    """Test transaction arrival formatting."""
    # Mock orchestrator with test data
    # Call log_transaction_arrivals
    # Verify output contains expected elements

def test_log_settlement_details_categorizes_mechanisms():
    """Test settlement categorization by mechanism."""
    # Mock events with different settlement types
    # Verify RTGS immediate, queued, LSM categories

def test_log_agent_queues_shows_nested_contents():
    """Test nested queue display."""
    # Mock agent with Queue 1 and Queue 2 contents
    # Verify transaction details shown

def test_log_lsm_cycle_visualization_formats_cycles():
    """Test LSM cycle arrow visualization."""
    # Mock bilateral and multilateral cycles
    # Verify cycle visualization format

def test_log_end_of_day_statistics_shows_all_sections():
    """Test end-of-day summary completeness."""
    # Mock day statistics
    # Verify all sections present
```

### Integration Tests (Python + FFI)

**File**: `api/tests/integration/test_verbose_cli_integration.py`

```python
def test_verbose_mode_shows_transaction_details():
    """Verify verbose mode displays transaction-level details."""
    # Create orchestrator
    # Run with verbose=True
    # Capture output
    # Verify transaction IDs, amounts, etc. present

def test_verbose_mode_tracks_settlement_mechanisms():
    """Verify settlement mechanism tracking."""
    # Create scenario with RTGS and LSM settlements
    # Run verbose mode
    # Verify both mechanisms shown

def test_verbose_mode_end_of_day_summary():
    """Verify end-of-day summary appears."""
    # Run multi-day simulation
    # Verify summary appears at day boundaries
```

### FFI Tests (Rust)

**File**: `backend/tests/test_verbose_cli_ffi.rs`

```rust
#[test]
fn test_get_tick_events_returns_all_events() {
    // Create orchestrator, run ticks
    // Query events for specific tick
    // Verify all event types present
}

#[test]
fn test_get_transaction_details_returns_full_data() {
    // Submit transaction
    // Query details
    // Verify all fields present
}

#[test]
fn test_get_rtgs_queue_contents_returns_tx_ids() {
    // Queue transactions to RTGS
    // Query queue contents
    // Verify correct transaction IDs
}
```

---

## Implementation Timeline

### Week 1: Phase 1 - Rust FFI Extensions
- **Day 1-2**: Add FFI methods (get_tick_events, get_transaction_details)
- **Day 3**: Add queue and credit queries
- **Day 4**: Add cost breakdown queries
- **Day 5**: Write FFI integration tests

### Week 2: Phase 2 - Python Output Helpers
- **Day 1**: Arrival and settlement detail functions
- **Day 2**: Queue and agent state detailed display
- **Day 3**: Policy decisions and collateral activity
- **Day 4**: Cost breakdown and LSM visualization
- **Day 5**: End-of-day statistics function

### Week 3: Phase 3 - CLI Integration
- **Day 1-2**: Refactor verbose tick loop in run.py
- **Day 3**: Wire up all display functions
- **Day 4**: Add end-of-day processing
- **Day 5**: Integration testing and polish

### Week 4: Testing and Documentation
- **Day 1-2**: Write comprehensive test suite
- **Day 3**: Performance testing (ensure verbose mode doesn't kill perf)
- **Day 4**: Documentation and examples
- **Day 5**: User testing and refinement

---

## Success Criteria

### Functional Requirements
✅ Every transaction arrival shown with full details
✅ Every settlement shown with mechanism (RTGS/LSM)
✅ Queue 1 and Queue 2 contents visible per agent
✅ Collateral post/withdraw events shown
✅ Policy decisions shown with reasoning
✅ Balance utilization percentage displayed
✅ Cost breakdown by type (overdraft, delay, split)
✅ LSM cycles visualized with agent chains
✅ End-of-day comprehensive statistics
✅ Color-coded priorities and alerts

### Non-Functional Requirements
✅ Performance: Verbose mode adds <10% overhead
✅ Readability: Clear visual hierarchy and formatting
✅ Testability: 100% test coverage for new functions
✅ Maintainability: Well-documented, follows project patterns

---

## Example Output Preview

```
═══ Tick 42 ═══

📥 3 transaction(s) arrived:
   • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00 | P:8 HIGH | ⏰ Tick 50
   • TX e5f6g7h8: BANK_B → BANK_C | $250.50 | P:5 MED | ⏰ Tick 55
   • TX i9j0k1l2: BANK_C → BANK_A | $5,000.00 | P:3 LOW | ⏰ Tick 60

🎯 Policy Decisions (2):
   BANK_A:
   • SUBMIT: TX a1b2c3d4 - Sufficient liquidity

   BANK_B:
   • HOLD: TX e5f6g7h8 - Preserving buffer below target

✅ 2 transaction(s) settled:

   RTGS Immediate (1):
   • TX a1b2c3d4: BANK_A → BANK_B | $1,000.00

   LSM Bilateral Offset (1):
   • TX m3n4o5p6 ⟷ TX q7r8s9t0: BANK_A ⇄ BANK_C | $500.00

Agent States:
  BANK_A: $4,500.00 (-$500.00) | Credit: 10% used
     Queue 1 (2 transactions, $1,250.00 total):
     • TX uvw12345 → BANK_D: $750.00 | P:5 | ⏰ Tick 48
     • TX xyz67890 → BANK_B: $500.00 | P:3 | ⏰ Tick 52

  BANK_B: $6,000.00 (+$1,000.00) | Credit: 5% used
     Queue 1 (1 transaction, $250.50):
     • TX e5f6g7h8 → BANK_C: $250.50 | P:5 | ⏰ Tick 55

💰 Costs Accrued This Tick: $25.50

   BANK_A: $15.25
   • Overdraft: $10.00
   • Delay: $5.00
   • Split: $0.25

  Summary: 3 in | 2 settled | 5 queued

════════════════════════════════════════════════════════════════
                          END OF DAY 0 SUMMARY
════════════════════════════════════════════════════════════════

📊 SYSTEM-WIDE METRICS:
• Total Transactions: 10,000
• Settled: 9,500 (95.0%)
• Unsettled: 500 (5.0%)
• LSM Releases: 1,200 (12.6% of settlements)

💰 COSTS:
• Total: $12,500.00

👥 AGENT PERFORMANCE:

BANK_A:
• Final Balance: $5,000,000.00
• Credit Utilization: 25%
• Sent: 2,500 ($12,500,000.00) | Received: 2,400 ($12,000,000.00)
• Settled: 2,450/2,500 (98.0%)
• Queue 1: 50 transactions ($500,000.00)
• Peak Queue Size: 120 (at tick 45)
• Total Costs: $3,200.00

════════════════════════════════════════════════════════════════
```

---

## Additional Features for Future Consideration

1. **Interactive Mode**: Pause/resume simulation, inspect specific transactions
2. **Filtering**: Show only specific agents or transaction types
3. **Threshold Alerts**: Highlight when queue sizes exceed thresholds
4. **Deadline Warnings**: Alert when transactions are X ticks from deadline
5. **Gridlock Detection**: Visual indicator when circular waiting detected
6. **WebSocket Streaming**: Stream verbose output to web UI
7. **Log Levels**: --verbose=1 (summary), --verbose=2 (detailed), --verbose=3 (debug)
8. **Export**: Save verbose output to HTML or Markdown for reports

---

## Dependencies

### Rust Crates
- No new dependencies (uses existing `serde`, `pyo3`)

### Python Packages
- `rich` (already used) - Enhanced terminal formatting
- No new dependencies

---

## Risk Analysis

### Performance Risk (MEDIUM)
**Issue**: Querying event log and transaction details on every tick could slow simulation
**Mitigation**:
- Benchmark verbose mode overhead
- Cache transaction details per tick if needed
- Consider batching FFI calls

### Complexity Risk (MEDIUM)
**Issue**: Verbose mode adds significant code complexity
**Mitigation**:
- Strict separation of concerns (3-layer architecture)
- Comprehensive test coverage
- Clear documentation

### Maintenance Risk (LOW)
**Issue**: Changes to event system break verbose output
**Mitigation**:
- Use well-defined Event enum from Rust
- Integration tests catch breakages early

---

## Documentation Updates Required

1. **README.md**: Add verbose mode examples
2. **CLI User Guide**: New section on verbose mode
3. **API Documentation**: Document new FFI methods
4. **CLAUDE.md**: Add verbose mode troubleshooting tips

---

## Conclusion

This plan transforms the CLI verbose mode from a basic summary tool into a comprehensive real-time monitoring system. By exposing granular event data through FFI and building a rich display layer in Python, we enable users to:

- **Understand exactly what's happening** at each tick
- **Debug policies and behaviors** with full visibility
- **Analyze settlement patterns** and LSM effectiveness
- **Monitor costs and utilization** in real-time
- **Review daily performance** with comprehensive statistics

The three-phase approach (Rust FFI → Python helpers → CLI integration) ensures clean separation of concerns, testability, and maintainability.
