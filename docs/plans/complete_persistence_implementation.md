# Complete Persistence Implementation Plan

**Status**: PLANNING
**Priority**: CRITICAL
**Principle**: **ALL SIMULATION DATA MUST BE PERSISTED**

---

## Executive Summary

**Current State**: Phase 10 is 90% complete - core data (transactions, metrics, policies) persists correctly, but **critical gaps exist** that violate the "all data must be persisted" requirement.

**Goal**: Achieve 100% data persistence - every piece of simulation state that exists in the Rust orchestrator must be persisted to the database.

**Approach**: Follow strict TDD (RED-GREEN-REFACTOR) for each missing data type.

---

## Gap Analysis: What Data is NOT Being Persisted?

### ❌ CRITICAL GAPS (Data exists but not persisted)

1. **Simulation Metadata** (Phase 5 `simulations` table)
   - Table exists, write logic missing
   - Breaks query interface functions
   - **Impact**: HIGH - Phase 11 depends on this

2. **Collateral Events** (individual post/withdraw/hold decisions)
   - Table exists, FFI method + write logic missing
   - Loses granular collateral behavior data
   - **Impact**: HIGH - Cannot analyze collateral policies
   - **REQUIREMENT**: Track EVERY collateral event with FULL detail:
     - Exact amount posted/withdrawn
     - Exact tick/day when it occurred
     - Reason for the action (insufficient liquidity, strategic decision, etc.)
     - Layer (strategic policy vs end-of-tick automatic)
     - Before/after balances and collateral states
     - Available capacity after the action

3. **Queue Contents** (actual transaction IDs in each queue)
   - Table does NOT exist
   - Only queue sizes persisted, not contents
   - **Impact**: MEDIUM - Cannot reconstruct exact queue state

4. **LSM Cycle Resolutions** (which transactions were released together)
   - Table does NOT exist
   - Only LSM release count persisted
   - **Impact**: MEDIUM - Cannot analyze LSM effectiveness

5. **RNG Seed State** (per-tick seed evolution)
   - Not persisted at tick granularity
   - Only initial seed stored
   - **Impact**: LOW - Determinism requires exact seed at each tick

### ⚠️ SCHEMA ISSUES

6. **Schema Migrations** (empty table)
   - Infrastructure table not being used
   - **Impact**: LOW - Migration system not tracking changes

---

## Implementation Plan: TDD Approach

### Phase 1: Simulation Metadata (CRITICAL - 4 hours)

**Goal**: Fix `simulations` table to enable Phase 5 query interface

#### Step 1.1: RED - Write Tests (1 hour)

**File**: `/api/tests/integration/test_simulation_metadata_persistence.py`

```python
"""
Test: Simulation metadata persisted to simulations table (Phase 5)
Status: RED - simulations table is empty
"""

def test_simulation_metadata_persisted_to_simulations_table(tmp_path):
    """Verify simulations table is populated with metadata."""
    from payment_simulator._core import Orchestrator
    from payment_simulator.persistence.connection import DatabaseManager

    db_path = tmp_path / "test.db"
    db_manager = DatabaseManager(str(db_path))
    db_manager.initialize_schema()

    config = {
        "ticks_per_day": 10,
        "num_days": 1,
        "rng_seed": 12345,
        "agent_configs": [
            {"id": "BANK_A", "opening_balance": 1_000_000, "credit_limit": 500_000,
             "policy": {"type": "Fifo"}},
        ],
    }

    orch = Orchestrator.new(config)

    # Simulate
    for _ in range(10):
        orch.tick()

    # Get metrics
    total_arrivals = 0  # Calculate from orch
    total_settlements = 0  # Calculate from orch

    # Persist simulation metadata
    import hashlib
    from datetime import datetime

    config_hash = hashlib.sha256(str(config).encode()).hexdigest()

    db_manager.conn.execute("""
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents,
            status, started_at, completed_at,
            total_arrivals, total_settlements, total_cost_cents,
            duration_seconds, ticks_per_second
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        "test-001",
        "test_config.yaml",
        config_hash,
        12345,
        10, 1, 1,
        "completed",
        datetime.now(),
        datetime.now(),
        total_arrivals,
        total_settlements,
        0,
        0.1,
        100.0
    ])

    # Verify
    result = db_manager.conn.execute("""
        SELECT simulation_id, num_agents, rng_seed, status
        FROM simulations
        WHERE simulation_id = 'test-001'
    """).fetchone()

    assert result is not None
    assert result[0] == "test-001"
    assert result[1] == 1
    assert result[2] == 12345
    assert result[3] == "completed"


def test_simulation_metadata_matches_simulation_runs(tmp_path):
    """Verify simulations table has same data as simulation_runs (migration check)."""
    # Both tables should contain identical core information
    pass


def test_list_simulations_query_returns_data(tmp_path):
    """Verify list_simulations() query works after persistence."""
    from payment_simulator.persistence.queries import list_simulations

    # After persisting simulation, list_simulations() should return results
    pass


def test_compare_simulations_query_works(tmp_path):
    """Verify compare_simulations() works after persistence."""
    from payment_simulator.persistence.queries import compare_simulations

    # After persisting two simulations, compare should work
    pass
```

**Success Criteria**: All tests FAIL (table empty, queries return no results)

---

#### Step 1.2: GREEN - Implement Write Logic (2 hours)

**File**: `/api/payment_simulator/cli/commands/run.py`

**Location**: After line 476 (after simulation_runs insert)

```python
# NEW CODE: Persist to simulations table (Phase 5 query interface)
import hashlib
from datetime import datetime

start_time = datetime.now()
end_time = datetime.now()
duration = (end_time - start_time).total_seconds()

config_hash = hashlib.sha256(str(config_dict).encode()).hexdigest()

# Calculate total cost from agent metrics
total_cost = 0
if persist:
    daily_metrics = orch.get_daily_agent_metrics(0)
    for metric in daily_metrics:
        total_cost += metric.get('total_cost', 0)

db_manager.conn.execute("""
    INSERT INTO simulations (
        simulation_id, config_file, config_hash, rng_seed,
        ticks_per_day, num_days, num_agents,
        status, started_at, completed_at,
        total_arrivals, total_settlements, total_cost_cents,
        duration_seconds, ticks_per_second
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", [
    sim_id,
    config.name,
    config_hash,
    ffi_dict["rng_seed"],
    ffi_dict["ticks_per_day"],
    ffi_dict["num_days"],
    len(agent_ids),
    "completed",
    start_time,
    end_time,
    total_arrivals,
    total_settlements,
    total_cost,
    duration,
    ticks_per_second
])

log_success(f"Simulation metadata persisted to simulations table", quiet)
```

**Success Criteria**: All tests PASS (table populated, queries work)

---

#### Step 1.3: REFACTOR - Extract Helper Function (1 hour)

**File**: `/api/payment_simulator/persistence/writers.py`

```python
def persist_simulation_metadata(
    db_manager: DatabaseManager,
    simulation_id: str,
    config_file: str,
    config_dict: dict,
    orchestrator,
    start_time: datetime,
    end_time: datetime,
    agent_ids: list[str]
) -> None:
    """Persist simulation metadata to simulations table.

    This is the Phase 5 query interface table that enables:
    - list_simulations()
    - get_simulation_summary()
    - compare_simulations()

    Args:
        db_manager: Database connection manager
        simulation_id: Unique simulation identifier
        config_file: Configuration file name
        config_dict: Full configuration dictionary
        orchestrator: FFI orchestrator instance
        start_time: Simulation start timestamp
        end_time: Simulation end timestamp
        agent_ids: List of agent IDs
    """
    import hashlib

    # Calculate metrics
    config_hash = hashlib.sha256(str(config_dict).encode()).hexdigest()
    duration = (end_time - start_time).total_seconds()

    # Get final metrics from orchestrator
    # TODO: Add FFI method to get system-wide stats
    total_arrivals = 0  # orchestrator.get_total_arrivals()
    total_settlements = 0  # orchestrator.get_total_settlements()
    total_cost = 0  # orchestrator.get_total_cost()

    ticks_per_second = config_dict["ticks_per_day"] / duration if duration > 0 else 0

    db_manager.conn.execute("""
        INSERT INTO simulations (
            simulation_id, config_file, config_hash, rng_seed,
            ticks_per_day, num_days, num_agents,
            status, started_at, completed_at,
            total_arrivals, total_settlements, total_cost_cents,
            duration_seconds, ticks_per_second
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        simulation_id,
        config_file,
        config_hash,
        config_dict["rng_seed"],
        config_dict["ticks_per_day"],
        config_dict["num_days"],
        len(agent_ids),
        "completed",
        start_time,
        end_time,
        total_arrivals,
        total_settlements,
        total_cost,
        duration,
        ticks_per_second
    ])
```

**Update run.py**: Call helper function instead of inline code

**Success Criteria**: Tests still pass, code is cleaner

---

### Phase 2: Collateral Events (CRITICAL - 8 hours)

**Goal**: Track every collateral post/withdraw/hold decision

#### Step 2.1: RED - Write Tests (2 hours)

**File**: `/api/tests/integration/test_collateral_event_persistence.py`

```python
"""
Test: Collateral events persisted to collateral_events table
Status: RED - FFI method doesn't exist
"""

def test_ffi_get_collateral_events_for_day_exists():
    """Verify FFI method get_collateral_events_for_day() exists."""
    from payment_simulator._core import Orchestrator

    config = create_config_with_collateral_triggers()
    orch = Orchestrator.new(config)

    # Simulate to trigger collateral actions
    for _ in range(20):
        orch.tick()

    # RED: This method doesn't exist yet
    collateral_events = orch.get_collateral_events_for_day(0)

    assert isinstance(collateral_events, list)


def test_collateral_event_has_required_fields():
    """Verify each collateral event dict has all required fields."""
    # Required fields: simulation_id, agent_id, tick, day,
    #                  action, amount, reason, layer,
    #                  balance_before, posted_collateral_before,
    #                  posted_collateral_after, available_capacity_after
    pass


def test_collateral_events_validate_with_pydantic():
    """Verify collateral events validate with CollateralEventRecord."""
    from payment_simulator.persistence.models import CollateralEventRecord

    # Each event should validate
    pass


def test_collateral_events_persisted_to_database(tmp_path):
    """Verify collateral events are persisted."""
    # After simulation with collateral activity, table should have rows
    pass


def test_collateral_events_match_metrics_counts(tmp_path):
    """Verify collateral event count matches daily_agent_metrics."""
    # Sum of collateral_events.action='post' should equal
    # daily_agent_metrics.num_collateral_posts
    pass


def test_collateral_events_capture_policy_layer():
    """Verify both strategic and end_of_tick layers captured."""
    # Events should have layer='strategic' or layer='end_of_tick'
    pass
```

**Success Criteria**: All tests FAIL (FFI method doesn't exist)

---

#### Step 2.2: GREEN - Implement Rust FFI Method (4-6 hours)

**⚠️ IMPORTANT**: This is a complex Rust implementation requiring strict TDD.

**📋 See Detailed Plan**: `/docs/plans/phase2_collateral_tracking_rust_tdd.md`

**Summary of Rust Implementation**:

```rust
/// Get collateral events for a specific day (Phase 10: Collateral Event Tracking)
///
/// Returns all collateral management events that occurred during the specified day,
/// including strategic layer decisions and end-of-tick automatic postings.
///
/// # Python Example
/// ```python
/// collateral_events = orch.get_collateral_events_for_day(0)
///
/// # Convert to Polars DataFrame
/// import polars as pl
/// df = pl.DataFrame(collateral_events)
///
/// # Write to DuckDB
/// conn.execute("INSERT INTO collateral_events SELECT * FROM df")
/// ```
#[pyo3(name = "get_collateral_events_for_day")]
fn get_collateral_events_for_day(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
    // Get collateral events from Rust orchestrator
    let events = self.inner.get_collateral_events_for_day(day);

    // Get simulation metadata for conversion
    let simulation_id = self.inner.simulation_id();

    // Convert each event to Python dict
    let py_list = PyList::empty(py);
    for event in events {
        let event_dict = collateral_event_to_py(py, event, &simulation_id)?;
        py_list.append(event_dict)?;
    }

    Ok(py_list.into())
}
```

**File**: `/backend/src/ffi/converters.rs` (new file or add to existing)

```rust
/// Convert CollateralEvent to Python dict
fn collateral_event_to_py(
    py: Python,
    event: &CollateralEvent,
    simulation_id: &str,
) -> PyResult<Py<PyDict>> {
    let dict = PyDict::new(py);

    dict.set_item("simulation_id", simulation_id)?;
    dict.set_item("agent_id", &event.agent_id)?;
    dict.set_item("tick", event.tick)?;
    dict.set_item("day", event.day)?;
    dict.set_item("action", event.action.to_string())?;  // "post", "withdraw", "hold"
    dict.set_item("amount", event.amount)?;
    dict.set_item("reason", &event.reason)?;
    dict.set_item("layer", event.layer.to_string())?;  // "strategic", "end_of_tick"
    dict.set_item("balance_before", event.balance_before)?;
    dict.set_item("posted_collateral_before", event.posted_collateral_before)?;
    dict.set_item("posted_collateral_after", event.posted_collateral_after)?;
    dict.set_item("available_capacity_after", event.available_capacity_after)?;

    Ok(dict.into())
}
```

**File**: `/backend/src/orchestrator/engine.rs`

**Add CollateralEvent tracking**:

```rust
pub struct CollateralEvent {
    pub agent_id: String,
    pub tick: usize,
    pub day: usize,
    pub action: CollateralAction,
    pub amount: i64,
    pub reason: String,
    pub layer: CollateralLayer,
    pub balance_before: i64,
    pub posted_collateral_before: i64,
    pub posted_collateral_after: i64,
    pub available_capacity_after: i64,
}

pub enum CollateralAction {
    Post,
    Withdraw,
    Hold,
}

pub enum CollateralLayer {
    Strategic,
    EndOfTick,
}

// In SimulationState:
pub struct SimulationState {
    // ... existing fields
    pub collateral_events: Vec<CollateralEvent>,
}

// In orchestrator tick loop (when collateral is posted/withdrawn):
fn record_collateral_event(&mut self, agent_id: &str, action: CollateralAction, amount: i64, reason: String, layer: CollateralLayer) {
    let agent = self.agents.get(agent_id).unwrap();

    let event = CollateralEvent {
        agent_id: agent_id.to_string(),
        tick: self.current_tick,
        day: self.current_day,
        action,
        amount,
        reason,
        layer,
        balance_before: agent.balance,
        posted_collateral_before: agent.posted_collateral,
        posted_collateral_after: agent.posted_collateral,  // Updated based on action
        available_capacity_after: agent.collateral_capacity - agent.posted_collateral,
    };

    self.collateral_events.push(event);
}

// Add method to get events for a day:
pub fn get_collateral_events_for_day(&self, day: usize) -> Vec<&CollateralEvent> {
    self.collateral_events
        .iter()
        .filter(|e| e.day == day)
        .collect()
}
```

**Success Criteria**: FFI method callable from Python, returns correct data structure

---

#### Step 2.3: GREEN - Implement Python Write Logic (1 hour)

**File**: `/api/payment_simulator/cli/commands/run.py`

**Location**: After agent metrics persistence (around line 422)

```python
# Persist collateral events
collateral_events = orch.get_collateral_events_for_day(day)
if collateral_events:
    df = pl.DataFrame(collateral_events)
    db_manager.conn.execute("INSERT INTO collateral_events SELECT * FROM df")
    log_success(f"  Persisted {len(collateral_events)} collateral events for day {day}", quiet)
```

**Success Criteria**: All tests PASS (collateral events persisted)

---

#### Step 2.4: REFACTOR - Add Collateral Event Tracking (1 hour)

**Ensure collateral events are recorded in ALL places where collateral is managed**:

1. Strategic layer (policy decisions)
2. End-of-tick layer (automatic posting)
3. Withdrawal triggers

**Success Criteria**: Tests still pass, all collateral actions tracked

---

### Phase 3: Queue Contents Tracking (IMPORTANT - 6 hours)

**Goal**: Persist actual transaction IDs in each queue, not just sizes

**Why Important**: Currently we only persist queue SIZES (queue1_eod_size), but not which specific transactions are in each queue. This makes it impossible to reconstruct exact queue state.

#### Step 3.1: RED - Create Schema (1 hour)

**File**: `/api/payment_simulator/persistence/models.py`

```python
class QueueSnapshotRecord(BaseModel):
    """Queue contents snapshot at end of day.

    Captures which transactions are in which queue at EOD.
    This enables perfect state reconstruction.
    """

    model_config = ConfigDict(
        table_name="queue_snapshots",
        primary_key=["id"],
        indexes=[
            ("idx_queue_sim_agent_day", ["simulation_id", "agent_id", "day"]),
        ],
    )

    id: Optional[int] = None  # Auto-increment
    simulation_id: str
    agent_id: str
    day: int
    tick: int  # End-of-day tick

    queue_type: str  # "queue1" or "queue2"
    position: int  # Position in queue (0-indexed)
    tx_id: str  # Transaction ID in this position
```

**File**: `/api/payment_simulator/persistence/schema_generator.py`

Add `QueueSnapshotRecord` to models list.

---

#### Step 3.2: RED - Write Tests (1 hour)

**File**: `/api/tests/integration/test_queue_snapshot_persistence.py`

```python
"""
Test: Queue contents persisted to queue_snapshots table
Status: RED - FFI method doesn't exist
"""

def test_ffi_get_queue_snapshots_for_day_exists():
    """Verify FFI method get_queue_snapshots_for_day() exists."""
    # RED: Method doesn't exist
    pass


def test_queue_snapshots_match_queue_sizes():
    """Verify queue_snapshots count matches queue sizes in daily_agent_metrics."""
    # If daily_agent_metrics says queue1_eod_size=23,
    # then queue_snapshots should have 23 rows for that agent/queue/day
    pass


def test_queue_reconstruction_from_snapshots():
    """Verify we can reconstruct exact queue state from snapshots."""
    # Given queue_snapshots, rebuild the queue and verify order
    pass
```

---

#### Step 3.3: GREEN - Implement FFI Method (2 hours)

**File**: `/backend/src/ffi/orchestrator.rs`

```rust
/// Get queue snapshots for a specific day (end-of-day queue contents)
#[pyo3(name = "get_queue_snapshots_for_day")]
fn get_queue_snapshots_for_day(&self, py: Python, day: usize) -> PyResult<Py<PyList>> {
    let snapshots = self.inner.get_queue_snapshots_for_day(day);
    let simulation_id = self.inner.simulation_id();

    let py_list = PyList::empty(py);
    for snapshot in snapshots {
        let dict = PyDict::new(py);
        dict.set_item("simulation_id", simulation_id)?;
        dict.set_item("agent_id", &snapshot.agent_id)?;
        dict.set_item("day", snapshot.day)?;
        dict.set_item("tick", snapshot.tick)?;
        dict.set_item("queue_type", &snapshot.queue_type)?;  // "queue1" or "queue2"
        dict.set_item("position", snapshot.position)?;
        dict.set_item("tx_id", &snapshot.tx_id)?;
        py_list.append(dict)?;
    }

    Ok(py_list.into())
}
```

**File**: `/backend/src/orchestrator/engine.rs`

```rust
pub struct QueueSnapshot {
    pub agent_id: String,
    pub day: usize,
    pub tick: usize,
    pub queue_type: String,  // "queue1" or "queue2"
    pub position: usize,
    pub tx_id: String,
}

// At end of each day:
pub fn capture_queue_snapshots(&self) -> Vec<QueueSnapshot> {
    let mut snapshots = Vec::new();

    // Capture Queue 1 (internal bank queues)
    for (agent_id, agent) in &self.agents {
        for (pos, tx_id) in agent.outgoing_queue.iter().enumerate() {
            snapshots.push(QueueSnapshot {
                agent_id: agent_id.clone(),
                day: self.current_day,
                tick: self.current_tick,
                queue_type: "queue1".to_string(),
                position: pos,
                tx_id: tx_id.clone(),
            });
        }
    }

    // Capture Queue 2 (RTGS central queue)
    for (pos, tx_id) in self.rtgs_queue.iter().enumerate() {
        // Queue 2 is system-wide, not per-agent
        snapshots.push(QueueSnapshot {
            agent_id: "SYSTEM".to_string(),  // Or track which agent's tx
            day: self.current_day,
            tick: self.current_tick,
            queue_type: "queue2".to_string(),
            position: pos,
            tx_id: tx_id.clone(),
        });
    }

    snapshots
}
```

---

#### Step 3.4: GREEN - Implement Python Write Logic (1 hour)

**File**: `/api/payment_simulator/cli/commands/run.py`

```python
# Persist queue snapshots (end-of-day queue contents)
queue_snapshots = orch.get_queue_snapshots_for_day(day)
if queue_snapshots:
    df = pl.DataFrame(queue_snapshots)
    db_manager.conn.execute("INSERT INTO queue_snapshots SELECT * FROM df")
    log_success(f"  Persisted {len(queue_snapshots)} queue snapshots for day {day}", quiet)
```

---

#### Step 3.5: REFACTOR - Verify Reconstruction (1 hour)

Write test that reconstructs queue state from snapshots and verifies correctness.

**Success Criteria**: Can rebuild exact queue state (with order) from database

---

### Phase 4: LSM Cycle Resolutions (OPTIONAL - 4 hours)

**Goal**: Track which transactions were released together in LSM cycles

**Why Important**: Currently we only track LSM release COUNT, not which specific transactions were released together. This loses valuable information about LSM effectiveness.

#### Step 4.1: RED - Create Schema (30 min)

**File**: `/api/payment_simulator/persistence/models.py`

```python
class LSMCycleRecord(BaseModel):
    """LSM cycle resolution events.

    Tracks when LSM finds bilateral offsets or cycles.
    """

    model_config = ConfigDict(
        table_name="lsm_cycles",
        primary_key=["id"],
        indexes=[
            ("idx_lsm_sim_day", ["simulation_id", "day"]),
            ("idx_lsm_cycle", ["cycle_id"]),
        ],
    )

    id: Optional[int] = None
    simulation_id: str
    cycle_id: str  # Unique cycle identifier
    tick: int
    day: int

    cycle_type: str  # "bilateral", "multilateral", "gross"
    num_transactions: int  # Transactions in this cycle
    total_amount: int  # Total value settled

    # Transactions involved (could be separate table)
    tx_ids: str  # JSON array of transaction IDs


class LSMCycleTransactionRecord(BaseModel):
    """Individual transactions in LSM cycles."""

    model_config = ConfigDict(
        table_name="lsm_cycle_transactions",
        primary_key=["id"],
    )

    id: Optional[int] = None
    cycle_id: str
    tx_id: str
    position: int  # Position in cycle
```

---

#### Step 4.2-4.5: Follow same TDD pattern as previous phases

**Success Criteria**: Can analyze which transactions were released together, LSM cycle effectiveness

---

### Phase 5: RNG Seed State Tracking (ADVANCED - 2 hours)

**Goal**: Track RNG seed evolution at each tick for perfect determinism

**Why Important**: For perfect reproducibility, need to know exact RNG seed at any point in time.

**Decision**: This may be overkill - initial seed + tick count should be sufficient for determinism. **DEFER** unless specifically needed.

---

### Phase 6: Integration & Testing (8 hours)

#### Step 6.1: End-to-End Integration Test (4 hours)

**File**: `/api/tests/integration/test_complete_persistence.py`

```python
"""
Test: ALL simulation data persisted to database
Status: INTEGRATION TEST - verifies 100% persistence
"""

def test_all_data_persisted_nothing_missing(tmp_path):
    """
    CRITICAL TEST: Verify ALL simulation data is persisted.

    This test fails if ANY data exists in the orchestrator that
    is not persisted to the database.
    """
    # 1. Run simulation
    # 2. Query ALL tables
    # 3. Verify row counts match expectations
    # 4. Verify can reconstruct EXACT orchestrator state from DB
    # 5. Verify second run with same seed produces identical DB state
    pass


def test_state_reconstruction_from_database(tmp_path):
    """Verify can rebuild orchestrator state from database."""
    # 1. Run simulation, persist everything
    # 2. Clear orchestrator
    # 3. Rebuild state from database queries
    # 4. Verify reconstructed state matches original
    pass


def test_cross_simulation_data_isolation(tmp_path):
    """Verify multiple simulations don't interfere."""
    # 1. Run simulation A
    # 2. Run simulation B (different config)
    # 3. Query simulation A data
    # 4. Verify simulation A data unchanged
    pass


def test_performance_all_writes_under_threshold(tmp_path):
    """Verify all persistence operations meet performance targets."""
    # - Transactions: <100ms for 40K
    # - Agent metrics: <20ms for 200 agents
    # - Collateral events: <50ms for 1K events
    # - Queue snapshots: <30ms for 5K entries
    # - LSM cycles: <20ms for 100 cycles
    pass
```

**Success Criteria**: All integration tests pass

---

#### Step 6.2: Update Documentation (2 hours)

**Files to Update**:
1. `/README.md` - Add complete persistence feature list
2. `/docs/grand_plan.md` - Mark Phase 10 as 100% complete
3. `/docs/persistence_implementation_plan.md` - Update status
4. `/CLAUDE.md` - Update persistence section

**Success Criteria**: Documentation accurately reflects 100% persistence

---

#### Step 6.3: Migration Path for Existing Data (2 hours)

**File**: `/api/payment_simulator/persistence/migrations/001_populate_simulations_from_simulation_runs.py`

```python
"""
Migration: Backfill simulations table from simulation_runs table
"""

def migrate_up(conn):
    """Copy existing simulation_runs data to simulations table."""
    # For each row in simulation_runs:
    # - Insert corresponding row in simulations
    # - Map fields appropriately
    # - Set defaults for new fields
    pass
```

**Success Criteria**: Existing simulations visible in new `simulations` table

---

## Implementation Schedule

### Week 1: Critical Gaps
- **Day 1-2**: Phase 1 (Simulation Metadata) - 4 hours
- **Day 3-5**: Phase 2 (Collateral Events) - 8 hours

### Week 2: Important Additions
- **Day 1-3**: Phase 3 (Queue Contents) - 6 hours
- **Day 4**: Phase 4 (LSM Cycles) - 4 hours (or defer)

### Week 3: Integration
- **Day 1-2**: Phase 6.1 (Integration Tests) - 4 hours
- **Day 3**: Phase 6.2 (Documentation) - 2 hours
- **Day 4**: Phase 6.3 (Migration) - 2 hours
- **Day 5**: Buffer for fixes

**Total Effort**: 30-34 hours

---

## Success Criteria: 100% Persistence Achieved

✅ **All Data Persisted**:
1. ✅ Transactions (596 records) - ALREADY WORKING
2. ✅ Daily agent metrics (22 records) - ALREADY WORKING
3. ✅ Policy snapshots (22 records) - ALREADY WORKING
4. ✅ Simulation metadata (simulations table) - **TO BE FIXED**
5. ✅ Collateral events (individual decisions) - **TO BE IMPLEMENTED**
6. ✅ Queue contents (transaction IDs) - **TO BE IMPLEMENTED**
7. ✅ LSM cycles (cycle resolutions) - **OPTIONAL**
8. ✅ RNG seed evolution - **DEFER**

✅ **Query Interface Working**:
- `list_simulations()` returns data
- `compare_simulations()` works
- `get_agent_policy_history()` works
- All 9 query functions operational

✅ **Determinism Verified**:
- Same seed + same config = identical database state
- Can reconstruct orchestrator from database
- No data loss across persistence boundary

✅ **Performance Targets Met**:
- All batch writes complete in <200ms total per day
- Database file size reasonable (<10 GB for 200 runs)
- Query performance <1s for aggregates

✅ **Phase 11 Ready**:
- All data needed for shadow replay available
- Policy comparison queries work
- Episode sampling possible
- Policy provenance tracking complete

---

## Priority Order (If Time Constrained)

1. **CRITICAL (DO FIRST)**: Phase 1 (Simulation Metadata) - 4 hours
   - Fixes Phase 5 query interface
   - Unblocks Phase 11

2. **CRITICAL (DO SECOND)**: Phase 2 (Collateral Events) - 8 hours
   - Essential for collateral policy research
   - Completes cost/behavior tracking

3. **IMPORTANT**: Phase 3 (Queue Contents) - 6 hours
   - Enables perfect state reconstruction
   - Useful for debugging congestion

4. **OPTIONAL**: Phase 4 (LSM Cycles) - 4 hours
   - Interesting but not critical
   - Can analyze LSM without this

5. **DEFER**: Phase 5 (RNG Seed Evolution) - 2 hours
   - Current determinism approach sufficient

---

## Rollback Plan

If implementation takes longer than expected:

**Minimum Viable Completion**:
- Phase 1 (Simulation Metadata) - **MUST COMPLETE**
- Phase 2 (Collateral Events) - **MUST COMPLETE**
- Phase 3-5 - Can defer to Phase 10.1 (future enhancement)

This achieves 95% persistence (only missing queue contents and LSM details).

---

## Testing Strategy

### Unit Tests (Rust)
- Test collateral event recording
- Test queue snapshot capture
- Test LSM cycle tracking

### Integration Tests (Python)
- Test FFI method data flow
- Test Polars DataFrame conversion
- Test DuckDB batch insertion

### End-to-End Tests
- Test full simulation persistence
- Test state reconstruction
- Test determinism preservation

### Performance Tests
- Benchmark each persistence operation
- Verify <200ms total per day
- Test with 200 agents × 30 days

---

## Documentation Requirements

### Code Documentation
- Docstrings for all new FFI methods
- Comments explaining collateral tracking
- Examples in persistence_implementation_plan.md

### User Documentation
- Update README.md with complete feature list
- Document query functions with examples
- Add troubleshooting guide

### Research Documentation
- Document what data is persisted where
- Explain how to reconstruct simulations
- Provide example analytical queries

---

## Risk Mitigation

### Risk 1: FFI Complexity
**Mitigation**: Follow existing patterns from get_transactions_for_day()

### Risk 2: Performance Degradation
**Mitigation**: Benchmark after each phase, optimize if >200ms

### Risk 3: Schema Changes Breaking Tests
**Mitigation**: Use Pydantic models as single source of truth

### Risk 4: Missing Edge Cases
**Mitigation**: Comprehensive integration tests with various scenarios

---

## Conclusion

**Current Status**: Phase 10 is 90% complete - core persistence works.

**Goal**: Achieve 100% persistence - ALL simulation data saved.

**Approach**: Follow strict TDD for each missing data type.

**Timeline**: 3 weeks (30-34 hours) for complete implementation.

**Minimum Viable**: 2 weeks (12 hours) for critical gaps only.

**Recommendation**: Start with Phase 1 (Simulation Metadata) immediately - it's a 4-hour fix that unblocks Phase 11.

---

*Created: 2025-10-30*
*Status: PLANNING - Ready for Implementation*
*Priority: CRITICAL - Required for Phase 11 (LLM Manager)*
