# Payment Simulator: Grand Plan 2.0
## From Foundation to Full Vision

**Document Version**: 2.1
**Date**: October 28, 2025
**Status**: Foundation + Integration Complete → Feature Expansion

---

## Executive Summary

### Project Purpose

Build a sandboxed, multi-agent simulator of high-value payment operations that demonstrates how banks strategically time and fund outgoing payments during the business day. The simulator models real-world RTGS (Real-Time Gross Settlement) systems like TARGET2, where banks must balance competing pressures: minimizing liquidity costs, meeting payment deadlines, avoiding gridlock, and maintaining system throughput.

**Core Innovation**: Each bank is controlled by a **decision-tree policy** (small, auditable program) that determines payment timing and liquidity management. An **asynchronous LLM Manager service** improves policies between simulation episodes through code editing, with all changes validated via automated testing and Monte Carlo shadow replay before deployment.

### What We've Achieved: Foundation Complete ✅

The Rust core backend is **complete and battle-tested**:

- ✅ **Phase 1-2**: Time management, RNG (xorshift64*), Agent state, Transaction models
- ✅ **Phase 3**: RTGS settlement engine + LSM (bilateral offsetting + cycle detection)
- ✅ **Phase 4a**: Queue 1 (internal bank queues) + Cash Manager policies (FIFO, Deadline, LiquidityAware)
- ✅ **Phase 4b**: Complete 9-step orchestrator tick loop integrating all components
- ✅ **Phase 5**: Transaction splitting (agent-initiated payment pacing)
- ✅ **Phase 6**: Arrival generation with configurable distributions (Poisson, normal, lognormal, uniform)
- ✅ **Phase 7**: Integration layer complete (PyO3 FFI, FastAPI, CLI tool)

**Test Coverage**: 107+ passing tests with zero failures (60+ Rust core + 24 FFI + 23 API integration), including critical invariants (determinism, balance conservation, gridlock resolution).

### Where We're Going: Feature Expansion 🎯

**Phase 7 Complete** ✅ (Integration Layer):
1. ✅ **PyO3 FFI Bindings**: Rust orchestrator exposed to Python
2. ✅ **Python API Layer**: FastAPI endpoints operational with 23+ integration tests
3. ✅ **CLI Tool**: Command-line interface with scenario loading, verbose mode
4. ✅ **Integration Testing**: 24 FFI tests + 23 API tests passing

**Next Steps** (12-16 weeks):
1. Cost modeling (liquidity, delay, split friction, deadline penalties)
2. Advanced policies (learning agents, LLM-driven evolution)
3. Multi-rail support (RTGS + DNS, cross-border corridors)
4. Shock scenarios (outages, liquidity squeezes, counterparty stress)
5. Production readiness (WebSocket streaming, frontend, observability)

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
- ✅ Verbose mode for detailed execution logging
- ✅ Large-scale scenarios tested (200 agents, 100 ticks)

**Performance**: 1,200 ticks/second, 8 seconds for 200-agent scenarios

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

### 3.3 Lessons Learned from Foundation & Integration Work

**1. Two-Queue Architecture is Powerful**:
- Clear separation of strategic decisions (Queue 1) vs. mechanical waits (Queue 2)
- Delay costs naturally apply only where bank has control
- Policies have intuitive decision hooks
- **Implication**: Maintain this clean separation as we add features

**2. Determinism Requires Discipline**:
- Must seed RNG explicitly at every source of randomness
- System time is forbidden (breaks replay)
- All stochastic processes (arrivals, counterparty selection) go through RNG
- **Implication**: Add determinism tests for every new feature with randomness

**3. LSM is Non-Negotiable**:
- Without LSM, even simple scenarios gridlock under moderate liquidity constraints
- Bilateral offsetting provides 30-40% liquidity savings in balanced flows
- Cycle detection is essential for realistic multi-agent scenarios
- **Implication**: LSM should be always-on (not optional) in production configs

**4. Rust Performance is Exceptional**:
- 1000+ ticks/second without optimization effort
- LSM cycle detection <1ms for typical payment graphs
- Memory-efficient state management
- **Implication**: We can afford complex policies and richer state without performance concerns

**5. Testing Pays Off**:
- 60+ tests caught edge cases early (deadline boundaries, negative balances, empty queues)
- Property tests (balance conservation) are invaluable invariants
- **Implication**: Maintain >80% coverage and add property tests for new features

**6. PyO3 FFI is Production-Ready**:
- Type conversions work seamlessly with proper error handling
- Memory safety maintained through clear ownership boundaries
- FFI overhead is minimal (<1% performance impact)
- **Implication**: Rust-Python hybrid approach validated for production use

**7. Pydantic V2 + YAML = Excellent DX**:
- Type-safe configuration with automatic validation
- Clear error messages guide users to fix config issues
- YAML provides human-friendly scenario definitions
- **Implication**: Configuration-driven architecture enables rapid experimentation

**8. CLI as First-Class Citizen**:
- Command-line tool invaluable for testing and validation
- Verbose mode essential for debugging complex scenarios
- Large-scale scenarios (200 agents) validate production readiness
- **Implication**: Maintain CLI alongside API for developer workflow

---

## Part IV: Roadmap to Full Vision

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

### 4.2 Phase 8: Cost Model & Metrics (Week 4)

**Goal**: Implement full cost accounting and KPI tracking

#### Cost Calculation
**Deliverable**: All five cost types operational

**Tasks**:
1. **Liquidity Costs**:
   - Track per-tick negative balances
   - Apply annualized overdraft rate
   - Accumulate to total cost

2. **Collateral Costs**:
   - Track posted collateral (if agent uses)
   - Apply opportunity cost rate
   - Haircut calculations (optional)

3. **Delay Costs**:
   - Queue 1 only (not Queue 2)
   - Per-transaction, per-tick accrual
   - Accumulate to agent and system totals

4. **Split Friction**:
   - Charged immediately on split decision
   - Formula: `f_s × (N-1)`
   - Added to transaction's total cost

5. **Deadline Penalties**:
   - Charged on transaction drop or EoD
   - Per-transaction large penalty
   - Logged separately for analysis

**Testing**:
- Cost accumulation tests (verify formulas)
- Multi-day cost persistence
- Edge cases (zero costs, massive penalties)

#### KPI Dashboard
**Deliverable**: Real-time metrics collection

**Metrics**:
- **Throughput**: Value settled / value arrived (by time)
- **Delays**: Average/max ticks from arrival to settlement
- **Queue Statistics**: Queue 1 + Queue 2 sizes, age distributions
- **Liquidity Usage**: Peak net debit per agent, system total
- **LSM Efficacy**: Bilateral offsets count, cycle settlements count
- **Cost Breakdown**: By type (liquidity, delay, split, penalty)

**API Endpoints**:
- `GET /kpis/costs` — cost breakdown
- `GET /kpis/throughput` — throughput over time
- `GET /kpis/liquidity` — peak debits, headroom usage

**Success Criteria**:
- All costs accumulate correctly
- KPIs update each tick
- Can export metrics for plotting

### 4.3 Phase 9: Advanced Policies (Weeks 5-7)

**Goal**: Richer policy options and learning foundation

#### Policy Framework Expansion
**Deliverable**: Decision-tree policies with expressions

**Tasks**:
1. **Expression Evaluator**:
   - Safe expression evaluation (no arbitrary code execution)
   - Access to agent state, transaction attributes, system signals
   - Supported operators: arithmetic, comparisons, Boolean logic
   - Nested structures (if-then-else trees)

2. **Policy DSL** (Domain-Specific Language):
   ```yaml
   policy:
     type: decision_tree
     rules:
       - condition: "transaction.priority >= 8 AND ticks_to_deadline < 10"
         action: submit_full
       - condition: "agent.liquidity_pressure > 0.8"
         action: hold
         reason: preserve_liquidity
       - condition: "transaction.amount > 100000000 AND can_split"
         action: submit_partial
         split_factor: 4
       - default: hold
   ```

3. **Advanced Policies**:
   - `ThresholdPolicy`: Submit if balance > threshold, else hold
   - `ProportionalPolicy`: Submit fraction based on liquidity pressure
   - `PriorityPolicy`: Weighted scoring of priority, deadline, amount
   - `AdaptivePolicy`: Adjust thresholds based on inflow forecast

4. **Policy Versioning**:
   - Git-backed policy storage
   - Commit hash tracking
   - Rollback support
   - A/B testing infrastructure

**Testing**:
- Expression evaluator safety tests
- Policy correctness tests (known scenarios)
- Versioning and rollback tests

#### Learning Infrastructure
**Deliverable**: Foundation for LLM-driven evolution

**Tasks**:
1. **Shadow Replay System**:
   - Re-evaluate past episodes with new policy
   - Monte Carlo sampling of opponent behaviors
   - KPI validation (check for regressions)
   - Guardrail enforcement

2. **Policy Evaluation Pipeline**:
   - Run candidate policy in shadow mode
   - Compare KPIs to baseline (cost, delays, throughput)
   - Flag violations (e.g., >10% cost increase)
   - Approve/reject with structured reasons

3. **Continuous Learning Loop**:
   - Episode collection (store deterministic seeds)
   - Policy proposal generation (LLM calls, async)
   - Validation gate (shadow replay, property checks)
   - Deployment (if approved, update policy)

**Testing**:
- Shadow replay determinism
- Guardrail violation detection
- Policy improvement verification

**Success Criteria**:
- Can define policies via YAML DSL
- Expression evaluator is safe and correct
- Shadow replay produces valid KPI comparisons
- Learning loop can propose and validate changes

### 4.4 Phase 10: Multi-Rail & Cross-Border (Weeks 8-9)

**Goal**: Support multiple settlement rails and currency corridors

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

### 4.5 Phase 11: Shock Scenarios & Resilience (Week 10)

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

### 4.6 Phase 12: Production Readiness (Weeks 11-13)

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

### 4.7 Phase 13: LLM Manager Integration (Weeks 14-16)

**Goal**: Asynchronous policy evolution via LLM

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
   - Output: Candidate policy (YAML DSL)

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

### 11.1 Phased Rollout (16-Week Plan)

**Phase 7: Integration Layer (Weeks 1-3)** ✅ — FFI, Python API, CLI **COMPLETE**
- ✅ Week 1: PyO3 bindings, FFI tests (24 tests passing)
- ✅ Week 2: FastAPI endpoints, simulation lifecycle (23 integration tests)
- ✅ Week 3: CLI tool, integration tests (verbose mode, scenario loading)
- **Milestone M1**: Can control simulation via HTTP/CLI ✅ **ACHIEVED**

**Phase 8: Cost Model & Metrics (Week 4)** — Full cost accounting
- All 5 cost types implemented and tested
- KPI dashboard operational (REST endpoints)
- **Milestone M2**: Accurate cost tracking ✅

**Phase 9: Advanced Policies (Weeks 5-7)** — Policy DSL, learning infrastructure
- Expression evaluator + decision-tree DSL
- Shadow replay system
- Policy versioning and A/B testing
- **Milestone M3**: Foundation for LLM-driven evolution ✅

**Phase 10: Multi-Rail & Cross-Border (Weeks 8-9)** — RTGS + DNS, currencies
- DNS rail implementation (batch netting)
- Multi-currency nostro accounts
- **Milestone M4**: Multi-rail simulations ✅

**Phase 11: Shock Scenarios (Week 10)** — Resilience testing
- Shock module (5 shock types)
- Shock-aware metrics and analysis
- **Milestone M5**: Stress testing capability ✅

**Phase 12: Production Readiness (Weeks 11-13)** — Observability, frontend
- WebSocket streaming to clients
- React frontend (dashboard, charts, controls)
- Prometheus metrics + Grafana dashboards
- **Milestone M6**: Production deployment ready ✅

**Phase 13: LLM Manager Integration (Weeks 14-16)** — Async learning loop
- LLM manager service (separate process)
- Policy proposal generation + validation
- Multi-agent learning infrastructure
- **Milestone M7**: Full learning loop operational ✅

### 11.2 Dependency Graph

```
Phase 7 (Integration) ──┬──> Phase 8 (Costs) ──> Phase 9 (Policies)
                        │                              │
                        │                              v
                        └──> Phase 10 (Multi-Rail) ──> Phase 11 (Shocks)
                                                         │
                                                         v
                        Phase 13 (LLM) <────── Phase 12 (Production)
```

**Critical Path**: 7 → 8 → 9 → 13 (learning features depend on policies)

**Parallel Work**: Phases 10-11 can proceed independently (multi-rail, shocks)

### 11.3 Go/No-Go Decision Points

**Milestone M1 (Week 3)**: Integration Layer Complete
- **Go Criteria**:
  - All FFI tests pass (roundtrip, memory safety)
  - Can create/control simulations via API
  - CLI functional for debugging
  - Determinism preserved across FFI boundary
- **No-Go**: Block Phase 8-13 until resolved

**Milestone M3 (Week 7)**: Policy Framework Complete
- **Go Criteria**:
  - Expression evaluator safe and correct
  - Shadow replay produces valid KPI estimates
  - Can define and validate policies via YAML
- **No-Go**: Block Phase 13 (LLM integration)

**Milestone M6 (Week 13)**: Production Ready
- **Go Criteria**:
  - WebSocket streaming works for 10+ clients
  - Frontend displays all state correctly
  - Performance targets met (>1000 ticks/sec)
  - Monitoring operational (Prometheus + Grafana)
- **No-Go**: Block public launch

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

This Grand Plan 2.1 provides a comprehensive roadmap from the completed foundation and integration layers (Phases 1-7) to the full vision of an LLM-driven, multi-agent payment simulator. The plan is structured in three major sections:

**Where We Are** (Part III): Both foundation and integration are complete — all Rust core components are implemented, tested, and validated, AND the Python integration layer is fully operational. We have a working 9-step tick loop, two-queue architecture, RTGS settlement, LSM optimization, cash manager policies, transaction splitting, arrival generation, PyO3 FFI bindings, FastAPI endpoints, and a production-ready CLI tool. 107+ tests pass with zero failures.

**Where We're Going** (Part IV): A phased plan to implement the full cost model, build advanced policy infrastructure (including LLM-driven evolution), support multi-rail and cross-border scenarios, add shock testing, and achieve production readiness with observability and a React frontend.

**How We'll Get There** (Parts V-XII): Detailed technical architecture, development guidelines, deployment strategies, risk mitigation, success metrics, and getting-started instructions ensure the plan is actionable and maintainable.

**Critical Success Factors**:
1. **Maintain determinism** — Every new feature must preserve replay capability ✅ Validated
2. **Preserve two-queue separation** — Clear distinction between strategic (Queue 1) and mechanical (Queue 2) decisions ✅ Validated
3. **Test ruthlessly** — >80% coverage, property tests for invariants, integration tests across FFI ✅ Achieved (107+ tests)
4. **Scope discipline** — Follow phased plan, defer non-critical features to backlog ✅ On track
5. **Document as we go** — Keep docs synchronized with code, examples for all public APIs ✅ Maintained

The foundation work validated the core architecture and proved the system can model real-world RTGS dynamics (liquidity recycling, gridlock, LSM efficacy). The integration work validated the Rust-Python hybrid approach and demonstrated that FFI overhead is minimal (<1%). The CLI tool enables rapid scenario testing, and large-scale validation (200 agents) confirms production readiness.

**Phase 7 Achievements**:
- ✅ PyO3 FFI bindings operational (24 tests)
- ✅ FastAPI endpoints complete (23 integration tests)
- ✅ CLI tool production-ready (scenario library, verbose mode)
- ✅ Performance validated (1,200 ticks/second, >1000 target)
- ✅ Large-scale testing (200 agents, 100 ticks in 8 seconds)

With the integration layer complete, we now have a fully functional payment simulator accessible via HTTP API and CLI. The system is ready for the next phases: cost modeling, advanced policies, and LLM-driven evolution.

**Next Immediate Action**: Begin Phase 8 (Cost Model & Metrics) to implement all five cost types (liquidity, collateral, delay, split friction, deadline penalties) and create the KPI dashboard. This provides the economic foundation for policy optimization and learning.

---

**Document Status**: Living Document (update as implementation progresses)
**Maintainer**: Payment Simulator Team
**Last Updated**: October 28, 2025
**Version**: 2.1 — Phase 7 Complete (Integration Layer)