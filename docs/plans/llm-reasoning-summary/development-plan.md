# LLM Reasoning Summary Capture - Development Plan

**Status**: In Progress
**Created**: 2025-12-20
**Branch**: claude/add-llm-reasoning-summary-Bwz0c

## Summary

Implement capture and persistence of LLM reasoning summaries from OpenAI models to understand why the LLM reasoned as it does during policy optimization. The reasoning will be associated with each policy response in the database for post-experiment analysis.

## Critical Invariants to Respect

- **INV-2**: Determinism is Sacred - Reasoning summaries are metadata; they don't affect simulation behavior
- **INV-3**: FFI Boundary is Minimal and Safe - Not directly affected (pure Python change)
- **INV-9**: Policy Evaluation Identity - The reasoning capture is observational only; it must not affect policy evaluation results

## Current State Analysis

### What Exists

1. **LLMConfig** (`api/payment_simulator/llm/config.py`):
   - Already has `reasoning_effort: str | None` for OpenAI reasoning models
   - Converts to `openai_reasoning_effort` in `to_model_settings()`
   - **Missing**: `openai_reasoning_summary` setting to get reasoning summaries

2. **LLMInteraction** (`api/payment_simulator/llm/audit_wrapper.py`):
   - Captures prompts, responses, latency, tokens
   - **Missing**: Field for reasoning/thinking content

3. **LLMInteractionRecord** (`api/payment_simulator/ai_cash_mgmt/persistence/models.py`):
   - Already has `llm_reasoning: str | None` field
   - **Not populated**: Currently always NULL

4. **PydanticAILLMClient** (`api/payment_simulator/llm/pydantic_client.py`):
   - Uses PydanticAI Agent but doesn't pass model settings
   - **Missing**: Model settings configuration (reasoning_effort, reasoning_summary)
   - **Missing**: Extraction of reasoning from response

5. **Database Schema** (`migrations/004_add_audit_tables.sql`):
   - `llm_interaction_log.llm_reasoning TEXT` column exists
   - Ready to store reasoning data

### How Reasoning Works in PydanticAI (from docs)

According to [Pydantic AI docs](https://ai.pydantic.dev/thinking/):

```python
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings

model = OpenAIResponsesModel('o1')
settings = OpenAIResponsesModelSettings(
    openai_reasoning_effort='low',
    openai_reasoning_summary='detailed',  # NEW: Enables reasoning summaries
)
agent = Agent(model, model_settings=settings)
```

- Reasoning content appears as `ThinkingPart` objects in message history
- `openai_reasoning_summary` controls detail level: `'concise'`, `'detailed'`
- Raw reasoning stored in `provider_details['raw_content']` when summaries disabled

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `llm/config.py` | Has `reasoning_effort` only | Add `reasoning_summary` field |
| `llm/pydantic_client.py` | No model settings, no reasoning capture | Pass model settings, extract reasoning from response |
| `llm/audit_wrapper.py` | `LLMInteraction` lacks reasoning field | Add `reasoning_summary` field |
| `llm/protocol.py` | Protocol returns data only | Update to return reasoning with data |
| `ai_cash_mgmt/persistence/repository.py` | May not store `llm_reasoning` | Verify reasoning is persisted |
| Tests | No reasoning tests | Add unit and integration tests |

## Solution Design

```
┌─────────────────────────────────────────────────────────────────┐
│                    LLM Call Flow with Reasoning                  │
└─────────────────────────────────────────────────────────────────┘

  ExperimentRunner
       │
       ▼
  PolicyOptimizer.generate_policy()
       │
       ▼
  AuditCaptureLLMClient
       │ wraps
       ▼
  PydanticAILLMClient.generate_structured_output()
       │
       │ 1. Creates Agent with model settings (reasoning_summary='detailed')
       │ 2. Runs agent.run(prompt)
       │ 3. Extracts reasoning from result.all_messages()
       │
       ▼
  LLMResult(data=T, reasoning_summary=str | None)
       │
       │ returned to
       ▼
  AuditCaptureLLMClient
       │ captures to
       ▼
  LLMInteraction(reasoning_summary=str | None)
       │
       │ persisted to
       ▼
  llm_interaction_log.llm_reasoning
```

### Key Design Decisions

1. **Reasoning is Optional**: Only captured when `reasoning_summary` is configured in LLMConfig
2. **Non-breaking Change**: Existing code that doesn't need reasoning continues to work
3. **Single Extraction Point**: Reasoning extraction happens in `PydanticAILLMClient` only
4. **Immutable Data Flow**: Use frozen dataclasses throughout

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Extend LLMConfig with reasoning_summary | Config validation, model settings | 4 tests |
| 2 | Create LLMResult wrapper | Result with reasoning | 3 tests |
| 3 | Update PydanticAILLMClient | Reasoning extraction | 5 tests |
| 4 | Update audit wrapper | Capture and persist reasoning | 4 tests |
| 5 | Integration tests | End-to-end reasoning capture | 3 tests |
| 6 | CLI/Query support | Query reasoning from database | 2 tests |

## Phase 1: Extend LLMConfig

**Goal**: Add `reasoning_summary` field to LLMConfig and update model settings generation.

### Deliverables
1. Updated `LLMConfig` with `reasoning_summary: str | None` field
2. Updated `to_model_settings()` to include `openai_reasoning_summary`

### TDD Approach
1. Write test for new config field validation
2. Write test for model settings conversion
3. Implement changes to pass tests

### Success Criteria
- [ ] `LLMConfig(model="openai:o1", reasoning_summary="detailed")` works
- [ ] `to_model_settings()` returns `{"openai_reasoning_summary": "detailed"}`
- [ ] Existing configs without reasoning_summary continue to work

## Phase 2: Create LLMResult Wrapper

**Goal**: Create a typed result wrapper that includes both the parsed data and optional reasoning.

### Deliverables
1. New `LLMResult[T]` generic dataclass
2. Protocol updates to return `LLMResult[T]`

### TDD Approach
1. Write tests for LLMResult creation and access
2. Implement the dataclass

### Success Criteria
- [ ] `LLMResult(data=policy, reasoning_summary="...")` works
- [ ] Generic typing is correct (`LLMResult[PolicyResponse]`)

## Phase 3: Update PydanticAILLMClient

**Goal**: Pass model settings to PydanticAI agent and extract reasoning from response.

### Deliverables
1. Updated `generate_structured_output()` to pass model settings
2. Reasoning extraction from `result.all_messages()`
3. Return `LLMResult[T]` with reasoning

### TDD Approach
1. Mock PydanticAI response with ThinkingPart
2. Test reasoning extraction logic
3. Test model settings are correctly passed

### Success Criteria
- [ ] Model settings (temperature, reasoning_effort, reasoning_summary) passed to agent
- [ ] ThinkingPart content extracted as reasoning_summary
- [ ] Works when no thinking parts present

## Phase 4: Update Audit Wrapper

**Goal**: Capture reasoning in LLMInteraction and ensure persistence.

### Deliverables
1. Add `reasoning_summary` to `LLMInteraction`
2. Update capture logic in `AuditCaptureLLMClient`
3. Verify persistence to `llm_interaction_log.llm_reasoning`

### TDD Approach
1. Test LLMInteraction includes reasoning
2. Test audit wrapper captures reasoning from LLMResult
3. Test persistence roundtrip

### Success Criteria
- [ ] `LLMInteraction.reasoning_summary` populated
- [ ] Reasoning persisted to database
- [ ] Queryable via standard repository methods

## Phase 5: Integration Tests

**Goal**: End-to-end verification that reasoning flows from LLM to database.

### Deliverables
1. Integration test with mock OpenAI response
2. Verify reasoning in database after experiment run

### Success Criteria
- [ ] Reasoning captured during policy optimization
- [ ] Reasoning queryable after experiment completes

## Phase 6: CLI/Query Support

**Goal**: Enable querying reasoning summaries from experiments.

### Deliverables
1. Query function in repository
2. Optional: CLI command to view reasoning

### Success Criteria
- [ ] Can query reasoning by game_id/iteration
- [ ] Reasoning displayed in audit output

## Testing Strategy

### Unit Tests
- LLMConfig with reasoning_summary
- LLMResult creation and access
- PydanticAI reasoning extraction
- Audit wrapper reasoning capture

### Integration Tests
- Full policy optimization with reasoning capture
- Database persistence and retrieval

## Documentation Updates

After implementation is complete, update:

- [ ] `docs/reference/llm/configuration.md` - Add reasoning_summary option
- [ ] `docs/reference/llm/index.md` - Mention reasoning capture capability
- [ ] `api/CLAUDE.md` - Update LLM section if needed

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
| Phase 3 | Pending | |
| Phase 4 | Pending | |
| Phase 5 | Pending | |
| Phase 6 | Pending | |
