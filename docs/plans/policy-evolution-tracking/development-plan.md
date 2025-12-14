# Policy Evolution Tracking - Development Plan

## Overview

This document outlines the phased TDD implementation plan for the `payment-sim experiment policy-evolution` CLI command. This command extracts and displays how policies evolved across experiment iterations for all bank agents.

**Status**: In Progress
**Original Plan**: [original-plan.md](./original-plan.md)

---

## Project Goals

1. Add a new CLI subcommand `payment-sim experiment policy-evolution <run_id>`
2. Extract policy evolution data from the experiment database
3. Display JSON output showing how policies changed across iterations
4. Support filtering by agent, iteration range, and optional LLM data inclusion
5. Follow strict TDD principles throughout

---

## Key Invariants to Respect

- **INV-1**: All costs are integer cents (never floats for money)
- **INV-9**: Policy Evaluation Identity (consistent parameter extraction)
- **Type Safety**: Complete type annotations, no bare generics, modern Python syntax
- **CLI Pattern**: Use `Annotated` pattern for Typer commands
- **Iteration Indexing**: 0-indexed internally (database), 1-indexed in output (user-facing)

---

## Output Format

```json
{
  "BANK_A": {
    "iteration_1": {
      "policy": {...},
      "explanation": "...",
      "diff": "...",
      "cost": 15000,
      "accepted": true,
      "llm": {
        "system_prompt": "...",
        "user_prompt": "...",
        "raw_response": "..."
      }
    },
    "iteration_2": {...}
  },
  "BANK_B": {...}
}
```

---

## Implementation Phases

### Phase 1: Policy Diff Calculator (Foundation)

**Goal**: Create a module for computing human-readable diffs between policy dictionaries.

**Files**:
- `api/payment_simulator/experiments/analysis/__init__.py`
- `api/payment_simulator/experiments/analysis/policy_diff.py`
- `api/tests/experiments/analysis/__init__.py`
- `api/tests/experiments/analysis/test_policy_diff.py`

**TDD Steps**:
1. Write failing tests for diff computation
2. Implement `compute_policy_diff()` to pass tests
3. Refactor for clarity

**Detailed Plan**: [phases/phase_1.md](./phases/phase_1.md)

---

### Phase 2: Domain Model

**Goal**: Create immutable dataclasses for evolution output structure.

**Files**:
- `api/payment_simulator/experiments/analysis/evolution_model.py`
- `api/tests/experiments/analysis/test_evolution_model.py`

**TDD Steps**:
1. Write failing tests for model structure and conversion
2. Implement dataclasses and `build_evolution_output()`
3. Ensure JSON serialization works correctly

**Detailed Plan**: [phases/phase_2.md](./phases/phase_2.md)

---

### Phase 3: Service Layer

**Goal**: Create `PolicyEvolutionService` that orchestrates data extraction.

**Files**:
- `api/payment_simulator/experiments/analysis/evolution_service.py`
- `api/tests/experiments/analysis/test_evolution_service.py`

**TDD Steps**:
1. Write failing tests for service methods
2. Implement service with repository queries
3. Wire together diff calculator and model builder

**Detailed Plan**: [phases/phase_3.md](./phases/phase_3.md)

---

### Phase 4: CLI Command

**Goal**: Add `policy-evolution` command to experiment CLI app.

**Files**:
- `api/payment_simulator/experiments/cli/commands.py` (modify)
- `api/tests/experiments/cli/test_policy_evolution_command.py`

**TDD Steps**:
1. Write failing tests for CLI command
2. Implement command with all options
3. Wire to service layer

**Detailed Plan**: [phases/phase_4.md](./phases/phase_4.md)

---

### Phase 5: Integration Tests

**Goal**: End-to-end tests validating the full CLI flow.

**Files**:
- `api/tests/experiments/integration/test_policy_evolution_integration.py`

**TDD Steps**:
1. Create test fixtures with real database
2. Test full CLI invocation
3. Verify JSON output structure

**Detailed Plan**: [phases/phase_5.md](./phases/phase_5.md)

---

## File Structure Summary

```
api/payment_simulator/experiments/
├── analysis/                              # NEW directory
│   ├── __init__.py                        # NEW
│   ├── evolution_model.py                 # NEW: Output models
│   ├── evolution_service.py               # NEW: Service layer
│   └── policy_diff.py                     # NEW: Diff calculator
├── cli/
│   └── commands.py                        # ADD: policy-evolution command
└── persistence/
    └── repository.py                      # (existing, may add helper methods)

api/tests/experiments/
├── analysis/                              # NEW directory
│   ├── __init__.py                        # NEW
│   ├── test_evolution_model.py            # NEW
│   ├── test_evolution_service.py          # NEW
│   └── test_policy_diff.py                # NEW
├── cli/
│   └── test_policy_evolution_command.py   # NEW
└── integration/
    └── test_policy_evolution_integration.py  # NEW
```

---

## Validation Checklist

### Type Safety
- [x] All functions have complete type annotations (params + return)
- [x] No bare `list`, `dict` without type arguments
- [x] Using `str | None` not `Optional[str]`
- [x] Typer commands use `Annotated` pattern

### Project Invariants
- [x] All costs are `int` (cents, never floats) - INV-1
- [x] Iteration numbers are 1-indexed in output (user-facing)
- [x] Iteration numbers are 0-indexed internally (database)

### Tests
- [x] Unit tests for each new module
- [x] Integration test for full CLI flow
- [x] Tests verify JSON output structure
- [x] Tests verify filter combinations

### Documentation
- [x] Update `docs/reference/cli/commands/` with new command
- [x] Add to experiment CLI help text
- [x] Example usage in docstrings

---

## Edge Cases to Handle

1. **Empty iterations**: Run has no iterations (just started)
2. **Single agent**: Only one agent being optimized
3. **No LLM events**: Events table doesn't have LLM data for some iterations
4. **Missing diff**: First iteration has nothing to diff against
5. **Large policies**: Policies with deeply nested trees
6. **Unicode in prompts**: LLM prompts/responses may contain special characters
7. **Agent not found**: Filter by agent that doesn't exist in experiment
8. **Invalid run ID**: Non-existent run ID
9. **Invalid iteration range**: start > end

---

## Progress Tracking

See [work_notes.md](./work_notes.md) for detailed session notes and progress.

| Phase | Status | Start Date | Completion Date |
|-------|--------|------------|-----------------|
| Phase 1: Policy Diff | Complete | 2025-12-14 | 2025-12-14 |
| Phase 2: Domain Model | Complete | 2025-12-14 | 2025-12-14 |
| Phase 3: Service Layer | Complete | 2025-12-14 | 2025-12-14 |
| Phase 4: CLI Command | Complete | 2025-12-14 | 2025-12-14 |
| Phase 5: Integration | Complete | 2025-12-14 | 2025-12-14 |
| Documentation | Complete | 2025-12-14 | 2025-12-14 |

---

## Dependencies

### Existing Code Used
- `ExperimentRepository` - Database access
- `IterationRecord`, `EventRecord` - Data models
- `experiment_app` - Typer CLI app to extend

### New Dependencies
- None (using existing packages: typer, rich, pydantic)

---

## Notes

- Iteration numbers are **1-indexed in output** (user-facing) but **0-indexed in database** (internal)
- The `diff` field is computed at query time, not stored in database
- LLM data may be large; JSON output goes to stdout for piping
- The command outputs JSON for tool interoperability (e.g., `jq`)
