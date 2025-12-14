# Unified Database Architecture - Development Plan

**Status**: In Progress
**Started**: 2025-12-14
**Last Updated**: 2025-12-14

---

## Overview

This plan consolidates SimCash's three separate database schemas into a single unified schema where:
- ALL CLI commands work on ANY database
- Experiments link to their constituent simulation runs
- Users can replay any simulation with full event detail
- Policy iterations are fully auditable

## Design Decisions (Final)

1. **No backwards compatibility** - Clean slate, no migration of old databases
2. **Structured simulation IDs** - Format: `{experiment_id}-iter{N}-{purpose}` for traceability
3. **Castro audit tables are dead code** - Delete `llm_interaction_log`, `policy_diffs`, `iteration_context`
4. **Policy storage** - Keep in `experiment_iterations` table (Option A)
5. **Default persistence policy**:
   - Full tick-level state snapshots for all evaluation simulations
   - Do NOT persist bootstrap sample transactions
   - Always persist final evaluation
   - Always persist every policy iteration (accepted AND rejected)

---

## Critical Invariants to Preserve

From `docs/reference/patterns-and-conventions.md`:

| Invariant | Description | Impact on This Work |
|-----------|-------------|---------------------|
| **INV-1** | Money is always i64 (integer cents) | All cost fields must be BIGINT, not DOUBLE |
| **INV-2** | Determinism is sacred | Seeds must be stored and reproducible |
| **INV-5** | Replay identity | Unified schema must support identical replay output |
| **INV-6** | Event completeness | Events must remain self-contained |

---

## Phase Overview

| Phase | Description | Status |
|-------|-------------|--------|
| **Phase 1** | Delete dead code (Castro audit tables) | ✅ Complete |
| **Phase 2** | Schema unification (single DatabaseManager) | ✅ Complete |
| **Phase 3** | Experiment → Simulation linking | ✅ Infrastructure Ready |
| **Phase 4** | Unified CLI commands | ✅ Complete (4.1-4.4) |
| **Phase 5** | Integration testing & cleanup | Pending |

---

## Phase 1: Delete Dead Code

**Goal**: Remove unused Castro audit tables and their associated code.

**Files to modify**:
- `api/payment_simulator/ai_cash_mgmt/persistence/models.py` - Remove dead model classes
- `api/payment_simulator/ai_cash_mgmt/persistence/repository.py` - Remove dead table creation and methods
- `api/migrations/004_add_audit_tables.sql` - Delete file
- `api/tests/` - Remove tests for dead code

**Dead code to remove**:
- `LLMInteractionRecord` model
- `PolicyDiffRecord` model
- `IterationContextRecord` model
- `llm_interaction_log` table and repository methods
- `policy_diffs` table and repository methods
- `iteration_context` table and repository methods

**Tests**:
- Verify existing experiments still work after removal
- Verify no import errors
- Run full pytest suite

---

## Phase 2: Schema Unification

**Goal**: Create a single unified schema that supports both standalone simulations and experiments.

**Schema changes**:

```sql
-- Add experiments table to standard simulation schema
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

-- Extend simulation_runs with experiment linkage
ALTER TABLE simulation_runs ADD COLUMN experiment_id VARCHAR;
ALTER TABLE simulation_runs ADD COLUMN iteration INTEGER;
ALTER TABLE simulation_runs ADD COLUMN sample_index INTEGER;
ALTER TABLE simulation_runs ADD COLUMN run_purpose VARCHAR;
-- run_purpose: 'standalone', 'initial', 'bootstrap', 'evaluation', 'best', 'final'

-- Add experiment_iterations for summary data
CREATE TABLE IF NOT EXISTS experiment_iterations (
    experiment_id VARCHAR NOT NULL,
    iteration INTEGER NOT NULL,
    costs_per_agent JSON NOT NULL,
    accepted_changes JSON NOT NULL,
    policies JSON NOT NULL,
    timestamp VARCHAR NOT NULL,
    evaluation_simulation_id VARCHAR,
    PRIMARY KEY (experiment_id, iteration),
    FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id)
);
```

**Code changes**:
- Merge `ExperimentRepository` into `DatabaseManager`
- Update `DatabaseManager.initialize_schema()` to create unified schema
- Add migration path for schema initialization

**Tests**:
- Schema creation tests
- Foreign key constraint tests
- Query tests across both table hierarchies

---

## Phase 3: Experiment → Simulation Linking

**Goal**: Modify experiment runner to persist simulation runs with experiment linkage.

**Structured simulation ID format**:
```
{experiment_id}-iter{N}-{purpose}

Examples:
  exp1-20251214-abc123-iter0-initial
  exp1-20251214-abc123-iter5-evaluation
  exp1-20251214-abc123-iter49-final
```

**Code changes**:
- Modify `OptimizationLoop._run_simulation_with_events()` to:
  - Generate structured `simulation_id`
  - Create `simulation_runs` entry with experiment linkage
  - Persist `simulation_events` for evaluation simulations
  - Use FULL persistence level (tick_agent_states, etc.)

**Persistence policy implementation**:
```python
@dataclass
class ExperimentPersistencePolicy:
    # Full tick-level snapshots for all evaluation simulations
    simulation_persistence: SimulationPersistenceLevel = SimulationPersistenceLevel.FULL

    # Do NOT persist bootstrap sample transactions
    persist_bootstrap_transactions: bool = False

    # Always persist final evaluation
    persist_final_evaluation: bool = True

    # Always persist every policy iteration (accepted AND rejected)
    persist_all_policy_iterations: bool = True
```

**Tests**:
- Simulation ID generation tests
- Experiment → simulation linkage tests
- Persistence level tests
- Policy iteration persistence tests

---

## Phase 4: Unified CLI Commands

**Goal**: All CLI commands work on any database.

**Commands to unify**:

1. `payment-sim db simulations --db <path>`
   - Query both standalone AND experiment-linked simulations
   - Show experiment context when applicable

2. `payment-sim db experiments --db <path>`
   - List all experiments with iteration counts

3. `payment-sim replay <id> --db <path>`
   - Auto-detect simulation vs experiment ID
   - Work for both standalone and experiment simulations

4. `payment-sim experiment replay <id> --db <path> --simulation iter5:eval`
   - Drill into specific simulation within experiment

**Tests**:
- CLI integration tests for each command
- Test with standalone simulation databases
- Test with experiment databases
- Test with unified databases (both types)

---

## Phase 5: Integration Testing & Cleanup

**Goal**: End-to-end validation and documentation.

**Tasks**:
- Full integration test suite
- Replay identity verification for experiment simulations
- Performance benchmarks (storage size, query speed)
- Update reference documentation
- Update CLAUDE.md files

**Tests**:
- End-to-end experiment workflow test
- Replay identity test for experiment simulations
- Cross-command workflow tests

---

## Storage Estimates

| Persistence Level | Per Simulation | 50 Iterations |
|-------------------|----------------|---------------|
| NONE              | 0 KB           | 0 KB          |
| SUMMARY           | 5 KB           | 250 KB        |
| EVENTS            | 500 KB         | 25 MB         |
| FULL              | 2 MB           | **100 MB**    |

With default policy (FULL for all evaluations):
- 50 iterations × 1 evaluation simulation = 50 simulations
- 50 × 2 MB = **100 MB per experiment**
- Plus policy iterations: ~2.5 MB
- **Total: ~103 MB per experiment**

---

## Files Reference

### Key Files to Modify

| File | Phase | Changes |
|------|-------|---------|
| `ai_cash_mgmt/persistence/models.py` | 1 | Remove dead models |
| `ai_cash_mgmt/persistence/repository.py` | 1 | Remove dead tables/methods |
| `persistence/connection.py` | 2 | Merge experiment schema |
| `persistence/models.py` | 2 | Add experiment models |
| `experiments/persistence/repository.py` | 2-3 | Refactor to use DatabaseManager |
| `experiments/runner/optimization.py` | 3 | Add simulation persistence |
| `cli/commands/db.py` | 4 | Unified listing |
| `cli/commands/replay.py` | 4 | Unified replay |

### Test Files

| File | Purpose |
|------|---------|
| `tests/unit/test_unified_schema.py` | Schema creation tests |
| `tests/integration/test_experiment_simulation_linking.py` | Linkage tests |
| `tests/integration/test_unified_cli.py` | CLI command tests |
| `tests/integration/test_experiment_replay_identity.py` | Replay identity for experiments |

---

## Progress Tracking

See `docs/plans/dbconsolidate/work_notes.md` for detailed progress notes.

Phase plans are in `docs/plans/dbconsolidate/phases/`:
- `phase_1.md` - Delete dead code
- `phase_2.md` - Schema unification
- `phase_3.md` - Experiment → Simulation linking
- `phase_4.md` - Unified CLI commands
- `phase_5.md` - Integration testing & cleanup
