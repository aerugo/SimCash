# Phase 2: Schema Unification

**Status**: In Progress
**Started**: 2025-12-14
**Estimated Effort**: Medium
**Risk Level**: Medium (schema changes, multiple systems affected)

---

## Goal

Create a single unified database schema that supports both standalone simulations and experiments. After this phase:
- `DatabaseManager` creates ALL tables (simulation + experiment)
- `simulation_runs` has experiment linkage columns
- `ExperimentRepository` is refactored to use `DatabaseManager`

## Current State

### Simulation Schema (DatabaseManager)

Tables created via Pydantic models in `persistence/models.py`:
- `simulation_runs` - Core simulation metadata
- `transactions` - Transaction lifecycle
- `daily_agent_metrics` - Per-agent metrics
- `collateral_events` - Collateral actions
- `simulation_events` - Tick-level events (for replay)
- `policy_snapshots` - Policy configurations
- `simulation_checkpoints` - Save/load support
- `agent_state_registers` - Policy micro-memory
- Plus several more for full replay

### Experiment Schema (ExperimentRepository)

Tables created directly with SQL in `experiments/persistence/repository.py`:
- `experiments` - Experiment metadata
- `experiment_iterations` - Per-iteration costs/policies
- `experiment_events` - High-level experiment events

### Problem

These are **separate databases** with **no linkage**. Running an experiment creates its own database, and simulations within that experiment are not persisted to `simulation_runs` or `simulation_events`.

---

## Design

### New Unified Schema

#### 1. Add `experiments` table to DatabaseManager

```sql
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    experiment_type VARCHAR NOT NULL,
    config JSON NOT NULL,
    scenario_path VARCHAR,
    master_seed BIGINT,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    num_iterations INTEGER DEFAULT 0,
    converged BOOLEAN DEFAULT FALSE,
    convergence_reason VARCHAR,
    final_cost BIGINT,  -- INV-1: Integer cents
    best_cost BIGINT    -- INV-1: Integer cents
);
```

#### 2. Add `experiment_iterations` table to DatabaseManager

```sql
CREATE TABLE IF NOT EXISTS experiment_iterations (
    experiment_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    costs_per_agent JSON NOT NULL,
    accepted_changes JSON NOT NULL,
    policies JSON NOT NULL,
    timestamp VARCHAR NOT NULL,
    evaluation_simulation_id VARCHAR,  -- Link to simulation_runs
    PRIMARY KEY (experiment_id, iteration),
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);
```

#### 3. Add `experiment_events` table to DatabaseManager

```sql
CREATE TABLE IF NOT EXISTS experiment_events (
    id INTEGER PRIMARY KEY,
    experiment_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    event_type VARCHAR NOT NULL,
    event_data JSON NOT NULL,
    timestamp VARCHAR NOT NULL,
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);
```

#### 4. Extend `simulation_runs` with experiment linkage

Add columns:
- `experiment_id VARCHAR` - Link to experiments table
- `iteration INTEGER` - Which iteration this simulation belongs to
- `sample_index INTEGER` - Which bootstrap sample (for evaluation sims)
- `run_purpose VARCHAR` - 'standalone', 'initial', 'bootstrap', 'evaluation', 'best', 'final'

---

## TDD Approach

### Step 1: Write Tests for New Schema (RED)

Create tests that verify the unified schema:

```python
# tests/integration/test_unified_schema.py

class TestUnifiedSchemaCreation:
    """Tests for unified schema creation."""

    def test_experiments_table_created(self):
        """Verify experiments table is created by DatabaseManager."""
        # DatabaseManager creates experiments table

    def test_experiment_iterations_table_created(self):
        """Verify experiment_iterations table is created by DatabaseManager."""
        pass

    def test_experiment_events_table_created(self):
        """Verify experiment_events table is created by DatabaseManager."""
        pass

    def test_simulation_runs_has_experiment_columns(self):
        """Verify simulation_runs has experiment linkage columns."""
        # Check for experiment_id, iteration, sample_index, run_purpose
        pass


class TestExperimentSimulationLinkage:
    """Tests for experiment → simulation linking."""

    def test_simulation_can_reference_experiment(self):
        """Verify simulation_runs.experiment_id FK works."""
        pass

    def test_iteration_can_reference_simulation(self):
        """Verify experiment_iterations.evaluation_simulation_id FK works."""
        pass


class TestInvariantCompliance:
    """Tests for critical invariants."""

    def test_experiment_costs_are_integer_cents(self):
        """INV-1: All cost fields use BIGINT, not DOUBLE."""
        pass

    def test_seeds_are_stored_for_determinism(self):
        """INV-2: Master seed is stored in experiments table."""
        pass
```

### Step 2: Add Experiment Pydantic Models

Create new models in `persistence/models.py`:

```python
class ExperimentRecord(BaseModel):
    """Experiment metadata for persistence."""
    model_config = ConfigDict(table_name="experiments", ...)

    experiment_id: str
    experiment_name: str
    experiment_type: str
    config: str  # JSON string
    # ... etc

class ExperimentIterationRecord(BaseModel):
    """Experiment iteration for persistence."""
    model_config = ConfigDict(table_name="experiment_iterations", ...)

    experiment_id: str
    iteration: int
    costs_per_agent: str  # JSON string
    # ... etc

class ExperimentEventRecord(BaseModel):
    """Experiment event for persistence."""
    model_config = ConfigDict(table_name="experiment_events", ...)

    experiment_id: str
    iteration: int
    event_type: str
    event_data: str  # JSON string
    timestamp: str
```

### Step 3: Update SimulationRunRecord with Experiment Columns

Add to existing `SimulationRunRecord`:

```python
# New optional fields for experiment linkage
experiment_id: str | None = Field(None, description="Link to experiments table")
iteration: int | None = Field(None, description="Iteration number within experiment")
sample_index: int | None = Field(None, description="Bootstrap sample index")
run_purpose: str | None = Field(None, description="'standalone', 'initial', 'evaluation', etc.")
```

### Step 4: Update Schema Generator

Update `schema_generator.py` to include new models in DDL generation.

### Step 5: Refactor ExperimentRepository

Make `ExperimentRepository` use `DatabaseManager` instead of creating its own connection:

```python
class ExperimentRepository:
    def __init__(self, db_manager: DatabaseManager) -> None:
        """Initialize with existing DatabaseManager."""
        self._manager = db_manager
        self._conn = db_manager.conn
        # No schema creation - DatabaseManager handles it

    # ... rest of methods unchanged, just use self._conn
```

### Step 6: Run Tests (GREEN)

Verify all tests pass with the new unified schema.

---

## Sub-Phase Checklist

- [ ] **2.1** Write tests for unified schema (RED)
- [ ] **2.2** Create Pydantic models for experiments, iterations, events
- [ ] **2.3** Add experiment linkage columns to SimulationRunRecord
- [ ] **2.4** Update schema_generator.py to include new models
- [ ] **2.5** Update DatabaseManager to validate new tables
- [ ] **2.6** Refactor ExperimentRepository to use DatabaseManager
- [ ] **2.7** Update GameRepository to use DatabaseManager (if still needed)
- [ ] **2.8** Run full test suite
- [ ] **2.9** Run mypy and ruff
- [ ] **2.10** Update work_notes.md

---

## Files to Modify

| File | Changes |
|------|---------|
| `persistence/models.py` | Add ExperimentRecord, ExperimentIterationRecord, ExperimentEventRecord |
| `persistence/models.py` | Add experiment columns to SimulationRunRecord |
| `persistence/schema_generator.py` | Include new models in DDL generation |
| `persistence/connection.py` | Update validate_schema() to include new tables |
| `experiments/persistence/repository.py` | Refactor to use DatabaseManager |
| `tests/integration/test_unified_schema.py` | New test file |

## Files to Create

| File | Purpose |
|------|---------|
| `api/tests/integration/test_unified_schema.py` | Schema unification tests |

---

## Acceptance Criteria

- [ ] `experiments` table created by DatabaseManager
- [ ] `experiment_iterations` table created by DatabaseManager
- [ ] `experiment_events` table created by DatabaseManager
- [ ] `simulation_runs` has `experiment_id`, `iteration`, `sample_index`, `run_purpose` columns
- [ ] ExperimentRepository works with DatabaseManager connection
- [ ] All existing tests pass
- [ ] New schema tests pass
- [ ] mypy passes
- [ ] ruff passes

---

## Migration Note

Since we decided on **no backwards compatibility**, existing experiment databases will NOT work with the new schema. Users must create new databases.

---

## Risks

1. **Breaking existing experiments**: Mitigated by clean slate decision
2. **FK constraint issues**: Test thoroughly with linked data
3. **JSON field compatibility**: Ensure consistent JSON handling across both systems
