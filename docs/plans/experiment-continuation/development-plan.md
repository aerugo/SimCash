# Experiment Continuation Feature - Development Plan

**Status**: In Progress
**Created**: 2025-12-19
**Branch**: claude/experiment-continuation-feature-3blfZ

## Summary

Implement a feature to continue interrupted experiments that do not have status "completed". The continuation uses the same seeds, configuration, and policies from the last completed iteration, resuming from iteration N+1.

## Critical Invariants to Respect

- **INV-1**: Money is ALWAYS i64 - All costs remain in integer cents
- **INV-2**: Determinism is Sacred - Same seed + same inputs = same outputs. Continuation must use the original master_seed and seed matrix
- **INV-5**: Replay Identity - Continued experiments produce events that can be replayed identically

## Current State Analysis

**What exists now:**
- `ExperimentRepository`: Persists experiment records with `completed_at` field (NULL = incomplete)
- `IterationRecord`: Stores iteration data including policies, costs, accepted_changes
- `GenericExperimentRunner`: Runs experiments from scratch
- `OptimizationLoop`: Main iteration loop with state tracking
- CLI commands: `run`, `replay`, `results` - but no `continue` command

**Problem solved:**
When an experiment is interrupted (network error, process killed, etc.), users currently have no way to resume. They must start from scratch, wasting LLM API costs and time.

### Files to Modify
| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `experiments/persistence/repository.py` | Has `load_experiment`, `get_iterations` | Add `get_last_iteration` helper method |
| `experiments/runner/experiment_runner.py` | Only supports fresh runs | Add continuation factory method and resume logic |
| `experiments/runner/optimization.py` | Initializes from scratch | Add `restore_state` method to load from iteration records |
| `experiments/cli/commands.py` | Has `run`, `replay` commands | Add `continue` command |

## Solution Design

```
┌─────────────────────────────────────────────────────────────────┐
│  payment-sim experiment continue <run_id>                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. Load ExperimentRecord from database                         │
│  2. Verify: completed_at IS NULL (incomplete)                   │
│  3. Load last IterationRecord (highest iteration number)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  4. Reconstruct ExperimentConfig from stored config JSON        │
│  5. Create OptimizationLoop with restored state:                │
│     - Same run_id (NOT new)                                     │
│     - Same master_seed from config                              │
│     - Restored policies from last iteration                     │
│     - _current_iteration = last_iteration                       │
│     - _best_cost, _iteration_history from database              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│  6. Resume loop.run() from iteration N+1                        │
│  7. Uses same SeedMatrix (deterministic)                        │
│  8. Saves completion when done                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Same run_id**: Continuation uses the SAME run_id, not a new one. This keeps all iteration data in one logical experiment run.

2. **Reconstructed Config**: We store the full config dict in `experiments.config` column. We reconstruct `ExperimentConfig` from this to ensure identical settings.

3. **Seed Matrix Determinism**: The `SeedMatrix` is deterministic based on master_seed. Re-creating it with the same seed produces identical seeds for iteration N+1 as if the experiment had never stopped.

4. **No Re-running Initial Simulation**: For bootstrap mode, we cannot re-run the initial simulation because the collected history is not persisted. Instead, we only support continuation for deterministic modes initially. Bootstrap continuation would require persisting the initial simulation history.

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Repository layer additions | Load last iteration, validate incomplete | 3 tests |
| 2 | OptimizationLoop state restoration | Restore from iteration record | 4 tests |
| 3 | CLI continue command | User-facing command with validation | 5 tests |
| 4 | Integration testing | End-to-end continuation flow | 3 tests |

## Phase 1: Repository Layer Additions

**Goal**: Add methods to load continuation state from database

### Deliverables
1. `ExperimentRepository.get_last_iteration(run_id)` method
2. `ExperimentRepository.is_incomplete(run_id)` method

### TDD Approach
1. Write failing tests for `get_last_iteration`
2. Implement minimal code to pass
3. Write failing tests for `is_incomplete`
4. Implement minimal code to pass

### Success Criteria
- [ ] `get_last_iteration` returns highest iteration number's record
- [ ] `is_incomplete` returns True when `completed_at` is NULL
- [ ] Returns None/False for non-existent run_ids

## Phase 2: OptimizationLoop State Restoration

**Goal**: Add ability to restore optimization state from database records

### Deliverables
1. `OptimizationLoop.restore_state(iteration_records, last_iteration)` method
2. Integration with `GenericExperimentRunner` for continuation mode

### TDD Approach
1. Write failing tests for state restoration
2. Implement `restore_state` method
3. Write tests for continuation from restored state
4. Implement continuation factory in runner

### Success Criteria
- [ ] Policies restored from last iteration
- [ ] `_current_iteration` set correctly
- [ ] `_iteration_history` populated from records
- [ ] Loop resumes from N+1

## Phase 3: CLI Continue Command

**Goal**: Add user-facing command to continue experiments

### Deliverables
1. `payment-sim experiment continue <run_id>` command
2. Validation: run exists, is incomplete, has iterations
3. Progress output and completion handling

### TDD Approach
1. Write failing tests for CLI command
2. Implement command with validation
3. Write tests for error cases
4. Implement error handling

### Success Criteria
- [ ] Command accepts run_id argument
- [ ] Validates experiment is incomplete
- [ ] Continues from correct iteration
- [ ] Shows appropriate progress/completion output

## Phase 4: Integration Testing

**Goal**: Verify end-to-end continuation flow

### Deliverables
1. Integration test: interrupt and continue flow
2. Test determinism: continued run matches what would have happened

### Success Criteria
- [ ] Can interrupt and continue an experiment
- [ ] Iteration N+1 produces same results as if never stopped
- [ ] Final completion is recorded correctly

## Testing Strategy

### Unit Tests
- Repository methods: `get_last_iteration`, `is_incomplete`
- State restoration: `restore_state` correctness

### Integration Tests
- Full continuation flow with database
- Determinism verification

### Identity/Invariant Tests
- INV-2 (Determinism): Same seed matrix produces same seeds
- INV-1 (Money): Costs remain integers after continuation

## Documentation Updates

After implementation is complete, update the following:

- [ ] `docs/reference/patterns-and-conventions.md` - Add continuation pattern if new
- [ ] CLI help text updated with `continue` command
- [ ] README or experiment docs mention continuation capability

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | Repository layer |
| Phase 2 | Pending | State restoration |
| Phase 3 | Pending | CLI command |
| Phase 4 | Pending | Integration tests |
