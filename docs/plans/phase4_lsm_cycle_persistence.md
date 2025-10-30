# Phase 4: LSM Cycle Persistence - TDD Implementation Plan

**Status**: 🟢 COMPLETE
**Priority**: OPTIONAL (for 100% coverage)
**Estimated Time**: 4 hours
**Actual Time**: ~2 hours
**Dependencies**: None (LSM infrastructure already exists)

---

## Goal

Persist the **exact details** of each LSM cycle settled during simulation, enabling analysis of:
- Which transactions were netted together
- Cycle patterns (bilateral, trilateral, multilateral)
- Total value settled per cycle
- LSM effectiveness metrics

---

## Current State

### ✅ What We Have (Aggregate Data)
- LSM counts tracked in `daily_agent_metrics`:
  - `num_lsm_releases` - count of transactions released via LSM
- Aggregate LSM stats in tick results:
  - `num_lsm_releases` per tick
  - `bilateral_offsets` + `cycles_settled` counts
- LSM code already has cycle detection and settlement

### ❌ What's Missing (Individual Cycle Details)
- **Which** transactions were settled together in each cycle
- **What** the cycle pattern was (e.g., A→B→C→A)
- **How much** net value was settled per cycle
- **When** (tick/day) each cycle was settled
- **Type** of cycle (bilateral vs multilateral)

### 🔍 Impact
Without cycle details:
- Can see "10 LSM releases this day"
- Can't answer "WHICH transactions were netted together?"
- Can't analyze LSM effectiveness patterns
- Can't debug complex gridlock scenarios

---

## Architecture Analysis

### Existing LSM Code

**File**: `backend/src/settlement/lsm.rs`

**Key Types**:
```rust
// Line 84-97
pub struct Cycle {
    pub agents: Vec<String>,         // [A, B, C, A]
    pub transactions: Vec<String>,   // Transaction IDs
    pub min_amount: i64,             // Bottleneck amount
    pub total_value: i64,            // Sum of all tx amounts
}

// Line 100-110
pub struct CycleSettlementResult {
    pub cycle_length: usize,
    pub settled_value: i64,
    pub transactions_affected: usize,
}

// Line 112-129
pub struct LsmPassResult {
    pub iterations_run: usize,
    pub total_settled_value: i64,
    pub final_queue_size: usize,
    pub bilateral_offsets: usize,
    pub cycles_settled: usize,
}
```

**Problem**: `run_lsm_pass()` only returns aggregate counts, not individual cycle details.

**TODO Comment** (engine.rs:1886-1888):
```rust
// TODO: Log detailed LSM events
// Currently the LSM module doesn't return enough details for proper event logging
// Would need to track which specific transactions were settled via LSM
```

### Database Schema

**New Table: `lsm_cycles`**
```sql
CREATE TABLE lsm_cycles (
    id INTEGER PRIMARY KEY,              -- Auto-increment
    simulation_id VARCHAR NOT NULL,
    tick INTEGER NOT NULL,
    day INTEGER NOT NULL,

    cycle_type VARCHAR NOT NULL,         -- 'bilateral' or 'multilateral'
    cycle_length INTEGER NOT NULL,       -- Number of agents (2, 3, 4, ...)

    agents TEXT NOT NULL,                -- JSON array of agent IDs
    transactions TEXT NOT NULL,          -- JSON array of transaction IDs

    settled_value BIGINT NOT NULL,       -- Net value settled
    total_value BIGINT NOT NULL,         -- Gross value (sum of all tx amounts)

    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
);

CREATE INDEX idx_lsm_sim_day ON lsm_cycles (simulation_id, day);
CREATE INDEX idx_lsm_cycle_type ON lsm_cycles (cycle_type);
```

**Rationale**:
- Store agents/transactions as JSON arrays (flexible for different cycle lengths)
- `cycle_type` distinguishes bilateral (2 agents) from multilateral (3+)
- `settled_value` is the net amount actually settled
- `total_value` is the gross amount before netting

---

## TDD Implementation Plan

### Phase 4.1: Python Tests (RED) - 1.5 hours

**File**: `api/tests/integration/test_lsm_cycle_persistence.py`

**Test Classes**:

1. **TestFFILsmCycleRetrieval** - Verify Rust FFI methods
   - `test_ffi_get_lsm_cycles_for_day_exists()` - Method exists and callable
   - `test_ffi_get_lsm_cycles_returns_list()` - Returns list of cycle dicts
   - `test_lsm_cycle_has_required_fields()` - Each cycle has all fields

2. **TestLsmCyclePersistence** - Verify persistence logic
   - `test_lsm_cycles_persisted()` - Cycles saved to database
   - `test_bilateral_vs_multilateral()` - Type field correct
   - `test_cycle_values_accurate()` - settled_value and total_value correct
   - `test_multiple_cycles_per_day()` - Multiple cycles tracked separately

3. **TestLsmCycleSchema** - Verify database schema
   - `test_lsm_cycles_table_exists()`
   - `test_lsm_cycles_table_schema()`

4. **TestLsmCycleDataIntegrity** - Verify data quality
   - `test_agents_array_valid_json()` - JSON arrays parseable
   - `test_transaction_ids_in_cycle_exist()` - All tx_ids reference real transactions

**Expected Result**: 8-10 tests, all FAILING (RED phase)

---

### Phase 4.2: Rust Implementation (GREEN) - 1.5 hours

**Scope**: Modify LSM code to capture and return individual cycle details

**Changes to `backend/src/settlement/lsm.rs`**:

1. **Create LsmCycleEvent struct**:
```rust
#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct LsmCycleEvent {
    pub tick: usize,
    pub day: usize,
    pub cycle_type: String,           // "bilateral" or "multilateral"
    pub cycle_length: usize,
    pub agents: Vec<String>,
    pub transactions: Vec<String>,
    pub settled_value: i64,
    pub total_value: i64,
}
```

2. **Modify LsmPassResult to include events**:
```rust
pub struct LsmPassResult {
    // ... existing fields ...
    pub cycle_events: Vec<LsmCycleEvent>,  // NEW
}
```

3. **Update run_lsm_pass() to collect events**:
```rust
pub fn run_lsm_pass(...) -> LsmPassResult {
    let mut cycle_events = Vec::new();

    // ... existing code ...

    for cycle in cycles.iter().take(config.max_cycles_per_tick) {
        if let Ok(result) = settle_cycle(state, cycle, tick) {
            // Capture event
            let event = LsmCycleEvent {
                tick,
                day: tick / ticks_per_day,
                cycle_type: if cycle.agents.len() == 2 { "bilateral" } else { "multilateral" },
                cycle_length: cycle.agents.len() - 1,  // Exclude duplicate agent
                agents: cycle.agents.clone(),
                transactions: cycle.transactions.clone(),
                settled_value: result.settled_value,
                total_value: cycle.total_value,
            };
            cycle_events.push(event);

            // ... existing settlement logic ...
        }
    }

    LsmPassResult {
        // ... existing fields ...
        cycle_events,
    }
}
```

**Changes to `backend/src/orchestrator/engine.rs`**:

1. **Add lsm_cycle_events field to SimulationState or Orchestrator**:
```rust
pub lsm_cycle_events: Vec<LsmCycleEvent>,
```

2. **Store events after LSM pass** (replace TODO at line 1886):
```rust
// STEP 5: LSM COORDINATOR
let lsm_result = lsm::run_lsm_pass(&mut self.state, &self.lsm_config, current_tick);
let num_lsm_releases = lsm_result.bilateral_offsets + lsm_result.cycles_settled;
num_settlements += num_lsm_releases;

// Store LSM cycle events (Phase 4)
self.state.lsm_cycle_events.extend(lsm_result.cycle_events);
```

3. **Add FFI method** in `backend/src/ffi/orchestrator.rs`:
```rust
fn get_lsm_cycles_for_day(&self, day: usize) -> Vec<HashMap<String, PyObject>> {
    // Filter events for this day and convert to Python dicts
}
```

**Testing**:
```bash
cargo test --no-default-features lsm
```

**Expected Result**: Rust tests pass, FFI method callable from Python

---

### Phase 4.3: Python Write Logic (GREEN) - 30 min

**File**: `api/payment_simulator/cli/commands/run.py`

**Location**: After queue snapshots persistence (lines ~462 and ~487)

**Code to Add**:

```python
# Write LSM cycles for this day (Phase 4.3)
lsm_cycles = orch.get_lsm_cycles_for_day(day)
if lsm_cycles:
    # Convert to DataFrame
    lsm_data = []
    for cycle in lsm_cycles:
        lsm_data.append({
            "simulation_id": sim_id,
            "tick": cycle["tick"],
            "day": cycle["day"],
            "cycle_type": cycle["cycle_type"],
            "cycle_length": cycle["cycle_length"],
            "agents": json.dumps(cycle["agents"]),        # Serialize to JSON
            "transactions": json.dumps(cycle["transactions"]),
            "settled_value": cycle["settled_value"],
            "total_value": cycle["total_value"],
        })

    df = pl.DataFrame(lsm_data)
    db_manager.conn.execute("INSERT INTO lsm_cycles SELECT * FROM df")
    log_info(f"  Persisted {len(lsm_cycles)} LSM cycles for day {day}", quiet)
```

**Database Migration**:

**File**: `api/payment_simulator/persistence/models.py`

Add:
```python
class LsmCycleRecord(BaseModel):
    """LSM cycle event for analyzing liquidity-saving mechanisms."""

    model_config = ConfigDict(
        table_name="lsm_cycles",
        primary_key=["id"],
        indexes=[
            ("idx_lsm_sim_day", ["simulation_id", "day"]),
            ("idx_lsm_cycle_type", ["cycle_type"]),
        ],
    )

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    tick: int
    day: int
    cycle_type: str  # 'bilateral' or 'multilateral'
    cycle_length: int
    agents: str  # JSON array
    transactions: str  # JSON array
    settled_value: int
    total_value: int
```

**File**: `api/payment_simulator/persistence/schema_generator.py`

Add `LsmCycleRecord` to imports and models list.

**Expected Result**: LSM cycles persisted to database

---

### Phase 4.4: Verification (REFACTOR) - 30 min

**Tasks**:

1. **Run Python Tests**:
   ```bash
   pytest api/tests/integration/test_lsm_cycle_persistence.py -v
   ```
   **Expected**: 8-10/10 tests passing

2. **End-to-End Test**:
   Create a scenario that triggers LSM cycles:
   ```yaml
   # examples/configs/lsm-trigger.yaml
   rng_seed: 42
   ticks_per_day: 20
   num_days: 1
   agents:
     - id: BANK_A
       opening_balance: 100000
       credit_limit: 0
     - id: BANK_B
       opening_balance: 100000
       credit_limit: 0
     - id: BANK_C
       opening_balance: 100000
       credit_limit: 0

   # Create circular dependency A→B→C→A
   arrivals:
     - sender: BANK_A
       receiver: BANK_B
       amount: 50000
       tick: 5
     - sender: BANK_B
       receiver: BANK_C
       amount: 50000
       tick: 5
     - sender: BANK_C
       receiver: BANK_A
       amount: 50000
       tick: 5
   ```

   ```bash
   payment-sim run --config examples/configs/lsm-trigger.yaml --persist --db-path test_lsm.db
   ```

3. **Verify Database**:
   ```python
   import duckdb
   import json

   conn = duckdb.connect('test_lsm.db')

   # Check LSM cycles
   cycles = conn.execute('SELECT * FROM lsm_cycles').fetchall()
   print(f"LSM cycles: {len(cycles)}")

   for cycle in cycles:
       agents = json.loads(cycle.agents)
       print(f"Cycle: {' → '.join(agents)}, settled: ${cycle.settled_value/100}")
   ```

4. **Performance Check**:
   - LSM cycle persistence should be fast (<10ms for 100 cycles)
   - No significant impact on simulation performance

**Expected Result**: All tests pass, LSM cycles verified in database

---

## Success Criteria

✅ **Implementation Complete When**:
1. FFI method `get_lsm_cycles_for_day()` exists and works
2. `lsm_cycles` table exists in schema
3. LSM cycles persisted at end of each day
4. 8-10/10 Python integration tests passing
5. JSON arrays properly serialized and parseable
6. Cycle types correctly identified (bilateral vs multilateral)

---

## Edge Cases to Handle

1. **No LSM Cycles**: Don't create rows if no cycles occurred (check `if lsm_cycles`)
2. **JSON Serialization**: Ensure agents/transactions arrays serialize correctly
3. **Bilateral vs Multilateral**: Correctly identify cycle type based on length
4. **Multiple Cycles per Day**: Each cycle gets its own row with unique ID

---

## Out of Scope (Intentionally Deferred)

### Queue 2 (RTGS) Cycles
- **Reason**: Focus on LSM cycles only (Queue 1 persistence already done in Phase 3)
- **Deferral**: Can add later if needed

### Per-Transaction LSM Attribution
- **Reason**: Complex to track which transaction was settled via which mechanism
- **Alternative**: LSM cycle details provide most of the analytical value

---

## Dependencies

### Required FFI Methods
- ⏳ `get_lsm_cycles_for_day(day)` - **TO IMPLEMENT**

### Required Database Schema
- ⏳ `lsm_cycles` table - **TO CREATE**

### Required Python Modules
- ✅ `polars` - Already used
- ✅ `duckdb` - Already used
- ✅ `json` - Built-in

---

## Testing Strategy

### Rust Unit Tests (Phase 4.2)
Focus: LSM cycle event generation
```bash
cargo test --no-default-features lsm
```

### Python Integration Tests (Phase 4.1, 4.4)
Focus: End-to-end persistence
```bash
pytest api/tests/integration/test_lsm_cycle_persistence.py -v
```

### Manual Verification (Phase 4.4)
Focus: Data integrity
```bash
payment-sim run --config examples/configs/lsm-trigger.yaml --persist
# Verify LSM cycles in database
```

---

## Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 4.1 | Write Python tests (RED) | 1.5h | ✅ COMPLETE |
| 4.2 | Rust LSM cycle tracking | 1.5h | ✅ COMPLETE |
| 4.3 | Python persistence logic | 0.5h | ✅ COMPLETE |
| 4.4 | Verification & cleanup | 0.5h | ✅ COMPLETE |
| **TOTAL** | | **~2h** | ✅ **COMPLETE** |

---

## Risks and Mitigations

### Risk: LSM May Not Trigger in Test Scenarios
**Mitigation**: Create explicit circular dependency scenario (lsm-trigger.yaml)
**Fallback**: Test with manual LSM cycle data

### Risk: JSON Serialization Issues
**Mitigation**: Use Python's built-in `json.dumps()` / `json.loads()`
**Verification**: Test roundtrip serialization in unit tests

### Risk: Performance Impact
**Mitigation**: LSM cycles are typically <50 per day, minimal overhead
**Monitoring**: Check simulation performance doesn't degrade

---

## Comparison with Previous Phases

| Aspect | Phase 2 (Collateral) | Phase 3 (Queues) | Phase 4 (LSM) |
|--------|---------------------|------------------|---------------|
| Rust Implementation | Already existed | FFI only | Need to modify LSM |
| Data Volume | Low (~10/day) | Medium (~500/day) | Low (~20/day) |
| Complexity | Medium | Low | **High** (modify existing) |
| Priority | CRITICAL | IMPORTANT | OPTIONAL |
| Time Required | 2h | 6h | **4h** |

---

## Expected Outcome

After Phase 4:
- **100% persistence coverage** ✅
- All simulation data persisted (transactions, metrics, policies, collateral, queues, LSM cycles)
- Perfect state reconstruction possible
- Complete analytical capabilities for research

---

*Created: 2025-10-30*
*Phase: 4 (LSM Cycles)*
*Status: PLANNING*
