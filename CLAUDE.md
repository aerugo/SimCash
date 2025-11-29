# Payment Simulator - Multi-Agent Payment System

## Quick Context for Claude Code

This is a **high-performance payment simulator** modeling real-time settlement between banks. It's a hybrid Rust-Python system where performance-critical code lives in Rust, while Python provides developer ergonomics.

**Your role**: You're an expert systems programmer who understands both high-performance computing and developer experience. You write correct, maintainable code that follows the project's strict invariants.

---

## 🔴 CRITICAL INVARIANTS - NEVER VIOLATE

### 1. Money is ALWAYS i64 (Integer Cents)
```rust
// ✅ CORRECT
let amount: i64 = 100000; // $1,000.00 in cents

// ❌ NEVER DO THIS
let amount: f64 = 1000.00; // NO FLOATS FOR MONEY
```

**Why**: Floating point arithmetic introduces rounding errors that compound over millions of transactions. Financial systems demand exact arithmetic.

**Rule**: Every amount, balance, cost, and fee MUST be `i64` representing the smallest currency unit (cents for USD). All arithmetic stays in integer space.

### 2. Determinism is Sacred
```rust
// ✅ CORRECT - Seeded RNG, persist new seed
let (value, new_seed) = rng_manager.next_u64(current_seed);
state.rng_seed = new_seed; // CRITICAL: Don't forget!

// ❌ NEVER DO THIS
use std::time::SystemTime;
let random = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
```

**Why**: Simulation must be perfectly reproducible for debugging, research validation, and compliance auditing. Same seed + same inputs = same outputs.

**Rule**: 
- ALL randomness via seeded xorshift64* RNG
- ALWAYS persist the new seed after each RNG call
- NEVER use system time, hardware RNG, or non-deterministic hash maps

### 3. FFI Boundary is Minimal and Safe
```python
# ✅ CORRECT - Simple types at boundary
orchestrator = Orchestrator.new({
    "ticks_per_day": 100,
    "seed": 12345,
})

# ❌ NEVER DO THIS
# Don't pass complex Python objects to Rust
orchestrator.process(my_python_dataclass)
```

**Why**: FFI is fragile. Complex types, lifetime issues, and panics cause undefined behavior.

**Rules**:
- Pass only primitives, strings, and simple dicts/lists across FFI
- Validate ALL inputs at the boundary
- Rust returns `PyResult<T>`, Python catches as exceptions
- Minimize boundary crossings (batch operations)
- NO references to Rust objects from Python side

---

## Architecture at a Glance

```
┌─────────────────────────────────────────────────┐
│  Python FastAPI Middleware (/api)               │
│  - REST/WebSocket endpoints                     │
│  - Configuration validation (Pydantic)          │
│  - Lifecycle management                         │
└──────────────────┬──────────────────────────────┘
                   │ FFI (PyO3)
┌──────────────────▼──────────────────────────────┐
│  Rust Simulation Engine (/backend)              │
│  - Tick loop & time management                  │
│  - Settlement engine (RTGS + LSM)               │
│  - Transaction processing                       │
│  - Deterministic RNG                            │
│  - Performance-critical code                    │
└─────────────────────────────────────────────────┘
```

**Design Philosophy**:
- **Rust owns state**: Python only gets snapshots, never mutable references
- **Python orchestrates**: Configuration, API, testing live in Python
- **FFI is thin**: Minimal, stable API surface

---

## Domain Model (Use These Terms)

### Time
- **Tick**: Smallest discrete time unit (e.g., 1 tick ≈ 10 real-world minutes)
- **Day**: Collection of ticks (e.g., 100 ticks = 1 business day)
- **Episode**: Complete simulation run

### Agents (Banks)
- **Agent**: A participating bank with settlement account
- **Balance**: Current reserves in settlement account (i64 cents)
- **Credit Limit**: Daylight overdraft or collateralized credit
- **Queue**: Pending outgoing transactions awaiting liquidity
- **Policy**: Decision algorithm for timing and funding payments

### Transactions
- **Amount**: Payment value (i64 cents)
- **Sender/Receiver**: Agent IDs
- **Arrival Tick**: When transaction enters the system
- **Deadline**: Latest tick for settlement (or penalty applies)
- **Priority**: Urgency level (0-10, higher = more important)
- **Divisible**: Can the payment be split into parts?
- **Status**: pending → overdue (if past deadline) → partially_settled → settled
- **Overdue**: Transaction past its deadline but still settleable (with higher costs)

### Arrival Configurations
Each agent has a configuration controlling automatic transaction generation:
- **Rate Per Tick**: Expected outgoing transactions per tick (Poisson λ)
- **Amount Distribution**: Normal, LogNormal, Uniform, Exponential
- **Counterparty Weights**: Preferred receivers (models correspondent banking)
- **Time Windows**: Intraday rate patterns (morning rush, end-of-day spike)

### Settlement
- **RTGS**: Real-Time Gross Settlement (immediate if liquidity available)
- **Queue**: Holds insufficient-liquidity payments
- **LSM**: Liquidity-Saving Mechanism (find bilateral/multilateral offsets)
- **Gridlock**: Circular waiting where all agents block each other

### Costs
- **Overdraft Cost**: Fee for negative balance (basis points per day)
- **Delay Penalty**: Time-based cost per tick unsettled
- **Overdue Delay Multiplier**: Cost multiplier for overdue transactions (default 5x)
- **Deadline Penalty**: One-time penalty when transaction becomes overdue
- **Split Fee**: Cost to divide a payment
- **EOD Penalty**: Large penalty for transactions unsettled at day end

---

## File Organization

```
/
├── CLAUDE.md                    ← You are here
├── backend/
│   ├── CLAUDE.md                ← Rust-specific guidance
│   ├── src/
│   │   ├── lib.rs               ← PyO3 FFI exports
│   │   ├── core/                ← Time management, initialization
│   │   ├── models/              ← Transaction, Agent, State, Events
│   │   ├── orchestrator/        ← Main simulation loop
│   │   ├── settlement/          ← RTGS + LSM engines
│   │   └── rng/                 ← Deterministic RNG
│   ├── tests/                   ← Rust integration tests
│   └── Cargo.toml
├── api/
│   ├── CLAUDE.md                ← Python-specific guidance (TYPE SAFETY REQUIRED)
│   ├── payment_simulator/
│   │   ├── api/                 ← FastAPI routes
│   │   ├── cli/                 ← CLI tool (Typer)
│   │   │   ├── commands/        ← CLI command implementations
│   │   │   └── execution/       ← SimulationRunner, persistence
│   │   ├── config/              ← Pydantic schemas
│   │   └── persistence/         ← DuckDB persistence layer
│   ├── migrations/              ← Database schema migrations
│   ├── tests/                   ← Python tests
│   └── pyproject.toml           ← Build config + mypy/ruff settings
├── docs/
│   ├── architecture.md
│   ├── api.md
│   ├── game-design.md
│   └── plans/                   ← Feature implementation plans
└── .claude/
    ├── commands/                ← Custom slash commands
    └── agents/                  ← Specialized subagents
```

---

## 🎯 Critical Invariant: Replay Identity

**RULE**: `payment-sim replay` output MUST be byte-for-byte identical to `payment-sim run` output (modulo timing information).

This is achieved through the **StateProvider Pattern**:

```
┌─────────────────────────────────────────────────────────┐
│          display_tick_verbose_output()                  │
│          (Single Source of Truth for Display)           │
└────────────────┬───────────────────────────────────────┘
                 │
         ┌───────┴────────┐
         │ StateProvider  │  ← Protocol (interface)
         │   Protocol     │
         └───────┬────────┘
                 │
    ┌────────────┴─────────────┐
    │                          │
    ▼                          ▼
┌────────────────┐      ┌──────────────────┐
│ Orchestrator   │      │ Database         │
│ StateProvider  │      │ StateProvider    │
│ (Live FFI)     │      │ (Replay)         │
└────────────────┘      └──────────────────┘
```

### StateProvider Pattern

1. **Shared Display Logic**: Both `run` and `replay` use the same `display_tick_verbose_output()` function
2. **Data Abstraction**: Display code calls `StateProvider` methods, never touches Rust/DB directly
3. **Two Implementations**:
   - **OrchestratorStateProvider**: Wraps live Rust FFI (`run` mode)
   - **DatabaseStateProvider**: Wraps DuckDB queries (`replay` mode)

**Key Strength**: If you update display logic, it automatically applies to both run and replay.

### The Single Source of Truth Principle

**GOLDEN RULE:** The `simulation_events` table is the ONLY source of events for replay. No legacy tables, no manual reconstruction.

```
Run Mode:     Rust Events → FFI → Python → Display
                    ↓
Replay Mode:  Database simulation_events → Python → Display
```

Both paths must produce identical output because they use the same enriched event data.

### When Adding a New Event Type (Mandatory Workflow)

Follow this **strictly enforced workflow** when adding a new event that should appear in verbose output:

#### Step 1: Define Enriched Event in Rust

**File:** `backend/src/models/event.rs`

```rust
pub enum Event {
    // ... existing variants ...

    MyNewEvent {
        tick: i64,
        // ⚠️ CRITICAL: Include ALL fields needed for display
        // Don't store just IDs - store full display data
        agent_id: String,
        amount: i64,
        reason: String,
        calculation_details: Vec<i64>,  // Whatever display needs
    },
}
```

**Key Principle:** Events must be **self-contained**. Display code should never need to fetch additional data.

#### Step 2: Generate Event at Source

**File:** Wherever the event happens (e.g., `backend/src/settlement/lsm.rs`)

```rust
// When event occurs, create it with ALL data
let event = Event::MyNewEvent {
    tick: self.current_tick,
    agent_id: agent.id.clone(),
    amount: value,
    reason: "liquidity_threshold_exceeded".to_string(),
    calculation_details: vec![threshold, current_value, delta],
};

// Add to event log
self.events.push(event);
```

#### Step 3: Serialize via FFI

**File:** `backend/src/ffi/orchestrator.rs`

In `get_tick_events()` and `get_all_events()`, add serialization:

```rust
Event::MyNewEvent { tick, agent_id, amount, reason, calculation_details } => {
    let mut dict = HashMap::new();
    dict.insert("event_type".to_string(), "my_new_event".into());
    dict.insert("tick".to_string(), tick.into());
    dict.insert("agent_id".to_string(), agent_id.into());
    dict.insert("amount".to_string(), amount.into());
    dict.insert("reason".to_string(), reason.into());
    dict.insert("calculation_details".to_string(), calculation_details.into());
    dict
}
```

**⚠️ CRITICAL:** Serialize EVERY field. Missing fields break replay.

#### Step 4: Verify Persistence (Usually Automatic)

**File:** `api/payment_simulator/cli/execution/persistence.py`

The `EventWriter` automatically stores events to `simulation_events.details` JSON column. Verify complex nested structures are handled:

```python
# Usually no changes needed - EventWriter handles it
# But verify for complex types:

def test_my_new_event_persists():
    """Verify MyNewEvent is correctly stored and retrieved."""
    # Create event, persist, retrieve, verify all fields present
```

#### Step 5: Add Display Logic

**File:** `api/payment_simulator/cli/display/verbose_output.py`

```python
def log_my_new_event(event: Dict):
    """Display MyNewEvent in verbose output."""
    console.print(f"[cyan]New Event:[/cyan] {event['agent_id']}")
    console.print(f"  Amount: ${event['amount']/100:.2f}")
    console.print(f"  Reason: {event['reason']}")
    # ... display calculation_details ...

# In display_tick_verbose_output():
for event in events:
    if event['event_type'] == 'my_new_event':
        log_my_new_event(event)
```

**Key Point:** This function receives events identically from both `run` (FFI) and `replay` (database).

#### Step 6: Write TDD Tests

**File:** `api/tests/integration/test_replay_identity_gold_standard.py`

```python
def test_my_new_event_has_all_fields():
    """Verify MyNewEvent contains all required fields."""
    # Create scenario that triggers event
    orch = Orchestrator.new(config)
    # ... trigger event ...

    events = orch.get_tick_events(orch.current_tick())
    my_events = [e for e in events if e['event_type'] == 'my_new_event']

    assert len(my_events) > 0, "Event should have occurred"
    event = my_events[0]

    # Verify ALL fields exist
    assert 'agent_id' in event
    assert 'amount' in event
    assert 'reason' in event
    assert 'calculation_details' in event
    assert isinstance(event['calculation_details'], list)
```

#### Step 7: Test Replay Identity

```bash
# Run with persistence
payment-sim run --config test.yaml --persist output.db --verbose > run.txt

# Replay
payment-sim replay output.db --verbose > replay.txt

# Compare (should be identical)
diff <(grep -v "Duration:" run.txt) <(grep -v "Duration:" replay.txt)
```

**If diff shows differences:** Your event is missing fields or replay is using legacy reconstruction.

### Anti-Pattern: Bypassing StateProvider

❌ **NEVER** access Rust/DB directly from display code:
```python
# BAD: Only works in run mode!
def display_new_metric(orch: Orchestrator):
    value = orch.get_new_metric_direct()  # Bypasses abstraction
    print(f"Metric: {value}")
```

✅ **ALWAYS** use StateProvider:
```python
# GOOD: Works in both run AND replay
def display_new_metric(provider: StateProvider):
    value = provider.get_new_metric()  # Abstracted
    print(f"Metric: {value}")
```

### What NOT To Do ❌

#### 1. Never Create Legacy Tables

❌ **BAD:**
```python
# In persistence code
cursor.execute("""
    CREATE TABLE my_special_events (
        id INTEGER PRIMARY KEY,
        tick INTEGER,
        data TEXT
    )
""")
```

✅ **GOOD:**
```python
# Events go into simulation_events automatically
# No special tables needed!
```

#### 2. Never Query Multiple Tables in Replay

❌ **BAD:**
```python
# replay.py
def replay_simulation(db, sim_id):
    events = get_simulation_events(sim_id, tick=tick)
    lsm_cycles = get_lsm_cycles_by_tick(sim_id, tick)  # ❌ LEGACY!
    collateral = get_collateral_events_by_tick(sim_id, tick)  # ❌ LEGACY!
    # ... manual reconstruction ...
```

✅ **GOOD:**
```python
# replay.py
def replay_simulation(db, sim_id):
    events = get_simulation_events(sim_id, tick=tick)  # ✅ ONLY SOURCE!
    display_tick_verbose_output(provider, tick, events)
```

#### 3. Never Manually Reconstruct Events

❌ **BAD:**
```python
def _reconstruct_lsm_events(lsm_cycles):
    """Manually rebuild event structure from raw data."""
    events = []
    for cycle in lsm_cycles:
        # Manual reconstruction - brittle!
        if len(cycle['agent_ids']) == 2:
            events.append({...})  # Bug: bilaterals have len==3!
    return events
```

✅ **GOOD:**
```python
# No reconstruction needed!
# Events are already complete from simulation_events table
```

#### 4. Never Store Partial Event Data

❌ **BAD:**
```rust
Event::LsmCycleSettlement {
    tx_ids: vec!["tx1", "tx2"],  // ❌ Insufficient!
    // Missing: agents, amounts, net_positions, etc.
}
```

✅ **GOOD:**
```rust
Event::LsmCycleSettlement {
    tick,
    agents: vec!["A", "B", "C"],
    tx_ids: vec!["tx1", "tx2", "tx3"],
    tx_amounts: vec![1000, 2000, 3000],
    net_positions: vec![500, -200, -300],
    max_net_outflow: 500,
    max_net_outflow_agent: "A".to_string(),
    total_value: 3000,
}
```

### Troubleshooting Replay Divergence

#### Symptom: "Replay output differs from run"

**Diagnosis Steps:**

1. **Check if replay uses legacy tables:**
```bash
# Search for legacy queries in replay.py
cd api
grep -n "get_lsm_cycles_by_tick\|get_collateral_events_by_tick" payment_simulator/cli/commands/replay.py
```

**Fix:** Remove legacy queries, use only `get_simulation_events()`.

2. **Check if event has all fields:**
```python
# In test
events = orch.get_tick_events(orch.current_tick())
print(json.dumps(events[0], indent=2))  # Inspect actual event structure
```

**Fix:** Add missing fields to Event enum and FFI serialization.

3. **Check if FFI serializes all fields:**
```bash
# In Rust
cd backend
grep -A 20 "Event::MyEventType" src/ffi/orchestrator.rs
```

**Fix:** Add missing `dict.insert()` calls.

#### Symptom: "Test skipped: Event didn't occur"

**Diagnosis:** Test scenario didn't trigger the event type.

**Fix:** Adjust test configuration to reliably trigger the event:
```python
# Example: Trigger LSM by creating low liquidity
config = {
    "agent_configs": [
        {"id": "A", "opening_balance": 1000, "credit_limit": 0},  # Low!
        {"id": "B", "opening_balance": 1000, "credit_limit": 0},
    ],
}
```

#### Symptom: "KeyError: 'field_name'"

**Diagnosis:** Display code expects field that doesn't exist in event.

**Fix Options:**
1. Add field to Event enum (if it should be there)
2. Use defensive access: `event.get('field_name', default_value)`

### Real-World Example: LSM Bilateral Offset Bug (Solved)

**Historical Bug:** LSM bilateral offsets were not replaying.

**Root Cause:**
- Rust stored bilaterals as `[A, B, A]` (cycle representation, len==3)
- Python reconstruction checked `if len(agent_ids) == 2`
- Bilaterals were silently skipped ❌

**Solution:**
```rust
// Rust: Store bilateral with explicit agent_a, agent_b fields
Event::LsmBilateralOffset {
    tick,
    agent_a: cycle.agent_ids[0].clone(),  // ✅ Explicit
    agent_b: cycle.agent_ids[1].clone(),  // ✅ Explicit
    amount_a: cycle.tx_amounts[0],        // ✅ Explicit
    amount_b: cycle.tx_amounts[1],        // ✅ Explicit
    tx_ids: cycle.tx_ids.clone(),
}
```

**Key Lesson:** Don't make Python guess Rust's data structure. Make events self-documenting.

### Testing Checklist

When implementing replay identity for a new event:

- [ ] Event enum has ALL display fields
- [ ] FFI serializes ALL fields to dict
- [ ] Test verifies all fields exist (`test_replay_identity_gold_standard.py`)
- [ ] Manual run+replay produces identical output
- [ ] No new tables created
- [ ] No manual reconstruction in `replay.py`
- [ ] Display code uses StateProvider (if needed)
- [ ] Integration test added

### Additional Resources

- **Implementation Guide:** [`docs/replay-unified-architecture-implementation.md`](docs/replay-unified-architecture-implementation.md)
- **Detailed Plan:** [`docs/plans/unified-replay-architecture-completion.md`](docs/plans/unified-replay-architecture-completion.md)
- **Gold Standard Tests:** [`api/tests/integration/test_replay_identity_gold_standard.py`](api/tests/integration/test_replay_identity_gold_standard.py)
- **StateProvider Protocol:** [`api/payment_simulator/cli/execution/state_provider.py`](api/payment_simulator/cli/execution/state_provider.py)
- **Replay Command Implementation:** [`api/payment_simulator/cli/commands/replay.py`](api/payment_simulator/cli/commands/replay.py)

---

## Common Workflows

### Starting a New Feature
1. **Think first**: `ultrathink` for complex features, `think` for simple ones
2. **Make a plan**: Create `/docs/plans/feature-name.md` with spec, approach, tasks
3. **Check existing patterns**: Look at similar code in the codebase
4. **Write tests first**: TDD when possible
5. **Implement in appropriate layer**:
   - Performance-critical? → Rust (`/backend`)
   - API/orchestration? → Python (`/api`)
6. **Test across FFI boundary**: Integration tests in `/api/tests/integration/`
7. **Commit often**: Small, atomic commits with clear messages

### Debugging an Issue
1. **Reproduce deterministically**: Same seed should give same behavior
2. **Add logging**: Use `tracing` in Rust, `logging` in Python
3. **Write a failing test**: Captures the bug
4. **Fix in correct layer**: Don't patch symptoms, fix root cause
5. **Verify determinism**: Run test 10 times with same seed

### Working on FFI
1. **Read `backend/CLAUDE.md`** for Rust patterns
2. **Read `api/CLAUDE.md`** for Python FFI patterns  
3. **Keep it simple**: Pass primitives, not complex types
4. **Validate at boundary**: Check inputs before crossing
5. **Test both sides**: Rust tests + Python integration tests
6. **Consider using FFI subagent**: `/agents ffi-specialist` for complex FFI work

---

## Anti-Patterns (Don't Do These)

### ❌ Float Contamination
```rust
// BAD: Mixing float and int
let fee = (amount as f64 * 0.001) as i64; // Rounding error!

// GOOD: Integer-only arithmetic
let fee = amount * 1 / 1000; // Or use fixed-point library
```

### ❌ Forgetting RNG Seed Update
```rust
// BAD: Seed not persisted
let value = rng.next_u64(state.seed);
// ... use value but forget to update state.seed

// GOOD: Always update
let (value, new_seed) = rng.next_u64(state.seed);
state.rng_seed = new_seed;
```

### ❌ Complex FFI Types
```python
# BAD: Passing Python objects to Rust
@dataclass
class ComplexConfig:
    nested: Dict[str, List[Any]]
    
orchestrator.configure(complex_config)  # Will fail!

# GOOD: Convert to simple types first
orchestrator.configure({
    "param1": 100,
    "param2": [1, 2, 3],
})
```

### ❌ Tight FFI Loops
```python
# BAD: Crossing FFI in loop
for tx_id in transaction_ids:
    orchestrator.process_transaction(tx_id)  # 1000 FFI calls!

# GOOD: Batch operations
orchestrator.process_transactions_batch(transaction_ids)  # 1 FFI call
```

### ❌ Stale Cached State
```python
# BAD: Caching Rust state in Python
cached_balance = orchestrator.get_balance("BANK_A")
# ... time passes, Rust state changes ...
print(cached_balance)  # WRONG: Stale data

# GOOD: Query fresh state when needed
current_balance = orchestrator.get_balance("BANK_A")
```

---

## Testing Strategy

### Rust Tests (`/backend/tests/`)
```rust
#[test]
fn test_rtgs_settles_with_sufficient_liquidity() {
    let mut state = create_test_state();
    state.agents.get_mut("A").unwrap().balance = 100000;
    
    let tx = create_transaction("A", "B", 50000);
    let result = settle(&mut state, &tx);
    
    assert!(result.is_ok());
    assert_eq!(state.agents.get("A").unwrap().balance, 50000);
}
```

**Focus**: Unit tests for core logic, property tests for invariants

### Python Integration Tests (`/api/tests/integration/`)
```python
def test_ffi_round_trip_determinism():
    """Same seed produces identical results."""
    config = {"seed": 12345, "ticks_per_day": 100}
    
    orch1 = Orchestrator.new(config)
    result1 = [orch1.tick() for _ in range(10)]
    
    orch2 = Orchestrator.new(config)
    result2 = [orch2.tick() for _ in range(10)]
    
    assert result1 == result2  # Must be identical
```

**Focus**: FFI boundary, determinism, end-to-end workflows

### E2E Tests (`/api/tests/e2e/`)
```python
async def test_full_simulation_via_api(client: TestClient):
    """Complete lifecycle via REST API."""
    config = load_config("test_scenario.yaml")
    response = await client.post("/api/simulations", json=config)
    sim_id = response.json()["simulation_id"]
    
    # Run simulation
    await client.post(f"/api/simulations/{sim_id}/run")
    
    # Check results
    results = await client.get(f"/api/simulations/{sim_id}/results")
    assert results.json()["metrics"]["settlement_rate"] > 0.95
```

**Focus**: Full system behavior, API contracts

---

## When to Use Subagents

Claude Code has a powerful subagent feature that keeps main context clean. Use subagents for:

1. **FFI Specialist** (`/agents ffi-specialist`)
   - When: Working on Rust↔Python boundary
   - Keeps: PyO3 patterns, error handling, type conversions
   
2. **Test Engineer** (`/agents test-engineer`)
   - When: Writing comprehensive test suites
   - Keeps: Test patterns, edge cases, mocking strategies
   
3. **Performance Analyst** (`/agents performance`)
   - When: Profiling and optimizing hot paths
   - Keeps: Benchmarking code, flamegraphs, optimization patterns
   
4. **Documentation Maintainer** (`/agents docs`)
   - When: Keeping docs in sync with code
   - Keeps: Documentation style, examples, API references

**How to use**: 
```bash
# Create a subagent
/agents ffi-specialist

# Then in your prompt:
"@ffi-specialist: How should I expose this Rust function to Python?"
```

The subagent will work in parallel, analyze relevant docs/code, and return only the essential answer to your main session.

---

## Slash Commands to Use

### Built-in Commands
- `/clear` - Start fresh conversation (use after completing a feature)
- `/compact` - Manually compress context (use before it auto-compacts)
- `/think` or `/ultrathink` - Engage extended thinking mode for complex problems
- `/resume <id>` - Return to a previous conversation
- `/agents` - Create a specialized subagent
- `/install-github-app` - Enable automatic PR reviews

### Custom Commands (to be created in `.claude/commands/`)
- `/test-determinism` - Run determinism verification suite
- `/benchmark` - Run performance benchmarks
- `/check-ffi` - Verify FFI boundary integrity
- `/review-money` - Audit money handling (check for floats)

---

## Key Resources

### Documentation
- `docs/reference/patterns-and-conventions.md` - **Consolidated patterns, invariants, and conventions** (read this for comprehensive reference)
- `docs/architecture.md` - System architecture deep dive
- `docs/game-design.md` - Domain model and rules
- `foundational_plan.md` - Original project plan
- `AGENTS.md` - Comprehensive agent documentation

### Example Configurations
- `sim_config_simple_example.yaml` - Minimal setup for testing
- `sim_config_example.yaml` - Full setup with automatic arrivals

### Subagent Definitions
- `.claude/agents/ffi-specialist.md` - FFI boundary expert
- `.claude/agents/test-engineer.md` - Testing specialist
- `.claude/agents/performance.md` - Performance optimization expert
- `.claude/agents/python-stylist.md` - Modern Python typing and patterns expert

---

## Getting Started Checklist

When starting work on this project:

1. ✅ Read this file (you're doing it!)
2. ✅ Read `docs/reference/patterns-and-conventions.md` for all invariants and patterns
3. ✅ Scan `backend/CLAUDE.md` for Rust patterns
4. ✅ Scan `api/CLAUDE.md` for Python patterns
5. ✅ Review `docs/architecture.md` for system design
6. ✅ Look at example configs to understand domain
7. ✅ Build and test:
   ```bash
   # Setup: Build Rust module and install everything (one command!)
   cd api
   uv sync --extra dev

   # Run Python tests
   .venv/bin/python -m pytest

   # After Rust code changes, rebuild with:
   uv sync --extra dev --reinstall-package payment-simulator

   # Run Rust tests
   cd ../backend
   cargo test --no-default-features
   ```
   - **Note**: `uv sync --extra dev` automatically builds the Rust module and installs the package in editable mode
   - After Python changes: No rebuild needed (editable mode)
   - After Rust changes: Add `--reinstall-package payment-simulator` flag
   - Rust tests require `--no-default-features` flag
8. ✅ Create subagents as needed for specialized work

---

## Pro Tips for Claude Code Users

### Context Management
- **Clear after each feature**: Don't carry old context
- **Use @-mentions**: `@backend/src/settlement/rtgs.rs` to pull specific files
- **Proactive compaction**: Manually `/compact` at natural breakpoints
- **Subagents for research**: Let them handle noisy investigations

### Thinking Modes
- Use `ultrathink` for architectural decisions
- Use `think hard` for complex algorithms
- Use `think` for straightforward features
- Default (no thinking): Simple edits and refactors

### Git Integration
- Ask Claude to write commit messages (it's good at this!)
- Have Claude create branches: `checkout -b feature/xyz`
- Use Claude for PR descriptions
- Let Claude resolve merge conflicts

### Image Support
- Drag architecture diagrams into terminal for reference
- Screenshot error messages for debugging

---

## Success Criteria

You're on the right track if:
- ✅ All tests pass with same seed (determinism check)
- ✅ No floats anywhere near money calculations
- ✅ FFI boundary is minimal and well-tested
- ✅ Performance targets met (1000+ ticks/second)
- ✅ Code is readable and well-commented
- ✅ New features have tests

Red flags:
- ❌ Non-deterministic behavior (different outputs with same seed)
- ❌ Panics or crashes at FFI boundary
- ❌ Float arithmetic in money calculations
- ❌ Degrading performance over time
- ❌ Untested code crossing FFI boundary

---

## 🔴 Python Code Quality Requirements

### Strict Typing is MANDATORY

All Python code in the `/api` directory MUST have complete type annotations. This is a **company styleguide requirement** enforced via static type checking.

**Key Requirements:**
- Every function parameter MUST have a type annotation
- Every function MUST have a return type (use `-> None` for void)
- Use modern syntax: `str | None` not `Optional[str]`, `list[str]` not `List[str]`
- Typer CLI commands MUST use the `Annotated` pattern

**Enforcement Tools:**
- **mypy**: Static type checker (MUST pass before committing)
- **ruff**: Fast linter (MUST pass before committing)

**Running Checks:**
```bash
cd api
.venv/bin/python -m mypy payment_simulator/
.venv/bin/python -m ruff check payment_simulator/
```

**Reference Modules (exemplary typing):**
- `persistence/models.py` - Pydantic models with Field descriptions
- `cli/execution/runner.py` - Protocol pattern, dataclasses
- `persistence/queries.py` - Return types, Optional parameters

**See `api/CLAUDE.md` for full typing guidelines and examples.**

---

## Breaking Changes

### Removed in 2025-11-16

**Deprecated `Settlement` event removed**

The generic `Settlement` event has been completely removed. All settlements now use specific event types:

- **RTGS immediate settlements**: Use `RtgsImmediateSettlement` event
- **Queue-2 releases**: Use `Queue2LiquidityRelease` event
- **LSM settlements**: Use `LsmBilateralOffset` or `LsmCycleSettlement` events

**Migration**: No action required for configurations. However, if you have custom analysis scripts that filter for `"Settlement"` events, update them to use the specific event types listed above.

**Rationale**: The generic Settlement event was a holdover from early development before settlement types were differentiated. Maintaining dual emission (both generic Settlement AND specific events) added complexity and risk of double-counting in metrics. The new event types provide richer metadata for analysis:
- `RtgsImmediateSettlement` includes `sender_balance_before` and `sender_balance_after` for audit trails
- `Queue2LiquidityRelease` includes `queue_wait_ticks` and `release_reason` for queue analysis

See `docs/research/deprecate-settlement-event-compatibility.md` for details.

---

## Questions? Issues?

1. Check subdirectory CLAUDE.md files for layer-specific guidance
2. Review similar code in the codebase for patterns
3. Create a subagent for deep dives
4. Ask Claude Code to search through git history
5. Reference the comprehensive docs in `/docs`

**Remember**: This project has strict invariants for good reasons. When in doubt about money, determinism, or FFI, ask before implementing. Better to get it right than to create subtle bugs that compound over time.

---

*Last updated: 2025-11-29*
*This is a living document. Update it as the project evolves.*
