# LLM Reasoning Summary Capture - Work Notes

**Project**: Capture and persist LLM reasoning summaries from OpenAI models
**Started**: 2025-12-20
**Branch**: claude/add-llm-reasoning-summary-Bwz0c

---

## Session Log

### 2025-12-20 - Initial Research and Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-2, INV-3, INV-9
- Read `api/payment_simulator/llm/config.py` - understood LLMConfig structure and model settings
- Read `api/payment_simulator/llm/pydantic_client.py` - understood current PydanticAI integration
- Read `api/payment_simulator/llm/audit_wrapper.py` - understood LLMInteraction capture
- Read `api/payment_simulator/ai_cash_mgmt/persistence/models.py` - found existing llm_reasoning field
- Read Pydantic AI docs at https://ai.pydantic.dev/thinking/ - understood reasoning summary API

**Applicable Invariants**:
- INV-2: Determinism - Reasoning is metadata only, doesn't affect simulation
- INV-3: FFI Boundary - Not affected, pure Python change
- INV-9: Policy Evaluation Identity - Reasoning capture is observational

**Key Insights**:

1. **Good News**: Database already has `llm_reasoning` column in `llm_interaction_log` table
2. **Good News**: `LLMConfig` already has `reasoning_effort` for OpenAI
3. **Gap**: Missing `reasoning_summary` setting to actually get summaries
4. **Gap**: `PydanticAILLMClient` doesn't pass model settings to Agent
5. **Gap**: No extraction of ThinkingPart from PydanticAI responses
6. **Gap**: `LLMInteraction` dataclass has no reasoning field

**From Pydantic AI Documentation**:
```python
settings = OpenAIResponsesModelSettings(
    openai_reasoning_effort='low',
    openai_reasoning_summary='detailed',  # This is what we need!
)
agent = Agent(model, model_settings=settings)
```

- Reasoning appears as `ThinkingPart` objects in `result.all_messages()`
- Need to iterate messages and extract thinking parts

**Completed**:
- [x] Research Pydantic AI reasoning API
- [x] Analyze current codebase
- [x] Identify gaps
- [x] Create development plan

**Next Steps**:
1. Create phase 1 plan
2. Implement LLMConfig changes
3. Test with unit tests

---

## Phase Progress

### Phase 1: Extend LLMConfig
**Status**: Pending
**Started**:
**Completed**:

### Phase 2: Create LLMResult Wrapper
**Status**: Pending
**Started**:
**Completed**:

### Phase 3: Update PydanticAILLMClient
**Status**: Pending
**Started**:
**Completed**:

### Phase 4: Update Audit Wrapper
**Status**: Pending
**Started**:
**Completed**:

### Phase 5: Integration Tests
**Status**: Pending
**Started**:
**Completed**:

### Phase 6: CLI/Query Support
**Status**: Pending
**Started**:
**Completed**:

---

## Key Decisions

### Decision 1: Use reasoning_summary='detailed' as default when reasoning_effort is set
**Rationale**: If a user enables reasoning_effort, they likely want to see the reasoning. 'detailed' provides more useful information for understanding LLM decision-making.

### Decision 2: Reasoning extraction in PydanticAILLMClient only
**Rationale**: Single point of extraction prevents duplication and ensures consistency. The audit wrapper just captures what it receives.

### Decision 3: LLMResult wrapper vs modifying existing return types
**Rationale**: Creating a new wrapper type is cleaner than changing existing method signatures. It's backward-compatible since data is still accessible.

---

## Issues Encountered

(None yet)

---

## Files Modified

### Created
- `docs/plans/llm-reasoning-summary/development-plan.md` - Main development plan
- `docs/plans/llm-reasoning-summary/work_notes.md` - This file

### To Be Modified
- `api/payment_simulator/llm/config.py` - Add reasoning_summary field
- `api/payment_simulator/llm/pydantic_client.py` - Pass model settings, extract reasoning
- `api/payment_simulator/llm/audit_wrapper.py` - Capture reasoning in LLMInteraction
- `api/payment_simulator/llm/protocol.py` - Update protocol if needed

### To Be Created
- `api/payment_simulator/llm/result.py` - LLMResult wrapper
- `api/tests/llm/test_reasoning_capture.py` - Tests for reasoning capture

---

## Documentation Updates Required

### Reference Documentation
- [ ] `docs/reference/llm/configuration.md` - Add reasoning_summary option
- [ ] `docs/reference/llm/index.md` - Mention reasoning capture

### patterns-and-conventions.md Changes
- No new invariants needed (this is observational metadata)
- No new patterns needed (uses existing audit pattern)
