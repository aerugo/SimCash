# Payment Simulator: Grand Plan 2.0
## From Foundation to Full Vision

**Document Version**: 2.7
**Date**: November 27, 2025
**Status**: Foundation + Integration + Policy DSL + Priority System + TARGET2 LSM Alignment Complete → LLM Integration + BIS Compatibility

---

## Executive Summary

### Project Purpose

Build a sandboxed, multi-agent simulator of high-value payment operations that demonstrates how banks strategically time and fund outgoing payments during the business day. The simulator models real-world RTGS (Real-Time Gross Settlement) systems like TARGET2, where banks must balance competing pressures: minimizing liquidity costs, meeting payment deadlines, avoiding gridlock, and maintaining system throughput.

**Core Innovation**: Each bank is controlled by a **decision-tree policy** (small, auditable program) that determines payment timing and liquidity management. An **asynchronous LLM Manager service** improves policies between simulation episodes through code editing, with all changes validated via automated testing and Monte Carlo shadow replay before deployment.

### What We've Achieved: Core + Integration + DSL Complete ✅

The Rust core backend is **complete and battle-tested**:

- ✅ **Phase 1-2**: Time management, RNG (xorshift64*), Agent state, Transaction models
- ✅ **Phase 3**: RTGS settlement engine + LSM (bilateral offsetting + cycle detection)
- ✅ **Phase 3.5**: T2-compliant LSM with unequal payment values (net position settlement)
- ✅ **Phase 4a**: Queue 1 (internal bank queues) + Cash Manager policies (FIFO, Deadline, LiquidityAware)
- ✅ **Phase 4b**: Complete 9-step orchestrator tick loop integrating all components
- ✅ **Phase 5**: Transaction splitting (agent-initiated payment pacing)
- ✅ **Phase 6**: Arrival generation with configurable distributions (Poisson, normal, lognormal, uniform)
- ✅ **Phase 7**: Integration layer complete (PyO3 FFI, FastAPI, CLI tool)
- ✅ **Phase 9 (DSL)**: Complete policy DSL infrastructure (~4,880 lines) with expression evaluator, JSON decision trees, validation pipeline, and 50+ field accessors

**Test Coverage**: 280+ passing tests with zero failures (102 Rust core + 24 FFI + 23 API integration + 38 priority system + 71 persistence + 60 TARGET2 LSM), including critical invariants (determinism, balance conservation, gridlock resolution, T2-compliant LSM, priority ordering, algorithm sequencing). Policy DSL has 940+ lines of tests.

### Where We're Going: Feature Expansion 🎯

**Completed Phases** ✅:
- **Phase 7** (Integration Layer): PyO3 FFI bindings, FastAPI endpoints, CLI tool - COMPLETE
- **Phase 9 DSL Infrastructure**: Expression evaluator, JSON decision trees, validation pipeline - COMPLETE

**Recently Completed** ✅:
- **Phase 8** (Cost Model): ✅ **100% complete** (2025-10-30)
  - ✅ Core structures (CostRates, CostBreakdown, CostAccumulator)
  - ✅ Cost calculations (5/5 types: liquidity, delay, split friction, deadline, collateral)
  - ✅ Policy-layer collateral management (Phase 1 of collateral plan)
  - ✅ FFI bindings (get_agent_accumulated_costs, get_system_metrics)
  - ✅ REST API endpoints (/costs, /metrics)
  - ✅ 41 comprehensive tests (all passing)
- **Phase 10** (Data Persistence): ✅ **100% complete** (2025-11-05)
  - ✅ DuckDB + Polars columnar storage with zero-copy Arrow
  - ✅ Mandatory end-of-day persistence (transactions + agent metrics)
  - ✅ Schema-as-code with Pydantic models
  - ✅ Checkpoint system for save/load orchestrator state
  - ✅ Query interface with 9 analytical functions
  - ✅ 71 persistence tests (all passing)
- **Phase 14-15** (Scenario Events): ✅ **100% complete** (2025-11-10)
  - ✅ 7 event types: DirectTransfer, CustomTransactionArrival, CollateralAdjustment, GlobalArrivalRateChange, AgentArrivalRateChange, CounterpartyWeightChange, DeadlineWindowChange
  - ✅ OneTime and Repeating schedules
  - ✅ Full replay identity support (events persist to simulation_events table)
  - ✅ Verbose output display for both live and replay modes
  - ✅ Pydantic validation schemas with FFI integration
  - ✅ 29 scenario event tests (all passing)
- **Priority System**: ✅ **100% complete** (2025-11-21)
  - ✅ Priority Distributions: Transaction-level priority variation (Fixed, Categorical, Uniform)
  - ✅ Queue 1 Priority Ordering: Sort by priority (desc), deadline (asc), arrival (FIFO)
  - ✅ T2 Priority Mode for Queue 2: Priority bands (Urgent 8-10, Normal 4-7, Low 0-3)
  - ✅ Dynamic Priority Escalation: Auto-boost priority as deadlines approach (linear curve)
  - ✅ PriorityEscalated events with CLI verbose output
  - ✅ 38+ priority-related integration tests (all passing)
  - ✅ Backward compatible: Existing configs work unchanged
- **TARGET2 LSM Alignment**: ✅ **100% complete** (2025-11-22)
  - ✅ Phase 0: Dual Priority System - Separate internal priority (0-10) from RTGS declared priority (HighlyUrgent/Urgent/Normal)
  - ✅ Phase 1: Bilateral/Multilateral Limits - Per-counterparty and total outflow caps with LSM awareness
  - ✅ Phase 2: Algorithm Sequencing - Formal 3-algorithm sequence (FIFO → Bilateral → Multilateral) per TARGET2 spec
  - ✅ Phase 3: Entry Disposition Offsetting - Pre-queue bilateral offset detection at payment entry
  - ✅ Withdraw/Resubmit: Change RTGS priority mid-queue (loses FIFO position)
  - ✅ 7 new event types: RtgsSubmission, RtgsWithdrawal, RtgsResubmission, BilateralLimitExceeded, MultilateralLimitExceeded, AlgorithmExecution, EntryDispositionOffset
  - ✅ CLI verbose output for all TARGET2 events with replay identity
  - ✅ 60 TARGET2 alignment tests (all passing)

**Next Steps** (8-12 weeks):
1. ❌ Phase 17: BIS AI Cash Management compatibility (priority-based delay costs, liquidity allocation, per-band arrivals) (2 weeks) ← **NEXT**
2. ❌ Phase 11: LLM Manager Integration with shadow replay and policy evolution (3 weeks)
3. ❌ Phase 12: Multi-rail support (RTGS + DNS, cross-border corridors) (2 weeks)
4. ❌ Phase 13: Enhanced shock scenarios (outages, liquidity squeezes, counterparty stress) (1 week)
5. ❌ Phase 16: Production readiness (WebSocket streaming, frontend, observability) (3 weeks)

---

## Part I: Background & Real-World Grounding

### 1.1 The Real-World Problem

**Who Are the Agents?**  
Real-world intraday cash managers (treasury operations teams) at banks who decide:
- **When** to release payments across settlement rails (Fedwire, CHAPS, TARGET2)
- **How** to fund them (overdraft, collateralized intraday credit, repo markets)
- **Which** payments to prioritize (client obligations, house flows, regulatory deadlines)

**What Actually Moves?**  
**Settlement balances** at the central bank. When a bank debits a customer's account internally, no interbank money moves yet. The scarce resource intraday is **settlement liquidity** — the bank's balance at the central bank plus any available intraday credit.

**How Do They Fund Payments?**
- Opening balances (overnight reserves)
- Incoming payments (liquidity recycling)
- Priced overdraft (10-50 bps annualized) or collateralized intraday credit
- Intraday repo/money market borrowing
- Pre-funded nostro accounts for cross-border corridors

### 1.2 Operational Realities

Real payment systems face multiple constraints:

**Time Constraints**:
- Cut-off windows (market closes, CLS/PvP deadlines, payroll times)
- Throughput expectations (settle X% by time T to avoid end-of-day bunching)
- Business day structure (morning peaks, lunchtime lulls, afternoon surges)

**Liquidity Constraints**:
- Credit limits at central bank
- Bilateral exposure caps between banks
- Collateral availability and haircuts
- Nostro prefunding requirements

**Operational Realities**:
- Gridlock risk (if everyone waits for inflows, nothing moves)
- Compliance holds (AML screening can delay time-critical payments)
- Message processing capacity limits
- System outages and degraded mode operations

### 1.3 Why Liquidity-Saving Mechanisms Matter

Modern RTGS systems incorporate **LSMs (Liquidity-Saving Mechanisms)** to reduce liquidity requirements:

**Bilateral Offsetting**: If Bank A owes Bank B $100M and Bank B owes Bank A $80M, settle the net ($20M A→B) instead of gross ($180M total).

**Cycle Detection**: Find circular payment chains (A→B→C→A) and settle with minimal liquidity. A 3-bank cycle with payments of $100M each can settle with zero net liquidity movement.

**Empirical Evidence**: TARGET2 studies show LSMs reduce average delay by 40-60% and peak liquidity usage by 30-50% under constrained conditions (Danmarks Nationalbank, ECB operational studies).

**The Coordination Problem**: With costly liquidity, each bank prefers to wait for inflows. If all wait, gridlock forms. LSMs alleviate but don't eliminate the coordination challenge — they still need a *feed* of submitted payments to work with.

---

## Part II: Game Mechanics & Simulator Design

### 2.1 Core Simulation Loop

The simulator operates in **discrete ticks** (60-100 per simulated business day), with each tick executing a 9-step process:

#### Tick Loop Structure

**1. Arrivals** → New payment orders arrive at banks, entering Queue 1 (internal bank queues)

**2. Policy Evaluation** → Cash manager policies decide what to submit to RTGS vs. hold, whether to split large payments, whether to add liquidity

**3. Liquidity Decisions** → Banks may draw intraday credit, post collateral, or adjust buffers

**4. Queue 1 Processing** → Release decisions executed (transactions move from Queue 1 to "pending submission")

**5. Transaction Splitting** → Large payments optionally divided into N separate payment instructions

**6. RTGS Submission** → Selected transactions submitted to central RTGS (Queue 2)

**7. RTGS Settlement** → Immediate settlement if balance + credit headroom sufficient, otherwise queue

**8. LSM Optimization** → Bilateral offsetting and cycle detection on Queue 2

**9. Cost Accrual & Metrics** → Update costs, track KPIs, generate events

### 2.2 Two-Queue Architecture

The simulator models real-world payment flows through **two distinct queues**:

#### Queue 1: Internal Bank Queues
- **Purpose**: Strategic decision point for cash managers
- **Location**: Inside each bank (agent state)
- **Control**: Bank's policy determines release timing
- **Costs Apply**: Delay costs accrue here (bank chose to hold)
- **Actions Available**: Submit now, hold, split into N parts, drop

#### Queue 2: RTGS Central Queue
- **Purpose**: Mechanical liquidity wait at central bank
- **Location**: Central RTGS system (simulation state)
- **Control**: Automatic retry every tick
- **Costs Apply**: No delay costs (liquidity-constrained, not policy choice)
- **Actions Available**: LSM optimization attempts settlement

**Design Rationale**: This separation captures the reality that banks choose when to submit, but cannot force settlement — that depends on liquidity availability.

### 2.3 Transaction Lifecycle

**States**:
1. **Pending** — Arrived but not settled
   - In Queue 1: Awaiting cash manager release decision
   - In Queue 2: Submitted to RTGS, awaiting liquidity or LSM offset
2. **Settled** — Fully settled with immediate finality (final state)
3. **Dropped** — Rejected or past deadline (terminal state)

**Settlement Rate Calculation**:

The settlement rate measures what percentage of original payment requests successfully completed.

**Formula**: `settlement_rate = effectively_settled_arrivals / total_arrivals`

Where:
- **total_arrivals**: Count of original transactions entering the system (excludes child transactions from splits)
- **effectively_settled**: A transaction is considered settled if:
  - It settled directly (no split), OR
  - ALL of its child transactions settled (recursive check for nested splits)

**Why This Definition?**

Split transactions create multiple child payments from one original request. The settlement rate should reflect whether the ORIGINAL payment request was fulfilled, not count internal split mechanics.

**Example**: If 1 transaction splits into 2 children that both settle:
- Arrivals: 1 (original request)
- Effectively settled: 1 (request fulfilled via children)
- Rate: 100% ✓

This semantic ensures rates ≤ 100% and measures actual payment completion.

**Splitting Mechanics**:
- Banks may **voluntarily split** large payments at Queue 1 decision point
- Creates N independent child transactions (each with unique ID)
- Children inherit parent's sender, receiver, deadline, priority
- Each child processes independently through RTGS
- **Not a system feature** — purely a policy decision (agent-initiated pacing)
- Incurs **split friction cost**: `f_s × (N-1)` to reflect operational overhead

### 2.4 Cost Model

The simulator tracks five cost types:

**1. Liquidity Costs** (intraday credit/overdraft)
- **When**: Charged per tick while balance < 0
- **Formula**: `c_L × max(0, -B_i) × (1/ticks_per_day)`
- **Interpretation**: Annualized overdraft rate (10-50 bps typical)

**2. Collateral Costs** (for collateralized credit)
- **When**: Charged per tick while collateral posted
- **Formula**: `c_C × collateral_value × (1/ticks_per_day)`
- **Interpretation**: Opportunity cost of tying up securities

**3. Delay Costs** (Queue 1 only)
- **When**: Per tick while transaction remains in Queue 1
- **Formula**: `p_k × (t - t_arrival)` for each transaction
- **Interpretation**: Client dissatisfaction, reputational risk, opportunity cost
- **Note**: Does NOT apply to Queue 2 (liquidity wait is beyond bank's control)

**4. Split Friction Costs**
- **When**: Charged immediately upon splitting decision
- **Formula**: `f_s × (N-1)` for N-way split
- **Interpretation**: Message processing, reconciliation, coordination overhead

**5. Deadline Penalties**
- **When**: Transaction exceeds deadline or unsettled at end-of-day
- **Formula**: Per-transaction penalty (large, to incentivize completion)
- **Interpretation**: SLA violations, regulatory scrutiny

### 2.5 Observation Space for Policies

Policies (and future LLM managers) observe:

**Agent-Local State**:
- Current settlement balance `B_i`
- Available credit headroom `H_i`
- Queue 1 contents (transactions, ages, priorities, deadlines)
- Posted collateral and remaining capacity
- Expected inflows (short-term forecast)

**System-Level Signals** (coarse, public):
- System-wide throughput percentage
- Queue 2 pressure (queue length, age distribution)
- Time remaining to cut-offs
- Liquidity price indicators

**Temporal Context**:
- Current tick and day
- Ticks to deadline for each transaction
- Time since last policy evaluation

**Note**: Banks do NOT see other banks' Queue 1 contents or exact balances (realistic information structure).

### 2.6 Design Principles Validated by Foundation

The foundation implementation validated several critical design choices:

**✅ Determinism is Achievable**:
- All randomness via seeded xorshift64* RNG
- Replay tests confirm identical outcomes for same seed
- Foundation for Monte Carlo shadow replay validation

**✅ Performance Targets Met**:
- Rust tick loop processes 1000+ ticks/second
- LSM cycle detection completes in <1ms for typical graphs
- Memory-efficient transaction queue management

**✅ Two-Queue Separation Works**:
- Clear distinction between policy decisions (Queue 1) and mechanical waits (Queue 2)
- Delay costs apply only to Queue 1 (as intended)
- Policies have natural decision hooks at arrival time

**✅ LSM Delivers Expected Benefits**:
- Four-bank ring test settles with minimal liquidity (Section 11 from Game Design Doc)
- Bilateral offsetting reduces settlement liquidity by 30-40% in balanced scenarios
- Cycle detection resolves simple gridlocks automatically

### 2.7 Scenario Events: Controlled Interventions

**Scenario events** enable researchers to inject deterministic state changes at specific ticks, modeling shock scenarios, policy changes, and controlled experiments. Unlike random arrivals, scenario events execute predictably, enabling reproducible stress tests.

#### Event Categories

**1. Liquidity Management:**
- **DirectTransfer**: Instant balance changes bypassing settlement (e.g., central bank emergency liquidity, interbank loans)
- **CollateralAdjustment**: Modify posted collateral (margin calls, haircut changes, regulatory adjustments)

**2. Transaction Control:**
- **CustomTransactionArrival**: Create transactions through normal arrival → settlement path (tests Queue 1 policy decisions and RTGS settlement)
- **Key difference from DirectTransfer**: Goes through Queue 1 (policy evaluation) → Queue 2 (RTGS) → potential LSM optimization

**3. System-Wide Shocks:**
- **GlobalArrivalRateChange**: Scale all agents' arrival rates (market surges, holiday slowdowns)
- **AgentArrivalRateChange**: Adjust specific agent's rate (bank-specific operational changes)

**4. Relationship Changes:**
- **CounterpartyWeightChange**: Modify correspondent banking preferences
- **DeadlineWindowChange**: Adjust agent's default deadline expectations

#### Scheduling Flexibility

**OneTime Events:**
```yaml
schedule:
  type: OneTime
  tick: 50  # Execute once at tick 50
```

**Repeating Events:**
```yaml
schedule:
  type: Repeating
  start_tick: 10
  interval: 5      # Every 5 ticks
  end_tick: 50     # Optional end boundary
```

#### Implementation Architecture

**Rust Layer:**
- Events defined as `ScenarioEvent` enum with all variants
- Executed at tick start, before normal arrivals
- Logged to `simulation_events` table with full details JSON

**Python Layer:**
- Pydantic schemas validate events at config load time
- FFI conversion handles optional parameters (priority, deadline, divisibility)
- Display logic works identically in live and replay modes

**Replay Identity:**
- Events persist to database with complete execution details
- Replay produces byte-for-byte identical output
- Critical for reproducible research and debugging

#### Use Cases

**Stress Testing:**
- Model liquidity crises with timed large outflows
- Test collateral haircut shocks mid-day
- Simulate counterparty failures (zero arrival rates)
- Validate gridlock resolution under extreme conditions

**Policy Evaluation:**
- Test how policies respond to known shocks (controlled conditions)
- Compare DirectTransfer (instant) vs CustomTransactionArrival (realistic settlement)
- Measure policy adaptation speed to liquidity changes

**Reproducible Research:**
- Exact control over experimental conditions (deterministic timing)
- Database persistence ensures complete provenance
- Peer review enabled by deterministic replay

#### Example: Liquidity Crisis Scenario

```yaml
agents:
  - id: BANK_A
    opening_balance: 1000000
    credit_limit: 200000
    policy: {type: LiquidityAware, buffer_target: 100000}

scenario_events:
  # Morning: Normal large payment
  - type: CustomTransactionArrival
    from_agent: BANK_A
    to_agent: BANK_B
    amount: 150000
    priority: 5
    deadline: 20
    schedule: {type: OneTime, tick: 10}

  # Midday: Liquidity shock (margin call to clearing house)
  - type: DirectTransfer
    from_agent: BANK_A
    to_agent: CLEARING_HOUSE
    amount: 500000  # Large outflow
    schedule: {type: OneTime, tick: 50}

  # Afternoon: Reduced collateral capacity
  - type: CollateralAdjustment
    agent: BANK_A
    delta: -100000  # Collateral haircut
    schedule: {type: OneTime, tick: 60}

  # Result: Tests how BANK_A policy adapts under cascading stress
```

**Expected Behavior:**
- Tick 10: CustomTransactionArrival tests normal queue decision
- Tick 50: DirectTransfer causes immediate liquidity drain
- Tick 60: Collateral reduction limits credit access
- **Research question:** Does LiquidityAware policy prevent gridlock?

#### Integration with Other Features

**Cost Model:** Scenario events can trigger:
- Liquidity costs (overdraft after DirectTransfer outflow)
- Deadline penalties (if CustomTransactionArrival doesn't settle in time)
- Collateral costs (opportunity cost after CollateralAdjustment)

**Persistence Layer:**
- Events stored in `simulation_events.details` as JSON
- Query interface enables analysis: "Find all sims with collateral shocks"
- Checkpoint system can save state before/after event execution

**Policy Testing:**
- LLM Manager (Phase 11) can propose policies tested against scenario library
- Shadow replay validates policies on 100+ shock scenarios
- Statistical comparison: does new policy handle shocks better?

---

## Part III: Current State Assessment

### 3.1 What's Complete: Foundation Phases 1-6

#### Phase 1-2: Core Domain Models ✅
**Modules**: `backend/src/core/`, `backend/src/models/`

**Implemented**:
- `TimeManager`: Discrete tick/day system with advancement
- `RngManager`: Seeded xorshift64* for determinism
- `AgentState`: Settlement balance, credit limits, queue management
- `Transaction`: Full lifecycle (Pending→Settled/Dropped), priority, divisibility
- `SimulationState`: Centralized state with agents + transactions

**Tests**: 48 passing tests covering time, RNG, agent operations, transactions

**Key Decisions Validated**:
- Money as `i64` (cents) — no floating-point contamination
- Agent balance represents central bank settlement account (not customer deposits)
- Transaction IDs as strings (UUID support ready)

#### Phase 3: RTGS Settlement Engine + LSM ✅
**Modules**: `backend/src/settlement/rtgs.rs`, `backend/src/settlement/lsm.rs`

**Implemented**:
- **RTGS**: Immediate settlement when balance + credit sufficient, else Queue 2
- **Queue processing**: FIFO retry with deadline expiration
- **Partial settlement**: For divisible transactions
- **Bilateral offsetting**: A↔B payment netting
- **Cycle detection**: DFS-based graph search for payment loops
- **LSM coordinator**: Multi-iteration optimization pass

**Tests**: 37 passing tests (22 RTGS + 15 LSM)

**Critical Validations**:
- Balance conservation maintained (sum of all balances constant)
- Liquidity recycling works (A→B→C payment chains)
- Gridlock detection and LSM-based resolution
- Four-bank ring scenario from Game Design Doc passes

#### Phase 3.5: T2-Realistic LSM with Unequal Payment Values ✅ **COMPLETE**
**Modules**: `backend/src/settlement/lsm.rs` (enhancement)

**Status**: Implemented and tested (2025-11-05)

**Goal**: Bring LSM into full compliance with T2 RTGS specifications for handling unequal payment values in multilateral cycles — **ACHIEVED**

**What Was Implemented**: Full T2-compliant LSM that settles the FULL value of each transaction in multilateral cycles, with each participant covering their net position (not the minimum amount).

**What T2 Actually Does** (from research in [docs/lsm-in-t2.md](lsm-in-t2.md)):
- **No partial settlement of individual payments**: Each payment settles in full or not at all
- **Bilateral offsetting with unequal values**: Already implemented correctly ✅
- **Multilateral cycles with unequal values**: T2 settles ALL transactions at full value, as long as each participant can cover their net position
- **All-or-nothing execution**: If any participant lacks liquidity for their net position, the entire cycle fails

**Key Implementation Changes**:
1. **Net Position Calculation**: For each agent in cycle, calculate `net = sum(incoming) - sum(outgoing)`
2. **Feasibility Check**: Verify all agents with net outflow can cover it BEFORE any settlements
3. **Full Amount Settlement**: Settle complete transaction values (not min)
4. **Atomic Execution**: Two-phase commit (check feasibility → execute all or nothing)

**Example**:
```rust
// Cycle: A→B (500k), B→C (800k), C→A (700k)
// Net positions:
//   A: -500k + 700k = +200k (net inflow)
//   B: -800k + 500k = -300k (net outflow, needs 300k liquidity)
//   C: -700k + 800k = +100k (net inflow)
//
// Current: Settle 500k from each (min) → partial amounts remain queued
// T2-compliant: Check if B has 300k → settle ALL three at full value
//
// Final balances: A=+200k, B=-300k, C=+100k (net=0, conservation maintained)
```

**Implementation Tasks** (see [docs/plans/t2-realistic-lsm-implementation.md](plans/t2-realistic-lsm-implementation.md)):
1. ✅ Net position calculation for multilateral cycles
2. ✅ Cycle feasibility check (verify liquidity before settlement)
3. ✅ Two-phase atomic settlement (check → execute)
4. ✅ Enhanced metrics (track net positions, liquidity efficiency)
5. ✅ Comprehensive testing (8+ new test scenarios)

**Benefits**:
- More realistic modeling of T2 behavior
- Better liquidity utilization (settle larger values with same net liquidity)
- Accurate simulation of gridlock resolution mechanisms
- Foundation for policy learning (agents can optimize for LSM benefits)

**Backward Compatibility**:
- Feature flag: `lsm_t2_compliant` (default: true)
- Legacy implementation preserved for comparison
- All existing tests pass

**Tests**: 10 comprehensive tests passing (all T2-compliant scenarios validated)

**Completed**: 2025-11-05 (implementation + testing complete)

**Dependencies**: None (enhancement to existing Phase 3)

**Enables**: Better policy learning in Phase 11 (LLM can optimize for LSM with realistic net position requirements)

#### Phase 4a: Queue 1 + Cash Manager Policies ✅
**Modules**: `backend/src/policy/`, extended `backend/src/models/agent.rs`

**Implemented**:
- **Queue 1 infrastructure**: Per-agent outgoing queues with analytics
- **Policy trait**: `CashManagerPolicy` with `evaluate_queue()` method
- **Three baseline policies**:
  - `FifoPolicy`: Submit all immediately (simplest baseline)
  - `DeadlinePolicy`: Prioritize urgent transactions
  - `LiquidityAwarePolicy`: Preserve buffer, override for urgency
- **Decision types**: `ReleaseDecision` enum with structured hold reasons

**Tests**: 12 passing policy tests

**Documentation**: 3200+ line guide at `docs/queue_architecture.md`

#### Phase 4b: Orchestrator Integration ✅
**Module**: `backend/src/orchestrator/engine.rs`

**Implemented**:
- Complete 9-step tick loop integrating all subsystems
- State transitions (Queue 1 → pending → Queue 2 → settled)
- Event logging for replay and debugging
- Clean separation of concerns between modules

**Tests**: 6 passing orchestrator integration tests

**Validation**: End-to-end flows confirmed (arrival → policy → submission → settlement)

#### Phase 5: Transaction Splitting ✅
**Module**: Integrated into `backend/src/orchestrator/engine.rs`

**Implemented**:
- Voluntary splitting at Queue 1 decision point
- Creates N independent child transactions
- Inheritance of parent attributes (sender, receiver, deadline, priority)
- Split friction cost calculation

**Tests**: Covered in orchestrator tests

#### Phase 6: Arrival Generation ✅
**Module**: `backend/src/orchestrator/engine.rs` (ArrivalGenerator)

**Implemented**:
- Poisson process for arrival timing (inter-arrival exponential)
- Four amount distributions: Normal, Lognormal, Uniform, Exponential
- Per-agent configuration (rate, distribution, parameters)
- Counterparty selection (weighted or uniform)

**Tests**: Determinism verified across multiple runs

### 3.2 Phase 7 Complete: Integration Layer ✅

#### PyO3 FFI Bindings ✅
**Status**: Complete
**Scope**: Expose Rust orchestrator to Python

**Implemented**:
- ✅ Wrapped `Orchestrator` in PyO3 class
- ✅ Type conversions between Rust and Python (dicts, lists)
- ✅ Error propagation (Rust `Result` → Python exceptions)
- ✅ Memory safety with clear ownership model
- ✅ Determinism preserved across boundary

**Tests**: 24 FFI tests passing

#### Python API Layer ✅
**Status**: Complete
**Scope**: FastAPI middleware for HTTP/WebSocket endpoints

**Implemented**:
- ✅ Configuration loading (YAML) with Pydantic V2 validation
- ✅ Simulation lifecycle management (create, start, stop, reset)
- ✅ Transaction submission and querying
- ✅ State snapshot endpoints
- ✅ Metrics aggregation and cost tracking

**Tests**: 23 integration tests passing

#### CLI Tool ✅
**Status**: Complete
**Scope**: Command-line interface for scenario execution

**Implemented**:
- ✅ Commands: `run <scenario.yaml>` with full execution
- ✅ Pretty-printed output (settlement stats, cost breakdowns)
- ✅ Config file support (YAML scenario loading)
- ✅ Verbose mode for detailed execution logging (categorized events)
- ✅ Event stream mode (`--event-stream`) for chronological one-line display
- ✅ Event filtering (4 filter types with AND logic):
  - `--filter-event-type`: Comma-separated event types (e.g., "Arrival,Settlement")
  - `--filter-agent`: Filter by agent ID (matches agent_id or sender_id)
  - `--filter-tx`: Filter by transaction ID
  - `--filter-tick-range`: Filter by tick range ("min-max", "min-", or "-max")
- ✅ Large-scale scenarios tested (200 agents, 100 ticks)

**Performance**: 1,200 ticks/second, 8 seconds for 200-agent scenarios

**Usage Examples**:
```bash
# Verbose mode with all event types
payment-sim run --config scenario.yaml --verbose --ticks 100

# Event stream mode (chronological, one-line format)
payment-sim run --config scenario.yaml --event-stream --ticks 50

# Filter to show only Arrival events
payment-sim run --config scenario.yaml --event-stream --filter-event-type Arrival

# Filter by specific agent
payment-sim run --config scenario.yaml --verbose --filter-agent BANK_A

# Combine multiple filters (AND logic)
payment-sim run --config scenario.yaml --event-stream \
  --filter-event-type "Arrival,Settlement" \
  --filter-agent BANK_A \
  --filter-tick-range "10-50"
```

#### Integration Testing ✅
**Status**: Complete
**Scope**: End-to-end validation across layers

**Implemented**:
- ✅ FFI boundary tests (Rust↔Python roundtrip) - 24 tests
- ✅ API endpoint tests (CRUD operations) - 23 tests
- ✅ Determinism tests (seed preservation across boundary)
- ✅ Performance validation (>1000 ticks/sec maintained)
- ✅ Large-scale validation (200 agents documented in LARGE_SCALE_RESULTS.md)

**Test Coverage**: 107+ total tests (60+ Rust + 24 FFI + 23 API)

### 4.1 Phase 7: Integration Layer ✅ **COMPLETE**

**Goal**: Connect Rust core to Python API and CLI tools — **ACHIEVED**

#### Summary of Accomplishments

**PyO3 FFI Bindings** ✅
- ✅ PyO3 fully integrated with Maturin build system
- ✅ `PyOrchestrator` class wrapping Rust `Orchestrator`
- ✅ Type conversions: Rust structs ↔ Python dicts (seamless)
- ✅ Error handling: Rust `Result` → Python exceptions with context
- ✅ Memory safety validated (no leaks detected)
- ✅ Determinism preserved across FFI boundary
- **Tests**: 24 FFI tests passing

**Python API Layer** ✅
- ✅ Pydantic V2 schemas for all config types
- ✅ YAML loader with comprehensive validation
- ✅ `SimulationManager` with full lifecycle support
- ✅ FastAPI endpoints operational:
  - `POST /simulations` — create with config
  - `POST /simulations/{id}/tick` — advance simulation
  - `GET /simulations/{id}/state` — get state snapshot
  - `POST /transactions` — submit transaction
  - `GET /transactions/{id}` — query transaction details
- **Tests**: 23 integration tests passing

**CLI Tool** ✅
- ✅ Command: `payment-sim run <scenario.yaml>` (full execution)
- ✅ Pretty-printed output (settlement stats, cost breakdowns)
- ✅ Verbose mode for detailed logging
- ✅ Scenario library with realistic examples
- ✅ Large-scale validation (200 agents, 100 ticks in ~8 seconds)
- **Performance**: 1,200 ticks/second maintained

**Integration Testing** ✅
- ✅ End-to-end scenarios validated:
  - Two-bank payment exchange ✅
  - Four-bank ring with LSM resolution ✅
  - Gridlock formation and recovery ✅
  - Large-scale scenarios (200 agents) ✅
- ✅ Performance targets met (>1000 ticks/sec)
- ✅ FFI overhead measured (<1%)
- ✅ Determinism validated across all layers
- **Total Tests**: 107+ (60+ Rust + 24 FFI + 23 API)

**All Success Criteria Met** ✅
- ✅ Can create orchestrator from Python with valid config
- ✅ Can advance ticks and retrieve state
- ✅ Same seed produces identical results
- ✅ No memory leaks detected
- ✅ Can create/manage simulations via HTTP
- ✅ State snapshots return correct data
- ✅ CLI is usable for debugging simulations
- ✅ Can reproduce any simulation from seed
- ✅ Performance targets exceeded (1200 ticks/sec vs 1000 target)

### 4.2 Phase 8: Cost Model & Metrics ✅ **COMPLETE**

**Goal**: Implement full cost accounting and KPI tracking — **ACHIEVED**

**Status Update (2025-10-30)**: Phase 8 fully complete. All Rust backend cost calculations operational. Python API layer with comprehensive FFI bindings and REST endpoints delivered. See [PHASE_8_COMPLETION_REPORT.md](../PHASE_8_COMPLETION_REPORT.md) for details.

#### What's Complete ✅

**Cost Structures** (backend/src/orchestrator/engine.rs):
- ✅ `CostRates` struct with all 5 cost type configurations (lines 188-224)
- ✅ `CostBreakdown` struct for per-agent cost tracking (lines 227-254)
- ✅ `CostAccumulator` maintaining cumulative totals (lines 257-300)
- ✅ Per-agent accumulated costs in orchestrator state

**Cost Calculations** (5 of 5 types operational):
1. ✅ **Liquidity Costs**: `calculate_overdraft_cost()` charges per-tick overdraft fees
2. ✅ **Delay Costs**: `calculate_delay_cost()` charges Queue 1 holding fees
3. ✅ **Split Friction**: Structure exists with formula `f_s × (N-1)`
4. ✅ **Deadline/EoD Penalties**: Framework in place, `handle_end_of_day()` implemented
5. ✅ **Collateral Costs**: `calculate_collateral_cost()` accrues opportunity cost per tick

**Cost Accrual Integration**:
- ✅ `accrue_costs()` called every tick (step 6 of 9-step loop)
- ✅ Costs accumulated per agent throughout simulation
- ✅ `total_cost` returned in tick response

**Collateral Management** (Phase 1 of collateral_management_plan.md - Policy Layer):
- ✅ Agent model has `posted_collateral` field (backend/src/models/agent.rs)
- ✅ `available_liquidity()` includes collateral: `balance + credit_limit + posted_collateral`
- ✅ Collateral cost accrues every tick (opportunity cost basis points)
- ✅ `CollateralDecision` and `CollateralReason` enums in policy layer
- ✅ `CashManagerPolicy::evaluate_collateral()` method (default returns Hold)
- ✅ Orchestrator executes collateral decisions (STEP 2.5 of tick loop)
- ✅ Agent helper methods: `max_collateral_capacity()`, `queue1_liquidity_gap()`
- ✅ Collateral events logged: `CollateralPost` and `CollateralWithdraw`
- ✅ 10 comprehensive tests for Agent collateral methods
- ✅ All 134 tests passing (backward compatible)

#### Implementation Status: 100% Complete ✅

**Completed on**: 2025-10-30
**Full Report**: [PHASE_8_COMPLETION_REPORT.md](../PHASE_8_COMPLETION_REPORT.md)

**API Layer** (Python/FastAPI): ✅ **COMPLETE**
- ✅ `/api/simulations/{id}/costs` endpoint exposes accumulated costs
- ✅ `/api/simulations/{id}/metrics` endpoint provides KPI dashboard
- ✅ Comprehensive OpenAPI documentation
- ✅ Error handling (404, 500) follows existing patterns

**FFI Exposure**: ✅ **COMPLETE**
- ✅ `get_agent_accumulated_costs(agent_id)` FFI method
- ✅ `get_system_metrics()` FFI method
- ✅ Type-safe conversion via PyO3
- ✅ Per-agent cost breakdown accessible from Python
- ✅ System-wide metrics (arrivals, settlements, throughput, delays, queues, overdrafts)

**Rust Core**: ✅ **COMPLETE**
- ✅ All 5 cost types implemented and operational
- ✅ Collateral cost accrues correctly every tick
- ✅ Policy-layer collateral management (Phase 1 of collateral plan)
- ✅ `SystemMetrics` struct with 9 performance indicators
- ✅ `calculate_system_metrics()` method (O(n) performance)

**Testing**: ✅ **COMPLETE**
- ✅ 16 FFI integration tests (test_cost_ffi.py)
- ✅ 25 API endpoint tests (test_cost_api.py)
- ✅ Determinism verification across runs
- ✅ 41 total new tests, all passing
- ✅ 203 total integration tests passing (no regressions)

**Files Created/Modified**:
- Created: `api/tests/integration/test_cost_ffi.py` (518 lines)
- Created: `api/tests/integration/test_cost_api.py` (600+ lines)
- Modified: `backend/src/orchestrator/engine.rs` (+115 lines)
- Modified: `backend/src/ffi/orchestrator.rs` (+99 lines)
- Modified: `api/payment_simulator/api/main.py` (+180 lines)

**Critical Invariants Preserved**:
- ✅ Money as i64 (no floating point contamination)
- ✅ Determinism (same seed = same results)
- ✅ Minimal FFI boundary (only primitives)
- ✅ Type safety (Pydantic validation)

**Future Enhancements** (Not Phase 8):
- End-of-Tick Collateral Layer (Phase 4 of collateral_management_plan.md)
  - Implemented as JSON tree policies (third tree in policy files)
  - Automatic cleanup: Withdraw collateral when safe
  - Runs at STEP 8 (after settlements, before costs)
  - Complements strategic layer (STEP 2.5)
  - Both layers use same context fields, just evaluated at different times

### 4.3 Phase 9 (DSL): Policy Expression Language ✅ **COMPLETE**

**Goal**: Safe, sandboxed policy DSL for hot-reloading decision trees — **ACHIEVED**

#### Implementation Status: 100% Complete

**Module**: backend/src/policy/tree/ (~4,880 lines of production code)

**Components Implemented** ✅:

1. **Expression Evaluator** (interpreter.rs, ~1,600 lines):
   - Safe expression evaluation (no code execution)
   - Arithmetic operators: `+`, `-`, `*`, `/`, `min()`, `max()`
   - Comparison operators: `==`, `!=`, `<`, `<=`, `>`, `>=`
   - Boolean operators: `and`, `or`, `not`
   - Nested expression support with depth limits
   - Division-by-zero protection
   - Type conversion (float, int, boolean)

2. **Policy DSL Schema** (types.rs, ~580 lines):
   - JSON-based decision tree format
   - `DecisionTreeDef` root structure
   - `TreeNode` with conditions and actions
   - `Expression` and `Value` types
   - `Computation` for complex calculations

3. **Tree Executor** (executor.rs, ~450 lines):
   - `TreePolicy` implementing `CashManagerPolicy` trait
   - Load from file: `TreePolicy::from_file(path)`
   - Load from JSON: `TreePolicy::from_json(json_string)`
   - Lazy validation before first use
   - Full integration with orchestrator

4. **Evaluation Context** (context.rs, ~320 lines):
   - 50+ accessible fields organized by category:
     - Agent state (balance, credit, liquidity_pressure)
     - Transaction fields (amount, deadline, priority)
     - Time fields (tick, ticks_to_deadline, queue_age)
     - System state (queue sizes, throughput)
     - Expected inflows (forecasts)

5. **Validation Pipeline** (validation.rs, ~970 lines):
   - Schema version validation
   - Unique node IDs (no duplicates)
   - Parameter reference validation
   - Maximum depth enforcement (limit 100)
   - Division-by-zero detection
   - Field reference validation
   - Cycle detection (prevents infinite loops)
   - Type consistency checking
   - 15+ specific error types

6. **Testing** (tests/, ~940 lines):
   - equivalence_tests.rs (~350 lines): Validates JSON trees ≡ Rust policies
   - scenario_tests.rs (~600 lines): Real-world scenario testing
   - Property-based tests for invariants

**Documentation** ✅:
- policy_dsl_design.md (2,700+ lines): Complete specification
- backend/CLAUDE.md: Development guidance
- Rustdoc comments on all public APIs

**What You Can Do Now**:
- ✅ Define complex decision trees in JSON
- ✅ Hot-reload policies without restarting
- ✅ Use LLM to generate/edit policy JSON safely
- ✅ Validate policies before execution
- ✅ A/B test different policies
- ✅ Version control policies (just need git wrapper)

#### What's Deferred to Phase 13 (LLM Manager)

The following features were designed in Phase 9 but intentionally deferred:

**Shadow Replay System** (Designed, Not Implemented):
- Re-evaluate historical episodes with new policy
- Monte Carlo opponent sampling
- KPI comparison and validation
- **Reason**: Requires episode collection infrastructure (Phase 13)

**Policy Evolution Pipeline** (Designed, Not Implemented):
- Async policy validation service
- KPI comparison engine (old vs. new)
- Guardrail checking (cost delta thresholds)
- Automated deployment logic
- **Reason**: Requires LLM Manager service (Phase 13)

**Continuous Learning Loop** (Designed, Not Implemented):
- Episode collection (store seeds + results)
- LLM policy proposal generation
- Policy validation pipeline
- Automated deployment (git commit + restart)
- **Reason**: This IS the LLM Manager system (Phase 13)

**Architectural Decision**: Phase 9 focused on building safe, sandboxed DSL infrastructure that works independently. Phase 11 will add the LLM integration layer that USES this DSL. This separation allows:
1. Testing and validating DSL before adding LLM complexity
2. Using the DSL for manual policy development
3. Hot-reloading policies without LLM involvement

### 4.4 Phase 10: Data Persistence ✅ **COMPLETE**

**Goal**: Implement file-based data persistence for simulation runs, transactions, agent states, and policy evolution.

**Status**: 100% complete - All 5 phases implemented and tested (71/71 tests passing)

**Implementation Plan**: See [docs/persistence_implementation_plan.md](persistence_implementation_plan.md) for complete specification.

**CRITICAL REQUIREMENT**: All simulation data and state MUST be persisted to the database at the end of each simulated day. This is mandatory for research reproducibility, policy evolution tracking, and LLM Manager integration (Phase 11).

#### Why Persistence is Critical

**Enables Phase 11 (LLM Manager)**:
- Shadow replay requires historical episode storage (deterministic seeds + results)
- Policy evolution needs version tracking (store diffs between policy v23 → v24)
- LLM Manager validates improvements by comparing KPIs across stored episodes
- Monte Carlo validation samples from episode database

**Research & Analysis**:
- Store 200+ simulation runs with 1.2M transactions each = 240M+ transaction records
- Query agent performance across runs ("which policies performed best under liquidity stress?")
- Track policy evolution over time ("how did BANK_A's policy improve from v1 to v30?")

#### Technology Stack

**Database**: DuckDB
- File-based (single `simulation_data.db` file)
- Columnar storage (fast analytical queries on 250M+ rows)
- Zero-copy integration with Polars via Apache Arrow

**DataFrame Library**: Polars
- Faster than Pandas (Rust-based, SIMD optimized)
- Native Arrow format (zero-copy to/from DuckDB)
- Lazy evaluation for complex query chains

**Schema Management**: Pydantic Models as Source of Truth
- Auto-generate DDL from Pydantic models
- Versioned migration system (numbered SQL files)
- Runtime validation prevents schema drift
- CLI tools: `payment-sim db migrate`, `payment-sim db validate`

#### Data Model

**Five Core Tables**:

1. **simulations** - Simulation run metadata
   - Config hash, seed, performance metrics, completion status
   - Enables queries: "show all 200-agent runs with seed 12345"

2. **transactions** - Every transaction across all runs
   - Full lifecycle (arrival_tick, settlement_tick, status, costs)
   - Granular analysis: "transaction delay distribution by priority level"

3. **daily_agent_metrics** - Agent state snapshots per day
   - Balance stats (min/max/opening/closing), queue sizes, cost breakdown
   - Fast queries without scanning millions of transactions
   - Example: "BANK_A's peak overdraft on day 5 of run X?"

4. **policy_snapshots** - Policy version tracking
   - File path to JSON policy, SHA256 hash, creation timestamp
   - Who created: 'manual', 'llm_manager', 'init'
   - Enables policy provenance: "what policy was BANK_A using on day 3?"

5. **config_archive** - Full config snapshots
   - Enables exact reproduction of any run
   - Deduplication by config hash

**Schema Example** (Pydantic model auto-generates DDL):
```python
class TransactionRecord(BaseModel):
    simulation_id: str
    tx_id: str
    sender_id: str
    receiver_id: str
    amount: int  # cents
    arrival_tick: int
    settlement_tick: Optional[int]
    status: TransactionStatus  # 'pending', 'settled', 'dropped'
    queue1_ticks: int
    delay_cost: int

    class Config:
        table_name = "transactions"
        primary_key = ["simulation_id", "tx_id"]
        indexes = [
            ("idx_tx_sim_sender", ["simulation_id", "sender_id"]),
            ("idx_tx_status", ["status"]),
        ]
```

#### Persistence Strategy

**Batch Writes at End of Each Day**:
- Not real-time (would slow simulation 10-50x)
- Accumulate full day's data in memory (200 ticks worth)
- Write all at once: 40K transactions in <100ms via Polars → DuckDB

**Workflow**:
```python
for day in range(num_days):
    # Simulate entire day (200 ticks)
    for tick in range(ticks_per_day):
        orch.tick()

    # End of day: persist
    daily_txs = orch.get_transactions_for_day(day)  # FFI call
    df = pl.DataFrame(daily_txs)  # Polars DataFrame
    conn.execute("INSERT INTO transactions SELECT * FROM df")  # Zero-copy
```

**FFI Extensions Needed**:
- `get_transactions_for_day(day)` → List of transaction dicts
- `get_daily_agent_metrics(day)` → List of agent metric dicts
- Rust maintains full state, clones data to Python at end of day

#### Schema Synchronization

**Problem**: How to keep database schema in sync with evolving Pydantic models?

**Solution**: Pydantic models as single source of truth
1. Developer updates Pydantic model (adds field)
2. Run `payment-sim db create-migration add_my_field`
3. Edit generated migration SQL
4. Run `payment-sim db migrate` (applies migration)
5. Runtime validation ensures schema matches models

**Example** (adding `settlement_type` field):
```python
# 1. Update model
class TransactionRecord(BaseModel):
    # ... existing fields ...
    settlement_type: Optional[str] = None  # NEW: 'immediate', 'lsm_bilateral', 'lsm_cycle'

# 2. Create migration
$ payment-sim db create-migration add_settlement_type

# 3. Edit migrations/002_add_settlement_type.sql
ALTER TABLE transactions ADD COLUMN settlement_type VARCHAR;

# 4. Apply
$ payment-sim db migrate

# 5. Validate (automatic on connection)
$ payment-sim db validate
✓ Schema validation passed
```

#### Implementation Phases

**5-Phase Rollout** (8-12 days total):

1. **Infrastructure** (2-3 days):
   - DuckDB + Polars dependencies
   - Pydantic models with metadata
   - DDL auto-generator from models
   - Migration system
   - CLI commands (`db init`, `db migrate`, `db validate`)

2. **Transaction Batch Writes** (2-3 days):
   - Rust FFI: `get_transactions_for_day()`
   - Python: Convert to Polars, insert to DuckDB
   - Test: 40K transactions in <100ms

3. **Agent Metrics Collection** (1-2 days):
   - Rust: Track daily min/max balance, queue sizes, costs
   - FFI: `get_daily_agent_metrics()`
   - Python: Batch insert agent snapshots

4. **Policy Snapshot Tracking** (1 day):
   - Record policy changes (initial + mid-simulation updates)
   - Store file path + SHA256 hash
   - Integrate with Phase 9 DSL

5. **Query Interface** (2-3 days):
   - Pre-defined analytical queries returning Polars DataFrames
   - CLI: `payment-sim query list-runs`, `payment-sim query agent-metrics`
   - Export to Parquet for external analysis

#### Success Criteria

**Functional Requirements**:
- ✅ Can store 200 runs × 1.2M transactions = 240M+ records
- ✅ Can query transaction-level details for any run
- ✅ Can track policy evolution across runs (v1 → v30)
- ✅ Can export data to Polars/Parquet for external tools
- ✅ Survives process crashes (data committed after each day)
- ✅ Determinism preserved (same seed = same persisted data)

**Performance Targets**:
- Daily transaction batch write: <100ms (40K transactions)
- Daily metrics batch write: <20ms (200 agent records)
- Analytical query (1M txs): <1 second (interactive analysis)
- Database file size (200 runs): <10 GB (compressed columnar storage)
- Memory overhead: <50 MB (minimal impact on simulation)

**Integration with Phase 11**:
- ✅ Provides episode storage for shadow replay
- ✅ Tracks policy versions for LLM Manager validation
- ✅ Stores KPIs for comparing old vs. new policies
- ✅ Enables Monte Carlo sampling from historical runs

#### What's Deferred

**Not Included in Phase 10**:
- Real-time streaming to database (use WebSocket in Phase 14)
- External database (PostgreSQL, etc.) - file-based DuckDB only
- Distributed/sharded storage - single file sufficient for scope

----

## Part IV: Roadmap to Full Vision

### 4.4 Phase 8 Completion: Cost Model API Layer (Week 4 - Remaining)

**Status**: 75% complete (Rust core COMPLETE, Python API layer needed)

**Status Update (2025-10-29)**: All Rust cost calculations complete, including collateral cost accrual and policy-layer collateral management (Phase 1 of collateral_management_plan.md). Only Python API exposure remains.

**Goal**: Expose cost data and metrics via REST API

**Remaining Tasks** (2-3 days):

1. **Rust FFI Additions** (backend/src/ffi/orchestrator.rs):
   ```rust
   // Add these methods to PyOrchestrator
   fn get_agent_costs(&self, agent_id: String) -> PyResult<HashMap<String, i64>>
   fn get_system_metrics(&self) -> PyResult<HashMap<String, f64>>
   ```

2. **Python API Endpoints** (api/payment_simulator/api/main.py):
   ```python
   @app.get("/simulations/{sim_id}/costs")
   async def get_costs(sim_id: str) -> CostBreakdownResponse

   @app.get("/simulations/{sim_id}/metrics")
   async def get_metrics(sim_id: str) -> MetricsResponse

   @app.get("/metrics")  # Prometheus format
   async def prometheus_metrics() -> Response
   ```

3. **Testing**:
   - Integration tests for FFI cost queries
   - E2E tests via FastAPI endpoints

**Success Criteria**:
- ✅ All 5 cost types operational (including collateral) - COMPLETE
- ❌ Can query per-agent costs via `/simulations/{id}/costs` - API endpoint missing
- ❌ Can query system-wide metrics via `/simulations/{id}/metrics` - API endpoint missing
- ❌ Prometheus `/metrics` endpoint operational - Not yet implemented

### 4.5 Phase 10: Data Persistence (Weeks 5-7) ✅ **COMPLETE**

**Goal**: Implement DuckDB-based persistence for simulation data with schema-as-code management

**Status**: 100% complete - All phases implemented with 71/71 tests passing

**Implementation**: See [docs/persistence_implementation_plan.md](persistence_implementation_plan.md) for complete specification

**Rationale**: This phase is positioned **after** Phase 8 (Cost Model) and **before** Phase 11 (LLM Manager) because:
1. Phase 8 cost data needs to be persisted for historical analysis
2. Phase 11 LLM Manager **requires** persistence infrastructure:
   - Shadow replay needs historical episode storage
   - Policy evolution tracking requires database (store v23 → v24 diffs)
   - Monte Carlo validation samples from episode database
   - KPI comparison (old policy vs. new policy) queries stored metrics

**Core Innovation**: Pydantic models as single source of truth for database schema. DDL auto-generated, migrations automated, runtime validation prevents schema drift.

**MANDATORY DAILY PERSISTENCE**: At the end of each simulated day, the system automatically persists:
- All transaction records (arrival, settlement, status, costs)
- Daily agent metrics (balance stats, queue sizes, transaction counts)
- Policy snapshots (if policies changed)
- Simulation progress and metadata

This is **not optional** - persistence is required for research reproducibility and enables all Phase 11 (LLM Manager) functionality.

#### Implementation Phases - ALL COMPLETE ✅

**Phase 10.1: Infrastructure Setup** ✅ COMPLETE (10 tests passing)

**Deliverables**:
- ✅ DuckDB + Polars dependencies added to `pyproject.toml`
- ✅ Pydantic models for all 6 tables (simulations, simulation_runs, transactions, daily_agent_metrics, policy_snapshots, simulation_checkpoints)
- ✅ DDL auto-generator (Pydantic → SQL CREATE TABLE statements)
- ✅ Migration system (versioned SQL files, automatic application)
- ✅ CLI commands: `payment-sim db init`, `db migrate`, `db validate`, `db create-migration`, `db list`

**Completed Modules**:
1. ✅ `api/payment_simulator/persistence/` module:
   - ✅ `models.py` - Pydantic schemas with table metadata
   - ✅ `schema_generator.py` - Auto-generate DDL from models
   - ✅ `migrations.py` - Migration manager class
   - ✅ `connection.py` - Database manager with validation
   - ✅ `queries.py` - Pre-built analytical queries
   - ✅ `writers.py` - Batch write helpers
2. ✅ `cli/commands/db.py` for database management commands

**Test Coverage**: 10/10 tests passing

---

**Phase 10.2: Transaction Batch Writes** ✅ COMPLETE (9 tests passing)

**Deliverables**:
- ✅ Rust FFI method: `get_transactions_for_day(day: usize) -> Vec<Dict>` - implemented in `backend/src/ffi/orchestrator.rs`
- ✅ Python batch write integration using Polars DataFrames
- ✅ End-of-day persistence hook in simulation loop
- ✅ Zero-copy Arrow integration (Polars → DuckDB)

**Completed Implementation**:
1. ✅ **Rust FFI** (`backend/src/ffi/orchestrator.rs:313-329`):
   ```rust
   fn get_transactions_for_day(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
       let transactions = self.inner.get_transactions_for_day(day);
       let simulation_id = self.inner.simulation_id();
       let ticks_per_day = self.inner.ticks_per_day();

       let py_list = PyList::empty(py);
       for tx in transactions {
           let tx_dict = transaction_to_py(py, tx, &simulation_id, ticks_per_day)?;
           py_list.append(tx_dict)?;
       }
       Ok(py_list.into())
   }
   ```

2. ✅ **Python Integration** (daily persistence workflow):
   ```python
   import polars as pl
   from payment_simulator.persistence import DatabaseManager

   db_manager = DatabaseManager('simulation_data.db')

   for day in range(num_days):
       for tick in range(ticks_per_day):
           orch.tick()

       # MANDATORY: Persist at end of each day
       daily_txs = orch.get_transactions_for_day(day)
       if daily_txs:
           df = pl.DataFrame(daily_txs)
           db_manager.conn.execute("INSERT INTO transactions SELECT * FROM df")
   ```

**Performance Validated**:
- ✅ 40K transaction batch write completes in <100ms
- ✅ Data survives process restart (query transactions from previous run)
- ✅ Determinism preserved (same seed → same persisted transactions)
- ✅ Zero-copy performance (Polars → DuckDB via Arrow)

**Test Coverage**: 9/9 tests passing

---

**Phase 10.3: Agent Metrics Collection** ✅ COMPLETE (9 tests passing)

**Deliverables**:
- ✅ Rust FFI method: `get_daily_agent_metrics(day: usize) -> Vec<Dict>` - implemented
- ✅ Daily metrics tracking in Rust orchestrator
- ✅ Batch write for agent snapshots
- ✅ Comprehensive collateral tracking (posted, capacity, costs)

**Completed Implementation**:
1. ✅ **Rust FFI** (`backend/src/ffi/orchestrator.rs:331-369`):
   - ✅ `DailyMetricsCollector` tracks during tick loop:
     - ✅ `min_balance` / `max_balance` (updated on every balance change)
     - ✅ `peak_overdraft` (max negative balance)
     - ✅ `queue1_peak_size` (max queue size during day)
     - ✅ Transaction counts (arrivals, settlements, drops, sent, received)
     - ✅ Cost accumulations (liquidity, delay, split, deadline, collateral costs)
     - ✅ Collateral fields (posted, capacity, peak posted, num posts/withdrawals)
   - ✅ Collector resets at start of each day

2. ✅ **Python Integration** (mandatory daily persistence):
   ```python
   # MANDATORY: Persist agent metrics at end of each day
   daily_metrics = orch.get_daily_agent_metrics(day)
   if daily_metrics:
       df = pl.DataFrame(daily_metrics)
       db_manager.conn.execute("INSERT INTO daily_agent_metrics SELECT * FROM df")
   ```

**Validated Queries**:
- ✅ Agent metrics match tick-by-tick accumulated values
- ✅ Can query: "BANK_A's peak overdraft on day 5 of run X"
- ✅ Fast analytical queries without scanning all transactions
- ✅ Full collateral lifecycle tracking

**Test Coverage**: 9/9 tests passing

---

**Phase 10.4: Policy Snapshot Tracking** ✅ COMPLETE (13 tests passing)

**Deliverables**:
- ✅ Policy snapshot records in database
- ✅ Integration with Phase 9 DSL (track policy file changes)
- ✅ SHA256 hashing for deduplication
- ✅ Policy provenance queries ("what policy was agent X using on day Y?")

**Completed Implementation**:
1. ✅ **Policy Recording** - Captures snapshots at:
   - ✅ Simulation initialization (initial policies)
   - ✅ Policy changes mid-simulation (manual or LLM-managed)
   - ✅ End-of-day (if policy changed during day)

2. ✅ **Database Storage** (`policy_snapshots` table):
   - ✅ `simulation_id` - Links to parent simulation
   - ✅ `agent_id` - Which agent owns this policy
   - ✅ `snapshot_day` / `snapshot_tick` - When snapshot taken
   - ✅ `policy_hash` - SHA256 of JSON content
   - ✅ `policy_json` - Full policy tree as JSON
   - ✅ `created_by` - 'init', 'manual', 'llm', 'scheduled'
   - ✅ `description` - Optional notes about the change

3. ✅ **Policy Provenance Query** (`queries.py:get_policy_at_day()`):
   ```python
   # Query: "What policy was BANK_A using on day 5?"
   policy = get_policy_at_day(
       conn=db_manager.conn,
       simulation_id="sim-001",
       agent_id="BANK_A",
       day=5
   )
   # Returns: Most recent policy snapshot on or before day 5
   ```

**Validated Capabilities**:
- ✅ Can reconstruct: "what policy was BANK_A using on day 3 of run X?"
- ✅ Hash-based deduplication avoids storing identical policies multiple times
- ✅ Provenance tracking: policy v23 → v24 change logged with timestamp
- ✅ Attribution: Track who created policy (human, LLM, system)

**Test Coverage**: 13/13 tests passing

---

**Phase 10.5: Query Interface & Analytics** ✅ COMPLETE (15 tests passing)

**Deliverables**:
- ✅ Pre-defined analytical query functions (9 queries implemented)
- ✅ CLI query commands integrated
- ✅ Polars DataFrame integration (zero-copy Arrow)
- ✅ Simulation comparison queries
- ✅ Policy provenance tracking

**Completed Implementation**:
1. ✅ **Query Module** (`api/payment_simulator/persistence/queries.py:396-743`) - **9 functions implemented**:
   - ✅ `list_simulations(status=None)` - List all simulation runs
   - ✅ `get_simulation_summary(sim_id)` - High-level simulation metadata
   - ✅ `get_agent_daily_metrics(sim_id, agent_id)` - Daily agent performance
   - ✅ `get_transactions(sim_id, filters)` - Query transactions with filters
   - ✅ `get_transaction_statistics(sim_id)` - Aggregate transaction stats
   - ✅ `compare_simulations(sim_id1, sim_id2)` - Side-by-side comparison
   - ✅ `compare_agent_performance(sim1, sim2, agent)` - Agent-specific comparison
   - ✅ `get_agent_policy_history(sim_id, agent_id)` - Policy evolution timeline
   - ✅ `get_policy_at_day(sim_id, agent_id, day)` - Policy provenance query

   Example usage:
   ```python
   # Query agent performance across simulation
   metrics = get_agent_daily_metrics(
       conn=db_manager.conn,
       simulation_id="sim-001",
       agent_id="BANK_A"
   )  # Returns Polars DataFrame with daily balance, costs, queue sizes

   # Compare two simulations
   comparison = compare_simulations(
       conn=db_manager.conn,
       simulation_id_1="sim-001",
       simulation_id_2="sim-002"
   )  # Returns side-by-side KPI comparison

   # Policy provenance: "What policy was BANK_A using on day 5?"
   policy = get_policy_at_day(
       conn=db_manager.conn,
       simulation_id="sim-001",
       agent_id="BANK_A",
       day=5
   )  # Returns policy JSON and metadata
   ```

2. ✅ **CLI Integration** - Ready for `cli/commands/query.py`:
   ```bash
   # Commands ready to implement:
   payment-sim query list-runs
   payment-sim query show-run <sim_id>
   payment-sim query agent-metrics <sim_id> <agent_id>
   payment-sim query compare <sim_id1> <sim_id2>
   payment-sim query policy-history <sim_id> <agent_id>
   ```

**Validated Performance**:
- ✅ Can query 250M transactions in <1 second for aggregated metrics (columnar storage)
- ✅ Polars DataFrames integrate seamlessly with Jupyter notebooks
- ✅ Zero-copy Arrow integration (Polars ↔ DuckDB)
- ✅ Can export to Parquet for external tools (R, Tableau, Python)

**Test Coverage**: 15/15 tests passing

---

#### Phase 10.6: Save/Load Checkpoints ✅ COMPLETE (15 tests passing)

**Deliverables**:
- ✅ Complete orchestrator state serialization
- ✅ Save checkpoint to database (`simulation_checkpoints` table)
- ✅ Load checkpoint and restore orchestrator
- ✅ Determinism validation (resume produces identical results)
- ✅ Config hash verification (prevent incompatible resumes)
- ✅ CLI integration (`payment-sim checkpoint save/load/list`)

**Completed Implementation**:
- ✅ **FFI Methods** (`backend/src/ffi/orchestrator.rs`):
  - ✅ `save_checkpoint()` - Serialize full orchestrator state
  - ✅ `from_checkpoint()` - Restore orchestrator from checkpoint
- ✅ **Persistence Layer** (`api/payment_simulator/persistence/checkpoint.py`):
  - ✅ Save checkpoint with metadata (tick, day, type, description)
  - ✅ List checkpoints for simulation
  - ✅ Load checkpoint with validation
  - ✅ Delete old checkpoints
- ✅ **CLI Commands** (`api/payment_simulator/cli/commands/checkpoint.py`):
  - ✅ `payment-sim checkpoint save <sim_id> --description "reason"`
  - ✅ `payment-sim checkpoint load <checkpoint_id>`
  - ✅ `payment-sim checkpoint list <sim_id>`

**Test Coverage**: 15/15 tests passing

---

#### Summary: Phase 10 Complete ✅

**Total Test Coverage**: 71/71 tests passing (100% success rate)

**All Components Delivered**:
- ✅ Phase 10.1: Infrastructure (10 tests)
- ✅ Phase 10.2: Transaction Batch Writes (9 tests)
- ✅ Phase 10.3: Agent Metrics Collection (9 tests)
- ✅ Phase 10.4: Policy Snapshot Tracking (13 tests)
- ✅ Phase 10.5: Query Interface & Analytics (15 tests)
- ✅ Phase 10.6: Save/Load Checkpoints (15 tests)

**Database Schema** (6 tables):
1. ✅ `simulations` - Simulation run metadata
2. ✅ `simulation_runs` - Legacy support (to be migrated)
3. ✅ `transactions` - All transaction records
4. ✅ `daily_agent_metrics` - Daily agent snapshots
5. ✅ `policy_snapshots` - Policy version tracking
6. ✅ `simulation_checkpoints` - Save/load state

**Performance Validated**:
- ✅ Daily transaction batch write: <100ms (40K transactions)
- ✅ Daily metrics batch write: <20ms (200 agent records)
- ✅ Analytical queries: <1s (250M transaction aggregates)
- ✅ Database file size: <10 GB (200 runs, compressed columnar)

#### Dependencies

**Required**:
- ✅ Phase 8 cost calculations (cost data to persist) - COMPLETE
- ✅ Phase 9 DSL (policy JSON files to track) - COMPLETE

**Enables**:
- **Phase 11 (LLM Manager)** - Critical dependency (NOW READY):
  - ✅ Shadow replay queries: `SELECT * FROM simulations WHERE config_hash = ?`
  - ✅ Policy comparison: `SELECT * FROM daily_agent_metrics WHERE simulation_id IN (?, ?)`
  - ✅ Episode sampling: Random sample from `simulations` table
  - ✅ Policy provenance: `SELECT * FROM policy_snapshots WHERE agent_id = ? ORDER BY day`

**Synergy**:
- Phase 14 (Production) can query database for frontend visualizations
- Research & publication: Rich dataset for analysis (200+ runs × 1.2M transactions = 240M+ records)

#### Testing Strategy

**Unit Tests**:
- Schema validation (Pydantic model → DDL → validation)
- Migration system (create, apply, rollback)
- Query correctness (aggregations match expected results)

**Integration Tests**:
- End-to-end: Run 2-agent, 2-day simulation, verify all data persisted
- Performance: 40K transaction insert in <100ms
- Determinism: Same seed produces identical database records

**Load Tests**:
- 200 agents × 10 days × 200 ticks/day simulation
- Verify database file size <10 GB (compressed columnar storage)
- Analytical query on 240M transactions completes in <1s

#### Success Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Daily transaction batch write | <100ms | 40K transactions, non-blocking |
| Daily metrics batch write | <20ms | 200 agent records |
| Analytical query (1M txs) | <1s | Interactive analysis |
| Database file size (200 runs) | <10 GB | Columnar compression |
| Schema change workflow | <5 min | Pydantic update → migration → apply |

**Estimated Effort**: 8-12 days (as detailed in `persistence_implementation_plan.md`)

---

> **Execution Order Note**: Phase 17 (BIS AI Cash Management, section 4.6 below) is the **immediate next priority**. Sections 4.7-4.10 follow after Phase 17 completion.

---

### 4.7 Phase 11: LLM Manager Integration (Weeks 10-12) ❌ **NOT STARTED**

**Goal**: Asynchronous policy evolution via LLM

**Dependencies**:
- Phase 9 DSL infrastructure is **complete** (expression evaluator, JSON trees, validation - see Part III Section 4.3)
- Phase 10 Persistence **required** (provides episode storage for shadow replay, policy version tracking)

**Note**: This phase builds the LLM-driven learning loop that uses the Phase 9 DSL and Phase 10 persistence infrastructure.

#### LLM Manager Service
**Deliverable**: Separate service for policy improvement

**Architecture**:
- **Decoupled**: Runs independently of simulator
- **Asynchronous**: Simulator never blocks on LLM calls
- **Episode-Driven**: Improves policies between simulation runs

**Tasks**:
1. **Policy Proposal Generation**:
   - Input: Episode history (seeds, KPIs, opponent policies)
   - LLM prompt: "Improve policy to reduce cost while maintaining throughput"
   - Output: Candidate policy (JSON DSL)

2. **Automated Validation**:
   - Schema validation (syntax correctness)
   - Property tests (no negative amounts, valid actions)
   - Shadow replay (Monte Carlo with sampled opponents)
   - Guardrails (KPI deltas within acceptable range)

3. **Deployment Pipeline**:
   - Git commit for approved policy
   - Tag with version (e.g., `agent_A_policy_v23`)
   - Rollback mechanism (revert to previous commit)

4. **Feedback Loop**:
   - Collect episode results with new policy
   - Update LLM context with outcomes
   - Iterate improvement proposals

**Testing**:
- LLM manager isolation (mock responses)
- Validation pipeline (reject malformed policies)
- Shadow replay correctness
- Full loop (propose → validate → deploy → collect results)

#### Shadow Replay System
**Deliverable**: Re-evaluate historical episodes with new policies

**Tasks**:
1. **Episode Collection** (uses Phase 10 persistence):
   - Query `simulations` table for historical episodes
   - Load deterministic seeds + configs from `config_archive`
   - Track performance metrics from `daily_agent_metrics` table
   - Sample episodes from database for Monte Carlo validation

2. **Replay Engine**:
   - Load historical episode (seed + config)
   - Swap in new policy for target agent
   - Re-run simulation deterministically
   - Collect KPIs for comparison

3. **Monte Carlo Validation**:
   - Sample opponent behaviors from recent episodes
   - Run candidate policy against diverse opponents
   - Estimate expected KPI improvements
   - Calculate confidence intervals

4. **Guardrail Enforcement**:
   - Check KPI deltas against thresholds (e.g., <10% cost increase)
   - Flag regressions or anomalies
   - Automatic rejection of unsafe policies

#### Multi-Agent Learning
**Deliverable**: Simultaneous policy evolution

**Challenges**:
- Non-stationary environment (opponents evolve)
- Credit assignment (who caused outcome?)
- Exploration vs. exploitation

**Approach**:
1. **Self-Play**:
   - Multiple agents improve simultaneously
   - Each sees others as evolving opponents
   - Sample opponent behaviors from recent episodes

2. **Population-Based Training**:
   - Maintain policy population per agent
   - Select diverse opponents for shadow replay
   - Promote successful policies

3. **Convergence Detection**:
   - Monitor KPI stability over episodes
   - Flag oscillations or divergence
   - Human-in-loop review for anomalies

**Testing**:
- Multi-agent learning scenarios (2-bank, 4-bank)
- Convergence validation (stable equilibrium)
- Robustness tests (shocks during learning)

**Success Criteria**:
- LLM manager can propose valid policy changes
- Shadow replay validates without false positives
- Policies improve over episodes (lower costs or higher throughput)
- Learning converges to stable strategies

**Estimated Effort**: 3 weeks

### 4.8 Phase 12: Multi-Rail & Cross-Border (Weeks 13-14) ❌ **NOT STARTED**

**Status**: 0% complete - All work is future

**Goal**: Support multiple settlement rails and currency corridors

**Current Limitation**: System only supports:
- Single RTGS rail (no DNS, no ACH)
- Single currency (i64 cents, no multi-currency)
- Domestic payments only (no cross-border)
- One central RTGS queue (Queue 2)

#### Multi-Rail Architecture
**Deliverable**: RTGS + DNS (Deferred Net Settlement) rail

**Concepts**:
- **RTGS**: Real-time gross (individual), immediate finality
- **DNS**: Batch net (bilateral), periodic settlement windows

**Tasks**:
1. **Rail Abstraction**:
   - `SettlementRail` trait with `submit()`, `process()` methods
   - Rail-specific configs (RTGS: LSM enabled; DNS: batch times)
   - Rail selection in transaction submission

2. **DNS Implementation**:
   - Accumulate bilateral positions (A→B net)
   - Periodic settlement windows (e.g., every 50 ticks)
   - Batch processing with netting

3. **Cross-Rail Transfers**:
   - Move liquidity between RTGS and DNS accounts
   - Cost implications (DNS cheaper but delayed)
   - Strategic rail selection

**Testing**:
- RTGS + DNS coexistence tests
- Netting correctness (bilateral positions)
- Liquidity transfers between rails

#### Cross-Border Corridors
**Deliverable**: Multi-currency nostro accounts

**Tasks**:
1. **Currency Model**:
   - Multiple currencies (USD, EUR, GBP, SEK)
   - Per-currency nostro accounts
   - Exchange rate management (static or dynamic)

2. **Correspondent Banking**:
   - Nostro prefunding (agents fund foreign currency accounts)
   - Cross-border payment routing (via correspondent)
   - Funding costs (nostro opportunity cost)

3. **FX Settlement**:
   - CLS-style PvP (Payment vs. Payment) timing
   - Simultaneous multi-leg settlement

**Testing**:
- Cross-border payment routing
- Multi-currency balance conservation
- PvP settlement atomicity

**Success Criteria**:
- Can configure RTGS + DNS rails
- DNS batch netting works correctly
- Cross-border payments settle via nostros
- Multi-currency accounting is correct

**Estimated Effort**: 2 weeks (as originally planned)

### 4.9 Phase 13: Shock Scenarios & Resilience (Week 15) ❌ **NOT STARTED**

**Goal**: Test system under stress conditions

#### Shock Module
**Deliverable**: Configurable shocks at runtime

**Shock Types**:
1. **Liquidity Squeeze**:
   - Reduce opening balances by X%
   - Increase collateral costs by Y%
   - Observe gridlock incidence, LSM efficacy

2. **Operational Outage**:
   - Disable LSM for N ticks
   - Simulate message processing capacity limit
   - Measure queue buildup and recovery time

3. **Counterparty Stress**:
   - Specific bank loses access to credit
   - Large idiosyncratic outflow (margin call)
   - Bilateral cap reduction (credit concern)

4. **Fee Regime Change**:
   - Switch overdraft pricing mid-day
   - Observe behavioral response (hoarding vs. release)

5. **Deadline Cascade**:
   - Concentrated deadline cluster (e.g., noon PvP window)
   - Measure priority escalation and LSM load

**Implementation**:
- `ShockSchedule` in config (tick, type, parameters)
- Runtime shock injection (via orchestrator)
- Shock-aware metrics (pre/during/post comparison)

**Testing**:
- Each shock type in isolation
- Combined shocks (liquidity squeeze + outage)
- Recovery validation (system returns to normal)

**Success Criteria**:
- Can inject shocks at specified ticks
- Metrics show expected responses
- System recovers after shock removal

**Estimated Effort**: 1 week

### 4.6 Phase 17: BIS AI Cash Management Compatibility (Weeks 8-9) ❌ **NOT STARTED** ← **NEXT**

**Goal**: Enable SimCash to run experiments matching BIS Working Paper 1310 ("AI agents for cash management in payment systems") by adding priority-differentiated delay costs, explicit liquidity allocation decisions, and per-band arrival functions.

**Background**: BIS Working Paper 1310 presents a simplified RTGS model for testing AI agent cash management decisions. SimCash's sophisticated TARGET2-aligned model requires specific enhancements to support the BIS experimental framework while maintaining backwards compatibility.

**Research Documentation**: See `docs/research/bis/` for:
- `bis-simcash-research-briefing.md` - Full comparison and configuration guide
- `bis-model-enhancements-tdd-implementation.md` - Detailed TDD implementation plan

#### Enhancement 17.1: Priority-Based Delay Cost Multipliers

**Purpose**: Different delay costs for urgent vs. normal payments (BIS uses 1.5% for urgent, 1.0% for normal)

**Current Limitation**: Single `delay_cost_per_tick_per_cent` applies uniformly to all transactions regardless of priority.

**Design**:
```rust
pub struct PriorityDelayMultipliers {
    /// Multiplier for urgent priority (8-10). Default: 1.5
    pub urgent_multiplier: f64,
    /// Multiplier for normal priority (4-7). Default: 1.0
    pub normal_multiplier: f64,
    /// Multiplier for low priority (0-3). Default: 1.0
    pub low_multiplier: f64,
}
```

**Configuration**:
```yaml
cost_rates:
  delay_cost_per_tick_per_cent: 0.01     # Base rate
  priority_delay_multipliers:             # NEW
    urgent_multiplier: 1.5               # Urgent: 1.5% per tick
    normal_multiplier: 1.0               # Normal: 1.0% per tick
    low_multiplier: 0.5                  # Low: 0.5% per tick (optional)
```

**Implementation**:
1. Add `PriorityDelayMultipliers` struct to `CostRates` (backend/src/orchestrator/engine.rs)
2. Add `PriorityBand` enum with `get_priority_band(priority: u8)` helper
3. Modify delay cost calculation to apply priority multiplier
4. Add `priority_delay_multiplier_for_this_tx` to policy EvalContext
5. Parse from config in FFI layer
6. Persist multipliers in cost events for replay identity

**Critical Invariants**:
- Money remains i64 (multiplier applied, result cast to i64)
- Backwards compatible: No multipliers configured = uniform delay cost
- Deterministic: Same priority always gets same multiplier

**Testing**:
- Unit tests: Priority band classification, multiplier application
- Integration tests: Urgent vs. normal cost difference in simulation
- Replay identity: Events contain applied multiplier for reconstruction

#### Enhancement 17.2: Liquidity Pool and Allocation

**Purpose**: Agents decide how much liquidity to allocate from an external pool at day start (BIS Period 0 decision)

**Current Limitation**: Agents have fixed `opening_balance`; no allocation decision with opportunity cost.

**Conceptual Distinction**:
| Aspect | Liquidity Allocation (NEW) | Collateral Posting (Existing) |
|--------|---------------------------|------------------------------|
| **Provides** | Positive cash balance | Credit capacity (overdraft) |
| **Effect** | `balance += allocated` | `credit_limit += posted * (1-haircut)` |
| **Timing** | Day start (Step 0) | Step 1.5 (before settlements) |
| **Cost** | `liquidity_cost_per_tick_bps` | `collateral_cost_per_tick_bps` |

**Configuration**:
```yaml
agent_configs:
  - id: BANK_A
    liquidity_pool: 2_000_000              # Total available external liquidity
    liquidity_allocation_fraction: 0.5     # Fixed: Allocate 50% at day start
    # OR policy-driven:
    liquidity_allocation_tree: {...}       # Policy tree for dynamic allocation

cost_rates:
  liquidity_cost_per_tick_bps: 15          # Opportunity cost of allocated liquidity
```

**Lifecycle Flow**:
```
Day Start (Tick 0):
  Step 0 (NEW): Liquidity Allocation
    For each agent with liquidity_pool:
      1. Evaluate liquidity_allocation_tree (or use fixed fraction)
      2. Calculate: allocated = pool × fraction
      3. Add to opening_balance: balance += allocated
      4. Track for cost accrual: allocated_liquidity = allocated

  Step 1: Normal tick processing begins...

Throughout Day:
  Accrue liquidity cost: cost += allocated_liquidity × liquidity_cost_per_tick_bps
```

**Implementation**:
1. Add `LiquidityPoolConfig` struct (pool, fraction or tree)
2. Add `liquidity_allocation_tree` policy evaluation (new tree type)
3. Add `Step0_LiquidityAllocation` to tick loop (before arrivals)
4. Add `LiquidityAllocation` event type with all fields
5. Track `allocated_liquidity` in agent state for cost accrual
6. Add `liquidity_cost_per_tick_bps` to CostRates
7. Persist allocation decision for replay identity

**Critical Invariants**:
- Allocation happens once at day start (not repeatable mid-day)
- Cannot allocate more than pool amount
- Liquidity cost distinct from collateral cost
- Balance changes are i64 (no floats)

**Testing**:
- Allocation fractions: 0%, 50%, 100%
- Policy-driven allocation with different tree conditions
- Cost accrual: Verify liquidity cost separate from collateral cost
- Multi-day: Fresh allocation each day
- Replay identity: Allocation events reconstruct correctly

#### Enhancement 17.3: Per-Band Arrival Functions

**Purpose**: Different arrival characteristics (rate, amount, deadline) per priority band

**Current Limitation**: Single `arrival_config` with one `rate_per_tick` and `amount_distribution` for all priorities.

**BIS Model Insight**: Urgent payments are rare but large; normal payments are common and smaller.

**Configuration**:
```yaml
agent_configs:
  - id: BANK_A
    # NEW: Per-band arrival configuration
    arrival_bands:
      urgent:                              # Priority 8-10
        rate_per_tick: 0.1                 # Rare
        amount_distribution:
          type: log_normal
          mean: 1_000_000                  # Large ($10k average)
          std_dev: 0.5
        deadline_offset:
          min_ticks: 5
          max_ticks: 15                    # Tight deadlines

      normal:                              # Priority 4-7
        rate_per_tick: 3.0                 # Common
        amount_distribution:
          type: log_normal
          mean: 50_000                     # Medium ($500 average)
          std_dev: 0.8
        deadline_offset:
          min_ticks: 20
          max_ticks: 50

      low:                                 # Priority 0-3
        rate_per_tick: 5.0                 # Frequent
        amount_distribution:
          type: log_normal
          mean: 10_000                     # Small ($100 average)
          std_dev: 0.6
        deadline_offset:
          min_ticks: 40
          max_ticks: 80                    # Relaxed deadlines
```

**Implementation**:
1. Add `ArrivalBandConfig` struct (rate, amount_distribution, deadline_offset, priority_range)
2. Add `ArrivalBandsConfig` with urgent/normal/low bands
3. Modify arrival generator to sample from each band independently
4. Use Poisson sampling per band with band-specific rate
5. Assign priority within band range (uniform or configurable)
6. Backwards compatible: `arrival_config` still works, `arrival_bands` is alternative

**Backwards Compatibility**:
```yaml
# EXISTING (still works)
arrival_config:
  rate_per_tick: 5.0
  amount_distribution: {...}
  priority_distribution: {...}

# NEW ALTERNATIVE
arrival_bands:
  urgent: {...}
  normal: {...}
  low: {...}
```

**Critical Invariants**:
- RNG seed must be persisted after EACH band's Poisson sample
- Amount distributions must produce i64 cents
- Priority assigned within band range (8-10 for urgent, 4-7 for normal, 0-3 for low)
- Deterministic: Same seed → same arrivals across all bands

**Testing**:
- Single band enabled: Only urgent arrivals
- All bands enabled: Mixed arrival stream
- Rate verification: Average arrivals match configured rates
- Amount verification: Distribution matches configured parameters
- Determinism: 10 runs with same seed produce identical arrivals
- Replay identity: Arrival events contain band metadata

#### BIS Compatibility Mode

When running BIS-style experiments, disable SimCash features not present in the BIS model:

```yaml
# BIS Compatibility Template
lsm_config:
  enable_bilateral: false
  enable_cycles: false

algorithm_sequencing: false
entry_disposition_offsetting: false

priority_escalation:
  enabled: false

cost_rates:
  delay_cost_per_tick_per_cent: 0.01
  priority_delay_multipliers:
    urgent_multiplier: 1.5
    normal_multiplier: 1.0
  eod_penalty_per_transaction: 0
  deadline_penalty: 0
  collateral_cost_per_tick_bps: 0
  overdue_delay_multiplier: 1.0

agent_configs:
  - id: BANK_A
    credit_limit: 0
    max_collateral_capacity: 0
    liquidity_pool: 2_000_000
    arrival_bands:
      urgent: {...}
      normal: {...}
```

See `docs/research/bis/bis-simcash-research-briefing.md` Part 6 for complete BIS compatibility checklist.

#### Success Criteria

| Metric | Target | Rationale |
|--------|--------|-----------|
| Priority multiplier accuracy | ±0.01% | Integer arithmetic precision |
| Liquidity allocation at day start | 100% reliable | Must happen before tick 1 |
| Per-band arrival rates | ±5% of configured | Poisson variance acceptable |
| Backwards compatibility | 100% | Existing configs unchanged |
| Replay identity | Byte-for-byte | All events self-contained |
| BIS Scenario 1 runnable | ✓ | Precautionary liquidity decision |
| BIS Scenario 2 runnable | ✓ | Priority-based delay costs |
| Monte Carlo support | ✓ | Different seeds, same config |

#### Testing Strategy

**TDD Implementation Procedure**: Follow strict Red-Green-Refactor cycle as documented in `docs/research/bis/bis-model-enhancements-tdd-implementation.md`.

**Test Categories** (per enhancement):
1. Configuration parsing tests (7 scenarios each)
2. Rust unit tests (boundary values, precision, determinism)
3. Python integration tests (FFI round-trip, multi-tick, multi-agent)
4. Replay identity tests (event fields, database persistence)
5. BIS scenario tests (runnable experiments)

**Estimated Test Count**: ~50 new tests across all three enhancements

**Estimated Effort**: 2 weeks (1 week for Enhancements 17.1-17.2, 1 week for 17.3 + integration)

### 4.10 Phase 14: Production Readiness (Weeks 16-18) ❌ **NOT STARTED**

**Goal**: Observability, performance, and user experience

#### WebSocket Streaming
**Deliverable**: Real-time state updates to clients

**Tasks**:
1. **Event Bus**:
   - Publish tick events (arrivals, settlements, cost updates)
   - Subscribe pattern (clients filter event types)
   - Buffering for slow clients

2. **WebSocket Endpoint**:
   - `WS /websocket` — real-time event stream
   - JSON-encoded events with timestamps
   - Heartbeat/keepalive mechanism

3. **Frontend Integration**:
   - React context for WebSocket connection
   - Live update of agent cards, transaction lists
   - Real-time charts (throughput, queues, costs)

**Testing**:
- WebSocket connection stability
- Event delivery under load
- Client disconnect/reconnect handling

#### React Frontend
**Deliverable**: Web UI for simulation control and visualization

**Components**:
1. **Dashboard**:
   - Agent cards (balance, queue size, costs)
   - System-wide KPIs (throughput, peak debit)
   - Timeline chart (tick progress)

2. **Transaction List**:
   - Filterable/sortable table (by status, agent, amount)
   - Detail modal (full transaction attributes)
   - Submission form (manual transactions)

3. **Control Panel**:
   - Start/stop/reset buttons
   - Tick stepping (manual advance)
   - Speed control (auto-tick interval)

4. **Configuration Editor**:
   - YAML editor with validation
   - Save/load config files
   - Example configs (dropdown)

**Testing**:
- Component unit tests
- E2E tests (user flows)
- Responsive design validation

#### Observability & Logging
**Deliverable**: Production-grade logging and metrics

**Tasks**:
1. **Structured Logging**:
   - JSON logs with trace IDs
   - Log levels (DEBUG, INFO, WARN, ERROR)
   - Per-request context (simulation ID, tick)

2. **Metrics Export**:
   - Prometheus-compatible endpoint
   - Metrics: request rate, latency, tick duration, queue sizes
   - Grafana dashboard template

3. **Health Checks**:
   - Liveness probe (service responding)
   - Readiness probe (simulation ready)
   - Dependency checks (optional DB, cache)

4. **Performance Profiling**:
   - `cargo flamegraph` for Rust hot paths
   - Python profiler for API layer
   - Optimization based on profiling data

**Success Criteria**:
- Real-time updates work for 10+ concurrent clients
- Frontend displays all simulation state correctly
- Logs and metrics enable debugging
- Performance targets met (>1000 ticks/sec maintained)

**Estimated Effort**: 3 weeks

---

## Part V: Technical Architecture Details

### 5.1 Component Interaction Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         DEPLOYMENT LAYER                              │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │   React    │  │  FastAPI   │  │  LLM Mgr    │  │ Monitoring   │ │
│  │  Frontend  │  │   Server   │  │  Service    │  │  (Grafana)   │ │
│  └─────┬──────┘  └──────┬─────┘  └──────┬──────┘  └──────┬───────┘ │
│        │ WebSocket      │ REST/WS       │ gRPC           │ Metrics  │
└────────┼────────────────┼───────────────┼────────────────┼──────────┘
         │                │               │                │
┌────────┼────────────────┼───────────────┼────────────────┼──────────┐
│        │    PYTHON API LAYER (FastAPI)  │                │           │
│        │                │               │                │           │
│  ┌─────▼────────────────▼───┐   ┌──────▼──────┐  ┌──────▼────────┐ │
│  │ SimulationManager        │   │ PolicyMgr   │  │ MetricsStore  │ │
│  │ - Lifecycle (CRUD)       │   │ - Versioning│  │ - Aggregation │ │
│  │ - Config validation      │   │ - Rollback  │  │ - Streaming   │ │
│  │ - State snapshots        │   │ - A/B test  │  │ - Prometheus  │ │
│  └──────────┬───────────────┘   └─────────────┘  └───────────────┘ │
│             │                                                         │
│  ┌──────────▼────────────────────────────────────────────────────┐  │
│  │              FFI Wrapper (backends/rust_backend.py)          │  │
│  │  - Type conversion (Rust ↔ Python)                           │  │
│  │  - Error propagation (Result → Exception)                    │  │
│  │  - Memory safety (ownership tracking)                        │  │
│  └──────────┬────────────────────────────────────────────────────┘  │
│             │                                                         │
└─────────────┼─────────────────────────────────────────────────────────┘
              │
     ═════════▼═════════════
     ║  FFI BOUNDARY (PyO3) ║
     ═════════▼═════════════
              │
┌─────────────┼─────────────────────────────────────────────────────────┐
│        RUST CORE BACKEND (payment-simulator-core-rs)                  │
│             │                                                           │
│  ┌──────────▼──────────────────────────────────────────────────────┐  │
│  │                    Orchestrator Engine                          │  │
│  │  - 9-step tick loop coordinator                                │  │
│  │  - State transitions (Queue 1 → Queue 2 → Settled)            │  │
│  │  - Event generation & logging                                  │  │
│  └────┬──────────┬──────────┬──────────┬──────────┬───────────────┘  │
│       │          │          │          │          │                   │
│  ┌────▼────┐ ┌──▼──────┐ ┌─▼────────┐ ┌▼────────┐ ┌▼──────────────┐ │
│  │ Arrival │ │ Policy  │ │  RTGS    │ │  LSM    │ │ CostTracker  │ │
│  │   Gen   │ │  Engine │ │  Engine  │ │ Engine  │ │              │ │
│  └────┬────┘ └──┬──────┘ └─┬────────┘ └┬────────┘ └┬──────────────┘ │
│       │         │           │           │           │                │
│  ┌────▼─────────▼───────────▼───────────▼───────────▼──────────────┐ │
│  │                   SimulationState                                │ │
│  │  - Agents (balances, queues, credit limits)                     │ │
│  │  - Transactions (lifecycle, costs, splits)                      │ │
│  │  - RTGS queue (Queue 2)                                         │ │
│  │  - LSM state (bilateral ledger, cycle candidates)              │ │
│  │  - Time (tick, day)                                             │ │
│  │  - RNG (seeded xorshift64*, deterministic)                     │ │
│  └──────────────────────────────────────────────────────────────────┘ │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Data Flow for Single Tick

**Tick N Execution Sequence**:

```
1. Arrival Generation
   ├─ RNG.sample_poisson(rate) → arrival_count
   ├─ For each arrival:
   │  ├─ RNG.sample_distribution(type, params) → amount
   │  ├─ RNG.select_counterparty(weights) → dest_bank
   │  └─ Transaction.new(sender, dest, amount, deadline, priority)
   ├─ SimulationState.add_transactions(new_txs)
   └─ Agent.queue_outgoing(tx_ids) → Queue 1

2. Policy Evaluation
   ├─ For each agent with Queue 1 items:
   │  ├─ Policy.evaluate_queue(agent, state, tick) → Vec<ReleaseDecision>
   │  ├─ Process decisions:
   │  │  ├─ SubmitFull: Remove from Queue 1, add to pending submissions
   │  │  ├─ Hold(reason): Keep in Queue 1, log hold reason
   │  │  ├─ SubmitPartial(factor): Create split children, remove parent
   │  │  └─ Drop: Remove from Queue 1, apply deadline penalty
   │  └─ Update agent.last_decision_tick

3. Liquidity Decisions
   ├─ For each agent:
   │  ├─ Check liquidity_pressure()
   │  ├─ If needed: Agent.draw_credit(amount)
   │  └─ If excess: Agent.repay_credit(amount)

4. Transaction Splitting
   ├─ For each split decision:
   │  ├─ Validate eligibility (amount > threshold, factor <= max)
   │  ├─ Create N child transactions (inherit parent attributes)
   │  ├─ Apply split friction cost: cost += f_s × (N-1)
   │  └─ Add children to pending submissions

5. RTGS Submission
   ├─ For each pending transaction:
   │  ├─ RTGS.submit_transaction(tx, agent_balance, credit_limit)
   │  ├─ If balance + credit >= amount:
   │  │  ├─ Immediate settlement: debit sender, credit receiver
   │  │  └─ Update tx.status = Settled, tx.settlement_tick = N
   │  └─ Else:
   │     ├─ Add to Queue 2 (RTGS central queue)
   │     └─ Update tx.status = Pending (in Queue 2)

6. Queue 2 Processing (FIFO Retry)
   ├─ For each transaction in Queue 2:
   │  ├─ Check deadline: if tick > deadline → Drop, apply penalty
   │  ├─ Else: RTGS.try_settle(tx, agent_balance, credit_limit)
   │  ├─ If success: Settle, remove from Queue 2
   │  └─ Else: Remain in Queue 2 (retry next tick)

7. LSM Optimization
   ├─ LSM.run_lsm_pass(Queue 2, agents, config):
   │  ├─ Iteration 1: Bilateral offsetting
   │  │  ├─ For each pair (i, j):
   │  │  │  ├─ Find A→B and B→A transactions
   │  │  │  ├─ If amounts match: Settle both with zero liquidity
   │  │  │  └─ Else: Net settlement (reduce larger, settle smaller)
   │  │  └─ Remove settled transactions from Queue 2
   │  ├─ Iteration 2+: Cycle detection
   │  │  ├─ Build payment graph from Queue 2
   │  │  ├─ DFS to detect cycles (A→B→C→...→A)
   │  │  ├─ For each cycle: Calculate bottleneck amount
   │  │  ├─ Settle cycle with net-zero liquidity (or minimal partial)
   │  │  └─ Remove settled/reduced transactions from Queue 2
   │  └─ Repeat until no progress (typically 2-3 iterations)

8. Cost Accrual
   ├─ For each agent:
   │  ├─ Liquidity cost: c_L × max(0, -balance) × (1/ticks_per_day)
   │  ├─ Collateral cost: c_C × collateral × (1/ticks_per_day)
   │  └─ For each tx in Queue 1:
   │     └─ Delay cost: p_k × (tick - arrival_tick)
   ├─ Accumulate to agent.total_cost
   └─ Accumulate to state.system_total_cost

9. Metrics Update
   ├─ Calculate throughput: settled_value / arrived_value
   ├─ Update queue statistics (sizes, ages)
   ├─ Track peak net debits (max negative balance)
   ├─ LSM efficacy: (bilateral_count, cycle_count, liquidity_saved)
   └─ Emit tick event (for WebSocket subscribers)

10. Time Advancement
    └─ TimeManager.advance_tick() → tick = N+1
```

### 5.3 Memory Management & Safety

#### Rust Ownership Model
- **SimulationState**: Owns all agents, transactions, queues
- **Orchestrator**: Owns SimulationState, RNG, time manager
- **No shared mutable state**: All mutations go through Orchestrator methods
- **No reference cycles**: State graph is acyclic (transactions ref agent IDs, not pointers)

#### FFI Boundary Safety
1. **Rust→Python**:
   - Clone data to Python-owned dictionaries (no shared references)
   - Return by value (Python gets copy, Rust retains ownership)
   - Never return raw pointers or references

2. **Python→Rust**:
   - Validate all inputs before crossing boundary
   - Convert to Rust-owned types (no Python object retention)
   - Use `Result<T, E>` for all fallible operations

3. **Memory Leak Prevention**:
   - No `Rc<RefCell<>>` across FFI (ownership must be clear)
   - PyO3 handles Python reference counting
   - Rust drops state when simulation deleted (RAII)

#### Testing Strategy
- **Valgrind**: Run FFI tests under memcheck (detect leaks)
- **ASAN/MSAN**: Sanitizers in CI (catch use-after-free, uninitialized memory)
- **Stress tests**: 10,000 tick simulations (verify no accumulation)

### 5.4 Determinism Guarantees

**Requirement**: Identical seed → identical outcomes (every time, every platform)

**Implementation**:
1. **Single RNG Source**: All randomness via `RngManager.xorshift64*`
2. **Explicit Seeding**: Every stochastic operation seeds from RNG
3. **No System Time**: Forbidden (use tick counter for time)
4. **No Floats in Core Logic**: Avoid IEEE rounding inconsistencies (money as `i64`)
5. **Stable Iteration Order**: Use `Vec` (not `HashMap`) for deterministic ordering

**Testing**:
- Replay tests: Run same seed 100 times, assert all outputs identical
- Cross-platform tests: Run on Linux/macOS/Windows, compare outputs
- Long-run tests: 10,000 tick simulation, verify final state matches

**Debugging Aid**:
- Event log: Record every RNG call with (tick, operation, seed, result)
- Replay tool: Load event log, reproduce exact sequence

---

## Part VI: Development Guidelines

### 6.1 Core Principles

**1. Test-Driven Development (TDD)**
- Write test first (defines specification)
- Implement feature to pass test
- Refactor with confidence (tests catch regressions)
- Maintain >80% coverage

**2. Type Safety**
- Rust: Leverage compiler (invalid states unrepresentable)
- Python: Type hints everywhere (`mypy` strict mode)
- FFI: Validate at boundary (don't trust inputs)

**3. Minimal Abstractions**
- Don't abstract prematurely
- Extract patterns after 3rd use (Rule of Three)
- Prefer explicit over clever

**4. Performance Awareness**
- Profile before optimizing
- Rust for hot paths (tick loop, LSM)
- Python for convenience (config, HTTP, testing)

**5. Documentation as Code**
- Rustdoc for public APIs
- Docstrings for Python (with examples)
- Inline comments for non-obvious logic
- Update docs with code (not after)

### 6.2 Code Review Checklist

**Before Committing**:
- [ ] All tests pass (`cargo test && pytest`)
- [ ] No compiler warnings (`cargo clippy`)
- [ ] Code formatted (`cargo fmt && black .`)
- [ ] Type checks pass (`mypy .`)
- [ ] Documentation updated (if public API changed)
- [ ] Changelog entry (if user-visible change)

**Reviewer Focus**:
- [ ] Correctness: Does it work as specified?
- [ ] Tests: Are edge cases covered?
- [ ] Safety: Any memory/threading issues?
- [ ] Performance: Any O(n²) loops, FFI chattiness?
- [ ] Maintainability: Is it understandable?

### 6.3 Git Workflow

**Branch Strategy**:
- `main`: Production-ready (always green CI)
- `develop`: Integration branch (feature PRs target here)
- `feature/X`: Short-lived feature branches (delete after merge)

**Commit Messages**:
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**: `feat`, `fix`, `test`, `refactor`, `docs`, `perf`, `chore`

**Examples**:
```
feat(lsm): Add cycle detection with DFS algorithm

Implements cycle detection for LSM optimization pass.
Uses depth-first search to find payment loops.

Closes #42
```

```
fix(rtgs): Prevent double settlement in race condition

Added settlement flag check before processing Queue 2.
Added regression test for concurrent settlement attempts.

Fixes #67
```

**Pull Request Template**:
```markdown
## Summary
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- [ ] Rust changes (list modules)
- [ ] Python changes (list files)
- [ ] Tests added/updated
- [ ] Documentation updated

## Testing
How was this tested? (steps to reproduce)

## Checklist
- [ ] All tests pass
- [ ] No new clippy warnings
- [ ] Documentation updated
- [ ] Changelog entry
```

### 6.4 Release Process

**Versioning**: Semantic versioning (MAJOR.MINOR.PATCH)
- MAJOR: Breaking API changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

**Release Steps**:
1. Create release branch: `release/vX.Y.Z`
2. Update version in `Cargo.toml` and `pyproject.toml`
3. Update `CHANGELOG.md` with release notes
4. Run full test suite (including benchmarks)
5. Build release artifacts (`maturin build --release`)
6. Tag commit: `git tag vX.Y.Z`
7. Merge to `main` and `develop`
8. Publish: `maturin publish` (if public registry)

**Hotfix Process** (critical bugs only):
1. Branch from `main`: `hotfix/vX.Y.Z+1`
2. Fix bug + add regression test
3. Fast-track review and merge
4. Follow release steps above

---

## Part VII: Deployment & Operations

### 7.1 Deployment Options

#### Option 1: Standalone Service (Development)
```bash
# Build Rust core
cd backend && cargo build --release

# Install Python package
cd .. && maturin develop --release

# Start API server
cd api && uvicorn main:app --reload --port 8000

# Start frontend (separate terminal)
cd frontend && npm run dev
```

**Use Case**: Local development, debugging, testing

#### Option 2: Docker Compose (Integration Testing)
```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: ./api
    ports:
      - "8000:8000"
    environment:
      - RUST_LOG=info
    volumes:
      - ./config:/config
  
  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api
  
  llm-manager:
    build: ./llm-manager
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - api
```

**Use Case**: Multi-component integration testing, demo environments

#### Option 3: Kubernetes (Production)
```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-simulator-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: payment-simulator-api
  template:
    metadata:
      labels:
        app: payment-simulator-api
    spec:
      containers:
      - name: api
        image: payment-simulator:v1.0.0
        ports:
        - containerPort: 8000
        env:
        - name: RUST_LOG
          value: "info"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

**Use Case**: Production deployment, high availability, auto-scaling

### 7.2 Monitoring & Observability

#### Metrics (Prometheus Format)
```
# HELP simulator_tick_duration_seconds Time to process one tick
# TYPE simulator_tick_duration_seconds histogram
simulator_tick_duration_seconds_bucket{le="0.001"} 450
simulator_tick_duration_seconds_bucket{le="0.01"} 980
simulator_tick_duration_seconds_bucket{le="+Inf"} 1000
simulator_tick_duration_seconds_sum 5.2
simulator_tick_duration_seconds_count 1000

# HELP simulator_queue_size Current queue sizes
# TYPE simulator_queue_size gauge
simulator_queue_size{queue="queue1",agent="BANK_A"} 12
simulator_queue_size{queue="queue2"} 8

# HELP simulator_settlement_total Total settlements
# TYPE simulator_settlement_total counter
simulator_settlement_total{type="immediate"} 5420
simulator_settlement_total{type="lsm_bilateral"} 234
simulator_settlement_total{type="lsm_cycle"} 42
```

#### Grafana Dashboard

**Panels**:
1. **Tick Rate**: Ticks/second over time (target: >1000)
2. **Queue Sizes**: Queue 1 + Queue 2 by agent (stacked area chart)
3. **Throughput**: Value settled / value arrived (line chart)
4. **Liquidity Usage**: Peak net debit per agent (bar chart)
5. **LSM Efficacy**: Offsets + cycles per tick (line chart)
6. **Cost Breakdown**: Stacked area (liquidity, delay, split, penalty)
7. **Error Rate**: API errors per minute (alerts if >1%)

#### Logging Strategy

**Structured JSON Logs**:
```json
{
  "timestamp": "2025-10-28T14:23:11.234Z",
  "level": "INFO",
  "simulation_id": "sim_abc123",
  "tick": 42,
  "agent": "BANK_A",
  "event": "transaction_settled",
  "transaction_id": "tx_def456",
  "amount": 1000000,
  "settlement_type": "lsm_bilateral",
  "trace_id": "xyz789"
}
```

**Log Levels**:
- **DEBUG**: RNG calls, policy decisions (verbose, disabled in prod)
- **INFO**: Tick progress, settlements, arrivals (default)
- **WARN**: Gridlock detected, queue buildup, guardrail near-violations
- **ERROR**: FFI errors, invalid configs, unexpected panics

### 7.3 Backup & Recovery

**State Persistence** (optional):
```yaml
# Save state every N ticks
persistence:
  enabled: true
  interval_ticks: 100
  storage:
    type: s3
    bucket: payment-simulator-state
    prefix: simulations/
```

**Snapshot Format**:
```json
{
  "version": "1.0",
  "simulation_id": "sim_abc123",
  "seed": 12345,
  "tick": 4200,
  "agents": [...],
  "transactions": [...],
  "queues": {...},
  "rng_state": "..."
}
```

**Recovery**:
```bash
# Restore from snapshot
curl -X POST http://api:8000/simulations/restore \
  -H "Content-Type: application/json" \
  -d @snapshot_tick_4200.json

# Resume from tick 4200
curl -X POST http://api:8000/simulations/sim_abc123/tick?n=100
```

---

## Part VIII: Future Directions & Research

### 8.1 Advanced Learning Techniques

**1. Multi-Agent Reinforcement Learning (MARL)**
- Replace decision trees with neural network policies
- Train with PPO/SAC on continuous action spaces
- Self-play with population-based training
- Emergent coordination strategies

**2. Causal Inference**
- Identify causal relationships (e.g., "early submission → lower systemic delay")
- Estimate treatment effects (e.g., "LSM enablement → 30% liquidity reduction")
- Support counterfactual queries ("What if agent A changed policy?")

**3. Meta-Learning**
- Learn to learn (adapt policies quickly to new regimes)
- Few-shot adaptation to shocks
- Transfer learning across currencies/jurisdictions

### 8.2 Extensions & Variants

**1. Regulatory Scenarios**
- Basel III NSFR/LCR constraints
- CPMI-IOSCO PFMI compliance monitoring
- Throughput guidelines enforcement

**2. Market Microstructure**
- Intraday repo markets (borrow/lend liquidity)
- Collateral haircuts and margin calls
- Nostro funding optimization

**3. Crisis Simulations**
- Bank runs (sudden outflow shocks)
- Interbank contagion (bilateral exposure chains)
- Central bank interventions (emergency liquidity, rate changes)

**4. Privacy-Preserving Simulation**
- Federated learning (banks train locally, share updates)
- Differential privacy (add noise to published throughput signals)
- Secure multi-party computation (joint settlement without revealing balances)

### 8.3 Open Research Questions

1. **What throughput targets are Pareto-optimal?**
   - Too strict → costly hoarding
   - Too loose → gridlock risk
   - Can we characterize optimal thresholds?

2. **How do policies co-evolve in multi-agent learning?**
   - Do we converge to Nash equilibria?
   - Are there oscillations or limit cycles?
   - Can we design coordination mechanisms to stabilize?

3. **What are the welfare implications of LSM design?**
   - Who benefits from bilateral offsetting vs. cycles?
   - Are there distributional effects (large banks vs. small)?
   - How to design fair LSM algorithms?

4. **How resilient are learned policies to regime shifts?**
   - If overdraft pricing changes, do policies adapt?
   - Can we measure robustness to shocks?
   - What safety margins should policies maintain?

---

## Part IX: Success Metrics & KPIs

### 9.1 Technical Success Metrics

**Performance**:
- [ ] Tick processing rate: >1000 ticks/second (pure Rust)
- [ ] FFI overhead: <5% latency increase (Python→Rust→Python)
- [ ] Memory usage: <500 MB per 10-agent simulation
- [ ] WebSocket latency: <50ms event delivery (p99)

**Quality**:
- [ ] Test coverage: >80% (Rust + Python)
- [ ] Zero clippy warnings
- [ ] Zero mypy errors (strict mode)
- [ ] No memory leaks (valgrind clean)

**Reliability**:
- [ ] Determinism: 100 runs with same seed produce identical results
- [ ] Balance conservation: Invariant holds across all tests
- [ ] No panics/crashes: 10,000 tick simulation completes
- [ ] API uptime: >99.9% (monitored)

### 9.2 Functional Success Metrics

**Simulation Capabilities**:
- [ ] Can model 2-100 agents
- [ ] Can process 1M+ transactions per simulation
- [ ] Can run multi-day episodes (10+ days)
- [ ] LSM reduces liquidity by 30-50% (validated vs. no-LSM baseline)

**Policy Evolution**:
- [ ] LLM manager proposes valid policies (>90% validation pass rate)
- [ ] Shadow replay correctly estimates KPI deltas (±10% accuracy)
- [ ] Policies improve over episodes (cost reduction OR throughput increase)
- [ ] Learning converges within 100 episodes

**User Experience**:
- [ ] Frontend displays all state correctly (validated E2E)
- [ ] Can configure simulation via YAML in <5 minutes
- [ ] CLI enables debugging (reproduce any scenario from seed)
- [ ] Documentation enables onboarding (new dev productive in <2 days)

### 9.3 Research Success Metrics

**Scientific Output**:
- [ ] Published case studies (gridlock formation, LSM efficacy, throughput targets)
- [ ] Documented emergent behaviors (coordination patterns, equilibria)
- [ ] Validation against real-world data (qualitative realism checks)

**Community Engagement**:
- [ ] Open-source contributions (external PRs accepted)
- [ ] Conference presentations (payment systems, AI research)
- [ ] Partnerships with central banks or payment operators

---

## Part X: Risk Register & Mitigation

### 10.1 Technical Risks

**Risk 1: FFI Instability**
- **Probability**: Medium
- **Impact**: High (blocks integration)
- **Mitigation**:
  - Start with simple types (primitives, strings)
  - Extensive FFI testing (roundtrip, memory leaks)
  - Valgrind in CI
  - Clear ownership model (Rust owns state)

**Risk 2: Determinism Breaks**
- **Probability**: Medium
- **Impact**: High (breaks replay, learning)
- **Mitigation**:
  - Determinism tests from day 1 (already in place)
  - Forbid system time, floats in core logic
  - Event log for debugging
  - Strict RNG discipline

**Risk 3: Performance Degradation**
- **Probability**: Low
- **Impact**: Medium (user experience)
- **Mitigation**:
  - Benchmarks in CI (catch regressions)
  - Profile regularly (`cargo flamegraph`)
  - Optimize hot paths only (tick loop, LSM)
  - FFI overhead monitoring

### 10.2 Architecture Risks

**Risk 4: Scope Creep**
- **Probability**: High
- **Impact**: Medium (delays delivery)
- **Mitigation**:
  - Strict adherence to phased plan
  - "No" to features outside roadmap
  - Defer to "future work" backlog
  - Time-box exploration

**Risk 5: Over-Abstraction**
- **Probability**: Medium
- **Impact**: Medium (complexity bloat)
- **Mitigation**:
  - Prefer explicit over clever
  - Extract abstractions after 3rd use (Rule of Three)
  - Code review focus on simplicity
  - Refactor when patterns emerge

**Risk 6: Poor Separation of Concerns**
- **Probability**: Low
- **Impact**: High (architecture erosion)
- **Mitigation**:
  - Enforce FFI boundary discipline
  - Rust = simulation, Python = API/tooling
  - No business logic in API layer
  - Regular architecture reviews

### 10.3 Learning Risks

**Risk 7: LLM Generates Invalid Policies**
- **Probability**: High (inevitable)
- **Impact**: Low (validation catches)
- **Mitigation**:
  - Multi-stage validation (schema, properties, shadow replay)
  - Reject malformed policies early
  - LLM prompt engineering (provide examples)
  - Human-in-loop for anomalies

**Risk 8: Learning Doesn't Converge**
- **Probability**: Medium
- **Impact**: Medium (research value reduced)
- **Mitigation**:
  - Start with simple scenarios (2-bank games)
  - Population-based training (diverse opponents)
  - Convergence monitoring (KPI stability)
  - Intervention mechanisms (reset if divergent)

**Risk 9: Overfitting to Training Scenarios**
- **Probability**: Medium
- **Impact**: Medium (poor generalization)
- **Mitigation**:
  - Diverse training scenarios (vary agents, arrivals, shocks)
  - Held-out test scenarios (never seen during training)
  - Robustness tests (regime shifts, shocks)
  - Regular policy evaluation on new conditions

---

## Part XI: Timeline & Milestones

### 11.1 Phased Rollout (18-20 Week Plan)

**Phase 7: Integration Layer (Weeks 1-3)** ✅ — FFI, Python API, CLI **COMPLETE**
- ✅ Week 1: PyO3 bindings, FFI tests (24 tests passing)
- ✅ Week 2: FastAPI endpoints, simulation lifecycle (23 integration tests)
- ✅ Week 3: CLI tool, integration tests (verbose mode, scenario loading)
- **Milestone M1**: Can control simulation via HTTP/CLI ✅ **ACHIEVED**

**Phase 8: Cost Model & Metrics (Week 4)** 🔄 — **60% COMPLETE**
- ✅ Core cost structures implemented (CostRates, CostBreakdown, CostAccumulator)
- ✅ 4 of 5 cost types operational (liquidity, delay, split friction, deadline)
- ❌ Missing: Collateral cost, API exposure, metrics endpoints
- **Milestone M2**: Accurate cost tracking 🔄 **PARTIAL** (2-3 days remaining)

**Phase 9: Policy Expression Language (Weeks 5-7)** ✅ — **COMPLETE**
- ✅ Expression evaluator + decision-tree DSL (~4,880 lines)
- ✅ Tree executor and validation pipeline
- ✅ 50+ field accessors, comprehensive testing (940+ lines)
- **Milestone M3**: DSL infrastructure for LLM-driven evolution ✅ **ACHIEVED**

**Phase 10: Data Persistence (Weeks 5-7)** ❌ — **NOT STARTED**
- DuckDB + Polars integration (zero-copy Arrow)
- Pydantic models as schema source of truth
- Batch writes (transactions, agent metrics, policy snapshots)
- Migration system + CLI tools (db migrate, db validate)
- Query interface for analytics
- **Milestone M4**: Can store/query 250M+ transaction records ❌ **NOT STARTED**

**Phase 11: LLM Manager Integration (Weeks 8-10)** ❌ — **NOT STARTED**
- LLM manager service (separate process)
- Shadow replay system (uses Phase 10 database)
- Policy proposal generation + validation
- Multi-agent learning infrastructure
- **Milestone M5**: Full learning loop operational ❌ **NOT STARTED**

**Phase 12: Multi-Rail & Cross-Border (Weeks 11-12)** ❌ — **NOT STARTED**
- DNS rail implementation (batch netting)
- Multi-currency nostro accounts
- **Milestone M6**: Multi-rail simulations ❌ **NOT STARTED**

**Phase 13: Shock Scenarios (Week 13)** ❌ — **NOT STARTED**
- Shock module (5 shock types)
- Shock-aware metrics and analysis
- **Milestone M7**: Stress testing capability ❌ **NOT STARTED**

**Phase 14: Production Readiness (Weeks 14-16)** ❌ — **NOT STARTED**
- WebSocket streaming to clients
- React frontend (dashboard, charts, controls)
- Prometheus metrics + Grafana dashboards
- **Milestone M8**: Production deployment ready ❌ **NOT STARTED**

### 11.2 Dependency Graph

```
Phase 7 (Integration) ──┬──> Phase 8 (Costs) ──> Phase 9 (DSL) ──┐
                        │                                         │
                        │                                         v
                        │                                   Phase 10 (Persistence) ──┐
                        │                                                            │
                        │                                                            v
                        │                                                       Phase 11 (LLM Manager)
                        │                                                            │
                        │                                                            v
                        └──> Phase 12 (Multi-Rail) ──> Phase 13 (Shocks) ──> Phase 14 (Production)
```

**Critical Path**: 7 → 8 → 9 → 10 → 11 (LLM Manager depends on persistence for episode storage and policy tracking)

**Key Dependencies**:
- Phase 11 (LLM Manager) **requires** Phase 10 (Persistence):
  - Shadow replay needs historical episode database
  - Policy evolution tracking requires `policy_snapshots` table
  - Monte Carlo validation samples from `simulations` table

**Parallel Work**: Phases 12-13 can proceed independently of Phase 11 (multi-rail, shocks)

### 11.3 Go/No-Go Decision Points

**Milestone M1 (Week 3)**: Integration Layer Complete
- **Go Criteria**:
  - All FFI tests pass (roundtrip, memory safety)
  - Can create/control simulations via API
  - CLI functional for debugging
  - Determinism preserved across FFI boundary
- **No-Go**: Block Phase 8-14 until resolved
- **Status**: ✅ **ACHIEVED**

**Milestone M2 (Week 5)**: Cost Model Complete
- **Go Criteria**:
  - All cost types implemented (overdraft, delay, deadline, EOD, split)
  - Cost API endpoints functional
  - Collateral cost model integrated
  - Metrics validated against financial formulas
- **No-Go**: Block Phase 10 (persistence needs complete cost data)
- **Status**: 🔄 **IN PROGRESS** (90% complete, collateral cost remaining)

**Milestone M3 (Week 7)**: Policy DSL Complete
- **Go Criteria**:
  - Expression evaluator safe and correct
  - Can define and validate policies via JSON DSL
  - Hot-reload policies without restart
- **Status**: ✅ **ACHIEVED**

**Milestone M4 (Week 7)**: Data Persistence Complete
- **Go Criteria**:
  - Can store 200 runs with 1.2M transactions each
  - Schema validation prevents drift (Pydantic models as source of truth)
  - Batch writes complete in <100ms
  - Query interface operational for analytics
  - Migration system functional
- **No-Go**: Block Phase 11 (LLM Manager needs episode database)
- **Status**: ❌ **NOT STARTED**

**Milestone M5 (Week 10)**: LLM Manager Operational
- **Go Criteria**:
  - Shadow replay produces valid KPI estimates
  - LLM manager proposes valid policy changes
  - Learning loop functional
  - Policy evolution tracking via persistence layer
- **No-Go**: Block production deployment
- **Status**: ❌ **NOT STARTED**

**Milestone M6 (Week 12)**: Multi-Rail Support Complete
- **Go Criteria**:
  - RTGS + DNS rails operational
  - Cross-border corridors functional
  - Rail-specific policies working
- **Status**: ❌ **NOT STARTED**

**Milestone M7 (Week 13)**: Shock Scenarios Validated
- **Go Criteria**:
  - Outage scenarios produce expected gridlock
  - Liquidity squeeze stress tests pass
  - Counterparty failure propagation correct
- **Status**: ❌ **NOT STARTED**

**Milestone M8 (Week 16)**: Production Ready
- **Go Criteria**:
  - WebSocket streaming works for 10+ clients
  - Frontend displays all state correctly
  - Performance targets met (>1000 ticks/sec)
  - Monitoring operational (Prometheus + Grafana)
- **No-Go**: Block public launch
- **Status**: ❌ **NOT STARTED**

---

## Part XII: Getting Started

### 12.1 Quick Start for New Developers

**Step 1: Environment Setup**
```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Install Python 3.11+
# (use pyenv, conda, or system package manager)

# Clone repository
git clone https://github.com/your-org/payment-simulator.git
cd payment-simulator

# Install Python dependencies
cd api && pip install -e ".[dev]"

# Build Rust core
cd ../backend && cargo build --release
cd .. && maturin develop --release

# Run tests
cargo test          # Rust tests
pytest              # Python tests
```

**Step 2: Run Your First Simulation**
```bash
# Start API server
cd api && uvicorn main:app --reload --port 8000

# In another terminal, use CLI
cd cli
./sim create config/simple.yaml
./sim tick 100
./sim state
```

**Step 3: Explore the Codebase**
- Read `docs/architecture.md` (high-level design)
- Read `docs/queue_architecture.md` (two-queue system)
- Review `backend/tests/` (see how components work)
- Check `CLAUDE.md` in each module (AI assistant docs)

### 12.2 Development Workflow

**Daily Loop**:
```bash
# Morning: Update and test
git pull
cargo test && pytest

# Develop: Write test first
# 1. Add test in `backend/tests/test_feature.rs`
# 2. Run `cargo test test_feature` (fails)
# 3. Implement feature
# 4. Run `cargo test test_feature` (passes)

# Before commit: Lint and format
cargo fmt && cargo clippy
black . && mypy .

# Commit
git add .
git commit -m "feat(module): description"
git push origin feature/my-feature

# Create PR (see template in .github/PULL_REQUEST_TEMPLATE.md)
```

**Testing Checklist**:
```bash
# Unit tests
cargo test --lib

# Integration tests
cargo test --test '*'

# Python tests
pytest tests/

# FFI tests
pytest tests/integration/

# Determinism
cargo test test_rng_determinism
pytest tests/test_determinism.py

# Performance
cargo bench     # (optional, for hot paths)
```

### 12.3 Where to Contribute

**Beginner-Friendly Tasks**:
- Add doc examples for public APIs
- Improve error messages
- Add tests for edge cases
- Fix clippy/mypy warnings

**Intermediate Tasks**:
- Implement new policy types
- Add shock scenarios
- Improve CLI output formatting
- Add API endpoints

**Advanced Tasks**:
- Optimize LSM cycle detection
- Implement new settlement rails
- Build LLM manager service
- Design multi-agent learning experiments

**See**: `CONTRIBUTING.md` and `docs/good-first-issues.md`

---

## Appendix A: Configuration Examples

### A.1 Minimal Configuration
```yaml
# config/minimal.yaml
simulation:
  ticks_per_day: 100
  seed: 12345

agents:
  - id: BANK_A
    balance: 1000000      # $10,000.00
    credit_limit: 500000  # $5,000.00
    
  - id: BANK_B
    balance: 1500000      # $15,000.00
    credit_limit: 750000  # $7,500.00

# No arrivals (manual submission only)
# No costs (zero rates)
# LSM enabled by default
```

### A.2 Realistic Configuration
```yaml
# config/realistic.yaml
simulation:
  ticks_per_day: 100
  seed: 67890
  rails:
    - type: rtgs
      lsm:
        bilateral_offsetting: true
        cycle_detection: true
        max_iterations: 3

agents:
  - id: BANK_A
    balance: 5000000       # $50,000.00
    credit_limit: 10000000 # $100,000.00
    liquidity_buffer: 2000000  # Target minimum balance
    arrival_config:
      rate_per_tick: 0.5   # Poisson λ = 0.5 transactions/tick
      distribution_type: lognormal
      amount_mean: 500000  # $5,000 median
      amount_std_dev: 200000
      counterparty_weights:
        BANK_B: 0.4
        BANK_C: 0.3
        BANK_D: 0.3
    
  - id: BANK_B
    balance: 8000000
    credit_limit: 15000000
    liquidity_buffer: 3000000
    arrival_config:
      rate_per_tick: 0.6
      distribution_type: lognormal
      amount_mean: 600000
      amount_std_dev: 250000
      counterparty_weights:
        BANK_A: 0.5
        BANK_C: 0.3
        BANK_D: 0.2

  # ... BANK_C, BANK_D ...

costs:
  liquidity_rate: 0.0005   # 5 bps annualized
  collateral_rate: 0.0002  # 2 bps annualized
  split_friction: 1000     # $10 per split
  deadline_penalty: 100000 # $1,000 per violation
  eod_penalty: 500000      # $5,000 per unsettled
```

### A.3 Multi-Rail Configuration
```yaml
# config/multi_rail.yaml
simulation:
  ticks_per_day: 100
  seed: 54321
  rails:
    - type: rtgs
      lsm:
        bilateral_offsetting: true
        cycle_detection: true
    - type: dns
      batch_ticks: [25, 50, 75, 100]  # Settlement windows
      netting: bilateral

agents:
  - id: BANK_A
    rtgs_balance: 3000000
    dns_balance: 2000000
    credit_limit: 8000000
    # ... arrival configs for each rail ...
```

---

## Appendix B: API Reference (Summary)

### B.1 Simulations
- `POST /simulations` — Create simulation from config
- `GET /simulations/{id}` — Get simulation info
- `POST /simulations/{id}/start` — Start simulation
- `POST /simulations/{id}/stop` — Stop simulation
- `POST /simulations/{id}/tick?n=10` — Advance N ticks
- `GET /simulations/{id}/state` — Get state snapshot
- `DELETE /simulations/{id}` — Delete simulation

### B.2 Transactions
- `POST /transactions` — Submit transaction
- `GET /transactions/{id}` — Get transaction details
- `GET /transactions?agent=BANK_A&status=pending` — Query transactions

### B.3 KPIs
- `GET /kpis/costs?simulation_id={id}` — Cost breakdown
- `GET /kpis/throughput?simulation_id={id}` — Throughput over time
- `GET /kpis/liquidity?simulation_id={id}` — Peak debits, headroom

### B.4 WebSocket
- `WS /websocket?simulation_id={id}` — Real-time event stream
  - Events: `tick`, `arrival`, `settlement`, `policy_decision`, `cost_update`

**Full API Documentation**: See `docs/API.md`

---

## Appendix C: Glossary (Extended)

| Term | Definition |
|------|------------|
| **Agent** | A bank participant in the simulation (holds settlement balance at central bank) |
| **Arrival** | New payment order entering a bank's Queue 1 |
| **Balance** | Bank's settlement account balance at central bank (can go negative with credit) |
| **Bilateral Offsetting** | LSM technique: net A→B and B→A transactions to reduce gross settlement |
| **Cash Manager** | Treasury operations role making intraday payment decisions (modeled by policies) |
| **Collateral** | Assets posted to secure intraday credit (incurs opportunity cost) |
| **Credit Limit** | Maximum intraday overdraft allowed (balance can go to `balance - credit_limit`) |
| **Cycle** | Circular payment chain (A→B→C→A) settleable with net-zero liquidity |
| **Deadline** | Latest tick for transaction settlement (penalties apply if missed) |
| **Determinism** | Property that same seed produces identical outcomes (essential for replay) |
| **DNS (Deferred Net Settlement)** | Batch netting rail (contrasts with RTGS gross settlement) |
| **EoD (End-of-Day)** | Last tick of business day (large penalties for unsettled transactions) |
| **Episode** | Complete simulation run (one or more business days) |
| **FFI (Foreign Function Interface)** | Boundary between Rust and Python (via PyO3) |
| **Gridlock** | Situation where all banks wait for inflows, no settlements occur |
| **Headroom** | Remaining unused credit capacity (`credit_limit + balance` if balance > 0) |
| **Liquidity Pressure** | Metric of how constrained an agent's liquidity is (0-1 scale) |
| **LSM (Liquidity-Saving Mechanism)** | Queue optimization techniques (offsetting, cycles) |
| **Nostro** | Account held at correspondent bank for cross-border settlements |
| **Orchestrator** | Central coordinator executing 9-step tick loop in Rust |
| **Policy** | Decision-making logic for cash manager (when to submit, split, hold) |
| **Priority** | Transaction urgency level (0-10, affects policy decisions) |
| **Queue 1** | Internal bank queue (agent-controlled, strategic decisions) |
| **Queue 2** | Central RTGS queue (system-controlled, mechanical liquidity retry) |
| **Recycling** | Using incoming settlement proceeds to fund outgoing payments |
| **RTGS (Real-Time Gross Settlement)** | Settlement system for individual, immediate finality |
| **Shadow Replay** | Re-evaluation of past episodes with new policy (validation technique) |
| **Splitting** | Voluntary division of large payment into N separate instructions (agent pacing) |
| **Throughput** | Cumulative value settled / cumulative value arrived (0-1 ratio) |
| **Tick** | Discrete time unit (60-100 per simulated business day) |

---

## Appendix D: References & Further Reading

### Academic Papers
1. **Gridlock Resolution in Payment Systems** — Danmarks Nationalbank (2001)
   - *Key Result*: LSM reduces gridlock duration by 40-60% under constrained liquidity

2. **Liquidity Distribution and Settlement in TARGET2** — ECB Economic Bulletin (2020)
   - *Key Result*: Bilateral offsetting provides 30-40% liquidity savings in typical operations

3. **Central Bank Digital Currency: Opportunities and Challenges** — BIS Quarterly Review (2021)
   - *Relevance*: RTGS design principles apply to CBDC settlement layers

### Technical Documentation
1. **TARGET2 User Guide** — European Central Bank
   - Details on priorities, timed transactions, limits, CLM

2. **CPMI-IOSCO Principles for Financial Market Infrastructures** — BIS (2012)
   - FMI safety and efficiency standards (relevant for compliance scenarios)

3. **PyO3 User Guide** — PyO3 Project
   - Best practices for Rust-Python FFI

### Code Examples & Tutorials
1. **Rust Performance Book** — Official Rust Documentation
   - Optimization techniques for hot paths

2. **FastAPI Documentation** — FastAPI Project
   - Async API design patterns

3. **Multi-Agent RL Resources** — OpenAI Spinning Up, RLlib
   - Self-play, population-based training

---

## Conclusion

This Grand Plan 2.2 provides a comprehensive roadmap from the completed foundation, integration, and DSL infrastructure (Phases 1-7, 9 DSL) to the full vision of an LLM-driven, multi-agent payment simulator. The plan is structured in three major sections:

**Where We Are** (Part III):
- ✅ **Foundation Complete** (Phases 1-7): All Rust core components implemented, tested, and validated. Python integration layer fully operational with PyO3 FFI bindings, FastAPI endpoints, and production-ready CLI tool. 107+ tests pass with zero failures.
- ✅ **Policy DSL Complete** (Phase 9): ~4,880 lines of production code providing expression evaluator, JSON decision trees, validation pipeline, and 50+ field accessors. 940+ lines of tests validate correctness. Policies can be hot-reloaded and LLM-generated safely.
- 🔄 **Cost Model Partial** (Phase 8): Core structures and 4/5 cost calculations complete in Rust. Missing: API exposure, collateral cost, metrics endpoints. ~60% complete, 2-3 days remaining.

**Where We're Going** (Part IV):
- Complete Phase 8 (cost/metrics API layer)
- **Phase 9: LLM Manager Integration** (shadow replay, policy evolution, multi-agent learning)
- Phase 10: Multi-rail support (RTGS + DNS, cross-border)
- Phase 11: Shock scenarios and resilience testing
- Phase 12: Production readiness (WebSocket, frontend, observability)

**How We'll Get There** (Parts V-XII): Detailed technical architecture, development guidelines, deployment strategies, risk mitigation, success metrics, and getting-started instructions ensure the plan is actionable and maintainable.

**Critical Success Factors**:
1. **Maintain determinism** — Every new feature must preserve replay capability ✅ Validated
2. **Preserve two-queue separation** — Clear distinction between strategic (Queue 1) and mechanical (Queue 2) decisions ✅ Validated
3. **Test ruthlessly** — >80% coverage, property tests for invariants, integration tests across FFI ✅ Achieved (107+ core tests, 940+ DSL tests)
4. **Scope discipline** — Follow phased plan, defer non-critical features to backlog ✅ On track (Phase 9 learning deferred to Phase 13)
5. **Document as we go** — Keep docs synchronized with code, examples for all public APIs ✅ Maintained (2,700+ line DSL design doc)

**Major Achievements Since v2.1**:
- ✅ Policy DSL infrastructure complete (~4,880 lines)
- ✅ Expression evaluator with safe sandboxed execution
- ✅ JSON decision tree format with comprehensive validation
- ✅ 50+ field accessors for policy evaluation context
- ✅ Hot-reloadable policies (no simulator restart needed)
- ✅ Foundation for LLM-generated policies established

**Architectural Decisions Validated**:
- ✅ Rust-Python hybrid approach works (FFI overhead <1%)
- ✅ Two-queue separation enables clear policy abstractions
- ✅ Determinism maintained across all layers
- ✅ DSL can be used independently before LLM integration
- ✅ Large-scale performance validated (200 agents, 1,200 ticks/sec)

**Current Capability**:
- Run complex multi-agent simulations with configurable policies
- Define custom decision trees in JSON with safe expression evaluation
- Hot-reload policies without restarting
- Track costs (liquidity, delay, split friction, deadline penalties)
- Access via HTTP API, CLI, or direct Rust/Python integration
- Reproduce any simulation deterministically from seed

**Next Immediate Actions**:
1. **Complete Phase 8** (2-3 days): Add cost/metrics API endpoints, implement collateral cost
2. **Begin Phase 10** (2 weeks): Data Persistence with DuckDB, Polars, and schema-as-code
3. **Prepare for Phase 11**: LLM Manager integration (depends on Phase 10 completion)

---

**Document Status**: Living Document (update as implementation progresses)
**Maintainer**: Payment Simulator Team
**Last Updated**: October 29, 2025
**Version**: 2.4 — Phase 7 Complete, Phase 9 DSL Complete, Phase 8 90% Complete, Phase 10 Persistence Planned
