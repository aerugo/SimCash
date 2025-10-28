# Payment Simulator - Foundation Implementation Plan

> **Status Update (2025-10-28)**: Phase 1-7 (Rust core + Python API) completed. CLI tool remaining. See implementation status below.

## Executive Summary

This plan outlined the implementation of a **minimal but complete** foundation. The goal was to prove the architecture works end-to-end with the simplest possible feature set, then add complexity incrementally.

**Current Progress**:
- ✅ **Phase 1-2 Complete**: Time, RNG, Agent, Transaction models
- ✅ **Phase 3 Complete**: RTGS settlement engine + LSM (Liquidity-Saving Mechanisms)
- ✅ **Phase 4a Complete**: Queue 1 (internal bank queues) + Cash Manager Policies
- ✅ **Phase 4b Complete**: Orchestrator integration with full 9-step tick loop
- ✅ **Phase 5 Complete**: Transaction splitting integrated into orchestrator
- ✅ **Phase 6 Complete**: Arrival generation integrated into orchestrator
- ✅ **Phase 7 Complete** (mostly): PyO3 FFI bindings + Python FastAPI + Configuration layer
- 🎯 **Remaining Work**: CLI tool (2-3 days), E2E integration tests, documentation

---

## Implementation Status

### ✅ Phase 1-2: COMPLETED (as of 2025-10-27)

**Git commits**:
- `23381fe` - Phase 1 & Phase 2 (Agent): Foundation implementation
- `375c24d` - Phase 2 (Transaction): Complete transaction model implementation

**What's Implemented**:

#### Core Domain (Rust)
1. **Time Management** ✅
   - Discrete ticks and days (`TimeManager`)
   - Tick advancement
   - Current time queries
   - **Tests**: 6 passing tests

2. **Agent State** ✅
   - Agent ID, balance (i64 cents), credit limit
   - Balance updates (debit/credit)
   - Liquidity checks (`can_pay()`, `available_liquidity()`)
   - **Tests**: 17 passing tests
   - **Note**: `Agent.balance` represents bank's settlement account **at central bank**

3. **Transactions** ✅
   - Create transaction (sender, receiver, amount, deadline)
   - Settlement status (Pending → PartiallySettled → Settled/Dropped)
   - Divisible vs. indivisible transactions
   - Priority levels (0-10)
   - Builder pattern (`with_priority()`, `divisible()`)
   - **Tests**: 21 passing tests

4. **Deterministic RNG** ✅
   - Seeded xorshift64* implementation (`RngManager`)
   - Deterministic random number generation
   - Seed persistence
   - **Tests**: 10 passing tests

5. **Orchestrator** ⏳ Phase 4+ (placeholder only)
   - Currently: `pub struct Orchestrator;` placeholder
   - Planned for Phase 4+

6. **RTGS Settlement** ⏳ Phase 3 (planned)
   - Currently: Placeholder in `backend/src/settlement/rtgs.rs`
   - Planned: See `/docs/phase3_rtgs_analysis.md`
   - Will implement:
     - Immediate settlement if liquidity sufficient
     - Central RTGS queue for insufficient liquidity
     - Queue retry each tick
     - Deadline-based transaction dropping

#### Python API Layer - ✅ COMPLETE (Phase 7)
1. **Configuration** ✅ COMPLETE
   - Load YAML config
   - Pydantic V2 validation
   - Convert to Rust format
   - **Tests**: 9 passing configuration tests

2. **FFI Wrapper** ✅ COMPLETE
   - PyO3 bindings for Orchestrator
   - Create orchestrator
   - Submit transactions
   - Advance ticks
   - Query state (balances, queues, agent IDs)
   - **Tests**: 24 passing FFI tests

3. **FastAPI Endpoints** ✅ COMPLETE
   - POST /simulations - Create simulation
   - POST /simulations/{id}/tick - Advance simulation
   - GET /simulations/{id}/state - Query state
   - GET /simulations - List simulations
   - DELETE /simulations/{id} - Delete simulation
   - POST /simulations/{id}/transactions - Submit transaction
   - GET /simulations/{id}/transactions/{tx_id} - Get transaction status
   - GET /simulations/{id}/transactions - List transactions (with filtering)
   - **Tests**: 23 passing API integration tests

4. **Basic Error Handling** ✅ COMPLETE
   - FFI error conversion (Rust → Python exceptions → HTTP errors)
   - HTTP error responses (400, 404, 422, 500)
   - Proper status codes for validation errors

#### CLI Tool - 🎯 Future (Phase 5+)
All CLI features are future work.

#### React Frontend - 🎯 Future (Phase 6+)
All frontend features are future work.

---

### ✅ Phase 3: RTGS Settlement Engine + LSM - **COMPLETE** (2025-10-27)

**Status**: Implementation complete

**Git commits**:
- Phase 3a (RTGS): Complete RTGS settlement with central queue
- Phase 3b (LSM): Complete liquidity-saving mechanisms

**What's Implemented**:

#### Phase 3a: RTGS Settlement Engine ✅
- **Module**: `backend/src/settlement/rtgs.rs` (571 lines)
- **Functions**:
  - `try_settle()` - immediate settlement with balance + credit checks
  - `try_settle_partial()` - partial settlement for divisible transactions
  - `submit_transaction()` - submit to RTGS with automatic queuing
  - `process_queue()` - FIFO retry with deadline expiration
- **Infrastructure**:
  - Extended `SimulationState` with `rtgs_queue: Vec<String>`
  - Error types: `SettlementError`
  - Result types: `SubmissionResult`, `QueueProcessingResult`
- **Tests**: **22 passing tests** in `backend/tests/test_rtgs_settlement.rs`
  - Immediate settlement (balance + credit)
  - Queue processing (FIFO, deadline expiration)
  - Liquidity recycling (A→B→C payment chains)
  - Gridlock formation and resolution
  - Balance conservation (critical invariant)
  - Partial settlement for divisible transactions

#### Phase 3b: LSM (Liquidity-Saving Mechanisms) ✅
- **Module**: `backend/src/settlement/lsm.rs` (598 lines)
- **Functions**:
  - `bilateral_offset()` - A↔B payment netting (reduces liquidity requirements)
  - `detect_cycles()` - DFS-based cycle detection in payment graph
  - `settle_cycle()` - net-zero cycle settlement (A→B→C→A)
  - `run_lsm_pass()` - coordinator with multi-iteration optimization
- **Infrastructure**:
  - `LsmConfig` with toggles for bilateral/cycles
  - Result types: `BilateralOffsetResult`, `CycleSettlementResult`, `LsmPassResult`
  - `Cycle` struct for detected payment cycles
- **Tests**: **15 passing tests** in `backend/tests/test_lsm.rs`
  - Bilateral offsetting (exact match, asymmetric, multiple transactions)
  - Cycle detection (3-cycle, 4-cycle, unequal amounts)
  - LSM coordinator (bilateral only, cycles only, full optimization)
  - Four-bank ring test (from game_concept_doc.md Section 11)

#### Test Status:
- **55 unit/integration tests passing** (0 failures)
- **42 doc tests passing** (all documentation examples)
- **Coverage**: All critical paths, edge cases, and invariants

#### Alignment with T2-Style RTGS:
- ✅ Central bank intermediary model (agents = bank settlement accounts)
- ✅ Immediate settlement when liquidity sufficient
- ✅ Central RTGS queue for insufficient liquidity
- ✅ Intraday credit limits (balance + credit headroom)
- ✅ FIFO queue processing with deadline expiration
- ✅ Bilateral offsetting (A↔B netting)
- ✅ Cycle detection and settlement (3-cycle, 4-cycle)
- ✅ Net-zero settlement for cycles (minimal liquidity usage)
- ✅ Gridlock resolution via LSM optimization

---

### ✅ Phase 4a: Queue 1 & Cash Manager Policies - **COMPLETE** (2025-10-27)

**Status**: Implementation complete

**Git commits**:
- `77d835d` - Phase 4a (Queue 1): Implement internal bank queues and cash manager policies
- `07138b4` - Fix doc test failures in policy module

**What's Implemented**:

#### Queue 1 Infrastructure ✅
- **Extended Agent Model**: `backend/src/models/agent.rs`
  - `outgoing_queue: Vec<String>` - Internal queue for transactions awaiting policy decision
  - `incoming_expected: Vec<String>` - Expected incoming payments for liquidity forecasting
  - `last_decision_tick: Option<usize>` - Last policy evaluation tick
  - `liquidity_buffer: i64` - Target minimum balance to maintain
  - **New methods** (15+ additions):
    - `queue_outgoing()`, `remove_from_queue()` - Queue management
    - `can_afford_to_send()`, `liquidity_pressure()` - Decision factors
    - `outgoing_queue_size()`, `outgoing_queue_value()` - Analytics

- **Extended SimulationState**: `backend/src/models/state.rs`
  - Queue 1 accessor methods:
    - `total_internal_queue_size()` - System-wide queue statistics
    - `total_internal_queue_value()` - Total queued value
    - `get_urgent_transactions()` - Find transactions approaching deadlines
    - `agents_with_queued_transactions()` - Which banks have pending transactions
    - `agent_queue_value()` - Per-agent queue analysis

#### Cash Manager Policy Framework ✅
- **Module**: `backend/src/policy/`
- **Core Trait**: `CashManagerPolicy`
  ```rust
  fn evaluate_queue(
      &mut self,
      agent: &Agent,
      state: &SimulationState,
      tick: usize,
  ) -> Vec<ReleaseDecision>;
  ```

- **Decision Types**:
  - `ReleaseDecision` enum: `SubmitFull`, `SubmitPartial`, `Hold`, `Drop`
  - `HoldReason` enum: Structured reasons for holding (liquidity, inflows, priority, etc.)

- **Three Baseline Policies** ✅:
  1. **FifoPolicy** (`fifo.rs`) - Submit all transactions immediately (simplest baseline)
  2. **DeadlinePolicy** (`deadline.rs`) - Prioritize urgent transactions, hold non-urgent
  3. **LiquidityAwarePolicy** (`liquidity_aware.rs`) - Preserve liquidity buffer, override for urgency

#### Documentation ✅
- **Comprehensive Guide**: `docs/queue_architecture.md` (3,200+ lines)
  - Two-queue architecture explanation
  - Complete transaction lifecycle diagrams
  - Policy decision factors enumeration
  - Integration patterns and code examples
  - Comparison: Queue 1 (policy) vs Queue 2 (mechanical)

- **Module Documentation**: Full rustdoc for policy module with examples

#### Test Status:
- **60 tests passing** (0 failures)
  - 22 RTGS tests (Phase 3a)
  - 15 LSM tests (Phase 3b)
  - 12 Policy tests (Phase 4a) - FIFO, Deadline, LiquidityAware
  - 11 Core model tests
  - Plus all doc tests

#### Alignment with Two-Queue Architecture:
- ✅ Queue 1 (internal bank queues) for strategic decisions
- ✅ Queue 2 (central RTGS queue) for mechanical liquidity retry
- ✅ Policy evaluation every tick (re-evaluate as conditions change)
- ✅ Access to agent state, transaction details, system signals
- ✅ Structured decision types with hold reasons
- ✅ Foundation for future LLM-driven policy evolution (Phase 6)

---

### ✅ Phase 4b: Orchestrator Integration - **COMPLETE** (2025-10-28)

**Status**: Implementation complete

**Git commits**:
- `fd48bb1` - Phase 4b.2: Implement complete tick() loop integrating all components
- `ac48262` - Phase 4b.1: Core Orchestrator Structure (Foundation)

**What's Implemented**:

#### Complete 9-Step Tick Loop ✅
- **Module**: `backend/src/orchestrator/engine.rs` (lines 4698-4986)
- **Full Integration**: All subsystems orchestrated in single tick() method

**Tick Loop Steps**:
1. **Arrivals** (lines 4706-4747) ✅
   - Generate new transactions via `ArrivalGenerator`
   - Add to `SimulationState`
   - Queue in agent's Queue 1
   - Log arrival events

2. **Policy Evaluation** (lines 4749-4908) ✅
   - For each agent with queued transactions
   - Call policy's `evaluate_queue()`
   - Process `ReleaseDecision` variants:
     - `SubmitFull`: Move from Queue 1 to pending settlements
     - `SubmitPartial`: Create child transactions (splitting)
     - `Hold`: Keep in Queue 1
     - `Drop`: Remove from Queue 1, mark as dropped

3. **RTGS Settlement** (lines 4910-4948) ✅
   - Try immediate settlement for pending transactions
   - If insufficient liquidity → queue in Queue 2 (RTGS queue)
   - Log settlement events

4. **Process RTGS Queue** (lines 4950-4953) ✅
   - Call `rtgs::process_queue()` with liquidity recycling
   - Retry all queued transactions after each settlement

5. **LSM Coordinator** (lines 4955-4963) ✅
   - Call `lsm::run_lsm_pass()`
   - Bilateral offsetting + cycle detection + settlement
   - Track releases for metrics

6. **Cost Accrual** (lines 4965-4966) ✅
   - Calculate overdraft costs (for negative balances)
   - Calculate delay costs (for Queue 1 only)
   - Accumulate per agent

7. **Advance Time** (line 4972) ✅
   - Call `time_manager.advance_tick()`

8. **End-of-Day Handling** (lines 4974-4976) ✅
   - If day boundary: apply EOD penalties
   - For unsettled transactions still in Queue 1

9. **Return Results** ✅
   - `TickResult` with metrics (arrivals, settlements, LSM releases, costs)

#### Supporting Infrastructure ✅
- **Per-Agent Policy Configuration**: HashMap of agent_id → Box<dyn Policy>
- **Event Logging**: Complete event stream for all actions
- **Cost Tracking**: Per-agent accumulated costs (overdraft, delay, split, EOD penalty)
- **Metrics Collection**: Comprehensive tick statistics

#### Test Status:
- **60+ tests passing** across all modules
- Integration tests in `backend/tests/test_orchestrator_integration.rs`
- Full tick loop tested with all components

---

### ✅ Phase 5: Transaction Splitting - **COMPLETE** (2025-10-28)

**Status**: Implementation complete, integrated into orchestrator

**Git commit**: Integrated in Phase 4b.2 (fd48bb1)

**What's Implemented**:

#### Transaction Splitting Mechanics ✅
- **Location**: Orchestrator tick loop, Policy Evaluation step (lines 4792-4878)
- **Trigger**: Policy returns `ReleaseDecision::SubmitPartial { tx_id, num_splits }`

**Implementation Details**:
1. **Parent Transaction Removal** ✅
   - Remove parent from Queue 1
   - Parent remains in state as "split" (not submitted to RTGS)

2. **Child Transaction Creation** ✅
   - Calculate base amount: `parent.amount() / num_splits`
   - Remainder goes to last child (ensures exact sum)
   - Each child created with `Transaction::new_split()`
   - Preserves parent's priority and deadline
   - Links to parent via `parent_id` field

3. **Child Submission** ✅
   - All children added to pending settlements (bypass Queue 1)
   - Each child independently processed by RTGS
   - Can settle at different ticks based on liquidity

4. **Cost Calculation** ✅
   - Split friction cost: `split_friction_cost × (num_splits - 1)`
   - Charged to sending agent
   - Tracked in `accumulated_costs`

5. **Event Logging** ✅
   - `Event::PolicySplit` with parent_id, num_splits, children IDs

#### Transaction Model Support ✅
- **Fields**:
  - `parent_id: Option<String>` - Links child to parent
  - `remaining_amount: i64` - Tracks partial settlement
- **Methods**:
  - `new_split()` - Constructor for child transactions
  - `is_split()` - Query if transaction is a split child
  - `parent_id()` - Get parent transaction ID

#### Policy Support ✅
- **Decision Type**: `ReleaseDecision::SubmitPartial { tx_id, num_splits }`
- **Policies Using Splitting**:
  - `LiquiditySplittingPolicy` (lines in `policy/splitting.rs`)
  - Configurable: max_splits, min_split_amount
  - Splits large transactions when liquidity is tight

#### Test Coverage ✅
- Tests in `backend/tests/test_transaction_splitting.rs`
- Validates:
  - Correct amount distribution (including remainder)
  - Parent-child linking
  - Split cost calculation
  - Independent settlement of children
  - Balance conservation across splits

**Note**: Transaction splitting is a **policy-level decision**, not an RTGS feature. Banks voluntarily split payments to manage liquidity. The RTGS engine only sees fully-formed individual instructions.

---

### ✅ Phase 6: Arrival Generation - **COMPLETE** (2025-10-28)

**Status**: Implementation complete, integrated into orchestrator

**What's Implemented**:

#### Arrival Generator ✅
- **Module**: `backend/src/arrivals/generator.rs`
- **Integration**: Step 1 of orchestrator tick loop (lines 4706-4747)

**Components**:
1. **ArrivalConfig** ✅
   - `rate_per_tick: f64` - Expected arrivals (Poisson λ)
   - `distribution: AmountDistribution` - Transaction size distribution
   - `counterparty_weights: HashMap<String, f64>` - Receiver preferences
   - `deadline_offset: usize` - Ticks until deadline

2. **AmountDistribution** ✅ (`backend/src/arrivals/distributions.rs`)
   - `Normal { mean, std_dev }` - Gaussian distribution
   - `LogNormal { mean_log, std_dev_log }` - Right-skewed distribution
   - `Uniform { min, max }` - Flat distribution
   - `Exponential { lambda }` - Decay distribution
   - All implemented with deterministic RNG

3. **ArrivalGenerator** ✅
   - Holds per-agent configurations
   - `generate_for_agent()` method:
     - Samples count from Poisson distribution
     - For each: samples amount, selects counterparty
     - Creates `Transaction` objects
     - Returns Vec<Transaction>

4. **Orchestrator Integration** ✅
   - Optional `arrival_generator: Option<ArrivalGenerator>` field
   - Called every tick before policy evaluation
   - Generated transactions automatically queued in Queue 1
   - All arrivals logged as events

#### Test Coverage ✅
- Determinism verified (same seed → same arrivals)
- Distribution shape validated
- Counterparty selection tested
- End-to-end integration in orchestrator tests

**Example Configuration**:
```yaml
arrival_config:
  rate_per_tick: 2.5  # Average 2-3 transactions per tick
  distribution:
    type: LogNormal
    mean_log: 11.5  # Median ~$1,000
    std_dev_log: 1.2
  counterparty_weights:
    BANK_B: 0.5
    BANK_C: 0.3
    BANK_D: 0.2
  deadline_offset: 50  # 50 ticks to settle
```

---

### ✅ Phase 7: Python API & FFI Layer - **COMPLETE** (2025-10-28)

**Status**: Implementation complete (API fully functional via FastAPI)

**Git commits**:
- Configuration layer (Pydantic V2 + YAML)
- FFI bindings (PyO3 0.27.1)
- FastAPI REST API with comprehensive endpoints
- Transaction tracking with status inference

**What's Implemented**:

#### 1. Configuration Layer (Pydantic V2) ✅
- **Module**: `api/payment_simulator/config/`
- **Components**:
  - `SimulationConfig` - Top-level simulation configuration
  - `AgentConfig` - Per-agent configuration
  - `ArrivalConfig` - Transaction arrival configuration
  - `CostRates` - Liquidity/delay cost configuration
  - `LsmConfig` - LSM optimization settings
  - YAML loading and validation
  - Conversion to FFI-compatible dict format
- **Tests**: 9 passing configuration tests

#### 2. FFI Bindings (PyO3) ✅
- **Module**: `backend/src/ffi/`
- **Exposed Types**:
  - `Orchestrator` class - Main simulation controller
  - Config parsing helpers
  - Type conversions (Python dict ↔ Rust structs)
- **Orchestrator Methods**:
  - `new(config: Dict)` - Create simulation from config
  - `tick()` - Execute one simulation tick
  - `submit_transaction()` - Submit transaction for processing
  - `get_agent_balance(agent_id)` - Query agent balance
  - `get_queue1_size(agent_id)` - Query internal queue size
  - `get_queue2_size()` - Query RTGS queue size
  - `get_agent_ids()` - List all agent IDs
  - `current_tick()`, `current_day()` - Time queries
- **Tests**: 24 passing FFI tests
  - Orchestrator creation and validation
  - State queries (balances, queues)
  - Transaction submission
  - Tick execution
  - Determinism verification

#### 3. FastAPI REST API ✅
- **Module**: `api/payment_simulator/api/main.py`
- **In-Memory State Management**: `SimulationManager` class
  - Multiple concurrent simulations
  - Transaction tracking with status inference
  - UUID-based simulation IDs

**Simulation Endpoints**:
- `POST /simulations` - Create new simulation
- `GET /simulations` - List all active simulations
- `GET /simulations/{id}/state` - Query simulation state
- `POST /simulations/{id}/tick?count=N` - Advance simulation
- `DELETE /simulations/{id}` - Delete simulation

**Transaction Endpoints**:
- `POST /simulations/{id}/transactions` - Submit transaction
- `GET /simulations/{id}/transactions/{tx_id}` - Get transaction status
- `GET /simulations/{id}/transactions?status=X&agent=Y` - List/filter transactions

**Utility Endpoints**:
- `GET /` - API root with basic info
- `GET /health` - Health check with active simulation count
- `GET /docs` - Auto-generated OpenAPI documentation (FastAPI)

**Error Handling**:
- 400: Bad request (invalid sender/receiver, FFI errors)
- 404: Not found (simulation/transaction doesn't exist)
- 422: Validation error (Pydantic validation failed)
- 500: Internal server error

**Tests**: 23 passing API integration tests
- Simulation lifecycle (create, state, tick, delete, list)
- Transaction submission and validation
- Transaction status tracking and lifecycle
- Transaction filtering (by status, by agent)
- Concurrent simulations
- Error handling (invalid inputs, not found)

#### 4. Transaction Tracking ✅
Since Rust doesn't expose transaction status queries yet, the API layer implements:
- In-memory transaction metadata storage
- Status inference based on balance changes
- Filtering by status and agent
- Complete transaction history per simulation

**Limitations** (future enhancements):
- Status inference is heuristic (checks balance delta, not actual settlement events)
- No event log parsing from Rust (would be more accurate)
- Sufficient for current testing and demo purposes

#### Test Coverage ✅
**Python Test Suite**: 56 tests passing
- 24 FFI tests (determinism, state queries, transactions)
- 23 API integration tests (simulations + transactions)
- 9 configuration tests (validation, YAML loading)

**Rust Test Suite**: 279 tests passing
- All core functionality verified

**Total**: 335 tests passing

#### Documentation ✅
- Auto-generated OpenAPI/Swagger docs at `/docs`
- Interactive API playground at `/docs` (FastAPI feature)
- Pydantic models provide schema validation and documentation

#### Example Usage:
```python
import requests

# Create simulation
config = {
    "simulation": {
        "ticks_per_day": 100,
        "num_days": 1,
        "rng_seed": 12345
    },
    "agents": [
        {
            "id": "BANK_A",
            "opening_balance": 1_000_000,
            "credit_limit": 500_000,
            "policy": {"type": "Fifo"}
        }
    ]
}

response = requests.post("http://localhost:8000/simulations", json=config)
sim_id = response.json()["simulation_id"]

# Submit transaction
tx_data = {
    "sender": "BANK_A",
    "receiver": "BANK_B",
    "amount": 100_000,
    "deadline_tick": 50,
    "priority": 5,
    "divisible": False
}

tx_response = requests.post(f"http://localhost:8000/simulations/{sim_id}/transactions", json=tx_data)
tx_id = tx_response.json()["transaction_id"]

# Advance simulation
requests.post(f"http://localhost:8000/simulations/{sim_id}/tick", params={"count": 10})

# Check transaction status
status = requests.get(f"http://localhost:8000/simulations/{sim_id}/transactions/{tx_id}")
print(status.json())
```

---

### 🎯 Future Phases (Integration Layer)

#### Phase 7: Policy DSL & LLM Integration (Future)
- **JSON Decision Tree Format**:
  - Schema definition and validation
  - Rust interpreter (~2,000 lines)
  - Expression language (conditions, computations)
  - Field enumeration (agent, transaction, system state)
  - Action types (Release, Hold, Pace, Drop)
  - Safety validation (cycles, depth limits, division-by-zero)
  - Hot-reload mechanism

- **LLM Manager Service**:
  - Policy mutation prompting patterns
  - Git-based version control for policy evolution
  - Shadow replay validation (test new policy on historical episodes)
  - Monte Carlo opponent sampling
  - Guardband checking (performance regression detection)
  - Rollback procedures

- **Hybrid Execution**:
  ```rust
  pub enum PolicyExecutor {
      Trait(Box<dyn CashManagerPolicy>),  // Rust policies (fast, hand-coded)
      Tree(TreeInterpreter),               // JSON DSL (LLM-editable)
  }
  ```

- **Migration Path**:
  - Port 1-2 baseline policies to JSON to validate DSL
  - Support both execution modes
  - No breaking changes to existing Rust policies

- **Complete Specification**: See `/docs/policy_dsl_design.md`

**Rationale for Deferring DSL to Phase 6**:
- Phase 4a trait-based policies allow fast iteration and validation
- Proves the abstraction works before adding 2,000+ lines of DSL infrastructure
- DSL needed only when starting RL/LLM-driven policy optimization
- Can validate JSON schema design now, implement interpreter later

#### Phase 7: Python API & FFI
- Python FFI wrapper (PyO3 bindings)
- FastAPI endpoints
- Configuration loading (YAML → Pydantic → Rust)
- CLI tool

#### Phase 8: Frontend & Visualization
- React visualization
- WebSocket streaming for real-time updates
- A/B testing framework
- Performance dashboards

---

## Success Criteria

The foundation is complete when:

### ✅ **Completed (Rust Core)**

1. ✅ **Rust compiles and tests pass**
   - All core types implemented
   - Unit tests for each module (60+ tests passing)
   - Integration tests for orchestrator
   - Complete 9-step tick loop
   - All subsystems integrated (RTGS, LSM, policies, arrivals, splitting)

2. ✅ **Determinism proven**
   - Same seed + same actions = same results
   - Replay tests pass
   - RNG state persists correctly
   - Verified across all modules

### ✅ **Completed (Integration Layer - Phase 7)**

3. ✅ **FFI boundary works**
   - Python can import Rust module ✅
   - Can create orchestrator from Python ✅
   - Can submit transactions and advance ticks via FFI ✅
   - Type conversions work correctly ✅
   - **Tests**: 24 passing FFI tests

4. ❌ **CLI functional** (2-3 days) - DEFERRED
   - Can run a 100-tick simulation
   - Can submit transactions
   - Output is readable
   - Useful for debugging
   - State persistence works

5. ✅ **API operational**
   - All endpoints work ✅
   - Returns correct data ✅
   - Error handling works ✅
   - OpenAPI documentation auto-generated via FastAPI ✅
   - **Tests**: 23 passing API integration tests

6. ⏸️ **Frontend displays state** (deferred to Phase 8)
   - Shows agents and balances
   - Shows transactions
   - Can advance ticks
   - Updates correctly

7. ❌ **End-to-end test passes** (after FFI/API/CLI complete)
   - Create simulation via API
   - Submit transaction via API
   - Advance ticks until settled
   - Query via CLI
   - Verify results

### **Current Status Summary**

**✅ Complete (95%)**:
- Rust simulation engine (Phases 1-6) - **279 tests passing**
- All core models, settlement, policies, orchestration
- PyO3 FFI bindings (Phase 7) - **24 FFI tests passing**
- Python FastAPI API (Phase 7) - **23 API integration tests passing**
- Pydantic configuration layer (Phase 7) - **9 config tests passing**
- **Total: 335 tests passing** (279 Rust + 56 Python)

**🎯 Remaining (5%)**:
- CLI tool (2-3 days) - DEFERRED (API provides all necessary functionality)
- E2E integration tests (optional - API tests cover most scenarios)
- Documentation (API docs, usage examples)

**Foundation is 95% complete** - Core functionality fully operational via API

---

## Implementation Plan

### Phase 1: Rust Core (Week 1-2)

**Goal**: Build minimal Rust core with tests

#### Week 1: Core Types

**Day 1-2: Project Setup**
```bash
# Directory structure
backend/
├── Cargo.toml
├── src/
│   ├── lib.rs
│   ├── core/
│   │   ├── mod.rs
│   │   └── time.rs
│   ├── models/
│   │   ├── mod.rs
│   │   ├── agent.rs
│   │   ├── transaction.rs
│   │   └── enums.rs
│   ├── rng/
│   │   ├── mod.rs
│   │   └── manager.rs
│   └── orchestrator/
│       ├── mod.rs
│       └── engine.rs
└── tests/
    ├── time_manager.rs
    ├── rng_determinism.rs
    ├── agent_state.rs
    └── transaction.rs
```

**Tasks**:
- [ ] Initialize Cargo workspace
- [ ] Add dependencies (pyo3, thiserror, serde)
- [ ] Create module structure
- [ ] Write Cargo.toml with proper settings

**Day 3-4: Time Manager**
- [ ] Write failing tests first (TDD)
- [ ] Implement `TimeManager` struct
- [ ] Methods: `new()`, `advance_tick()`, `current_tick()`, `current_day()`
- [ ] Verify all tests pass

**Day 5: RNG Manager**
- [ ] Write determinism tests
- [ ] Implement `RngManager` with xorshift64*
- [ ] Methods: `new(seed)`, `next_u64()`, `gen_range()`, `get_seed()`
- [ ] Test: same seed produces same sequence

**Day 6-7: Agent and Transaction**
- [ ] Write tests for Agent (balance updates, liquidity checks)
- [ ] Implement `AgentState` struct
- [ ] Write tests for Transaction (creation, settlement)
- [ ] Implement `Transaction` struct
- [ ] All money as i64 (cents)

**Deliverable**: Core types compile, all unit tests pass

#### Week 2: Orchestrator

**Day 1-2: Basic Orchestrator**
- [ ] Write tests for orchestrator creation
- [ ] Implement `Orchestrator` struct
- [ ] Constructor from config dict
- [ ] Hold agents, transactions, time, rng
- [ ] Test creation from various configs

**Day 3-4: Tick Logic**
- [ ] Write tests for tick advancement
- [ ] Implement `tick()` method
- [ ] Simple settlement: try to settle all pending transactions
- [ ] Update agent balances
- [ ] Advance time
- [ ] Return tick summary

**Day 5: Transaction Submission**
- [ ] Write tests for manual transaction submission
- [ ] Implement `submit_transaction()` method
- [ ] Validate sender/receiver exist
- [ ] Check amount is positive
- [ ] Assign deadline from current tick
- [ ] Add to transaction list

**Day 6-7: Integration Tests**
- [ ] Write multi-tick simulation test
- [ ] Test determinism (same seed = same results)
- [ ] Test transaction lifecycle (submit → tick → settled)
- [ ] Test insufficient funds (transaction stays pending)

**Deliverable**: Orchestrator works, integration tests pass

### Phase 2: PyO3 Bindings (Week 3)

**Goal**: Expose Rust to Python

#### Day 1-2: Module Exports

**Setup**:
```python
# pyproject.toml
[build-system]
requires = ["maturin>=1.9.6"]
build-backend = "maturin"

[tool.maturin]
python-source = "api"
module-name = "payment_simulator_core_rs"
```

**Tasks**:
- [ ] Add `#[pymodule]` to lib.rs
- [ ] Add `#[pyclass]` to Transaction, AgentState
- [ ] Add `#[pymethods]` for constructors and getters
- [ ] Build with `maturin develop`
- [ ] Test import in Python

**Day 3-4: Orchestrator Binding**
- [ ] Make Orchestrator a `#[pyclass]`
- [ ] Expose `new()` constructor (takes dict)
- [ ] Expose `tick()` → returns dict
- [ ] Expose `submit_transaction()` → returns tx_id
- [ ] Expose `get_state()` → returns dict
- [ ] Test all methods from Python

**Day 5: Error Handling**
- [ ] Convert Rust errors to Python exceptions
- [ ] Test error propagation
- [ ] Ensure helpful error messages

**Day 6-7: Integration Tests**
- [ ] Create `api/tests/integration/test_rust_ffi.py`
- [ ] Test create orchestrator
- [ ] Test tick advancement
- [ ] Test transaction submission
- [ ] Test determinism from Python
- [ ] Test error handling

**Deliverable**: Python can use Rust, FFI tests pass

### Phase 3: Python API (Week 4)

**Goal**: FastAPI layer

#### Day 1-2: Configuration

**Setup**:
```
api/
├── payment_simulator/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── schemas.py  # Pydantic models
│   │   └── loader.py   # YAML loader
│   ├── backends/
│   │   ├── __init__.py
│   │   └── rust_wrapper.py
│   └── api/
│       ├── __init__.py
│       ├── main.py
│       ├── dependencies.py
│       └── routes/
│           ├── simulations.py
│           └── transactions.py
└── tests/
    └── integration/
```

**Tasks**:
- [ ] Create Pydantic models (SimulationConfig, AgentConfig)
- [ ] Create YAML loader
- [ ] Validate config
- [ ] Test config loading

**Day 3-4: API Routes**
- [ ] Create FastAPI app in main.py
- [ ] Implement simulation routes:
  - POST /simulations/create
  - POST /simulations/tick
  - GET /simulations/state
  - POST /simulations/reset
- [ ] Implement transaction routes:
  - POST /transactions
  - GET /transactions/{id}
- [ ] Use dependency injection for orchestrator

**Day 5: Testing**
- [ ] Create `tests/integration/test_api.py`
- [ ] Test all endpoints with httpx
- [ ] Test error cases
- [ ] Test full lifecycle (create → tick → query)

**Day 6-7: Documentation**
- [ ] Add docstrings to all endpoints
- [ ] FastAPI generates OpenAPI docs
- [ ] Test docs at /docs endpoint
- [ ] Create README for API

**Deliverable**: API works, all endpoints tested

### Phase 4: CLI Tool (Week 5)

**Goal**: Debugging interface

#### Day 1-2: Basic CLI

**Setup**:
```
cli/
├── Cargo.toml
└── src/
    ├── main.rs
    ├── commands/
    │   ├── mod.rs
    │   ├── create.rs
    │   ├── tick.rs
    │   ├── submit.rs
    │   └── state.rs
    └── display/
        ├── mod.rs
        └── formatters.rs
```

**Dependencies**:
```toml
[dependencies]
payment-simulator-core-rs = { path = "../backend" }
clap = { version = "4.5", features = ["derive"] }
serde_json = "1.0"
serde_yaml = "0.9"
```

**Tasks**:
- [ ] Set up clap argument parsing
- [ ] Implement `create` command (load config, create orchestrator)
- [ ] Implement `state` command (display current state)
- [ ] Test basic functionality

**Day 3-4: Interactive Commands**
- [ ] Implement `tick` command with optional count
- [ ] Implement `submit-tx` command (interactive prompts)
- [ ] Add pretty-printing for state
- [ ] Add color output (green/red for balances)

**Day 5: State Persistence**
- [ ] Add `save` command (serialize state to file)
- [ ] Add `load` command (deserialize state from file)
- [ ] Test save/load cycle

**Day 6-7: Documentation and Polish**
- [ ] Add `--help` text for all commands
- [ ] Create examples in README
- [ ] Test full workflow:
  ```bash
  payment-sim create --config config.yaml
  payment-sim submit-tx --sender A --receiver B --amount 100000
  payment-sim tick --count 10
  payment-sim state
  ```

**Deliverable**: CLI works, useful for debugging

### Phase 5: React Frontend (Week 6)

**Goal**: Basic visualization

#### Day 1-2: Project Setup

**Setup**:
```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install
```

**Structure**:
```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts
│   ├── components/
│   │   ├── Dashboard.tsx
│   │   ├── AgentCard.tsx
│   │   ├── TransactionList.tsx
│   │   └── ControlPanel.tsx
│   ├── context/
│   │   └── SimulationContext.tsx
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   └── main.tsx
└── package.json
```

**Tasks**:
- [ ] Initialize React project
- [ ] Set up TypeScript types
- [ ] Create API client wrapper
- [ ] Test API connection

**Day 3-4: Core Components**
- [ ] Implement `AgentCard` component
  - Show ID, balance, credit used
  - Color code: green (positive), red (negative)
- [ ] Implement `TransactionList` component
  - Show all transactions
  - Status badges (pending/settled/dropped)
- [ ] Implement `ControlPanel` component
  - Tick button
  - Reset button
  - Tick count display

**Day 5: State Management**
- [ ] Create SimulationContext
- [ ] Implement polling (every 1 second)
- [ ] Update state from API
- [ ] Handle errors

**Day 6: Dashboard**
- [ ] Create main Dashboard layout
- [ ] Arrange components in grid
- [ ] Add basic styling (Tailwind or CSS)
- [ ] Test responsiveness

**Day 7: Polish**
- [ ] Add loading states
- [ ] Add error displays
- [ ] Test full workflow
- [ ] Create README

**Deliverable**: Frontend displays state, can control simulation

### Phase 6: Integration & Testing (Week 7)

**Goal**: Everything works together

#### Day 1-2: End-to-End Testing

**Create E2E test suite**:
```python
# tests/e2e/test_full_stack.py

async def test_full_simulation_lifecycle():
    """Test complete flow: API → Rust → Frontend"""
    
    # 1. Create simulation via API
    response = await client.post("/simulations/create", json=config)
    assert response.status_code == 200
    
    # 2. Submit transaction
    tx_response = await client.post("/transactions", json={
        "sender_id": "A",
        "receiver_id": "B",
        "amount": 100000,
    })
    tx_id = tx_response.json()["id"]
    
    # 3. Advance ticks until settled
    for _ in range(20):
        await client.post("/simulations/tick")
        tx = await client.get(f"/transactions/{tx_id}")
        if tx.json()["status"] == "settled":
            break
    
    # 4. Verify final state
    state = await client.get("/simulations/state")
    agents = state.json()["agents"]
    
    assert agents["A"]["balance"] < initial_balance_a
    assert agents["B"]["balance"] > initial_balance_b
```

**Tasks**:
- [ ] Write E2E tests for all features
- [ ] Test error paths
- [ ] Test edge cases

**Day 3-4: CLI Testing**

**Test CLI with real scenarios**:
```bash
# Script: tests/cli/test_scenarios.sh

# Scenario 1: Simple payment
./payment-sim create --config examples/simple.yaml
./payment-sim submit-tx --sender A --receiver B --amount 100000
./payment-sim tick --count 10
./payment-sim state | grep "SETTLED"

# Scenario 2: Insufficient funds
./payment-sim create --config examples/low-balance.yaml
./payment-sim submit-tx --sender A --receiver B --amount 999999999
./payment-sim tick --count 10
./payment-sim state | grep "PENDING"

# Scenario 3: Determinism
./payment-sim create --config examples/seed-12345.yaml
./payment-sim tick --count 100 > output1.txt
./payment-sim create --config examples/seed-12345.yaml
./payment-sim tick --count 100 > output2.txt
diff output1.txt output2.txt  # Should be identical
```

**Tasks**:
- [ ] Create test scenarios
- [ ] Automate testing
- [ ] Verify determinism

**Day 5: Performance Testing**

**Benchmark core operations**:
```rust
// benches/foundation_bench.rs

fn tick_performance(c: &mut Criterion) {
    let mut orch = create_test_orchestrator();
    
    c.bench_function("tick_100_agents", |b| {
        b.iter(|| {
            orch.tick().unwrap()
        })
    });
}
```

**Targets**:
- [ ] Tick with 10 agents, 100 transactions: < 1ms
- [ ] Create orchestrator: < 10ms
- [ ] Submit transaction: < 100μs

**Day 6-7: Documentation**

**Create comprehensive docs**:
- [ ] Update AGENTS.md with foundation features
- [ ] Create API.md with endpoint documentation
- [ ] Create TESTING.md with test instructions
- [ ] Create DEVELOPMENT.md with setup guide
- [ ] Record demo video (optional)

**Deliverable**: Fully tested, documented foundation

---

## File Structure (Complete)

```
payment-simulator/
├── README.md
├── AGENTS.md
├── Cargo.toml                 # Workspace
│
├── backend/                   # Rust core
│   ├── Cargo.toml
│   ├── src/
│   │   ├── lib.rs            # PyO3 exports
│   │   ├── core/
│   │   │   ├── mod.rs
│   │   │   └── time.rs
│   │   ├── models/
│   │   │   ├── mod.rs
│   │   │   ├── agent.rs
│   │   │   ├── transaction.rs
│   │   │   └── enums.rs
│   │   ├── rng/
│   │   │   ├── mod.rs
│   │   │   └── manager.rs
│   │   └── orchestrator/
│   │       ├── mod.rs
│   │       └── engine.rs
│   ├── tests/
│   │   ├── time_manager.rs
│   │   ├── rng_determinism.rs
│   │   ├── agent_state.rs
│   │   ├── transaction.rs
│   │   └── orchestrator.rs
│   └── benches/
│       └── foundation_bench.rs
│
├── api/                       # Python API
│   ├── payment_simulator/
│   │   ├── __init__.py
│   │   ├── config/
│   │   │   ├── __init__.py
│   │   │   ├── schemas.py
│   │   │   └── loader.py
│   │   ├── backends/
│   │   │   ├── __init__.py
│   │   │   └── rust_wrapper.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── main.py
│   │       ├── dependencies.py
│   │       └── routes/
│   │           ├── simulations.py
│   │           └── transactions.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── integration/
│   │   │   ├── test_rust_ffi.py
│   │   │   └── test_api.py
│   │   └── e2e/
│   │       └── test_full_stack.py
│   └── pyproject.toml
│
├── cli/                       # CLI tool
│   ├── Cargo.toml
│   ├── src/
│   │   ├── main.rs
│   │   ├── commands/
│   │   │   ├── mod.rs
│   │   │   ├── create.rs
│   │   │   ├── tick.rs
│   │   │   ├── submit.rs
│   │   │   └── state.rs
│   │   └── display/
│   │       ├── mod.rs
│   │       └── formatters.rs
│   └── tests/
│       └── cli_tests.rs
│
├── frontend/                  # React UI
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── AgentCard.tsx
│   │   │   ├── TransactionList.tsx
│   │   │   └── ControlPanel.tsx
│   │   ├── context/
│   │   │   └── SimulationContext.tsx
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── tsconfig.json
│
├── config/                    # Example configs
│   ├── simple.yaml
│   └── demo.yaml
│
├── docs/
│   ├── API.md
│   ├── TESTING.md
│   └── DEVELOPMENT.md
│
└── scripts/
    ├── build-all.sh
    ├── test-all.sh
    └── demo.sh
```

---

## Daily Development Loop

### Morning (30 min)
```bash
# Pull, rebuild, test
git pull
cd backend && cargo build --release
cd .. && maturin develop --release
cargo test && pytest
```

### During Work
1. Write test first (TDD)
2. Implement feature
3. Run tests frequently
4. Commit small changes

### Before Commit
```bash
# Format and lint
cd backend && cargo fmt && cargo clippy
cd ../api && black . && mypy .
cd ../frontend && npm run lint

# Full test suite
./scripts/test-all.sh

# Commit
git add .
git commit -m "feat: add transaction settlement"
```

---

## Key Implementation Rules

### 1. Test-Driven Development
```rust
// ALWAYS write test first
#[test]
fn test_agent_debit() {
    let mut agent = AgentState::new("A".into(), 100_000, 50_000);
    agent.debit(30_000).unwrap();
    assert_eq!(agent.balance(), 70_000);
}

// Then implement
impl AgentState {
    pub fn debit(&mut self, amount: i64) -> Result<()> {
        if amount > self.available_liquidity() {
            return Err(Error::InsufficientFunds);
        }
        self.balance -= amount;
        Ok(())
    }
}
```

### 2. Money Always i64
```rust
// ✅ CORRECT
pub struct Transaction {
    amount: i64,  // cents
}

// ❌ WRONG
pub struct Transaction {
    amount: f64,  // DON'T
}
```

### 3. Determinism Checks
```python
def test_determinism():
    """Same seed must produce same results."""
    results1 = run_simulation(seed=12345)
    results2 = run_simulation(seed=12345)
    assert results1 == results2
```

### 4. Minimal FFI Crossings
```python
# ✅ GOOD: One call
tx_ids = ["tx1", "tx2", "tx3"]
results = orchestrator.process_transactions(tx_ids)

# ❌ BAD: Three calls
for tx_id in tx_ids:
    orchestrator.process_transaction(tx_id)
```

### 5. Clear Error Messages
```rust
if amount <= 0 {
    return Err(Error::InvalidAmount {
        amount,
        reason: "Amount must be positive"
    });
}
```

---

## Success Metrics

### Technical
- [ ] All tests pass (Rust, Python, E2E)
- [ ] No memory leaks (run valgrind)
- [ ] Determinism verified (100 runs, same results)
- [ ] Performance targets met
- [ ] No panics or crashes

### Functional
- [ ] Can create simulation with 10 agents
- [ ] Can submit 100 transactions
- [ ] Can run 1000 ticks
- [ ] CLI is usable for debugging
- [ ] Frontend displays state correctly
- [ ] API returns correct data

### Quality
- [ ] Code coverage > 80%
- [ ] No clippy warnings
- [ ] No mypy errors
- [ ] Documentation complete
- [ ] Examples work

---

## Risk Mitigation

### Risk 1: FFI Issues
**Mitigation**:
- Start with simple types only
- Test thoroughly at each step
- Use valgrind to check memory
- Keep FFI surface minimal

### Risk 2: Determinism Breaks
**Mitigation**:
- Test determinism from day 1
- Never use system time or random.random()
- Always seed RNG explicitly
- Add determinism tests to CI

### Risk 3: Architecture Mistakes
**Mitigation**:
- Follow documented patterns strictly
- Review with AGENTS.md frequently
- Keep scope minimal
- Refactor early if needed

### Risk 4: Scope Creep
**Mitigation**:
- Stick to foundation scope
- Say "no" to features
- Document deferred features
- Focus on architecture proof

---

## Post-Foundation (What's Next)

After foundation is solid, add features in order:

### Phase 7: Queues (Week 8)
- Add transaction queue per agent
- Queue management (add, remove, peek)
- Settlement from queue

### Phase 8: Arrivals (Week 9-10)
- Implement arrival generation
- Per-agent configurations
- Distribution sampling
- Test heterogeneous agents

### Phase 9: LSM (Week 11-12)
- Bilateral offsetting
- Cycle detection
- Batch optimization

### Phase 10: Costs (Week 13)
- Overdraft costs
- Delay penalties
- Split fees

### Phase 11: Policies (Week 14-15)
- Policy framework
- Simple policies
- Policy evaluation

### Phase 12: WebSocket (Week 16)
- Real-time streaming
- Frontend updates
- Performance optimization

---

## Appendix: Example Minimal Config

```yaml
# config/foundation-demo.yaml
simulation:
  ticks_per_day: 100
  seed: 12345

agents:
  - id: BANK_A
    balance: 1000000  # $10,000.00
    credit_limit: 500000  # $5,000.00
    
  - id: BANK_B
    balance: 1500000  # $15,000.00
    credit_limit: 750000  # $7,500.00
    
  - id: BANK_C
    balance: 2000000  # $20,000.00
    credit_limit: 1000000  # $10,000.00

# No arrivals - manual transaction submission only
# No costs - just track balances
# No LSM - just immediate settlement
```

---

## Timeline Summary

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Rust core types | Types compile, unit tests pass |
| 2 | Rust orchestrator | Integration tests pass |
| 3 | PyO3 bindings | FFI works, Python tests pass |
| 4 | Python API | API endpoints work |
| 5 | CLI tool | CLI functional for debugging |
| 6 | React frontend | Frontend displays state |
| 7 | Integration & testing | All tests pass, docs complete |

**Total**: 7 weeks for solid foundation

**Then**: Add features incrementally (1-2 weeks each)

---

*This foundation establishes the architecture while remaining simple enough to build quickly and test thoroughly. Each layer is proven before adding the next. Once complete, you have a solid base for adding complexity.*