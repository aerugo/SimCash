# Phase 2: Domain Model

## Overview

Create immutable dataclasses for policy evolution output structure.

**Status**: In Progress
**Start Date**: 2025-12-14

---

## Goals

1. Create `LLMInteractionData` dataclass for LLM prompts/responses
2. Create `IterationEvolution` dataclass for single iteration data
3. Create `AgentEvolution` dataclass for agent history
4. Create `build_evolution_output()` for JSON conversion
5. Ensure proper JSON serialization

---

## TDD Steps

### Step 2.1: Create Test File (RED)

Create `api/tests/experiments/analysis/test_evolution_model.py`

**Test Cases**:
1. `test_iteration_evolution_is_immutable` - Frozen dataclass
2. `test_llm_interaction_data_is_immutable` - Frozen dataclass
3. `test_build_evolution_output_formats_correctly` - JSON structure
4. `test_build_evolution_output_handles_optional_fields` - None excluded
5. `test_iteration_keys_are_1_indexed` - User-facing format
6. `test_serialization_handles_nested_policy` - Complex policies

### Step 2.2: Create Implementation File (GREEN)

Create `api/payment_simulator/experiments/analysis/evolution_model.py`

**Dataclasses**:
```python
@dataclass(frozen=True)
class LLMInteractionData:
    system_prompt: str
    user_prompt: str
    raw_response: str

@dataclass(frozen=True)
class IterationEvolution:
    policy: dict[str, Any]
    explanation: str | None = None
    diff: str | None = None
    llm: LLMInteractionData | None = None
    cost: int | None = None
    accepted: bool | None = None

@dataclass(frozen=True)
class AgentEvolution:
    agent_id: str
    iterations: dict[str, IterationEvolution]

def build_evolution_output(evolutions: list[AgentEvolution]) -> dict[str, dict[str, dict[str, Any]]]:
    ...
```

### Step 2.3: Refactor

- Ensure JSON serialization is clean
- Add comprehensive docstrings
- Verify type safety

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added
- [ ] JSON serialization works
