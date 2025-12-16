# Unified Simulation Persistence - Work Notes

**Project**: Unify simulation persistence between CLI and experiment runner
**Started**: 2025-12-16
**Branch**: `claude/simcash-experiment-replay-fAM35`

---

## Session Log

### 2025-12-16 - Initial Investigation and Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-1, INV-2, INV-5, INV-6, INV-9, INV-10
- Read `docs/plans/CLAUDE.md` - understood plan structure requirements
- Analyzed git history to understand what consolidation work was done and what's missing
- Read `api/payment_simulator/experiments/persistence/repository.py` - understood experiment schema
- Read `api/payment_simulator/cli/execution/runner.py` and `persistence.py` - understood CLI persistence path

**Applicable Invariants**:
- INV-5 (Replay Identity): Must ensure replay works for experiment simulations
- INV-6 (Event Completeness): Events must be self-contained
- INV-9 (Policy Evaluation Identity): Follow same Protocol pattern
- INV-10 (Scenario Config Identity): Follow same Protocol pattern

**Key Insights**:

1. **The documentation lied**: Commit `d1cf8c6` documented a "unified database architecture" but implementation was incomplete

2. **Two separate schemas exist**:
   - CLI uses: `simulations`, `simulation_events`, `transactions`, `daily_agent_metrics`
   - Experiments use: `experiments`, `experiment_iterations`, `experiment_events`, `policy_evaluations`

3. **The shortcut in commit `926d552`**: Simulation events stored as JSON blobs in `experiment_events.event_data["events"]` instead of standard `simulation_events` table

4. **Existing patterns to follow**:
   - `ScenarioConfigBuilder` Protocol (INV-10)
   - `PolicyConfigBuilder` Protocol (INV-9)
   - `StateProvider` Protocol (INV-5)
   - All use: Protocol + StandardXxx implementation + single source of truth

**Completed**:
- [x] Investigate current state of persistence architecture
- [x] Trace git history to understand what work was done
- [x] Identify the gap: experiments don't write to `simulation_events` table
- [x] Create development plan following docs/plans/CLAUDE.md structure

**Next Steps**:
1. Create Phase 1 detailed plan
2. Create Phase 2 detailed plan
3. Begin implementation following TDD

---

## Key Decisions

### Decision 1: Protocol-Based Abstraction

**Rationale**: Following established patterns (StateProvider, ConfigBuilder), using a Protocol ensures:
- Type safety via runtime_checkable
- Clear interface contract
- Single implementation that ALL paths must use
- Future extensibility if needed

### Decision 2: Extend Rather Than Replace

**Rationale**: Don't remove `ExperimentRepository` - it still serves experiment-level data (iterations, policy evaluations). Instead, ADD `SimulationPersistenceProvider` for simulation-level data. Both can coexist in the same database file.

### Decision 3: Optional Persistence for Experiments

**Rationale**: Not all experiment runs need simulation-level persistence. The `--persist-bootstrap` flag already exists; we'll wire it to use `SimulationPersistenceProvider` when enabled.

---

## Git History Analysis

Key commits in chronological order:

| Commit | Date | What it claimed | What it actually did |
|--------|------|-----------------|---------------------|
| `d1cf8c6` | Dec 14, 11:39 | "unified database architecture" | Only updated documentation |
| `926d552` | Dec 14, 18:29 | "persist simulation events to experiment database" | Stored as JSON blob in `experiment_events`, NOT in `simulation_events` |
| `5f04ad7` | Dec 14, 20:43 | "consolidate simulation execution" | Unified execution, but not persistence |

The documentation updates in `d1cf8c6` describe an architecture that was never implemented.

---

## Files to Modify

### Create
- `api/payment_simulator/persistence/simulation_persistence_provider.py` - Protocol and implementation
- `api/tests/unit/test_simulation_persistence_provider.py` - Unit tests
- `api/tests/integration/test_experiment_simulation_persistence.py` - Integration tests
- `api/tests/integration/test_experiment_replay_identity.py` - Replay identity tests

### Modify
- `api/payment_simulator/experiments/runner/optimization.py` - Use SimulationPersistenceProvider
- `api/payment_simulator/persistence/__init__.py` - Export new provider
- `docs/reference/patterns-and-conventions.md` - Add INV-11

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] Add INV-11: Simulation Persistence Identity
- [ ] Add Pattern N: SimulationPersistenceProvider
- [ ] Update Key Source Files table with new provider file
- [ ] Increment version number

### Other Documentation
- [ ] `docs/reference/architecture/09-persistence-layer.md` - Add experiment integration section
- [ ] `CLAUDE.md` - Clarify that unified architecture is now actually implemented
- [ ] `docs/reference/cli/commands/replay.md` - Document experiment simulation replay

---

## Phase Progress

### Phase 1: SimulationPersistenceProvider Protocol
**Status**: Pending
**Started**:
**Completed**:

### Phase 2: Experiment Runner Integration
**Status**: Pending
**Started**:
**Completed**:

### Phase 3: Replay Identity Verification
**Status**: Pending
**Started**:
**Completed**:

### Phase 4: Documentation
**Status**: Pending
**Started**:
**Completed**:
