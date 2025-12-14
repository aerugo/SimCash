# Unified Database Architecture Exploration

## Problem Statement

SimCash currently has **three separate database schemas**:

1. **Simulation Database** - 14 tables, per-tick/per-transaction granularity
2. **Experiment Database** - 3 tables, per-iteration aggregates
3. **Castro (AI Cash Mgmt) Database** - 5 tables, LLM audit trails

This fragmentation causes:
- `payment-sim db simulations` fails on experiment databases
- `payment-sim replay <sim_id>` cannot inspect simulations run within experiments
- No way to drill down from experiment iteration → simulation events
- Duplicated schema definitions and persistence logic
- Inconsistent CLI experience

## Goal

Create a **single unified database schema** where:
- ALL CLI commands work on ANY database
- Experiments link to their constituent simulation runs
- Users can replay any simulation with full event detail
- Storage remains efficient (selective persistence)

---

## Current Architecture

### Simulation Database (14 tables)

```
simulation_runs (PK: simulation_id)
├── simulation_events     # Tick-level events (RTGS, LSM, queue, etc.)
├── transactions          # Transaction lifecycle
├── daily_agent_metrics   # Per-agent, per-day metrics
├── collateral_events     # Collateral post/withdraw actions
├── policy_snapshots      # Policy configuration history
├── simulation_checkpoints # Save/load functionality
├── agent_queue_snapshots # Queue contents at EOD
├── policy_decisions      # Every policy decision
├── tick_agent_states     # Per-tick agent snapshots
├── tick_queue_snapshots  # Per-tick queue snapshots
├── lsm_cycles           # LSM settlement tracking
└── agent_state_registers # Policy micro-memory
```

**Created by**: `payment-sim run --persist <db>`

### Experiment Database (3 tables)

```
experiments (PK: run_id)
├── experiment_iterations  # Per-iteration costs, policies
└── experiment_events      # High-level events (iteration_start, etc.)
```

**Created by**: `payment-sim experiment run <config> --db <db>`

### Key Difference

| Aspect | Simulation DB | Experiment DB |
|--------|--------------|---------------|
| Granularity | Per-tick, per-transaction | Per-iteration |
| Simulation events | Full detail | **Not stored** |
| Replay support | Complete | Iteration-level only |
| Typical size | 10-100 MB per run | <1 MB per experiment |

---

## Design Challenges

### 1. Data Volume

An experiment with:
- 50 iterations
- 10 bootstrap samples per iteration
- 500 simulations total

Would generate **massive** event data if we stored everything:
- ~10,000 events per simulation (300 ticks × 30+ events/tick)
- 5,000,000 total events per experiment
- Storage: 500 MB - 2 GB per experiment

### 2. Identifier Relationships

Currently no way to link:
- `experiments.run_id` → `simulation_runs.simulation_id`
- `experiment_iterations.iteration` → specific simulation run

### 3. Selective Persistence

Need to balance:
- **Debuggability**: Drill into any simulation
- **Storage efficiency**: Don't store everything
- **Determinism**: Ability to re-run any simulation exactly

---

## Proposed Unified Schema

### Core Principle: Hierarchical Containment

```
experiments (optional container)
└── simulation_runs (can exist standalone or within experiment)
    └── simulation_events (detailed tick-by-tick data)
```

### Schema Changes

#### 1. Extend `simulation_runs` with experiment linkage

```sql
ALTER TABLE simulation_runs ADD COLUMN experiment_id VARCHAR;
ALTER TABLE simulation_runs ADD COLUMN iteration INTEGER;
ALTER TABLE simulation_runs ADD COLUMN sample_index INTEGER;
ALTER TABLE simulation_runs ADD COLUMN run_purpose VARCHAR;  -- 'standalone', 'bootstrap', 'evaluation', 'final'

CREATE INDEX idx_sim_experiment ON simulation_runs(experiment_id);
```

#### 2. Add `experiments` table to simulation schema

```sql
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id VARCHAR PRIMARY KEY,
    experiment_name VARCHAR NOT NULL,
    experiment_type VARCHAR NOT NULL,  -- 'castro', 'generic', 'custom'
    config JSON NOT NULL,
    scenario_path VARCHAR,
    master_seed BIGINT,
    created_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    num_iterations INTEGER DEFAULT 0,
    converged BOOLEAN DEFAULT FALSE,
    convergence_reason VARCHAR,
    final_cost BIGINT,  -- Integer cents (INV-1)
    best_cost BIGINT    -- Integer cents (INV-1)
);
```

#### 3. Keep `experiment_iterations` for summary data

```sql
CREATE TABLE IF NOT EXISTS experiment_iterations (
    experiment_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    costs_per_agent JSON NOT NULL,
    accepted_changes JSON NOT NULL,
    policies JSON NOT NULL,
    timestamp VARCHAR NOT NULL,
    -- NEW: Links to simulation runs
    evaluation_simulation_id VARCHAR,  -- Main evaluation run
    bootstrap_simulation_ids JSON,     -- Array of simulation IDs
    PRIMARY KEY (experiment_id, iteration)
);
```

#### 4. Selective simulation persistence

Add a `persistence_level` to control what gets stored:

```python
class SimulationPersistenceLevel(Enum):
    NONE = "none"           # No persistence (fast evaluation)
    SUMMARY = "summary"     # Just simulation_runs + daily_agent_metrics
    EVENTS = "events"       # + simulation_events (for replay)
    FULL = "full"           # + tick_agent_states, tick_queue_snapshots (full replay)
```

---

## Implementation Strategy

### Phase 1: Schema Unification

1. Add `experiments` table to the standard simulation schema
2. Add `experiment_id`, `iteration`, `sample_index` columns to `simulation_runs`
3. Update `DatabaseManager.initialize_schema()` to create both
4. Migrate `ExperimentRepository` to use unified schema

### Phase 2: Experiment → Simulation Linking

1. Modify `OptimizationLoop._run_simulation_with_events()` to:
   - Generate unique `simulation_id` for each simulation
   - Persist `simulation_runs` entry with experiment linkage
   - Optionally persist `simulation_events` based on persistence level

2. Add persistence level configuration:
   ```yaml
   # experiment.yaml
   output:
     database: results/exp.db
     persistence_level: events  # none, summary, events, full
     persist_simulations:
       - initial      # First simulation
       - best         # Best cost so far
       - worst        # Worst cost (for debugging)
       - final        # Final evaluation
   ```

### Phase 3: Unified CLI Commands

1. `payment-sim db simulations --db <path>`:
   - Query both standalone runs AND experiment-linked runs
   - Show experiment context when applicable

2. `payment-sim db experiments --db <path>`:
   - List all experiments
   - Show linked simulation counts

3. `payment-sim replay <id> --db <path>`:
   - Works for both standalone simulations and experiment simulations
   - Auto-detects simulation vs experiment ID

4. `payment-sim experiment replay <id> --db <path>`:
   - Show iteration-level summary (existing)
   - NEW: `--simulation <iter>.<sample>` to drill into specific simulation

### Phase 4: Smart Persistence Policies

Implement intelligent defaults:

```python
def should_persist_simulation(
    iteration: int,
    sample_index: int,
    is_best: bool,
    is_worst: bool,
    is_final: bool,
    policy: PersistencePolicy
) -> SimulationPersistenceLevel:
    """Determine persistence level for a simulation within an experiment."""

    if policy == PersistencePolicy.ALL:
        return SimulationPersistenceLevel.EVENTS

    if policy == PersistencePolicy.SMART:
        # Always persist key simulations
        if iteration == 0 and sample_index == 0:
            return SimulationPersistenceLevel.EVENTS  # Initial
        if is_best:
            return SimulationPersistenceLevel.EVENTS  # Best so far
        if is_final:
            return SimulationPersistenceLevel.EVENTS  # Final evaluation
        # Summary for others
        return SimulationPersistenceLevel.SUMMARY

    return SimulationPersistenceLevel.NONE
```

---

## Unified Query Examples

### List all simulations (standalone + experiment)

```sql
SELECT
    sr.simulation_id,
    sr.config_name,
    sr.status,
    sr.start_time,
    e.experiment_name,
    sr.iteration,
    sr.sample_index,
    sr.run_purpose
FROM simulation_runs sr
LEFT JOIN experiments e ON sr.experiment_id = e.experiment_id
ORDER BY sr.start_time DESC
```

### Get replayable simulations from an experiment

```sql
SELECT
    sr.simulation_id,
    sr.iteration,
    sr.sample_index,
    sr.run_purpose,
    (SELECT COUNT(*) FROM simulation_events se
     WHERE se.simulation_id = sr.simulation_id) as event_count
FROM simulation_runs sr
WHERE sr.experiment_id = ?
  AND sr.simulation_id IN (
      SELECT DISTINCT simulation_id FROM simulation_events
  )
ORDER BY sr.iteration, sr.sample_index
```

### Drill down: experiment → iteration → simulation → events

```sql
-- 1. Find experiment
SELECT * FROM experiments WHERE experiment_id = 'exp2-20251214-011720-cd2e23';

-- 2. Find iterations
SELECT iteration, costs_per_agent, evaluation_simulation_id
FROM experiment_iterations
WHERE experiment_id = 'exp2-20251214-011720-cd2e23';

-- 3. Get simulation events for iteration 5
SELECT se.*
FROM simulation_events se
JOIN simulation_runs sr ON se.simulation_id = sr.simulation_id
WHERE sr.experiment_id = 'exp2-20251214-011720-cd2e23'
  AND sr.iteration = 5
  AND sr.run_purpose = 'evaluation'
ORDER BY se.tick;
```

---

## CLI UX Design

### Listing

```bash
# List everything
$ payment-sim db list --db results/exp2.db

Experiments: 3
  exp2-20251214-011720-cd2e23  |  castro  |  50 iterations  |  converged
  exp1-20251213-143022-a1b2c3  |  castro  |  25 iterations  |  max_iterations

Standalone Simulations: 2
  sim-20251214-120000-xyz  |  scenario.yaml  |  completed

Experiment Simulations: 12 (replayable)
  Use: payment-sim db simulations --db results/exp2.db --experiment exp2-...

# List simulations with experiment context
$ payment-sim db simulations --db results/exp2.db

ID                              | Experiment        | Iter | Purpose    | Events
--------------------------------|-------------------|------|------------|-------
sim-exp2-iter0-eval-abc123      | exp2-2025...      | 0    | initial    | 8,432
sim-exp2-iter5-eval-def456      | exp2-2025...      | 5    | best       | 9,102
sim-exp2-iter49-eval-ghi789     | exp2-2025...      | 49   | final      | 8,876
sim-standalone-xyz              | -                 | -    | standalone | 12,450
```

### Replay

```bash
# Replay standalone simulation (existing)
$ payment-sim replay sim-standalone-xyz --db results/exp2.db --verbose

# Replay experiment simulation (NEW)
$ payment-sim replay sim-exp2-iter5-eval-def456 --db results/exp2.db --verbose

# Shorthand: replay by experiment + iteration
$ payment-sim experiment replay exp2-20251214-011720-cd2e23 --db results/exp2.db \
    --simulation iter5:eval --verbose
```

---

## Migration Path

### Existing Databases

1. Experiment DBs without simulation linkage continue to work
2. Add migration to add new columns (nullable)
3. New experiments use unified schema automatically

### Code Changes

1. `ExperimentRepository` → becomes thin wrapper over `DatabaseManager`
2. `OptimizationLoop` → uses `PersistenceManager` for simulation persistence
3. `replay.py` → unified logic for both simulation and experiment replay

---

## Storage Estimates

| Persistence Level | Per Simulation | 500 Simulations |
|-------------------|----------------|-----------------|
| NONE              | 0 KB           | 0 KB            |
| SUMMARY           | 5 KB           | 2.5 MB          |
| EVENTS            | 500 KB         | 250 MB          |
| FULL              | 2 MB           | 1 GB            |

With SMART policy (initial + best + final only):
- ~10 simulations with EVENTS = 5 MB
- ~490 simulations with SUMMARY = 2.5 MB
- **Total: ~8 MB per experiment** (vs 250 MB for all)

---

## Open Questions

1. **Backwards compatibility**: How to handle old experiment databases?
   - Option A: Read-only support, no migration
   - Option B: One-time migration script

2. **Simulation ID format**: Should experiment simulations have structured IDs?
   - Current: `sim-20251214-120000-xyz` (random)
   - Proposed: `exp2-iter5-sample0-eval` (structured)

3. **Castro integration**: Merge Castro tables into unified schema?
   - `llm_interaction_log`, `policy_diffs`, `iteration_context`
   - These are LLM-specific, maybe keep separate?

4. **Deterministic re-run**: If events aren't persisted, can we re-run exactly?
   - Need: scenario config + policies + seed
   - Store in `experiment_iterations.policies` (already done)

---

## Next Steps

1. [ ] Review this proposal with stakeholders
2. [ ] Decide on persistence policy defaults
3. [ ] Implement Phase 1: Schema unification
4. [ ] Implement Phase 2: Experiment → Simulation linking
5. [ ] Implement Phase 3: Unified CLI commands
6. [ ] Write migration for existing databases

---

## Appendix: Full Unified Schema

```sql
-- =============================================================================
-- EXPERIMENTS (Container for optimization runs)
-- =============================================================================
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
    final_cost BIGINT,
    best_cost BIGINT
);

-- =============================================================================
-- EXPERIMENT ITERATIONS (Per-iteration summary)
-- =============================================================================
CREATE TABLE IF NOT EXISTS experiment_iterations (
    experiment_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    costs_per_agent JSON NOT NULL,
    accepted_changes JSON NOT NULL,
    policies JSON NOT NULL,
    timestamp VARCHAR NOT NULL,
    evaluation_simulation_id VARCHAR,
    bootstrap_simulation_ids JSON,
    PRIMARY KEY (experiment_id, iteration),
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

-- =============================================================================
-- SIMULATION RUNS (Extended with experiment linkage)
-- =============================================================================
CREATE TABLE IF NOT EXISTS simulation_runs (
    simulation_id VARCHAR PRIMARY KEY,
    config_name VARCHAR,
    config_hash VARCHAR,
    rng_seed BIGINT,
    ticks_per_day INTEGER,
    num_days INTEGER,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR,
    total_transactions INTEGER,
    config_json JSON,
    -- NEW: Experiment linkage
    experiment_id VARCHAR,
    iteration INTEGER,
    sample_index INTEGER,
    run_purpose VARCHAR,  -- 'standalone', 'initial', 'bootstrap', 'evaluation', 'best', 'final'
    persistence_level VARCHAR,  -- 'none', 'summary', 'events', 'full'
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);

-- =============================================================================
-- SIMULATION EVENTS (Unchanged - core replay data)
-- =============================================================================
CREATE TABLE IF NOT EXISTS simulation_events (
    event_id INTEGER PRIMARY KEY,
    simulation_id VARCHAR NOT NULL,
    tick INTEGER NOT NULL,
    day INTEGER,
    event_type VARCHAR NOT NULL,
    details JSON,
    agent_id VARCHAR,
    tx_id VARCHAR,
    FOREIGN KEY (simulation_id) REFERENCES simulation_runs(simulation_id)
);

-- ... (rest of simulation tables unchanged)
```
