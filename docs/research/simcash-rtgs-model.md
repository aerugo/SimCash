# SimCash RTGS Model

## Overview

SimCash is a high-performance payment simulator modeling Real-Time Gross Settlement (RTGS) systems. It implements a sophisticated multi-agent payment system where banks (agents) settle transactions through a central bank infrastructure with liquidity constraints, queuing mechanisms, and liquidity-saving mechanisms (LSM).

This document provides a comprehensive technical description of SimCash's RTGS model, covering the architecture, settlement mechanisms, cost model, and behavioral dynamics.

---

## System Architecture

### Hybrid Rust-Python Design

SimCash uses a hybrid architecture:

- **Rust Backend** (`/backend`): Performance-critical simulation engine
  - Tick loop and time management
  - Settlement engine (RTGS + LSM)
  - Transaction processing
  - Deterministic RNG
  - All state management

- **Python API** (`/api`): Developer ergonomics
  - REST/WebSocket endpoints
  - Configuration validation (Pydantic)
  - CLI interface
  - Test harness

- **FFI Boundary** (PyO3): Minimal, safe interface between layers

### Core Components

```
┌─────────────────────────────────────────────────────┐
│              Orchestrator Engine                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │
│  │   Arrivals  │  │   Policies  │  │  Settlement │ │
│  │  Generator  │  │   Engine    │  │   Engine    │ │
│  └─────────────┘  └─────────────┘  └─────────────┘ │
│                           │                         │
│  ┌─────────────────────────────────────────────┐   │
│  │              Simulation State                │   │
│  │  ┌─────────┐  ┌─────────────┐  ┌─────────┐  │   │
│  │  │ Agents  │  │ Transactions │  │ Queues  │  │   │
│  │  └─────────┘  └─────────────┘  └─────────┘  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Time Model

### Tick-Based Discrete Time

SimCash uses discrete time steps called **ticks**:

- **Tick**: Smallest discrete time unit (configurable, e.g., 1 tick ≈ 5-10 real-world minutes)
- **Day**: Collection of ticks (configurable, e.g., 100 ticks = 1 business day)
- **Episode**: Complete simulation run spanning multiple days

### Tick Loop Sequence

Each tick executes the following sequence (from `backend/src/orchestrator/engine.rs`):

```
For each tick t:
1. Generate arrivals (Poisson sampling)
2. Evaluate policies (Queue 1 → settlement decisions)
3. Execute RTGS settlements (immediate if liquidity available)
4. Process RTGS queue (Queue 2 retry)
5. Run LSM coordinator (find bilateral/multilateral offsets)
6. Accrue costs (liquidity, delay, collateral)
7. Drop expired transactions (past deadline)
8. Log events
9. Advance time
10. Handle end-of-day if needed
```

### End-of-Day Processing

At day boundaries:
- Outstanding Queue 2 transactions incur EOD penalties
- Agent balances are reset to opening positions (configurable)
- Daily statistics are collected
- Bilateral/multilateral limits are reset

---

## Agent Model

### Agent Definition

Each agent (bank) is characterized by:

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | String | Unique identifier (e.g., "BANK_A") |
| `balance` | i64 | Current settlement account balance (cents) |
| `opening_balance` | i64 | Start-of-day balance (cents) |
| `credit_limit` | i64 | Legacy unsecured overdraft cap (cents) |
| `unsecured_cap` | i64 | Maximum unsecured overdraft (cents) |
| `posted_collateral` | i64 | Collateral pledged for secured credit (cents) |
| `outgoing_queue` | Vec | Queue 1: Internal payment queue |

### Liquidity Calculation

Available liquidity for settlement:

```rust
available_liquidity = balance + allowed_overdraft_limit()

allowed_overdraft_limit = credit_limit + unsecured_cap + posted_collateral
```

A transaction can settle if:
```rust
sender.balance - amount >= -(sender.allowed_overdraft_limit() as i64)
```

### Two-Queue Architecture

SimCash implements a **two-queue model**:

#### Queue 1 (Internal Bank Queue)
- Per-agent internal queue for policy decisions
- Transactions wait here until agent's policy decides to submit
- Agent controls release timing via policy evaluation
- Supports priority ordering, deadline awareness, liquidity awareness

#### Queue 2 (Central RTGS Queue)
- Central bank queue for liquidity-based retry
- Transactions enter when submitted but insufficient liquidity
- Mechanical retry: checks liquidity availability each tick
- LSM operates on this queue (bilateral/multilateral offsets)

```
┌──────────────┐     Submit      ┌──────────────┐
│   Queue 1    │  ───────────►   │   Queue 2    │
│  (Internal)  │                 │   (Central)  │
│              │                 │              │
│ Policy-based │                 │ Liquidity-   │
│  decisions   │                 │ based retry  │
└──────────────┘                 └──────────────┘
       │                                │
       │ Hold/Drop                      │ LSM
       ▼                                ▼
   Remains in                    Bilateral/Multilateral
   agent queue                   Offsetting
```

---

## Transaction Model

### Transaction Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `id` | String | Unique identifier (UUID) |
| `sender_id` | String | Sending agent ID |
| `receiver_id` | String | Receiving agent ID |
| `amount` | i64 | Original payment amount (cents) |
| `remaining_amount` | i64 | Unsettled portion (for partial settlements) |
| `arrival_tick` | usize | When transaction entered system |
| `deadline_tick` | usize | Latest tick for on-time settlement |
| `priority` | u8 | Urgency level (0-10, higher = more urgent) |
| `is_divisible` | bool | Can be split into partial payments |
| `status` | TransactionStatus | Current state |

### Transaction Status Lifecycle

```
        ┌─────────────────────────────────────────────────┐
        │                                                 │
        ▼                                                 │
    [Pending] ───► [Queued] ───► [PartiallySettled] ◄────┘
        │             │                   │
        │             │                   │
        │             ▼                   ▼
        │         [Overdue] ◄─────────────┤
        │             │                   │
        ▼             ▼                   ▼
    [Settled] ◄───────┴───────────────────┘
        │
        ▼
    [Dropped] (deadline expired with unsettled amount)
```

### Priority System

SimCash supports T2-style priority processing:

| Band | Priority Range | Description |
|------|----------------|-------------|
| Urgent | 8-10 | Processed first (e.g., CLS, critical) |
| Normal | 4-7 | Standard processing |
| Low | 0-3 | Best-effort, deferred if needed |

**Priority Escalation**: Transactions can have their priority automatically boosted as deadlines approach, preventing starvation of low-priority payments.

---

## Settlement Engine

### RTGS Settlement (Immediate)

The core RTGS settlement function (`backend/src/settlement/rtgs.rs`):

```rust
pub fn try_settle(
    state: &mut SimulationState,
    tx_id: &str,
    tick: usize,
) -> Result<SettlementResult, SettlementError>
```

Settlement succeeds if:
1. Sender has sufficient available liquidity (balance + overdraft headroom)
2. Transaction is not already fully settled
3. Bilateral/multilateral limits are not exceeded (if configured)

On successful settlement:
- Sender balance decreases by amount
- Receiver balance increases by amount
- Transaction marked as settled
- Event logged for replay

### Queue 2 Processing

When immediate settlement fails, transactions enter Queue 2:

```rust
pub fn process_queue(
    state: &mut SimulationState,
    tick: usize,
) -> QueueProcessResult
```

Queue 2 is processed:
1. **FIFO order** (default) or **Priority order** (T2 mode)
2. Each transaction is re-attempted for settlement
3. Settled transactions are removed from queue
4. Unsettled transactions remain for next tick

### Liquidity-Saving Mechanism (LSM)

SimCash implements T2-compliant LSM with two mechanisms:

#### Bilateral Offsetting

Finds pairs of banks with mutual obligations:

```
Example: A owes B $500k, B owes A $300k
Without LSM: Need $800k total liquidity
With LSM: Net $200k (A→B), settles BOTH transactions
  - A needs $200k to cover net outflow
  - B needs $0 (net inflow)
```

**Algorithm** (`backend/src/settlement/lsm.rs`):
1. Build bilateral payment matrix from queue
2. For each pair (A,B), find sum(A→B) and sum(B→A)
3. If both > 0, offset to settle both directions
4. Settle net direction with reduced liquidity requirement

#### Multilateral Cycle Settlement

Finds payment cycles (A→B→C→A) for simultaneous settlement:

```
Example: A→B ($500k), B→C ($800k), C→A ($700k)
Net positions:
  A: -$500k + $700k = +$200k (net inflow)
  B: +$500k - $800k = -$300k (net outflow, needs $300k)
  C: +$800k - $700k = +$100k (net inflow)

With LSM: If B has $300k available, settles ALL 3 transactions
Total settled value: $2M (not $500k minimum)
```

**T2-Compliant Behavior**:
- Supports **unequal payment values** (partial netting)
- Each payment settles at **full value** or not at all
- Each participant must cover their **net position**
- **Two-phase commit** for atomic all-or-nothing execution

**Two-Phase Settlement Protocol**:
1. **Phase 1 (Feasibility Check)**: Calculate net positions, verify all can be covered
2. **Phase 2 (Atomic Settlement)**: Execute all transfers simultaneously

#### LSM Configuration

```rust
pub struct LsmConfig {
    pub enable_bilateral: bool,        // Enable bilateral offsetting
    pub enable_cycles: bool,           // Enable cycle detection
    pub max_cycle_length: usize,       // Max cycle length (3-5 typical)
    pub max_cycles_per_tick: usize,    // Performance limit
}
```

---

## Cost Model

SimCash implements a comprehensive cost model that captures the economic trade-offs in payment systems.

### Cost Categories

| Cost Type | Rate Parameter | Description |
|-----------|----------------|-------------|
| **Overdraft Cost** | `overdraft_bps_per_tick` | Cost of negative balance (using credit) |
| **Delay Cost** | `delay_cost_per_tick_per_cent` | Cost of queued transactions per tick |
| **Collateral Cost** | `collateral_cost_per_tick_bps` | Opportunity cost of pledged collateral |
| **Deadline Penalty** | `deadline_penalty` | One-time penalty when deadline missed |
| **EOD Penalty** | `eod_penalty_per_transaction` | Penalty for unsettled EOD transactions |
| **Split Friction** | `split_friction_cost` | Cost per transaction split |

### Default Cost Rates

From `backend/src/orchestrator/engine.rs`:

```rust
impl Default for CostRates {
    fn default() -> Self {
        Self {
            overdraft_bps_per_tick: 0.001,        // 1 bp/tick (~10 bp/day)
            delay_cost_per_tick_per_cent: 0.0001, // 0.1 bp/tick
            collateral_cost_per_tick_bps: 0.0002, // ~2 bps annualized
            eod_penalty_per_transaction: 10_000,  // $100 per unsettled tx
            deadline_penalty: 50_000,             // $500 per missed deadline
            split_friction_cost: 1000,            // $10 per split
            overdue_delay_multiplier: 5.0,        // 5x for overdue
        }
    }
}
```

### Cost Calculation Formulas

**Overdraft Cost (per tick)**:
```
cost = max(0, -balance) × overdraft_bps_per_tick / 10000
```

**Delay Cost (per tick, per queued transaction)**:
```
cost = remaining_amount × delay_cost_per_tick_per_cent
if (transaction.is_overdue):
    cost = cost × overdue_delay_multiplier
```

**Collateral Opportunity Cost (per tick)**:
```
cost = posted_collateral × collateral_cost_per_tick_bps / 10000
```

### Cost Breakdown Structure

```rust
pub struct CostBreakdown {
    pub liquidity_cost: i64,      // Overdraft cost
    pub delay_cost: i64,          // Queue delay cost
    pub collateral_cost: i64,     // Collateral opportunity cost
    pub penalty_cost: i64,        // Deadline/EOD penalties
    pub split_friction_cost: i64, // Transaction splitting cost
}
```

---

## Policy System

### Available Policies

SimCash supports configurable agent policies for Queue 1 management:

| Policy | Description |
|--------|-------------|
| **FIFO** | First-In-First-Out (submit oldest first) |
| **LiquidityAware** | Maintain target buffer, submit based on liquidity |
| **PriorityDeadline** | Sort by priority then deadline |
| **Strategic** | Complex multi-factor decision making |
| **Custom** | User-defined via configuration |

### Policy Evaluation

Each tick, policies decide for each Queue 1 transaction:
- **Submit**: Move to settlement (try RTGS, else Queue 2)
- **Hold**: Keep in Queue 1 (wait for better conditions)
- **Drop**: Abandon transaction (too costly to settle)
- **Split**: Divide into smaller transactions (if divisible)

### Policy Configuration Example

```yaml
agent_configs:
  - id: "BANK_A"
    opening_balance: 1_000_000
    credit_limit: 500_000
    policy:
      type: "liquidity_aware"
      target_buffer: 200_000
      urgency_threshold: 5
```

---

## Arrival Model

### Transaction Generation

SimCash generates transactions using configurable arrival patterns:

```rust
pub struct ArrivalConfig {
    pub rate_per_tick: f64,              // Poisson λ (expected arrivals)
    pub amount_distribution: Distribution, // Amount sampling
    pub counterparty_weights: HashMap,    // Receiver preferences
    pub priority_distribution: Distribution,
    pub deadline_offset: DeadlineConfig,
}
```

### Amount Distributions

Supported distributions:
- **Normal**: `Normal { mean, std_dev }`
- **LogNormal**: `LogNormal { mu, sigma }`
- **Uniform**: `Uniform { min, max }`
- **Exponential**: `Exponential { lambda }`
- **Fixed**: `Fixed { value }`

### Counterparty Selection

Agents can specify weighted preferences for receivers:

```yaml
arrival_config:
  counterparty_weights:
    BANK_B: 0.6  # 60% of payments to BANK_B
    BANK_C: 0.3  # 30% to BANK_C
    BANK_D: 0.1  # 10% to BANK_D
```

---

## Event System

### Event Types

SimCash logs all significant state changes for replay and analysis:

| Event Type | Description |
|------------|-------------|
| `Arrival` | New transaction enters system |
| `PolicySubmit` | Policy submits transaction to settlement |
| `PolicyHold` | Policy holds transaction in Queue 1 |
| `PolicyDrop` | Policy drops transaction |
| `PolicySplit` | Policy splits transaction |
| `RtgsImmediateSettlement` | Transaction settled immediately via RTGS |
| `Queue2LiquidityRelease` | Transaction settled from Queue 2 |
| `LsmBilateralOffset` | Bilateral offset settlement |
| `LsmCycleSettlement` | Multilateral cycle settlement |
| `CostAccrual` | Costs accrued for agent |
| `TransactionOverdue` | Transaction passed deadline |
| `CollateralPost` | Agent posted collateral |
| `CollateralWithdraw` | Agent withdrew collateral |

### Deterministic Replay

Events enable perfect replay:
- Same seed + same config = identical output
- Events capture complete state transitions
- `payment-sim replay` reproduces `payment-sim run` exactly

---

## Key Invariants

### Critical System Invariants

1. **Money is ALWAYS i64 (Integer Cents)**
   - No floating-point for money calculations
   - All amounts in smallest currency unit (cents)
   - Prevents rounding errors in financial calculations

2. **Determinism is Sacred**
   - All randomness via seeded xorshift64* RNG
   - Same seed + inputs = identical outputs
   - Enables reproducible research and debugging

3. **Balance Conservation**
   - Sum of all agent balances is constant (within a day)
   - Settlements transfer, not create/destroy money

4. **Queue Validity**
   - All Queue 2 transaction IDs exist in transaction map
   - No orphan references

---

## Comparison to BIS Model

SimCash extends the simplified BIS cash management model significantly:

| Feature | BIS Model | SimCash |
|---------|-----------|---------|
| **Agents** | Single-agent perspective | Multi-agent (N banks) |
| **Time** | 2-3 discrete periods | Configurable ticks/day |
| **Settlement** | Immediate/queued | RTGS + LSM |
| **LSM** | Not modeled | Bilateral + Multilateral |
| **Queues** | Implicit | Two-queue architecture |
| **Costs** | 3 types | 6 types + configurability |
| **Policies** | Not modeled | Pluggable policy system |
| **Priority** | Binary (urgent/normal) | 11 levels (0-10) |
| **Splitting** | No | Yes (divisible payments) |
| **Collateral** | Implicit | Explicit management |
| **Replay** | No | Full deterministic replay |

---

## Configuration Reference

### Minimal Configuration

```yaml
ticks_per_day: 100
num_days: 1
rng_seed: 12345

agent_configs:
  - id: "BANK_A"
    opening_balance: 1_000_000
    credit_limit: 500_000

  - id: "BANK_B"
    opening_balance: 2_000_000
    credit_limit: 0

cost_rates:
  overdraft_bps_per_tick: 0.001
  delay_cost_per_tick_per_cent: 0.0001

lsm_config:
  enable_bilateral: true
  enable_cycles: true
  max_cycle_length: 4
```

### Full Configuration Example

See `/sim_config_example.yaml` for complete configuration with:
- Multiple agents with different policies
- Arrival configurations
- Scenario events
- All cost parameters
- LSM tuning

---

## Performance Characteristics

### Complexity Analysis

| Operation | Complexity | Notes |
|-----------|------------|-------|
| Tick execution | O(A + T + Q) | A=agents, T=arrivals, Q=queue |
| RTGS settlement | O(1) | Per transaction |
| Queue 2 processing | O(Q) | Linear scan |
| Bilateral offsetting | O(Q log Q) | PairIndex optimization |
| Cycle detection (triangles) | O(V + E) | SCC + triangle enumeration |
| Cycle detection (4+) | O(V! / (V-k)!) | DFS fallback (bounded) |

### Target Performance

- 1000+ ticks/second on standard hardware
- Handles 10+ agents with 1000+ transactions/day
- LSM bounded by `max_cycles_per_tick` parameter

---

## References

### Internal Documentation

- `/docs/game_concept_doc.md` - Domain model and rules
- `/docs/research/rtgs-simulation.md` - Detailed RTGS simulation guide
- `/CLAUDE.md` - Project instructions and invariants
- `/backend/CLAUDE.md` - Rust implementation patterns

### External References

- Bech & Garratt (2003). "The intraday liquidity management game"
- TARGET2 documentation (ECB)
- CHAPS Reference Manual (Bank of England)

---

*Document created: November 2025*
*SimCash version: Current development*
