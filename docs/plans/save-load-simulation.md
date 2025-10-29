# Save/Load Simulation State - Design & TDD Plan

**Status**: Planning
**Created**: 2025-10-29
**Author**: Claude Code

---

## Overview

Enable simulations to be saved to database and resumed later, supporting both CLI and API workflows.

**Key Requirements**:
1. ✅ **Determinism**: Resume produces identical results to continuous run
2. ✅ **Atomicity**: Save/load succeeds completely or fails cleanly
3. ✅ **CLI Support**: Save before exit, load on startup
4. ✅ **API Support**: Create simulation from previous checkpoint
5. ✅ **Integrity**: All invariants preserved (balance conservation, queue validity)

---

## Architecture Design

### 1. Data Model - What Gets Saved?

```rust
// Complete orchestrator state snapshot
pub struct StateSnapshot {
    // Temporal position
    pub current_tick: usize,
    pub current_day: usize,

    // Determinism anchor
    pub rng_seed: u64,  // CRITICAL: Current RNG state

    // Agent state (all banks)
    pub agents: Vec<AgentSnapshot>,

    // Transaction state (all payments)
    pub transactions: Vec<TransactionSnapshot>,

    // Queue state
    pub rtgs_queue: Vec<String>,  // Queue 2 (central RTGS)

    // Configuration (for validation)
    pub config_hash: String,  // SHA256 of original config
}

pub struct AgentSnapshot {
    pub id: String,
    pub balance: i64,                    // Current reserves
    pub credit_limit: i64,
    pub outgoing_queue: Vec<String>,     // Queue 1 (internal)
    pub incoming_expected: Vec<String>,
    pub last_decision_tick: Option<usize>,
    pub liquidity_buffer: i64,
    pub posted_collateral: i64,
}

pub struct TransactionSnapshot {
    pub id: String,
    pub sender_id: String,
    pub receiver_id: String,
    pub amount: i64,                     // Original amount
    pub remaining_amount: i64,           // Still to settle
    pub arrival_tick: usize,
    pub deadline_tick: usize,
    pub priority: u8,
    pub status: TransactionStatus,
    pub parent_id: Option<String>,
}
```

### 2. Database Schema (Python Pydantic)

```python
class SimulationCheckpointRecord(BaseModel):
    """Full simulation state snapshot."""
    # Identifiers
    checkpoint_id: str              # UUID for this checkpoint
    simulation_id: str              # Parent simulation

    # Temporal position
    checkpoint_tick: int
    checkpoint_day: int
    checkpoint_timestamp: datetime  # Wall-clock time saved

    # State payload
    state_json: str                 # JSON serialized StateSnapshot
    state_hash: str                 # SHA256 for integrity check
    config_hash: str                # Must match original config

    # Metadata
    checkpoint_type: CheckpointType # manual/auto/eod
    description: Optional[str]
    created_by: str                 # 'cli', 'api', 'scheduled'

    # Size tracking
    num_agents: int
    num_transactions: int
    total_size_bytes: int

class CheckpointType(str, Enum):
    MANUAL = "manual"        # User-requested save
    AUTO = "auto"            # Periodic auto-save
    EOD = "end_of_day"       # End of day checkpoint
    FINAL = "final"          # Simulation complete
```

### 3. Component Design

#### Layer 1: Rust Core (backend/src/)

**File**: `backend/src/orchestrator/checkpoint.rs` (NEW)

```rust
impl Orchestrator {
    /// Serialize complete state to JSON
    pub fn save_state(&self) -> Result<String, OrchestratorError> {
        let snapshot = StateSnapshot {
            current_tick: self.state.current_tick,
            current_day: self.state.current_day,
            rng_seed: self.rng_manager.current_seed(),  // CRITICAL!
            agents: self.state.agents.values()
                .map(|a| a.to_snapshot())
                .collect(),
            transactions: self.state.transactions.values()
                .map(|t| t.to_snapshot())
                .collect(),
            rtgs_queue: self.state.rtgs_queue.clone(),
            config_hash: self.config_hash.clone(),
        };

        // Validate invariants before serializing
        self.validate_state_invariants(&snapshot)?;

        serde_json::to_string(&snapshot)
            .map_err(|e| OrchestratorError::SerializationFailed(e.to_string()))
    }

    /// Restore state from JSON
    pub fn load_state(
        config: OrchestratorConfig,
        state_json: &str,
    ) -> Result<Self, OrchestratorError> {
        let snapshot: StateSnapshot = serde_json::from_str(state_json)
            .map_err(|e| OrchestratorError::DeserializationFailed(e.to_string()))?;

        // Validate config matches
        let config_hash = compute_config_hash(&config);
        if snapshot.config_hash != config_hash {
            return Err(OrchestratorError::ConfigMismatch {
                expected: snapshot.config_hash,
                actual: config_hash,
            });
        }

        // Reconstruct state
        let state = SimulationState::from_snapshot(snapshot)?;

        // Validate invariants after reconstruction
        Self::validate_restored_state(&state)?;

        Ok(Self {
            config,
            state,
            rng_manager: RngManager::new(snapshot.rng_seed),
            // ... other fields
        })
    }

    /// Verify state integrity
    fn validate_state_invariants(
        &self,
        snapshot: &StateSnapshot,
    ) -> Result<(), OrchestratorError> {
        // 1. Balance conservation
        let total_balance: i64 = snapshot.agents.iter()
            .map(|a| a.balance)
            .sum();
        let expected_balance = self.compute_expected_total_balance();
        if total_balance != expected_balance {
            return Err(OrchestratorError::BalanceConservationViolated {
                expected: expected_balance,
                actual: total_balance,
            });
        }

        // 2. Transaction referential integrity
        let tx_ids: HashSet<_> = snapshot.transactions.iter()
            .map(|t| t.id.clone())
            .collect();

        for agent in &snapshot.agents {
            for tx_id in &agent.outgoing_queue {
                if !tx_ids.contains(tx_id) {
                    return Err(OrchestratorError::OrphanedQueueTransaction {
                        agent_id: agent.id.clone(),
                        tx_id: tx_id.clone(),
                    });
                }
            }
        }

        for tx_id in &snapshot.rtgs_queue {
            if !tx_ids.contains(tx_id) {
                return Err(OrchestratorError::OrphanedRtgsTransaction {
                    tx_id: tx_id.clone(),
                });
            }
        }

        // 3. Queue uniqueness (no tx in multiple places)
        let mut seen = HashSet::new();
        for agent in &snapshot.agents {
            for tx_id in &agent.outgoing_queue {
                if !seen.insert(tx_id.clone()) {
                    return Err(OrchestratorError::DuplicateQueueEntry {
                        tx_id: tx_id.clone(),
                    });
                }
            }
        }
        for tx_id in &snapshot.rtgs_queue {
            if !seen.insert(tx_id.clone()) {
                return Err(OrchestratorError::DuplicateQueueEntry {
                    tx_id: tx_id.clone(),
                });
            }
        }

        Ok(())
    }
}

/// Compute deterministic config hash
fn compute_config_hash(config: &OrchestratorConfig) -> String {
    let json = serde_json::to_string(config).unwrap();
    let normalized = json; // TODO: normalize JSON (sort keys)
    format!("{:x}", sha2::Sha256::digest(normalized.as_bytes()))
}
```

#### Layer 2: FFI Boundary (backend/src/ffi/orchestrator.rs)

```rust
#[pymethods]
impl PyOrchestrator {
    /// Save current state to JSON string
    fn save_state(&self) -> PyResult<String> {
        self.inner.save_state()
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to save state: {}", e)
            ))
    }

    /// Create orchestrator from saved state
    #[staticmethod]
    fn load_state(
        config: &Bound<'_, PyDict>,
        state_json: &str,
    ) -> PyResult<Self> {
        let rust_config = parse_orchestrator_config(config)?;
        let inner = RustOrchestrator::load_state(rust_config, state_json)
            .map_err(|e| PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(
                format!("Failed to load state: {}", e)
            ))?;
        Ok(PyOrchestrator { inner })
    }

    /// Get checkpoint metadata (without full state)
    fn get_checkpoint_info(&self) -> PyResult<Py<PyDict>> {
        Python::with_gil(|py| {
            let dict = PyDict::new(py);
            dict.set_item("current_tick", self.inner.current_tick())?;
            dict.set_item("current_day", self.inner.current_day())?;
            dict.set_item("rng_seed", self.inner.rng_seed())?;
            dict.set_item("num_agents", self.inner.num_agents())?;
            dict.set_item("num_transactions", self.inner.num_transactions())?;
            Ok(dict.into())
        })
    }
}
```

#### Layer 3: Python Persistence (api/payment_simulator/persistence/)

**File**: `api/payment_simulator/persistence/checkpoint.py` (NEW)

```python
import json
import hashlib
from datetime import datetime
from typing import Optional
import duckdb

from .models import SimulationCheckpointRecord, CheckpointType
from .connection import DatabaseManager

class CheckpointManager:
    """Manages simulation checkpoints in DuckDB."""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def save_checkpoint(
        self,
        simulation_id: str,
        state_json: str,
        checkpoint_type: CheckpointType,
        description: Optional[str] = None,
        created_by: str = "api",
    ) -> str:
        """Save simulation checkpoint to database.

        Returns:
            checkpoint_id: UUID of created checkpoint
        """
        # Parse state to extract metadata
        state = json.loads(state_json)

        # Compute integrity hash
        state_hash = hashlib.sha256(state_json.encode()).hexdigest()

        # Create record
        checkpoint_id = str(uuid.uuid4())
        record = SimulationCheckpointRecord(
            checkpoint_id=checkpoint_id,
            simulation_id=simulation_id,
            checkpoint_tick=state["current_tick"],
            checkpoint_day=state["current_day"],
            checkpoint_timestamp=datetime.utcnow(),
            state_json=state_json,
            state_hash=state_hash,
            config_hash=state["config_hash"],
            checkpoint_type=checkpoint_type,
            description=description,
            created_by=created_by,
            num_agents=len(state["agents"]),
            num_transactions=len(state["transactions"]),
            total_size_bytes=len(state_json.encode()),
        )

        # Write to database (atomic)
        with self.db.conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO simulation_checkpoints
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.checkpoint_id,
                    record.simulation_id,
                    record.checkpoint_tick,
                    record.checkpoint_day,
                    record.checkpoint_timestamp,
                    record.state_json,
                    record.state_hash,
                    record.config_hash,
                    record.checkpoint_type.value,
                    record.description,
                    record.created_by,
                    record.num_agents,
                    record.num_transactions,
                    record.total_size_bytes,
                )
            )

        return checkpoint_id

    def load_checkpoint(self, checkpoint_id: str) -> SimulationCheckpointRecord:
        """Load checkpoint by ID."""
        cursor = self.db.conn.cursor()
        result = cursor.execute(
            "SELECT * FROM simulation_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,)
        ).fetchone()

        if not result:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        # Convert to Pydantic model
        record = SimulationCheckpointRecord(**dict(result))

        # Verify integrity
        actual_hash = hashlib.sha256(record.state_json.encode()).hexdigest()
        if actual_hash != record.state_hash:
            raise ValueError(
                f"Checkpoint corrupted: hash mismatch for {checkpoint_id}"
            )

        return record

    def list_checkpoints(
        self,
        simulation_id: Optional[str] = None,
        checkpoint_type: Optional[CheckpointType] = None,
    ) -> list[SimulationCheckpointRecord]:
        """List checkpoints with optional filters."""
        query = "SELECT * FROM simulation_checkpoints WHERE 1=1"
        params = []

        if simulation_id:
            query += " AND simulation_id = ?"
            params.append(simulation_id)

        if checkpoint_type:
            query += " AND checkpoint_type = ?"
            params.append(checkpoint_type.value)

        query += " ORDER BY checkpoint_timestamp DESC"

        cursor = self.db.conn.cursor()
        results = cursor.execute(query, params).fetchall()

        return [SimulationCheckpointRecord(**dict(row)) for row in results]

    def get_latest_checkpoint(
        self,
        simulation_id: str,
    ) -> Optional[SimulationCheckpointRecord]:
        """Get most recent checkpoint for simulation."""
        cursor = self.db.conn.cursor()
        result = cursor.execute(
            """
            SELECT * FROM simulation_checkpoints
            WHERE simulation_id = ?
            ORDER BY checkpoint_timestamp DESC
            LIMIT 1
            """,
            (simulation_id,)
        ).fetchone()

        if not result:
            return None

        return SimulationCheckpointRecord(**dict(result))

    def delete_checkpoint(self, checkpoint_id: str) -> None:
        """Delete checkpoint (use with caution)."""
        cursor = self.db.conn.cursor()
        cursor.execute(
            "DELETE FROM simulation_checkpoints WHERE checkpoint_id = ?",
            (checkpoint_id,)
        )
```

#### Layer 4: API Endpoints (api/payment_simulator/api/main.py)

```python
@router.post("/simulations/{simulation_id}/checkpoint")
async def save_checkpoint(
    simulation_id: str,
    request: CheckpointRequest,
    checkpoint_mgr: CheckpointManager = Depends(get_checkpoint_manager),
) -> CheckpointResponse:
    """Save current simulation state to database.

    Request body:
        {
            "checkpoint_type": "manual",
            "description": "Before policy change"
        }
    """
    # Get active simulation
    if simulation_id not in sim_manager.simulations:
        raise HTTPException(404, "Simulation not found")

    orchestrator = sim_manager.simulations[simulation_id]

    # Save state (async to avoid blocking)
    state_json = await asyncio.get_event_loop().run_in_executor(
        None,
        orchestrator.save_state
    )

    # Persist to database
    checkpoint_id = checkpoint_mgr.save_checkpoint(
        simulation_id=simulation_id,
        state_json=state_json,
        checkpoint_type=request.checkpoint_type,
        description=request.description,
        created_by="api",
    )

    # Get metadata
    checkpoint = checkpoint_mgr.load_checkpoint(checkpoint_id)

    return CheckpointResponse(
        checkpoint_id=checkpoint_id,
        simulation_id=simulation_id,
        checkpoint_tick=checkpoint.checkpoint_tick,
        checkpoint_day=checkpoint.checkpoint_day,
        checkpoint_timestamp=checkpoint.checkpoint_timestamp,
        size_bytes=checkpoint.total_size_bytes,
    )


@router.post("/simulations/from-checkpoint")
async def create_from_checkpoint(
    request: LoadCheckpointRequest,
    checkpoint_mgr: CheckpointManager = Depends(get_checkpoint_manager),
) -> CreateSimulationResponse:
    """Create new simulation from saved checkpoint.

    Request body:
        {
            "checkpoint_id": "uuid-here",
            "new_simulation_id": "optional-custom-id"
        }
    """
    # Load checkpoint from database
    checkpoint = checkpoint_mgr.load_checkpoint(request.checkpoint_id)

    # Get original config
    original_sim = sim_manager.configs.get(checkpoint.simulation_id)
    if not original_sim:
        raise HTTPException(404, "Original simulation config not found")

    # Create new orchestrator from checkpoint
    new_sim_id = request.new_simulation_id or str(uuid.uuid4())

    orchestrator = await asyncio.get_event_loop().run_in_executor(
        None,
        Orchestrator.load_state,
        original_sim,
        checkpoint.state_json
    )

    # Register in manager
    sim_manager.simulations[new_sim_id] = orchestrator
    sim_manager.configs[new_sim_id] = original_sim

    return CreateSimulationResponse(
        simulation_id=new_sim_id,
        status="ready",
        current_tick=checkpoint.checkpoint_tick,
        current_day=checkpoint.checkpoint_day,
        message=f"Restored from checkpoint {request.checkpoint_id}",
    )


@router.get("/simulations/{simulation_id}/checkpoints")
async def list_checkpoints(
    simulation_id: str,
    checkpoint_mgr: CheckpointManager = Depends(get_checkpoint_manager),
) -> ListCheckpointsResponse:
    """List all checkpoints for a simulation."""
    checkpoints = checkpoint_mgr.list_checkpoints(simulation_id=simulation_id)

    return ListCheckpointsResponse(
        simulation_id=simulation_id,
        checkpoints=[
            CheckpointSummary(
                checkpoint_id=c.checkpoint_id,
                checkpoint_tick=c.checkpoint_tick,
                checkpoint_day=c.checkpoint_day,
                checkpoint_timestamp=c.checkpoint_timestamp,
                checkpoint_type=c.checkpoint_type,
                description=c.description,
                size_bytes=c.total_size_bytes,
            )
            for c in checkpoints
        ],
        total_count=len(checkpoints),
    )
```

#### Layer 5: CLI Commands (NEW)

**File**: `api/payment_simulator/cli/checkpoint.py` (NEW)

```python
import click
from pathlib import Path

@click.group()
def checkpoint():
    """Checkpoint management commands."""
    pass


@checkpoint.command()
@click.option("--simulation-id", required=True, help="Simulation ID to save")
@click.option("--description", help="Checkpoint description")
def save(simulation_id: str, description: str):
    """Save running simulation to database."""
    # Connect to running simulation (via IPC or shared memory)
    # Or read from environment variable

    orchestrator = get_active_simulation(simulation_id)
    state_json = orchestrator.save_state()

    checkpoint_mgr = get_checkpoint_manager()
    checkpoint_id = checkpoint_mgr.save_checkpoint(
        simulation_id=simulation_id,
        state_json=state_json,
        checkpoint_type=CheckpointType.MANUAL,
        description=description,
        created_by="cli",
    )

    click.echo(f"✅ Checkpoint saved: {checkpoint_id}")
    click.echo(f"   Tick: {orchestrator.current_tick()}")
    click.echo(f"   Day: {orchestrator.current_day()}")


@checkpoint.command()
@click.option("--checkpoint-id", required=True, help="Checkpoint to load")
def load(checkpoint_id: str):
    """Load and resume simulation from checkpoint."""
    checkpoint_mgr = get_checkpoint_manager()
    checkpoint = checkpoint_mgr.load_checkpoint(checkpoint_id)

    # Get original config
    config = get_simulation_config(checkpoint.simulation_id)

    # Restore orchestrator
    orchestrator = Orchestrator.load_state(config, checkpoint.state_json)

    click.echo(f"✅ Simulation restored from checkpoint")
    click.echo(f"   Simulation ID: {checkpoint.simulation_id}")
    click.echo(f"   Tick: {checkpoint.checkpoint_tick}")
    click.echo(f"   Day: {checkpoint.checkpoint_day}")

    # Continue running
    click.echo("\nResuming simulation...")
    run_simulation_interactive(orchestrator, checkpoint.simulation_id)


@checkpoint.command()
@click.option("--simulation-id", help="Filter by simulation ID")
def list(simulation_id: str):
    """List available checkpoints."""
    checkpoint_mgr = get_checkpoint_manager()
    checkpoints = checkpoint_mgr.list_checkpoints(simulation_id=simulation_id)

    if not checkpoints:
        click.echo("No checkpoints found")
        return

    click.echo(f"\n{'Checkpoint ID':<36}  {'Sim ID':<36}  {'Day':<4}  {'Tick':<6}  {'Type':<10}  {'Timestamp'}")
    click.echo("-" * 140)

    for c in checkpoints:
        click.echo(
            f"{c.checkpoint_id:<36}  "
            f"{c.simulation_id:<36}  "
            f"{c.checkpoint_day:<4}  "
            f"{c.checkpoint_tick:<6}  "
            f"{c.checkpoint_type.value:<10}  "
            f"{c.checkpoint_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        )
```

---

## TDD Implementation Plan

### Phase 1: Rust Core (Serialization/Deserialization)

#### Test File: `backend/tests/test_checkpoint.rs` (NEW)

```rust
#[cfg(test)]
mod tests {
    use super::*;

    // ============ Unit Tests ============

    #[test]
    fn test_save_state_returns_valid_json() {
        let orchestrator = create_test_orchestrator();
        let state_json = orchestrator.save_state().unwrap();

        // Should be valid JSON
        let parsed: serde_json::Value = serde_json::from_str(&state_json).unwrap();
        assert!(parsed.is_object());
    }

    #[test]
    fn test_save_state_includes_all_required_fields() {
        let orchestrator = create_test_orchestrator();
        let state_json = orchestrator.save_state().unwrap();
        let parsed: serde_json::Value = serde_json::from_str(&state_json).unwrap();

        // Required fields
        assert!(parsed["current_tick"].is_number());
        assert!(parsed["current_day"].is_number());
        assert!(parsed["rng_seed"].is_number());
        assert!(parsed["agents"].is_array());
        assert!(parsed["transactions"].is_array());
        assert!(parsed["rtgs_queue"].is_array());
        assert!(parsed["config_hash"].is_string());
    }

    #[test]
    fn test_load_state_restores_exact_state() {
        let mut original = create_test_orchestrator();

        // Run a few ticks
        for _ in 0..10 {
            original.tick().unwrap();
        }

        // Save state
        let config = original.config.clone();
        let state_json = original.save_state().unwrap();

        // Load state
        let restored = Orchestrator::load_state(config, &state_json).unwrap();

        // Verify exact match
        assert_eq!(restored.current_tick(), original.current_tick());
        assert_eq!(restored.current_day(), original.current_day());
        assert_eq!(restored.rng_seed(), original.rng_seed());
        assert_eq!(restored.num_agents(), original.num_agents());
        assert_eq!(restored.num_transactions(), original.num_transactions());
    }

    #[test]
    fn test_determinism_after_restore() {
        let mut sim1 = create_test_orchestrator();

        // Run 50 ticks
        for _ in 0..50 {
            sim1.tick().unwrap();
        }

        // Save state
        let config = sim1.config.clone();
        let state_json = sim1.save_state().unwrap();

        // Continue sim1 for 50 more ticks
        let mut results1 = Vec::new();
        for _ in 0..50 {
            let result = sim1.tick().unwrap();
            results1.push((
                result.num_arrivals,
                result.num_settlements,
                result.queue1_size,
            ));
        }

        // Restore sim2 from checkpoint
        let mut sim2 = Orchestrator::load_state(config, &state_json).unwrap();

        // Run sim2 for 50 ticks (same as continuation)
        let mut results2 = Vec::new();
        for _ in 0..50 {
            let result = sim2.tick().unwrap();
            results2.push((
                result.num_arrivals,
                result.num_settlements,
                result.queue1_size,
            ));
        }

        // Results must be IDENTICAL (determinism test)
        assert_eq!(results1, results2);
    }

    #[test]
    fn test_balance_conservation_preserved() {
        let mut orchestrator = create_test_orchestrator();

        // Initial total balance
        let initial_balance = orchestrator.total_system_balance();

        // Run simulation
        for _ in 0..100 {
            orchestrator.tick().unwrap();
        }

        // Save and restore
        let config = orchestrator.config.clone();
        let state_json = orchestrator.save_state().unwrap();
        let restored = Orchestrator::load_state(config, &state_json).unwrap();

        // Balance must be conserved
        assert_eq!(restored.total_system_balance(), initial_balance);
    }

    #[test]
    fn test_queue_integrity_preserved() {
        let mut orchestrator = create_test_orchestrator_with_queued_transactions();

        // Save state with items in queues
        let config = orchestrator.config.clone();
        let state_json = orchestrator.save_state().unwrap();

        // Restore
        let restored = Orchestrator::load_state(config, &state_json).unwrap();

        // All queued transactions must exist in transaction map
        for agent_id in restored.agent_ids() {
            let queue1 = restored.get_agent_queue1(&agent_id).unwrap();
            for tx_id in queue1 {
                assert!(restored.get_transaction(tx_id).is_some());
            }
        }

        let queue2 = restored.get_rtgs_queue();
        for tx_id in queue2 {
            assert!(restored.get_transaction(tx_id).is_some());
        }
    }

    #[test]
    fn test_config_mismatch_rejected() {
        let mut orchestrator = create_test_orchestrator();
        orchestrator.tick().unwrap();

        let state_json = orchestrator.save_state().unwrap();

        // Different config
        let different_config = create_test_orchestrator_config_with_different_params();

        // Should fail to load
        let result = Orchestrator::load_state(different_config, &state_json);
        assert!(result.is_err());
        assert!(matches!(result.unwrap_err(), OrchestratorError::ConfigMismatch { .. }));
    }

    #[test]
    fn test_corrupted_state_json_rejected() {
        let config = create_test_orchestrator_config();
        let corrupted_json = r#"{"current_tick": "invalid"}"#;

        let result = Orchestrator::load_state(config, corrupted_json);
        assert!(result.is_err());
    }

    #[test]
    fn test_orphaned_transaction_detected() {
        // Manually construct invalid state with orphaned queue entry
        let mut state_json = create_valid_state_json();

        // Add tx_id to queue1 that doesn't exist in transactions
        // (requires manual JSON manipulation)

        let result = Orchestrator::load_state(config, &state_json);
        assert!(result.is_err());
        assert!(matches!(
            result.unwrap_err(),
            OrchestratorError::OrphanedQueueTransaction { .. }
        ));
    }

    // ============ Property Tests ============

    #[test]
    fn test_save_load_roundtrip_preserves_state() {
        // Run property test with random seeds
        for seed in [42, 123, 999, 54321] {
            let mut original = create_test_orchestrator_with_seed(seed);

            // Random number of ticks
            let num_ticks = (seed % 100) + 1;
            for _ in 0..num_ticks {
                original.tick().unwrap();
            }

            // Save and restore
            let config = original.config.clone();
            let state_json = original.save_state().unwrap();
            let restored = Orchestrator::load_state(config, &state_json).unwrap();

            // Continue both for same number of ticks
            for _ in 0..50 {
                let r1 = original.tick().unwrap();
                let r2 = restored.tick().unwrap();
                assert_eq!(r1, r2);
            }
        }
    }
}
```

### Phase 2: FFI Boundary Tests

#### Test File: `api/tests/integration/test_checkpoint_ffi.py` (NEW)

```python
import pytest
import json
from payment_simulator.backends.rust import Orchestrator

def test_ffi_save_state_returns_valid_json():
    """FFI save_state() returns valid JSON string."""
    config = create_minimal_test_config()
    orch = Orchestrator.new(config)

    state_json = orch.save_state()

    # Should be valid JSON
    state = json.loads(state_json)
    assert isinstance(state, dict)
    assert "current_tick" in state
    assert "agents" in state

def test_ffi_load_state_restores_orchestrator():
    """FFI load_state() creates functioning orchestrator."""
    config = create_minimal_test_config()
    orch1 = Orchestrator.new(config)

    # Run some ticks
    for _ in range(10):
        orch1.tick()

    # Save state
    state_json = orch1.save_state()

    # Restore
    orch2 = Orchestrator.load_state(config, state_json)

    # Should be at same position
    assert orch2.current_tick() == orch1.current_tick()
    assert orch2.current_day() == orch1.current_day()

def test_ffi_determinism_preserved_across_checkpoint():
    """Restored simulation produces identical results."""
    config = create_test_config_with_arrivals()
    orch1 = Orchestrator.new(config)

    # Run to checkpoint
    for _ in range(50):
        orch1.tick()

    # Save
    state_json = orch1.save_state()

    # Continue original
    results1 = [orch1.tick() for _ in range(50)]

    # Restore and run
    orch2 = Orchestrator.load_state(config, state_json)
    results2 = [orch2.tick() for _ in range(50)]

    # Must be identical
    assert results1 == results2

def test_ffi_checkpoint_info_matches_state():
    """get_checkpoint_info() returns correct metadata."""
    config = create_test_config()
    orch = Orchestrator.new(config)

    for _ in range(25):
        orch.tick()

    info = orch.get_checkpoint_info()
    state_json = orch.save_state()
    state = json.loads(state_json)

    assert info["current_tick"] == state["current_tick"]
    assert info["current_day"] == state["current_day"]
    assert info["num_agents"] == len(state["agents"])

def test_ffi_error_on_config_mismatch():
    """load_state() raises error if config doesn't match."""
    config1 = create_test_config()
    orch1 = Orchestrator.new(config1)
    orch1.tick()

    state_json = orch1.save_state()

    # Different config
    config2 = create_test_config_with_different_agents()

    with pytest.raises(RuntimeError, match="ConfigMismatch"):
        Orchestrator.load_state(config2, state_json)
```

### Phase 3: Database Layer Tests

#### Test File: `api/tests/integration/test_checkpoint_persistence.py` (NEW)

```python
import pytest
from payment_simulator.persistence.checkpoint import CheckpointManager
from payment_simulator.persistence.models import CheckpointType

def test_save_checkpoint_creates_record(db_manager, checkpoint_manager):
    """save_checkpoint() persists to database."""
    state_json = create_mock_state_json()

    checkpoint_id = checkpoint_manager.save_checkpoint(
        simulation_id="sim-123",
        state_json=state_json,
        checkpoint_type=CheckpointType.MANUAL,
        description="Test checkpoint",
        created_by="test",
    )

    assert checkpoint_id is not None

    # Verify in database
    loaded = checkpoint_manager.load_checkpoint(checkpoint_id)
    assert loaded.simulation_id == "sim-123"
    assert loaded.state_json == state_json
    assert loaded.checkpoint_type == CheckpointType.MANUAL

def test_load_checkpoint_verifies_integrity(checkpoint_manager):
    """load_checkpoint() detects corrupted data."""
    # Save checkpoint
    checkpoint_id = checkpoint_manager.save_checkpoint(
        simulation_id="sim-123",
        state_json='{"current_tick": 100}',
        checkpoint_type=CheckpointType.MANUAL,
    )

    # Manually corrupt in database
    with checkpoint_manager.db.conn.cursor() as cursor:
        cursor.execute(
            "UPDATE simulation_checkpoints SET state_json = ? WHERE checkpoint_id = ?",
            ('{"current_tick": 999}', checkpoint_id)
        )

    # Should raise integrity error
    with pytest.raises(ValueError, match="corrupted"):
        checkpoint_manager.load_checkpoint(checkpoint_id)

def test_list_checkpoints_filters_by_simulation(checkpoint_manager):
    """list_checkpoints() returns only matching simulation."""
    # Create checkpoints for different simulations
    checkpoint_manager.save_checkpoint("sim-A", '{"tick": 1}', CheckpointType.MANUAL)
    checkpoint_manager.save_checkpoint("sim-A", '{"tick": 2}', CheckpointType.MANUAL)
    checkpoint_manager.save_checkpoint("sim-B", '{"tick": 1}', CheckpointType.MANUAL)

    checkpoints = checkpoint_manager.list_checkpoints(simulation_id="sim-A")

    assert len(checkpoints) == 2
    assert all(c.simulation_id == "sim-A" for c in checkpoints)

def test_get_latest_checkpoint_returns_most_recent(checkpoint_manager):
    """get_latest_checkpoint() returns newest."""
    import time

    # Create multiple checkpoints with delays
    checkpoint_manager.save_checkpoint("sim-123", '{"tick": 1}', CheckpointType.MANUAL)
    time.sleep(0.1)
    checkpoint_manager.save_checkpoint("sim-123", '{"tick": 2}', CheckpointType.MANUAL)
    time.sleep(0.1)
    latest_id = checkpoint_manager.save_checkpoint(
        "sim-123", '{"tick": 3}', CheckpointType.MANUAL
    )

    latest = checkpoint_manager.get_latest_checkpoint("sim-123")

    assert latest.checkpoint_id == latest_id
```

### Phase 4: API Endpoint Tests

#### Test File: `api/tests/e2e/test_checkpoint_api.py` (NEW)

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_save_checkpoint_endpoint(client: AsyncClient, running_simulation):
    """POST /simulations/{id}/checkpoint saves state."""
    sim_id = running_simulation["simulation_id"]

    response = await client.post(
        f"/api/simulations/{sim_id}/checkpoint",
        json={
            "checkpoint_type": "manual",
            "description": "Test save"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "checkpoint_id" in data
    assert data["simulation_id"] == sim_id

@pytest.mark.asyncio
async def test_create_from_checkpoint_endpoint(client: AsyncClient, saved_checkpoint):
    """POST /simulations/from-checkpoint creates new simulation."""
    checkpoint_id = saved_checkpoint["checkpoint_id"]

    response = await client.post(
        "/api/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id}
    )

    assert response.status_code == 200
    data = response.json()
    assert "simulation_id" in data
    assert data["current_tick"] == saved_checkpoint["checkpoint_tick"]

@pytest.mark.asyncio
async def test_restored_simulation_continues_correctly(client: AsyncClient):
    """Restored simulation produces correct results."""
    # Create initial simulation
    config = create_test_config()
    response = await client.post("/api/simulations", json=config)
    sim_id = response.json()["simulation_id"]

    # Run 50 ticks
    await client.post(f"/api/simulations/{sim_id}/run", json={"num_ticks": 50})

    # Save checkpoint
    checkpoint_response = await client.post(
        f"/api/simulations/{sim_id}/checkpoint",
        json={"checkpoint_type": "manual"}
    )
    checkpoint_id = checkpoint_response.json()["checkpoint_id"]

    # Continue original for 50 more ticks
    response1 = await client.post(
        f"/api/simulations/{sim_id}/run",
        json={"num_ticks": 50}
    )
    results1 = response1.json()

    # Restore and run 50 ticks
    restore_response = await client.post(
        "/api/simulations/from-checkpoint",
        json={"checkpoint_id": checkpoint_id}
    )
    new_sim_id = restore_response.json()["simulation_id"]

    response2 = await client.post(
        f"/api/simulations/{new_sim_id}/run",
        json={"num_ticks": 50}
    )
    results2 = response2.json()

    # Results must match (determinism)
    assert results1["final_tick"] == results2["final_tick"]
    # More detailed assertions...

@pytest.mark.asyncio
async def test_list_checkpoints_endpoint(client: AsyncClient, simulation_with_checkpoints):
    """GET /simulations/{id}/checkpoints returns list."""
    sim_id = simulation_with_checkpoints["simulation_id"]

    response = await client.get(f"/api/simulations/{sim_id}/checkpoints")

    assert response.status_code == 200
    data = response.json()
    assert "checkpoints" in data
    assert len(data["checkpoints"]) > 0
```

### Phase 5: CLI Tests

#### Test File: `api/tests/e2e/test_checkpoint_cli.py` (NEW)

```python
import pytest
from click.testing import CliRunner
from payment_simulator.cli.checkpoint import checkpoint

def test_cli_save_command(runner: CliRunner, active_simulation):
    """CLI save command persists checkpoint."""
    sim_id = active_simulation["simulation_id"]

    result = runner.invoke(checkpoint, [
        "save",
        "--simulation-id", sim_id,
        "--description", "CLI test save"
    ])

    assert result.exit_code == 0
    assert "Checkpoint saved" in result.output

def test_cli_load_command(runner: CliRunner, saved_checkpoint):
    """CLI load command restores simulation."""
    checkpoint_id = saved_checkpoint["checkpoint_id"]

    result = runner.invoke(checkpoint, [
        "load",
        "--checkpoint-id", checkpoint_id
    ])

    assert result.exit_code == 0
    assert "Simulation restored" in result.output

def test_cli_list_command(runner: CliRunner):
    """CLI list command shows checkpoints."""
    result = runner.invoke(checkpoint, ["list"])

    assert result.exit_code == 0
    # Should show table header
    assert "Checkpoint ID" in result.output
```

---

## Implementation Order (TDD Red-Green-Refactor)

### Sprint 1: Rust Core (Week 1)
1. ✅ Write failing Rust unit tests (test_checkpoint.rs)
2. ✅ Implement StateSnapshot structs with serde derives
3. ✅ Implement Orchestrator::save_state()
4. ✅ Implement Orchestrator::load_state()
5. ✅ Implement validation functions
6. ✅ All Rust tests pass (GREEN)

### Sprint 2: FFI Boundary (Week 1)
1. ✅ Write failing Python FFI tests
2. ✅ Implement PyOrchestrator::save_state()
3. ✅ Implement PyOrchestrator::load_state()
4. ✅ Implement PyOrchestrator::get_checkpoint_info()
5. ✅ All FFI tests pass (GREEN)

### Sprint 3: Database Layer (Week 2)
1. ✅ Add SimulationCheckpointRecord Pydantic model
2. ✅ Generate database schema
3. ✅ Write failing persistence tests
4. ✅ Implement CheckpointManager class
5. ✅ All persistence tests pass (GREEN)

### Sprint 4: API Layer (Week 2)
1. ✅ Write failing API endpoint tests
2. ✅ Implement POST /simulations/{id}/checkpoint
3. ✅ Implement POST /simulations/from-checkpoint
4. ✅ Implement GET /simulations/{id}/checkpoints
5. ✅ All API tests pass (GREEN)

### Sprint 5: CLI Layer (Week 3)
1. ✅ Write failing CLI tests
2. ✅ Implement checkpoint save command
3. ✅ Implement checkpoint load command
4. ✅ Implement checkpoint list command
5. ✅ All CLI tests pass (GREEN)

### Sprint 6: Integration & Documentation (Week 3)
1. ✅ End-to-end integration tests
2. ✅ Performance benchmarks (checkpoint size, save/load time)
3. ✅ Update documentation
4. ✅ Add examples to README
5. ✅ User acceptance testing

---

## Success Criteria

### Functional Requirements
- ✅ Simulation can be saved at any tick
- ✅ Saved simulation can be restored and continues correctly
- ✅ Determinism preserved (same seed → same results)
- ✅ Balance conservation maintained
- ✅ Queue integrity preserved
- ✅ Config mismatch detected and rejected
- ✅ Corrupted checkpoints detected

### Non-Functional Requirements
- ✅ Checkpoint save time < 100ms for typical simulation
- ✅ Checkpoint load time < 200ms
- ✅ Database size growth < 10MB per checkpoint
- ✅ No memory leaks across save/load cycles
- ✅ Thread-safe (concurrent checkpoint access)

### User Experience
- ✅ Clear error messages for failures
- ✅ Progress indicators for long operations
- ✅ Easy CLI commands for common workflows
- ✅ API documentation with examples

---

## Risk Mitigation

### Risk 1: Large State Size
**Problem**: Checkpoints may be too large for frequent saves
**Mitigation**:
- Use compression (gzip/zstd) for state_json
- Implement incremental/delta checkpoints (future)
- Monitor checkpoint sizes in tests

### Risk 2: Serialization Bugs
**Problem**: Subtle state corruption during save/load
**Mitigation**:
- Extensive validation in tests
- Property-based testing with random seeds
- Integrity hashes for all checkpoints
- Balance conservation checks

### Risk 3: FFI Memory Safety
**Problem**: Rust-Python boundary issues
**Mitigation**:
- Use `PyResult` for all FFI functions
- Validate all inputs at boundary
- No raw pointers across FFI
- Extensive integration tests

### Risk 4: Database Concurrency
**Problem**: Concurrent checkpoint access
**Mitigation**:
- DuckDB transactions for atomicity
- Row-level locking where needed
- Clear API documentation about concurrency

---

## Future Enhancements

1. **Incremental Checkpoints**: Save only changed state (delta encoding)
2. **Automatic Checkpointing**: Periodic auto-save during long runs
3. **Checkpoint Compression**: Reduce database size with zstd
4. **Checkpoint Branching**: Create alternative timelines from checkpoint
5. **Cloud Storage**: Upload checkpoints to S3/GCS for sharing
6. **Checkpoint Diffing**: Compare two checkpoints to see what changed

---

## Questions for Team

1. Should we support checkpoints across different software versions?
2. What's the expected frequency of checkpoint saves?
3. Do we need checkpoint expiration/cleanup?
4. Should checkpoints be exportable to JSON files?
5. Do we need checkpoint encryption for sensitive simulations?

---

*This plan follows TDD principles: write tests first, implement to pass tests, refactor for quality.*
