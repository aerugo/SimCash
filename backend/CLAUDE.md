# Rust Backend - Payment Simulator Core

## You Are Here: `/backend`

This is the **Rust simulation engine** - the performance-critical core of the payment simulator. Everything here prioritizes correctness, safety, and speed.

**Your role**: You're an expert Rust developer who understands systems programming, zero-cost abstractions, and FFI safety with PyO3.

---

## 🎯 Quick Reference

### Project Structure
```
backend/
├── src/
│   ├── lib.rs              ← PyO3 FFI exports (what Python sees)
│   ├── core/               ← Time management, initialization
│   │   ├── mod.rs
│   │   ├── time.rs         ← TimeManager (tick/day tracking)
│   │   └── init.rs         ← State initialization from config
│   ├── models/             ← Core domain types
│   │   ├── mod.rs
│   │   ├── transaction.rs  ← Transaction struct
│   │   ├── agent.rs        ← Agent (bank) struct
│   │   └── state.rs        ← SimulationState
│   ├── orchestrator/       ← Main simulation loop
│   │   ├── mod.rs
│   │   └── tick.rs         ← tick() function - the heart
│   ├── settlement/         ← Settlement engines
│   │   ├── mod.rs
│   │   ├── rtgs.rs         ← Real-time gross settlement
│   │   └── lsm.rs          ← Liquidity-saving mechanism
│   ├── arrivals/           ← Transaction generation
│   │   ├── mod.rs
│   │   ├── generator.rs    ← ArrivalGenerator
│   │   └── distributions.rs ← Amount sampling (Normal, LogNormal, etc.)
│   ├── costs/              ← Cost calculations
│   │   ├── mod.rs
│   │   └── calculator.rs   ← Fee/penalty calculation
│   └── rng/                ← Deterministic RNG
│       ├── mod.rs
│       └── xorshift.rs     ← xorshift64* implementation
├── tests/                  ← Integration tests
│   ├── test_determinism.rs
│   ├── test_settlement.rs
│   └── test_arrivals.rs
└── Cargo.toml
```

---

## 🔴 Rust-Specific Critical Rules

### 1. Money is ALWAYS i64 - No Exceptions

```rust
// ✅ CORRECT
pub struct Transaction {
    pub amount: i64,              // Cents
    pub remaining_amount: i64,    // Cents
}

pub struct Agent {
    pub balance: i64,             // Cents
    pub credit_limit: i64,        // Cents
}

// ❌ WRONG - Never use floats for money
pub struct BadTransaction {
    pub amount: f64,  // NO!
}
```

**Conversion Helpers** (if you MUST interface with human-readable dollars):
```rust
/// Convert cents to dollars for display ONLY
pub fn cents_to_dollars_string(cents: i64) -> String {
    format!("${}.{:02}", cents / 100, cents.abs() % 100)
}

/// Parse dollars to cents (for configuration input only)
pub fn dollars_to_cents(dollars: f64) -> i64 {
    (dollars * 100.0).round() as i64
}
```

**Never** use these functions in calculation logic. They're for I/O only.

### 2. PyO3 FFI Patterns

#### Exporting to Python (`lib.rs`)
```rust
use pyo3::prelude::*;

#[pyclass]
pub struct Orchestrator {
    state: SimulationState,
}

#[pymethods]
impl Orchestrator {
    #[new]
    pub fn new(config: &PyDict) -> PyResult<Self> {
        // Validate and extract
        let ticks_per_day = config
            .get_item("ticks_per_day")?
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyValueError, _>(
                "Missing 'ticks_per_day' in config"
            ))?
            .extract::<usize>()?;
        
        // Build Rust types
        let state = SimulationState::new(ticks_per_day);
        
        Ok(Self { state })
    }
    
    pub fn tick(&mut self) -> PyResult<PyObject> {
        // Do work in Rust
        let events = self.state.advance_tick()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Tick failed: {}", e)
            ))?;
        
        // Convert to Python-friendly format
        Python::with_gil(|py| {
            let result = PyDict::new(py);
            result.set_item("events", events.into_py(py))?;
            Ok(result.into())
        })
    }
}
```

**Key Rules**:
- Use `PyResult<T>` for all fallible operations
- Validate inputs at boundary before passing to internal Rust functions
- Convert errors to `PyErr` with descriptive messages
- Return simple types: `PyDict`, `PyList`, primitives
- Never return references to internal Rust state

#### Error Handling Pattern
```rust
pub enum SimulationError {
    InvalidAgent(String),
    InsufficientFunds { agent_id: String, required: i64, available: i64 },
    TransactionNotFound(String),
}

impl std::fmt::Display for SimulationError {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            Self::InvalidAgent(id) => write!(f, "Agent '{}' does not exist", id),
            Self::InsufficientFunds { agent_id, required, available } => {
                write!(f, "Agent '{}' has {} but needs {}", agent_id, available, required)
            }
            Self::TransactionNotFound(id) => write!(f, "Transaction '{}' not found", id),
        }
    }
}

impl From<SimulationError> for PyErr {
    fn from(err: SimulationError) -> PyErr {
        PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(err.to_string())
    }
}
```

### 3. Deterministic RNG Pattern

```rust
pub struct RngManager {
    state: u64,
}

impl RngManager {
    pub fn new(seed: u64) -> Self {
        Self { state: seed }
    }
    
    /// xorshift64* algorithm
    /// Returns: (random_value, new_state)
    pub fn next(&mut self) -> (u64, u64) {
        let mut x = self.state;
        x ^= x >> 12;
        x ^= x << 25;
        x ^= x >> 27;
        self.state = x;
        let result = x.wrapping_mul(0x2545F4914F6CDD1D);
        (result, x)
    }
    
    /// Sample from range [min, max)
    pub fn range(&mut self, min: i64, max: i64) -> i64 {
        let (value, _) = self.next();
        let range_size = (max - min) as u64;
        min + (value % range_size) as i64
    }
}

// Usage in state
pub struct SimulationState {
    pub rng: RngManager,
    // ... other fields
}

impl SimulationState {
    pub fn sample_arrival(&mut self) -> i64 {
        let amount = self.rng.range(10000, 100000); // $100-$1000
        // RNG state already updated by .range()
        amount
    }
}
```

**Critical**: The RNG mutates its own state. No manual seed management needed within Rust. Only persist seed across FFI boundary.

### 4. Performance Hot Paths

These functions are called thousands of times per simulation. Optimize ruthlessly:

#### Tick Loop (orchestrator/tick.rs)
```rust
pub fn advance_tick(state: &mut SimulationState) -> Result<TickEvents, SimulationError> {
    // Pre-allocate capacity
    let mut events = TickEvents::with_capacity(state.agents.len() * 2);
    
    // Increment time
    state.time.advance();
    
    // Generate arrivals (hot path)
    let arrivals = generate_arrivals(state)?;
    events.arrivals = arrivals;
    
    // Attempt settlements (hot path)
    let settlements = attempt_settlements(state)?;
    events.settlements = settlements;
    
    // Update costs (moderate path)
    update_costs(state);
    
    Ok(events)
}
```

**Optimization Checklist**:
- ✅ Pre-allocate Vecs with `with_capacity()`
- ✅ Use `&mut` for in-place updates (avoid clones)
- ✅ Inline small hot functions `#[inline]`
- ✅ Avoid allocations in tight loops
- ❌ Don't optimize prematurely - profile first!

#### RTGS Settlement (settlement/rtgs.rs)
```rust
#[inline]
pub fn try_settle(
    sender: &mut Agent,
    receiver: &mut Agent,
    amount: i64,
) -> Result<(), SettlementError> {
    // Fast path: sufficient balance
    if sender.balance >= amount {
        sender.balance -= amount;
        receiver.balance += amount;
        return Ok(());
    }
    
    // Check credit
    let effective_balance = sender.balance + sender.credit_limit;
    if effective_balance >= amount {
        sender.balance -= amount;
        receiver.balance += amount;
        return Ok(());
    }
    
    Err(SettlementError::InsufficientLiquidity {
        required: amount,
        available: effective_balance,
    })
}
```

---

## Common Rust Patterns for This Project

### Pattern 1: Builder for Complex Types

```rust
pub struct Transaction {
    pub id: String,
    pub sender_id: String,
    pub receiver_id: String,
    pub amount: i64,
    pub remaining_amount: i64,
    pub arrival_tick: usize,
    pub deadline_tick: usize,
    pub priority: u8,
    pub is_divisible: bool,
    pub status: TransactionStatus,
}

impl Transaction {
    pub fn new(
        sender_id: String,
        receiver_id: String,
        amount: i64,
        arrival_tick: usize,
        deadline_tick: usize,
    ) -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            sender_id,
            receiver_id,
            amount,
            remaining_amount: amount,
            arrival_tick,
            deadline_tick,
            priority: 5, // Default
            is_divisible: false, // Default
            status: TransactionStatus::Pending,
        }
    }
    
    pub fn with_priority(mut self, priority: u8) -> Self {
        self.priority = priority;
        self
    }
    
    pub fn divisible(mut self) -> Self {
        self.is_divisible = true;
        self
    }
}

// Usage
let tx = Transaction::new(
    "BANK_A".to_string(),
    "BANK_B".to_string(),
    100000,
    10,
    50,
).with_priority(8).divisible();
```

### Pattern 2: State Access with HashMap

```rust
use std::collections::HashMap;

pub struct SimulationState {
    pub agents: HashMap<String, Agent>,
    pub transactions: HashMap<String, Transaction>,
    pub time: TimeManager,
    pub rng: RngManager,
}

impl SimulationState {
    pub fn get_agent_mut(&mut self, id: &str) -> Result<&mut Agent, SimulationError> {
        self.agents
            .get_mut(id)
            .ok_or_else(|| SimulationError::InvalidAgent(id.to_string()))
    }
    
    pub fn get_transaction(&self, id: &str) -> Result<&Transaction, SimulationError> {
        self.transactions
            .get(id)
            .ok_or_else(|| SimulationError::TransactionNotFound(id.to_string()))
    }
}
```

**Note**: For determinism, iterate over HashMap entries in sorted order:
```rust
// Sort keys for deterministic iteration
let mut agent_ids: Vec<_> = state.agents.keys().collect();
agent_ids.sort();

for agent_id in agent_ids {
    let agent = &state.agents[agent_id];
    // ... process
}
```

### Pattern 3: Event Collection

```rust
#[derive(Debug, Clone)]
pub struct TickEvents {
    pub tick: usize,
    pub arrivals: Vec<Transaction>,
    pub settlements: Vec<Settlement>,
    pub queued: Vec<String>, // Transaction IDs
    pub dropped: Vec<String>,
}

impl TickEvents {
    pub fn with_capacity(cap: usize) -> Self {
        Self {
            tick: 0,
            arrivals: Vec::with_capacity(cap),
            settlements: Vec::with_capacity(cap),
            queued: Vec::with_capacity(cap / 2),
            dropped: Vec::with_capacity(cap / 10),
        }
    }
}

// Convert to Python
impl IntoPy<PyObject> for TickEvents {
    fn into_py(self, py: Python) -> PyObject {
        let dict = PyDict::new(py);
        dict.set_item("tick", self.tick).unwrap();
        dict.set_item("arrivals", self.arrivals.len()).unwrap();
        // ... more fields
        dict.into()
    }
}
```

---

## Testing Patterns

### Unit Tests (in same file as code)

```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_rtgs_settles_with_sufficient_balance() {
        let mut sender = Agent::new("A".to_string(), 100000, 0);
        let mut receiver = Agent::new("B".to_string(), 50000, 0);
        
        let result = try_settle(&mut sender, &mut receiver, 30000);
        
        assert!(result.is_ok());
        assert_eq!(sender.balance, 70000);
        assert_eq!(receiver.balance, 80000);
    }
    
    #[test]
    fn test_rtgs_fails_insufficient_liquidity() {
        let mut sender = Agent::new("A".to_string(), 10000, 0);
        let mut receiver = Agent::new("B".to_string(), 0, 0);
        
        let result = try_settle(&mut sender, &mut receiver, 50000);
        
        assert!(matches!(result, Err(SettlementError::InsufficientLiquidity { .. })));
    }
}
```

### Integration Tests (`tests/`)

```rust
// tests/test_determinism.rs
use payment_simulator_core_rs::Orchestrator;

#[test]
fn test_deterministic_replay() {
    let config = test_config_with_seed(12345);
    
    let mut orch1 = Orchestrator::new(config.clone()).unwrap();
    let mut orch2 = Orchestrator::new(config.clone()).unwrap();
    
    for _ in 0..100 {
        let events1 = orch1.tick().unwrap();
        let events2 = orch2.tick().unwrap();
        
        assert_eq!(events1.arrivals.len(), events2.arrivals.len());
        // ... compare more fields
    }
}
```

### Property-Based Tests (with proptest)

```rust
use proptest::prelude::*;

proptest! {
    #[test]
    fn test_settlement_preserves_money(
        sender_balance in 0i64..1000000,
        receiver_balance in 0i64..1000000,
        amount in 1i64..100000,
    ) {
        let mut sender = Agent::new("A".to_string(), sender_balance, 0);
        let mut receiver = Agent::new("B".to_string(), receiver_balance, 0);
        
        let total_before = sender.balance + receiver.balance;
        
        if sender.balance >= amount {
            try_settle(&mut sender, &mut receiver, amount).unwrap();
            let total_after = sender.balance + receiver.balance;
            prop_assert_eq!(total_before, total_after); // Money conserved!
        }
    }
}
```

---

## Debugging Tips

### Add Logging (use tracing crate)

```rust
use tracing::{debug, info, warn, error};

pub fn attempt_settlement(
    state: &mut SimulationState,
    tx_id: &str,
) -> Result<(), SimulationError> {
    let tx = state.get_transaction(tx_id)?;
    
    debug!(
        tx_id = %tx.id,
        sender = %tx.sender_id,
        amount = tx.remaining_amount,
        "Attempting settlement"
    );
    
    let sender = state.get_agent_mut(&tx.sender_id)?;
    
    if sender.balance < tx.remaining_amount {
        warn!(
            agent = %sender.id,
            balance = sender.balance,
            required = tx.remaining_amount,
            "Insufficient liquidity"
        );
        return Err(SimulationError::InsufficientFunds {
            agent_id: sender.id.clone(),
            required: tx.remaining_amount,
            available: sender.balance,
        });
    }
    
    info!(
        tx_id = %tx.id,
        amount = tx.remaining_amount,
        "Settlement successful"
    );
    
    Ok(())
}
```

### Verify Determinism in Tests

```rust
#[test]
fn test_rng_determinism() {
    let mut rng1 = RngManager::new(12345);
    let mut rng2 = RngManager::new(12345);
    
    for _ in 0..1000 {
        let (val1, _) = rng1.next();
        let (val2, _) = rng2.next();
        assert_eq!(val1, val2);
    }
}
```

### Check for Float Contamination

```bash
# Search for any float usage in money code
rg "f32|f64" backend/src/ --type rust | grep -v "test"
```

---

## Performance Profiling

### Criterion Benchmarks (`benches/`)

```rust
// benches/tick_benchmark.rs
use criterion::{black_box, criterion_group, criterion_main, Criterion};
use payment_simulator_core_rs::*;

fn bench_tick(c: &mut Criterion) {
    let mut state = create_large_test_state(); // 100 agents, 1000 transactions
    
    c.bench_function("tick_100_agents", |b| {
        b.iter(|| {
            let _ = black_box(advance_tick(&mut state));
        });
    });
}

criterion_group!(benches, bench_tick);
criterion_main!(benches);
```

Run with:
```bash
cargo bench
```

### Flamegraphs

```bash
cargo install flamegraph
cargo flamegraph --bench tick_benchmark
```

---

## Common Mistakes in This Codebase

### ❌ Mistake 1: Modifying Borrowed State
```rust
// BAD: Can't modify while iterating
for (id, agent) in &state.agents {
    state.process_agent(id); // COMPILE ERROR: Can't borrow mutably
}

// GOOD: Collect IDs first
let agent_ids: Vec<String> = state.agents.keys().cloned().collect();
for id in agent_ids {
    state.process_agent(&id);
}
```

### ❌ Mistake 2: Panic in FFI Boundary
```rust
// BAD: Unwrap can panic
#[pymethods]
impl Orchestrator {
    pub fn tick(&mut self) -> PyObject {
        let events = self.state.advance_tick().unwrap(); // DON'T PANIC!
        // ...
    }
}

// GOOD: Return PyResult
#[pymethods]
impl Orchestrator {
    pub fn tick(&mut self) -> PyResult<PyObject> {
        let events = self.state.advance_tick()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Tick failed: {}", e)
            ))?;
        // ...
        Ok(result)
    }
}
```

### ❌ Mistake 3: Forgetting to Update RNG State
```rust
// BAD: RNG not advanced
let (random_value, new_seed) = rng.next_u64(current_seed);
// ... use random_value but forget to update state

// GOOD: RNG is self-mutating in our design
let random_value = self.rng.range(0, 100); // State updated internally
```

---

## Build and Run Commands

```bash
# Build (debug)
cargo build

# Build (optimized)
cargo build --release

# Run tests
cargo test

# Run tests with output
cargo test -- --nocapture

# Run specific test
cargo test test_determinism

# Check without building
cargo check

# Lint
cargo clippy -- -D warnings

# Format
cargo fmt

# Build Python extension (requires maturin)
cd .. && maturin develop --release

# Run benchmarks
cargo bench
```

---

## 🎯 Phase 3+ Target Design: T2-Style RTGS Settlement

**Current Status**: ⏳ Phase 3 implementation planned (see `/docs/phase3_rtgs_analysis.md`)

**What's Already Complete** (Phase 1-2):
- ✅ `Agent` model with balance and credit_limit
- ✅ `Transaction` model with status lifecycle
- ✅ `TimeManager` for discrete time
- ✅ Deterministic `RngManager`

**What This Section Describes**: Target patterns for Phase 3+ implementation based on T2-style RTGS design from `/docs/game_concept_doc.md`.

### Target: Central Bank Settlement Model

In the T2-style model, settlement happens at the **central bank level**:

```
Client A → Bank A (internal) → RTGS @ Central Bank → Bank B (internal) → Client B
```

**Current `Agent` model interpretation for Phase 3**:
- `Agent.balance` = Bank's settlement account balance **at central bank**
- `Agent.credit_limit` = Intraday credit headroom (overdraft/collateralized)
- `Agent.can_pay(amount)` = Checks `balance + credit_limit >= amount`

**Phase 3 will implement**: RTGS settlement engine that operates on these agent balances.

### Target Pattern: RTGS Settlement Function (Phase 3)

```rust
// ⏳ PHASE 3 TARGET PATTERN

/// Settle payment at RTGS (central bank settlement)
///
/// This is the core T2-style settlement operation:
/// 1. Check sender has sufficient liquidity (balance + credit)
/// 2. Debit sender's central bank account
/// 3. Credit receiver's central bank account
/// 4. Mark transaction as settled
///
/// If insufficient liquidity, returns error and no state changes occur.
pub fn try_settle_rtgs(
    sender: &mut Agent,
    receiver: &mut Agent,
    transaction: &mut Transaction,
    tick: usize,
) -> Result<(), SettlementError> {
    // Validate transaction state
    if transaction.is_fully_settled() {
        return Err(SettlementError::AlreadySettled);
    }

    let amount = transaction.remaining_amount();

    // Check liquidity (balance + credit headroom)
    if !sender.can_pay(amount) {
        return Err(SettlementError::InsufficientLiquidity {
            required: amount,
            available: sender.available_liquidity(),
        });
    }

    // Execute settlement (atomic operation at CB)
    sender.debit(amount)?;
    receiver.credit(amount);
    transaction.settle(amount, tick)?;

    Ok(())
}
```

### Target Pattern: Central RTGS Queue (Phase 3)

```rust
// ⏳ PHASE 3 TARGET PATTERN

/// SimulationState will be extended to include central RTGS queue
pub struct SimulationState {
    pub agents: HashMap<String, Agent>,
    pub transactions: HashMap<String, Transaction>,

    // Phase 3: Central RTGS queue (transactions awaiting liquidity)
    pub rtgs_queue: Vec<String>,  // Transaction IDs

    // Phase 1 components
    pub time: TimeManager,
    pub rng: RngManager,
}

/// Submit transaction to RTGS (Phase 3)
///
/// Attempts immediate settlement. If insufficient liquidity, adds to central queue.
pub fn submit_to_rtgs(
    state: &mut SimulationState,
    transaction: Transaction,
    tick: usize,
) -> Result<SubmissionResult, SettlementError> {
    let tx_id = transaction.id().to_string();
    state.transactions.insert(tx_id.clone(), transaction);

    // Attempt immediate settlement
    let sender = state.agents.get_mut(&sender_id)?;
    let receiver = state.agents.get_mut(&receiver_id)?;
    let transaction = state.transactions.get_mut(&tx_id).unwrap();

    match try_settle_rtgs(sender, receiver, transaction, tick) {
        Ok(()) => Ok(SubmissionResult::SettledImmediately { tick }),
        Err(SettlementError::InsufficientLiquidity { .. }) => {
            // Add to central queue
            state.rtgs_queue.push(tx_id);
            Ok(SubmissionResult::Queued { position: state.rtgs_queue.len() })
        }
        Err(e) => Err(e),
    }
}
```

### Target Pattern: Queue Processing (Phase 3)

```rust
// ⏳ PHASE 3 TARGET PATTERN

/// Process RTGS queue each tick (retry pending transactions)
pub fn process_rtgs_queue(
    state: &mut SimulationState,
    tick: usize,
) -> QueueProcessingResult {
    let mut settled_count = 0;
    let mut settled_value = 0i64;
    let mut still_pending = Vec::new();

    for tx_id in state.rtgs_queue.drain(..) {
        let transaction = state.transactions.get_mut(&tx_id).unwrap();

        // Check if past deadline → drop
        if transaction.is_past_deadline(tick) {
            transaction.drop_transaction(tick);
            continue;
        }

        // Attempt settlement
        let sender = state.agents.get_mut(transaction.sender_id()).unwrap();
        let receiver = state.agents.get_mut(transaction.receiver_id()).unwrap();

        match try_settle_rtgs(sender, receiver, transaction, tick) {
            Ok(()) => {
                settled_count += 1;
                settled_value += transaction.amount();
            }
            Err(SettlementError::InsufficientLiquidity { .. }) => {
                // Still can't settle, re-queue
                still_pending.push(tx_id);
            }
            Err(_) => {} // Other errors, don't re-queue
        }
    }

    state.rtgs_queue = still_pending;

    QueueProcessingResult {
        settled_count,
        settled_value,
        remaining_queue_size: state.rtgs_queue.len(),
    }
}
```

### Target Pattern: LSM Procedures (Phase 4)

```rust
// 🎯 PHASE 4 TARGET PATTERN (after Phase 3 complete)

/// Liquidity-Saving Mechanism: Bilateral Offsetting
///
/// Find A→B and B→A pairs in queue, settle with minimal net liquidity
pub fn lsm_bilateral_offset(
    queue: &[String],
    transactions: &HashMap<String, Transaction>,
) -> Vec<OffsetPair> {
    let mut offsets = Vec::new();

    for i in 0..queue.len() {
        for j in (i + 1)..queue.len() {
            let tx_i = &transactions[&queue[i]];
            let tx_j = &transactions[&queue[j]];

            // Check if A→B and B→A
            if tx_i.sender_id() == tx_j.receiver_id()
                && tx_i.receiver_id() == tx_j.sender_id()
            {
                let settle_amount = tx_i.remaining_amount().min(tx_j.remaining_amount());
                offsets.push(OffsetPair {
                    tx_a: queue[i].clone(),
                    tx_b: queue[j].clone(),
                    amount: settle_amount,
                });
            }
        }
    }

    offsets
}

/// LSM: Cycle Detection (A→B→C→A)
///
/// Find payment cycles that can settle with minimal net liquidity
pub fn lsm_find_cycles(
    queue: &[String],
    transactions: &HashMap<String, Transaction>,
    max_cycle_length: usize,
) -> Vec<Cycle> {
    // Detect cycles of length 3, 4, etc.
    // Settle cycle with min amount on cycle
    // This reduces net liquidity needed under gridlock

    vec![] // Implementation in Phase 4
}
```

### Key Differences: Current vs. Phase 3+

| Aspect | Current (Phase 1-2) | Phase 3 Target | Phase 4 Target |
|--------|---------------------|----------------|----------------|
| **Settlement** | Not implemented | RTGS immediate + queue | + LSM optimization |
| **Queue** | None | Central RTGS queue | + LSM procedures |
| **Agent balance** | Simple field | = CB settlement account | + liquidity recycling |
| **Terminology** | `Agent.balance` | (same, but interpreted as CB account) | (same) |

**Important**: Phase 1-2 code is **correct as-is**. The `Agent` and `Transaction` models don't need changes for Phase 3. They already represent the right concepts (see `/docs/phase3_rtgs_analysis.md` sections 1.1-1.2).

### Next Steps for Phase 3 Implementation

See `/docs/phase3_rtgs_analysis.md` for:
- Detailed implementation plan
- Test-driven development approach
- Complete function signatures
- Test case specifications

**Timeline**: Phase 3 estimated at 2-3 days (see phase3_rtgs_analysis.md section 5).

---

## When to Ask for Help

1. **FFI not working?** → Consider using the `ffi-specialist` subagent
2. **Complex algorithm needed?** → Use `ultrathink` mode
3. **Performance issue?** → Profile first, optimize second
4. **Not sure about pattern?** → Look for similar code in codebase
5. **Determinism broken?** → Check RNG usage and HashMap iteration

---

## Quick Checklist Before Committing

- [ ] No `f32` or `f64` for money calculations
- [ ] All public functions have doc comments
- [ ] Tests pass: `cargo test`
- [ ] No compiler warnings: `cargo clippy`
- [ ] Code formatted: `cargo fmt`
- [ ] FFI functions return `PyResult`
- [ ] RNG state properly managed
- [ ] Determinism verified (if relevant)
- [ ] Performance acceptable (if hot path)

---

*Last updated: 2025-10-27*
*For Python/FFI guidance, see `/api/CLAUDE.md`*
*For general patterns, see root `/CLAUDE.md`*