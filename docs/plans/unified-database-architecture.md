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

## Design Decisions (Confirmed)

1. **No backwards compatibility** - Clean slate, no migration of old databases
2. **Structured simulation IDs** - Format: `{experiment_id}-iter{N}-{purpose}` for traceability
3. **Castro audit tables are dead code** - See analysis below
4. **Default persistence policy** - Full tick-level snapshots, no bootstrap sample transactions

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

### Castro Audit Tables Analysis

The `ai_cash_mgmt` module defines 5 tables, but **3 are effectively dead code**:

| Table | Defined In | Written To? | Status |
|-------|-----------|-------------|--------|
| `game_sessions` | `ai_cash_mgmt/persistence/` | Unknown | Legacy |
| `policy_iterations` | `ai_cash_mgmt/persistence/` | Unknown | Legacy |
| `llm_interaction_log` | `ai_cash_mgmt/persistence/` | **NO** | Dead code |
| `policy_diffs` | `ai_cash_mgmt/persistence/` | **NO** | Dead code |
| `iteration_context` | `ai_cash_mgmt/persistence/` | **NO** | Dead code |

**Why dead code?** The experiment framework (`experiments/runner/optimization.py`) saves LLM interactions as events in the `experiment_events` table via `_save_llm_interaction_event()`, which calls `self._repository.save_event(event)`. It does NOT use `GameRepository.save_llm_interaction()`.

**Recommendation**: Do not migrate these tables. Instead:
- Consolidate LLM audit data into `experiment_events` (current approach works)
- OR create a unified `llm_interactions` table that both systems use
- Delete the unused `GameRepository` methods and models

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

#### 4. Default Experiment Persistence Policy

The default persistence policy for experiments:

```python
@dataclass
class ExperimentPersistencePolicy:
    """Default persistence policy for experiments."""

    # Full tick-level state snapshots for ALL evaluation simulations
    simulation_persistence: SimulationPersistenceLevel = SimulationPersistenceLevel.FULL

    # Do NOT persist bootstrap sample transactions (they're resampled, not real)
    persist_bootstrap_transactions: bool = False

    # Always persist final evaluation simulation
    persist_final_evaluation: bool = True

    # Always persist every policy iteration for every agent (accepted AND rejected)
    persist_all_policy_iterations: bool = True


class SimulationPersistenceLevel(Enum):
    NONE = "none"           # No persistence (fast evaluation)
    SUMMARY = "summary"     # Just simulation_runs + daily_agent_metrics
    EVENTS = "events"       # + simulation_events (for replay)
    FULL = "full"           # + tick_agent_states, tick_queue_snapshots (full replay)
```

**Key points**:
- Every evaluation simulation gets FULL persistence (tick-level snapshots)
- Bootstrap sample transactions are NOT stored (they're synthetic resamples)
- All policy iterations persisted regardless of acceptance (for audit trail)
- Final evaluation always persisted

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

| Persistence Level | Per Simulation | 50 Iterations (1 eval each) |
|-------------------|----------------|----------------------------|
| NONE              | 0 KB           | 0 KB                       |
| SUMMARY           | 5 KB           | 250 KB                     |
| EVENTS            | 500 KB         | 25 MB                      |
| FULL              | 2 MB           | **100 MB**                 |

With new default policy (FULL for all evaluations):
- 50 iterations × 1 evaluation simulation = 50 simulations
- 50 × 2 MB = **100 MB per experiment**
- Plus policy iterations: ~50 × 50 KB = 2.5 MB
- **Total: ~103 MB per experiment**

This is acceptable for research/audit purposes. The key savings come from NOT storing:
- Bootstrap sample transactions (would add ~5 MB × N samples per iteration)
- Intermediate bootstrap evaluation states

---

## Open Questions (Remaining)

1. ~~**Backwards compatibility**~~ → **DECIDED**: Clean slate, no migration

2. ~~**Simulation ID format**~~ → **DECIDED**: Structured format `{experiment_id}-iter{N}-{purpose}`

3. ~~**Castro integration**~~ → **DECIDED**: Castro audit tables are dead code, don't migrate

4. **Deterministic re-run**: Can we re-run any simulation exactly?
   - Need: scenario config + policies + seed
   - With FULL persistence, we have everything needed
   - Policies stored in `experiment_iterations.policies`
   - Seeds stored in `simulation_runs.rng_seed`

5. **Policy iteration storage location**: Where to store accepted/rejected policies?
   - Option A: `experiment_iterations` table (current)
   - Option B: New `policy_proposals` table with richer schema
   - Needs: old_policy, new_policy, accepted, rejection_reason, LLM metadata

---

## Next Steps

1. [x] Review this proposal with stakeholders
2. [x] Decide on persistence policy defaults → FULL for all evaluations
3. [ ] Delete dead code: Castro audit tables (`llm_interaction_log`, `policy_diffs`, `iteration_context`)
4. [ ] Implement Phase 1: Schema unification (single DatabaseManager)
5. [ ] Implement Phase 2: Experiment → Simulation linking with structured IDs
6. [ ] Implement Phase 3: Unified CLI commands
7. [ ] Add `policy_proposals` table for rich policy audit trail

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
