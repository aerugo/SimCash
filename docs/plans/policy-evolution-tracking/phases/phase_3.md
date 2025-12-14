# Phase 3: Service Layer

## Overview

Create `PolicyEvolutionService` that orchestrates data extraction from the repository.

**Status**: In Progress
**Start Date**: 2025-12-14

---

## Goals

1. Create `PolicyEvolutionService` class
2. Implement `get_evolution()` method with filtering
3. Wire together repository, diff calculator, and model builder
4. Handle iteration indexing (0-indexed DB, 1-indexed output)

---

## TDD Steps

### Step 3.1: Create Test File (RED)

Create `api/tests/experiments/analysis/test_evolution_service.py`

**Test Cases**:
1. `test_get_evolution_returns_all_agents` - No filter
2. `test_get_evolution_filters_by_agent` - Agent filter
3. `test_get_evolution_filters_by_iteration_range` - Start/end filters
4. `test_get_evolution_includes_llm_when_requested` - --llm flag
5. `test_get_evolution_excludes_llm_by_default` - Default behavior
6. `test_get_evolution_computes_diffs` - Diff between iterations
7. `test_get_evolution_handles_first_iteration_no_diff` - First iteration
8. `test_get_evolution_raises_for_invalid_run_id` - Error handling
9. `test_get_evolution_iteration_numbers_are_1_indexed` - Output format

### Step 3.2: Create Implementation File (GREEN)

Create `api/payment_simulator/experiments/analysis/evolution_service.py`

**Main Class**:
```python
class PolicyEvolutionService:
    def __init__(self, repository: ExperimentRepository) -> None: ...

    def get_evolution(
        self,
        run_id: str,
        include_llm: bool = False,
        agent_filter: str | None = None,
        start_iteration: int | None = None,
        end_iteration: int | None = None,
    ) -> list[AgentEvolution]: ...

    def _extract_llm_data(
        self,
        run_id: str,
        iteration: int,
        agent_id: str,
    ) -> LLMInteractionData | None: ...
```

### Step 3.3: Refactor

- Ensure clean separation of concerns
- Handle edge cases
- Add comprehensive docstrings

---

## Key Implementation Details

### Iteration Indexing
- Database: 0-indexed (`iteration = 0, 1, 2, ...`)
- Output: 1-indexed (`"iteration_1", "iteration_2", ...`)
- User CLI args: 1-indexed (`--start 1 --end 10`)

### LLM Event Extraction
- Events table has `event_type = 'llm_call_complete'`
- `event_data` contains prompts and response
- Filter by `agent_id` within event_data

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added
- [ ] Handles all edge cases
