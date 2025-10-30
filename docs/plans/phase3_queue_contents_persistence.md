# Phase 3: Queue Contents Persistence - TDD Implementation Plan

**Status**: 🟡 IN PROGRESS
**Priority**: IMPORTANT (for perfect state reconstruction)
**Estimated Time**: 6 hours
**Dependencies**: None (Rust queue infrastructure already exists)

---

## Goal

Persist the **exact contents** of agent queues (Queue 1) and the RTGS central queue (Queue 2) at end-of-day, enabling perfect state reconstruction and debugging.

---

## Current State

### ✅ What We Have (Aggregate Data)
- Queue sizes tracked in `daily_agent_metrics`:
  - `queue1_eod_size` - count of transactions in agent's internal queue
  - `queue2_eod_size` - count of transactions in RTGS central queue (global)
- Total queue sizes available via Rust methods:
  - `Agent.outgoing_queue_size()` - Queue 1 size per agent
  - `SimulationState.queue_size()` - Queue 2 size (global)

### ❌ What's Missing (Individual Transaction IDs)
- **Which** transactions are in Queue 1 for each agent
- **Which** transactions are in Queue 2 (RTGS central queue)
- **Position/order** of transactions in queues

### 🔍 Impact
Without queue contents:
- Can see "BANK_A has 23 transactions queued"
- Can't answer "WHICH 23 transactions?"
- Can't perfectly reconstruct queue state for replay/debugging

---

## Architecture Analysis

### Queue Structure (Rust)

**Agent (Queue 1 - Internal Bank Queue)**:
```rust
// File: backend/src/models/agent.rs:81
outgoing_queue: Vec<String>  // Transaction IDs awaiting policy decision

// Access methods:
pub fn outgoing_queue(&self) -> &[String]  // Get queue contents
pub fn outgoing_queue_size(&self) -> usize // Get queue size
```

**SimulationState (Queue 2 - RTGS Central Queue)**:
```rust
// File: backend/src/models/state.rs:69
rtgs_queue: Vec<String>  // Transaction IDs awaiting settlement

// Access methods:
pub fn get_rtgs_queue(&self) -> &Vec<String>  // Get queue contents
pub fn queue_size(&self) -> usize             // Get queue size
```

### Database Schema

**New Table: `agent_queue_snapshots`**
```sql
CREATE TABLE agent_queue_snapshots (
    simulation_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    day INTEGER NOT NULL,
    queue_type VARCHAR NOT NULL CHECK(queue_type IN ('queue1')),  -- Future: 'queue2' if needed
    position INTEGER NOT NULL,     -- 0-indexed position in queue
    transaction_id VARCHAR NOT NULL,

    PRIMARY KEY (simulation_id, agent_id, day, queue_type, position),
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
);
```

**Rationale for Schema**:
- **Per-agent Queue 1**: Each agent has their own internal queue
- **Position field**: Preserves queue order (FIFO, Priority, etc.)
- **No Queue 2 table yet**: Queue 2 is global and can be reconstructed from agent queues in most cases (defer if time-constrained)

**Alternative Approach** (if Queue 2 needed):
```sql
CREATE TABLE rtgs_queue_snapshots (
    simulation_id VARCHAR NOT NULL,
    day INTEGER NOT NULL,
    position INTEGER NOT NULL,
    transaction_id VARCHAR NOT NULL,

    PRIMARY KEY (simulation_id, day, position)
);
```

---

## TDD Implementation Plan

### Phase 3.1: Python Tests (RED) - 2 hours

**File**: `api/tests/integration/test_queue_persistence.py`

**Test Classes**:

1. **TestFFIQueueRetrieval** - Verify Rust FFI methods
   - `test_ffi_get_agent_queue_exists()` - Method exists and callable
   - `test_ffi_get_agent_queue_returns_list()` - Returns list of transaction IDs
   - `test_ffi_get_agent_queue_ordering()` - Preserves queue order

2. **TestQueuePersistence** - Verify persistence logic
   - `test_agent_queue_snapshots_persisted()` - Queue 1 contents saved
   - `test_queue_snapshots_preserve_order()` - Position field correct
   - `test_queue_snapshots_match_queue_size()` - Count matches aggregate metric
   - `test_multiple_agents_multiple_queues()` - Multiple agents with queues

3. **TestQueueSchema** - Verify database schema
   - `test_agent_queue_snapshots_table_exists()`
   - `test_agent_queue_snapshots_table_schema()`

4. **TestQueueDataIntegrity** - Verify data quality
   - `test_queue_positions_sequential()` - No gaps in positions
   - `test_queue_transaction_ids_valid()` - All tx_ids exist in transactions table

**Expected Result**: 8-10 tests, all FAILING (RED phase)

---

### Phase 3.2: Rust Implementation (GREEN) - 2 hours

**Scope**: Add FFI method to retrieve agent queue contents

**File**: `backend/src/lib.rs` (or create `backend/src/orchestrator/queue_snapshot.rs`)

**FFI Method to Add**:

```rust
#[pymethod]
pub fn get_agent_queue_snapshot(&self, agent_id: &str) -> PyResult<Vec<PyObject>> {
    Python::with_gil(|py| {
        let agent = self.state.get_agent(agent_id)
            .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>(
                format!("Agent {} not found", agent_id)
            ))?;

        let queue_items: Vec<PyObject> = agent
            .outgoing_queue()
            .iter()
            .enumerate()
            .map(|(position, tx_id)| {
                let dict = PyDict::new(py);
                dict.set_item("position", position).unwrap();
                dict.set_item("transaction_id", tx_id.clone()).unwrap();
                dict.to_object(py)
            })
            .collect();

        Ok(queue_items)
    })
}
```

**Alternative Simpler Approach** (if time-constrained):
```rust
#[pymethod]
pub fn get_agent_queue1_contents(&self, agent_id: &str) -> PyResult<Vec<String>> {
    let agent = self.state.get_agent(agent_id)
        .ok_or_else(|| PyErr::new::<pyo3::exceptions::PyKeyError, _>(
            format!("Agent {} not found", agent_id)
        ))?;

    Ok(agent.outgoing_queue().to_vec())
}
```

**Testing**:
```bash
cd backend
cargo test --no-default-features queue
```

**Expected Result**: Rust tests pass, FFI method callable from Python

---

### Phase 3.3: Python Write Logic (GREEN) - 1 hour

**File**: `api/payment_simulator/cli/commands/run.py`

**Location**: After agent metrics persistence (lines ~390 and ~415)

**Code to Add**:

```python
# Write agent queue snapshots for this day (Phase 3.3)
for agent_id in orch.get_agent_ids():
    queue_contents = orch.get_agent_queue1_contents(agent_id)

    if queue_contents:
        # Create DataFrame with position index
        queue_data = [
            {
                "simulation_id": sim_id,
                "agent_id": agent_id,
                "day": day,
                "queue_type": "queue1",
                "position": idx,
                "transaction_id": tx_id,
            }
            for idx, tx_id in enumerate(queue_contents)
        ]

        df = pl.DataFrame(queue_data)
        db_manager.conn.execute("INSERT INTO agent_queue_snapshots SELECT * FROM df")

log_info(f"  Persisted queue snapshots for {len([a for a in orch.get_agent_ids() if orch.get_agent_queue1_contents(a)])} agents", quiet)
```

**Database Migration**:

**File**: `api/payment_simulator/persistence/schema.py`

Add to schema:
```python
CREATE TABLE IF NOT EXISTS agent_queue_snapshots (
    simulation_id VARCHAR NOT NULL,
    agent_id VARCHAR NOT NULL,
    day INTEGER NOT NULL,
    queue_type VARCHAR NOT NULL CHECK(queue_type IN ('queue1')),
    position INTEGER NOT NULL,
    transaction_id VARCHAR NOT NULL,

    PRIMARY KEY (simulation_id, agent_id, day, queue_type, position),
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
)
```

**Expected Result**: Queue contents persisted to database

---

### Phase 3.4: Verification (REFACTOR) - 1 hour

**Tasks**:

1. **Run Python Tests**:
   ```bash
   cd api
   source .venv/bin/activate
   pytest tests/integration/test_queue_persistence.py -v
   ```
   **Expected**: 8-10/10 tests passing

2. **End-to-End Test**:
   ```bash
   payment-sim run --config examples/configs/high-pressure.yaml --persist --db-path test_queue.db
   ```

3. **Verify Database**:
   ```python
   import duckdb
   conn = duckdb.connect('test_queue.db')

   # Check queue snapshots exist
   count = conn.execute('SELECT COUNT(*) FROM agent_queue_snapshots').fetchone()[0]
   print(f"Queue snapshots: {count}")

   # Verify counts match metrics
   result = conn.execute('''
       SELECT
           m.agent_id,
           m.day,
           m.queue1_eod_size,
           COUNT(q.transaction_id) as snapshot_count
       FROM daily_agent_metrics m
       LEFT JOIN agent_queue_snapshots q
           ON m.simulation_id = q.simulation_id
           AND m.agent_id = q.agent_id
           AND m.day = q.day
       GROUP BY m.agent_id, m.day, m.queue1_eod_size
   ''').fetchall()

   for row in result:
       assert row[2] == row[3], f"Queue size mismatch: {row}"
   ```

4. **Performance Check**:
   - Queue snapshots insert should be fast (<100ms for 1000 queued transactions)
   - No significant impact on simulation performance

**Expected Result**: All tests pass, queue contents verified in database

---

## Success Criteria

✅ **Implementation Complete When**:
1. FFI method `get_agent_queue1_contents()` exists and works
2. `agent_queue_snapshots` table exists in schema
3. Queue contents persisted at end of each day
4. 8-10/10 Python integration tests passing
5. Queue snapshot counts match `queue1_eod_size` in metrics
6. Position field preserves queue order correctly

---

## Edge Cases to Handle

1. **Empty Queues**: Don't create rows for empty queues (check `if queue_contents`)
2. **Queue Order**: Preserve order using position field (0-indexed)
3. **Multiple Days**: Snapshot per day, not cumulative
4. **Agent Without Queue**: Skip agents with empty queues

---

## Out of Scope (Deferred)

### Queue 2 (RTGS Central Queue) Persistence
- **Reason**: Queue 2 can be reconstructed from transaction states in most cases
- **Deferral**: Implement only if explicitly needed for research
- **Time Saved**: ~2 hours

### Queue Position History (Intraday)
- **Reason**: Only EOD snapshots needed for most analysis
- **Deferral**: Would require per-tick snapshots (storage explosion)
- **Alternative**: Use transaction queue timing metrics

---

## Dependencies

### Required FFI Methods
- ✅ `get_agent_ids()` - Already exists
- ⏳ `get_agent_queue1_contents(agent_id)` - **TO IMPLEMENT**

### Required Database Schema
- ⏳ `agent_queue_snapshots` table - **TO CREATE**

### Required Python Modules
- ✅ `polars` - Already used
- ✅ `duckdb` - Already used

---

## Testing Strategy

### Rust Unit Tests (Phase 3.2)
Focus: FFI method correctness
```bash
cd backend
cargo test --no-default-features queue
```

### Python Integration Tests (Phase 3.1, 3.4)
Focus: End-to-end persistence
```bash
cd api
pytest tests/integration/test_queue_persistence.py -v
```

### Manual Verification (Phase 3.4)
Focus: Data integrity
```bash
payment-sim run --config examples/configs/high-pressure.yaml --persist
# Verify queue snapshots in database
```

---

## Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 3.1 | Write Python tests (RED) | 2h | ⏳ PENDING |
| 3.2 | Rust FFI implementation | 2h | ⏳ PENDING |
| 3.3 | Python persistence logic | 1h | ⏳ PENDING |
| 3.4 | Verification & cleanup | 1h | ⏳ PENDING |
| **TOTAL** | | **6h** | |

---

## Risks and Mitigations

### Risk: FFI Overhead for Large Queues
**Mitigation**: Test with high-pressure scenario (100+ queued transactions per agent)
**Fallback**: Batch queue snapshots if needed

### Risk: Database Size Growth
**Mitigation**: Queue snapshots only at EOD (not per-tick)
**Impact**: Typical simulation: 10 agents × 10 days × 50 avg queue size = 5,000 rows (negligible)

### Risk: Queue Order Not Preserved
**Mitigation**: Use explicit position field in schema
**Verification**: Test with non-FIFO policies to ensure order matters

---

## Comparison with Phase 2 (Collateral Events)

| Aspect | Phase 2 (Collateral) | Phase 3 (Queues) |
|--------|---------------------|------------------|
| Rust Implementation | ✅ Already existed | ⚠️ FFI method needed |
| Data Volume | Low (few events) | Medium (50-500 per day) |
| Complexity | Medium | Low |
| Priority | CRITICAL | IMPORTANT |
| Time Required | 2h (Rust existed) | 6h (need FFI) |

---

## Next Steps After Phase 3

**Option A**: Phase 4 (LSM Cycles) - 4 hours
**Option B**: Stop at 95% coverage, proceed to Policy Engine/LLM work
**Option C**: Refactor Phases 1-3 for consistency

**Recommendation**: Option B - 95% coverage is excellent, remaining 5% is optional

---

*Created: 2025-10-30*
*Phase: 3 (Queue Contents)*
*Status: PLANNING*
