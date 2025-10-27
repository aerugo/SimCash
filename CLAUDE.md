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
│  TypeScript React Frontend (future)             │
│  - Real-time visualization via WebSocket        │
└──────────────────┬──────────────────────────────┘
                   │ HTTP/WS
┌──────────────────▼──────────────────────────────┐
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
- **Priority**: Urgency level (higher = more important)
- **Divisible**: Can the payment be split into parts?
- **Status**: pending → partially_settled → settled (or dropped)

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
│   │   ├── models/              ← Transaction, Agent, State
│   │   ├── orchestrator/        ← Main simulation loop
│   │   ├── settlement/          ← RTGS + LSM engines
│   │   └── rng/                 ← Deterministic RNG
│   ├── tests/                   ← Rust integration tests
│   └── Cargo.toml
├── api/
│   ├── CLAUDE.md                ← Python-specific guidance
│   ├── payment_simulator/
│   │   ├── api/                 ← FastAPI routes
│   │   ├── backends/            ← FFI wrapper
│   │   ├── config/              ← Pydantic schemas
│   │   └── core/                ← Lifecycle management
│   └── tests/                   ← Python tests
├── frontend/
│   ├── CLAUDE.md                ← React-specific guidance (future)
│   └── src/
├── docs/
│   ├── architecture.md
│   ├── api.md
│   └── game-design.md
└── .claude/
    ├── commands/                ← Custom slash commands
    └── agents/                  ← Specialized subagents
```

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
   - User interaction? → React (`/frontend`)
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

---

## Getting Started Checklist

When starting work on this project:

1. ✅ Read this file (you're doing it!)
2. ✅ Scan `backend/CLAUDE.md` for Rust patterns
3. ✅ Scan `api/CLAUDE.md` for Python patterns
4. ✅ Review `docs/architecture.md` for system design
5. ✅ Look at example configs to understand domain
6. ✅ Run tests to verify setup: `cargo test` and `pytest`
7. ✅ Create subagents as needed for specialized work

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
- Paste UI mockups for frontend work (future)

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

## Questions? Issues?

1. Check subdirectory CLAUDE.md files for layer-specific guidance
2. Review similar code in the codebase for patterns
3. Create a subagent for deep dives
4. Ask Claude Code to search through git history
5. Reference the comprehensive docs in `/docs`

**Remember**: This project has strict invariants for good reasons. When in doubt about money, determinism, or FFI, ask before implementing. Better to get it right than to create subtle bugs that compound over time.

---

*Last updated: 2025-10-27*
*This is a living document. Update it as the project evolves.*
