# Payment Simulator - Foundation Implementation Plan

> **Status Update (2025-10-27)**: Phase 1-3 completed. See implementation status below.

## Executive Summary

This plan outlined the implementation of a **minimal but complete** foundation. The goal was to prove the architecture works end-to-end with the simplest possible feature set, then add complexity incrementally.

**Current Progress**:
- ✅ **Phase 1-2 Complete**: Time, RNG, Agent, Transaction models
- ✅ **Phase 3 Complete**: RTGS settlement engine + LSM (Liquidity-Saving Mechanisms)
- 🎯 **Future Phases**: Orchestrator, API layer, Frontend

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

#### Python API Layer - 🎯 Future (Phase 4+)
1. **Configuration** - Not implemented
   - Load YAML config
   - Pydantic validation
   - Convert to Rust format

2. **FFI Wrapper** - Not implemented
   - Create orchestrator
   - Submit transactions
   - Advance ticks
   - Query state

3. **FastAPI Endpoints** - Not implemented
   - POST /simulations/create
   - POST /simulations/tick
   - GET /simulations/state
   - POST /transactions
   - GET /transactions/{id}

4. **Basic Error Handling** - Not implemented
   - FFI error conversion
   - HTTP error responses

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

### 🎯 Future Phases (After Phase 3)

#### Phase 4: Orchestrator & Arrivals
- Tick loop orchestration
- Arrival generation (deterministic RNG)
- Integration: RTGS + LSM coordination
- Policy evaluation hooks
- Cost accrual (liquidity, delay, penalties)

#### Phase 5: Python API & FFI
- Python FFI wrapper (PyO3 bindings)
- FastAPI endpoints
- Configuration loading (YAML → Pydantic → Rust)
- CLI tool

#### Phase 6+: Frontend & Advanced Features
- React visualization
- WebSocket streaming for real-time updates

**Deferred Features** (beyond Phase 6):
- Agent policies/decision trees (AI/RL)
- Advanced cost calculation
- Split transactions
- Priority-based queue ordering
- Timed transactions (T2-style)
- WebSocket streaming
- A/B testing framework

---

## Success Criteria

The foundation is complete when:

1. ✅ **Rust compiles and tests pass**
   - All core types implemented
   - Unit tests for each module
   - Integration tests for orchestrator

2. ✅ **FFI boundary works**
   - Python can import Rust module
   - Can create orchestrator
   - Can submit transactions and advance ticks
   - No memory leaks or crashes

3. ✅ **Determinism proven**
   - Same seed + same actions = same results
   - Replay tests pass
   - RNG state persists correctly

4. ✅ **CLI functional**
   - Can run a 100-tick simulation
   - Can submit transactions
   - Output is readable
   - Useful for debugging

5. ✅ **API operational**
   - All endpoints work
   - Returns correct data
   - Error handling works

6. ✅ **Frontend displays state**
   - Shows agents and balances
   - Shows transactions
   - Can advance ticks
   - Updates correctly

7. ✅ **End-to-end test passes**
   - Create simulation via API
   - Submit transaction via API
   - Advance ticks until settled
   - Verify in frontend
   - Query via CLI

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