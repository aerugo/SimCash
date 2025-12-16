# Phase 4: Documentation and Cleanup

**Status**: Pending
**Started**:

---

## Objective

Update all relevant documentation to reflect the unified simulation persistence architecture. Add INV-11 to patterns-and-conventions.md. Clean up any remaining issues from implementation.

---

## Deliverables

### 1. Update `docs/reference/patterns-and-conventions.md`

Add INV-11 (Simulation Persistence Identity):

```markdown
### INV-11: Simulation Persistence Identity

**Rule**: For any simulation S, persistence MUST produce identical database records
regardless of which code path executes the simulation.

```python
# Both paths MUST use SimulationPersistenceProvider
persistence(cli_path, S) == persistence(experiment_path, S)
```

**Requirements**:
- ALL code paths that persist simulations MUST use `SimulationPersistenceProvider`
- Event capture, transformation, and storage logic MUST be in one place
- Table schema MUST be consistent across all paths
- Simulation IDs from ANY path MUST be stored in `simulations` table

**Where it applies**:
- `cli/execution/persistence.py` - CLI simulation persistence
- `experiments/runner/optimization.py` - Experiment simulation persistence

**Rationale**: Without this invariant, the same simulation could be persisted
differently depending on execution context, breaking replay identity (INV-5)
and making debugging impossible.

**Related**: INV-5 (Replay Identity) is achieved BECAUSE of persistence identity.
```

Add Pattern 7 (SimulationPersistenceProvider):

```markdown
### Pattern 7: SimulationPersistenceProvider

**Purpose**: Ensure identical simulation persistence across all execution contexts.

```python
@runtime_checkable
class SimulationPersistenceProvider(Protocol):
    """Protocol for persisting simulation data."""

    def persist_simulation_start(
        self,
        simulation_id: str,
        config: dict[str, Any],
        experiment_run_id: str | None = None,
        experiment_iteration: int | None = None,
    ) -> None: ...

    def persist_tick_events(
        self,
        simulation_id: str,
        tick: int,
        events: list[dict[str, Any]],
    ) -> None: ...

    def persist_simulation_complete(
        self,
        simulation_id: str,
        metrics: dict[str, Any],
    ) -> None: ...
```

**Implementation**: `StandardSimulationPersistenceProvider`

**Key Features**:
- Single implementation used by ALL paths (CLI and experiments)
- Wraps existing `write_events_batch()` and database operations
- Stores experiment context (run_id, iteration) for cross-referencing
- Enables unified replay via `payment-sim replay`

**Usage**:
```python
# In CLI
provider = StandardSimulationPersistenceProvider(db_manager)
provider.persist_simulation_start(sim_id, config)
for tick in range(total_ticks):
    events = orch.get_tick_events(tick)
    provider.persist_tick_events(sim_id, tick, events)
provider.persist_simulation_complete(sim_id, metrics)

# In experiments - SAME code!
provider = StandardSimulationPersistenceProvider(db_manager)
provider.persist_simulation_start(sim_id, config, experiment_run_id=run_id)
# ... identical persistence calls ...
```

**Anti-patterns**:
- ❌ Storing events as JSON blobs in `experiment_events`
- ❌ Using different persistence logic per execution context
- ❌ Creating simulation records without using the provider
```

### 2. Update `CLAUDE.md`

In the "Replay Identity" section, add note about experiment simulations:

```markdown
### Experiment Simulation Replay

Simulations run during experiments (with `--persist-bootstrap`) are now persisted
to the same `simulations` and `simulation_events` tables as CLI runs. This means:

```bash
# Replay simulation from experiment
payment-sim replay --simulation-id <experiment-sim-id> --verbose
```

Experiment simulations include additional context columns:
- `experiment_run_id`: Links to parent experiment run
- `experiment_iteration`: Which iteration the simulation was part of
```

### 3. Update `docs/reference/architecture/09-persistence-layer.md`

Add section on experiment integration:

```markdown
## Experiment Integration

Experiments use the same persistence infrastructure as CLI runs via
`SimulationPersistenceProvider` (Pattern 7).

### Shared Tables

| Table | CLI Writes | Experiments Write |
|-------|-----------|-------------------|
| `simulations` | ✅ | ✅ (with experiment context) |
| `simulation_events` | ✅ | ✅ |
| `experiments` | ❌ | ✅ |
| `experiment_iterations` | ❌ | ✅ |
| `experiment_events` | ❌ | ✅ (non-simulation events only) |

### Cross-Referencing

Simulations from experiments can be linked back via:

```sql
SELECT s.*, e.experiment_name
FROM simulations s
JOIN experiments e ON s.experiment_run_id = e.run_id
WHERE s.experiment_run_id IS NOT NULL;
```
```

### 4. Update `docs/reference/cli/commands/replay.md`

Add note about experiment simulations:

```markdown
## Replaying Experiment Simulations

Simulations run as part of experiments (with `--persist-bootstrap` flag) can
be replayed just like regular simulations:

```bash
# List simulations from an experiment database
payment-sim db list --db-path experiment_results.db

# Replay a specific simulation
payment-sim replay --db-path experiment_results.db \
    --simulation-id exp-initial-bootstrap-12345 \
    --verbose
```

The replay output will be identical to what verbose mode would have shown
during the experiment run.
```

### 5. Update Key Source Files Table

In `patterns-and-conventions.md`, add:

```markdown
| `persistence/simulation_persistence_provider.py` | SimulationPersistenceProvider protocol and implementation |
```

---

## Cleanup Tasks

### Remove Dead Code

1. Remove JSON blob persistence from `optimization.py` (the old path)
2. Remove any deprecated comments referencing "temporary" storage

### Verify Migrations

1. Ensure migration for `experiment_run_id` and `experiment_iteration` columns exists
2. Migration should be idempotent (safe to run multiple times)

### Update Version Numbers

1. Increment version in `patterns-and-conventions.md`
2. Update "Last Updated" date

---

## Files to Modify

| File | Changes |
|------|---------|
| `docs/reference/patterns-and-conventions.md` | Add INV-11, Pattern 7, update version |
| `CLAUDE.md` | Add experiment replay note |
| `docs/reference/architecture/09-persistence-layer.md` | Add experiment integration section |
| `docs/reference/cli/commands/replay.md` | Add experiment simulation note |

---

## Verification

1. All documentation changes reviewed for accuracy
2. Cross-references between docs are consistent
3. Examples in docs are executable
4. Version numbers updated

---

## Completion Criteria

- [ ] INV-11 added to patterns-and-conventions.md
- [ ] Pattern 7 (SimulationPersistenceProvider) documented
- [ ] Key Source Files table updated
- [ ] Version number incremented in patterns-and-conventions.md
- [ ] CLAUDE.md updated with experiment replay info
- [ ] Architecture docs updated
- [ ] CLI replay docs updated
- [ ] All documentation is internally consistent
- [ ] Work notes reflect final state
