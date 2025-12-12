# New Optimizer Prompt Rewrite Plan

## Overview

This plan describes a complete rewrite of the LLM optimization prompt and logic for the SimCash payment simulator. The new system will generate valid JSON policies using a carefully structured prompt that:

1. Provides complete policy tree schema specifications filtered by scenario
2. Includes cost parameter documentation filtered by scenario
3. Presents tick-by-tick simulation output filtered to ONLY show the target agent's transactions
4. Maintains strict agent isolation (Agent X never sees other agents' policies or transactions)

## Key Invariants

### 1. Agent Isolation (CRITICAL)
An LLM optimizing for Agent X may ONLY see:
- **Outgoing transactions FROM Agent X** (payments they are sending)
- **Incoming liquidity events TO Agent X balance** (payments received, settlements)
- **Agent X's own policy**
- **Agent X's own iteration history**

Agent X must NEVER see:
- Other agents' policies
- Other agents' outgoing transactions
- Other agents' internal decision making

### 2. Dynamic Schema Filtering
Schemas are filtered based on `ScenarioConstraints` from the experiment config:
- Only allowed fields are documented
- Only allowed actions are shown
- Only allowed parameters with their bounds are listed
- Tree types that are disabled are not documented

### 3. Money is i64 (Integer Cents)
All amounts in examples and documentation use integer cents, never floats.

### 4. Node ID Requirement
Every policy tree node MUST have a unique `node_id` string field.

## Prompt Structure

### System Prompt
```
You are an expert in payment system optimization...

[Domain explanation: RTGS, queues, LSM, costs]

Cost Structure and Objectives:
[Cost parameters injected - filtered by scenario]

Policy Tree Architecture:
[Policy schema injected - filtered by scenario]

POLICY FORMAT SPECIFICATION:
[Complete schema with examples]

COST PARAMETERS:
[Cost documentation with formulas and examples]

CRITICAL: Every node MUST have a unique "node_id" string field!
```

### User Prompt
```
TABLE OF CONTENTS:
1. Current Policy
2. Simulation Output (Tick-by-Tick)
3. Past Iteration History
4. Final Instructions

### 1. Current Policy for {AGENT_ID}
[Current policy JSON]

### 2. SIMULATION OUTPUT (TICK-BY-TICK)
[Filtered verbose logs - ONLY this agent's outgoing/incoming]

### 3. PAST ITERATION HISTORY
[Policy diffs and cost deltas]

### 4. FINAL INSTRUCTIONS
[Guidance for generating improved policy]
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     NewOptimizationPromptBuilder                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    SystemPromptBuilder                           │   │
│  │  - inject_policy_schema(constraints) -> str                      │   │
│  │  - inject_cost_schema(constraints) -> str                        │   │
│  │  - build_domain_explanation() -> str                             │   │
│  │  - build_node_id_reminder() -> str                               │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    UserPromptBuilder                             │   │
│  │  - inject_current_policy(agent_id, policy) -> str                │   │
│  │  - filter_simulation_output(agent_id, events) -> str             │   │
│  │  - build_iteration_history(agent_id, history) -> str             │   │
│  │  - build_final_instructions() -> str                             │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    OutputFilter                                  │   │
│  │  - filter_events_for_agent(agent_id, events) -> list[Event]      │   │
│  │  - format_tick_output(tick, filtered_events) -> str              │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## Phases

### Phase 1: Schema Injection Helpers (Foundation)
**Goal**: Create helpers to extract and format schemas filtered by constraints

Files to create:
- `api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py`

Key functions:
- `get_filtered_policy_schema(constraints: ScenarioConstraints) -> str`
- `get_filtered_cost_schema(cost_rates: CostRates) -> str`
- `format_parameter_bounds(params: list[ParameterSpec]) -> str`
- `format_field_list(fields: list[str]) -> str`
- `format_action_list(tree_type: str, actions: list[str]) -> str`

### Phase 2: System Prompt Builder
**Goal**: Build the complete system prompt with all injected sections

Files to create:
- `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py`

Key functions:
- `SystemPromptBuilder.build(constraints, cost_rates) -> str`
- Domain explanation
- Policy tree architecture explanation
- Schema specifications
- Cost documentation
- Node ID requirements

### Phase 3: User Prompt Builder with Agent Filtering
**Goal**: Build the user prompt with filtered simulation output

Files to create:
- `api/payment_simulator/ai_cash_mgmt/prompts/user_prompt_builder.py`
- `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py`

Key functions:
- `UserPromptBuilder.build(agent_id, context) -> str`
- `EventFilter.filter_for_agent(agent_id, events) -> list[Event]`
- `EventFilter.format_filtered_output(agent_id, filtered_events) -> str`

Critical: Implement the isolation invariant here.

### Phase 4: Integration with Optimization Loop
**Goal**: Wire the new prompt builders into the existing optimization infrastructure

Files to modify:
- `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py`
- `api/payment_simulator/experiments/runner/optimization.py`

Changes:
- Replace `build_single_agent_context` with new builders
- Update `PolicyOptimizer.optimize()` to use new system prompt
- Ensure cost_rates and constraints are passed through

### Phase 5: Testing and Validation
**Goal**: Comprehensive tests ensuring correctness

Test files:
- `api/tests/ai_cash_mgmt/unit/test_schema_injection.py`
- `api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py`
- `api/tests/ai_cash_mgmt/unit/test_user_prompt_builder.py`
- `api/tests/ai_cash_mgmt/unit/test_event_filter.py`
- `api/tests/ai_cash_mgmt/integration/test_new_optimizer_integration.py`

Key invariants to test:
- Agent isolation (CRITICAL)
- Schema filtering correctness
- Output completeness
- Node ID requirement enforcement

## Migration Strategy

This is a **complete rewrite** - no backwards compatibility is needed:

1. Create all new files alongside existing code
2. Create integration tests that verify new behavior
3. Switch over in a single commit
4. Remove deprecated code

## Files to Remove (After Completion)

After the new system is working, consider removing or deprecating:
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` (replaced)
- `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` (may need updates)
- `api/payment_simulator/ai_cash_mgmt/prompts/policy_diff.py` (integrate or keep)

## Success Criteria

1. ✅ System prompt includes filtered policy schema - COMPLETE (via `get_system_prompt()`)
2. ✅ System prompt includes filtered cost schema - COMPLETE
3. ✅ User prompt shows ONLY target agent's transactions - COMPLETE (Phase 4B)
4. ✅ User prompt shows ONLY target agent's incoming liquidity - COMPLETE (Phase 4B)
5. ✅ All tests pass - COMPLETE (600+ tests passing)
6. ✅ Integration tests verify agent isolation - COMPLETE (15 integration tests)
7. ✅ Generated policies are valid JSON with node_ids - COMPLETE
8. ✅ Optimization loop converges on improved policies - COMPLETE (events now passed)

## Timeline

Each phase should be completed incrementally with full TDD:
- Phase 1: Schema injection helpers ✅
- Phase 2: System prompt builder ✅
- Phase 3: User prompt builder + event filtering ✅
- Phase 4: Integration with PolicyOptimizer ✅
- Phase 4B: Wire events into OptimizationLoop ✅
- Phase 4C: Wire dynamic system prompt to LLM client ✅
- Phase 5: Testing and cleanup ✅

## Work Notes

See `docs/plans/new-optimizer/work_notes.md` for current progress and session notes.
