# New Optimizer Work Notes

## Current Session: 2025-12-12

### Status
- [x] Created main plan document (`new-optimizer-plan.md`)
- [x] Created directory structure
- [x] Phase 1 COMPLETE
  - Created `api/tests/ai_cash_mgmt/unit/test_schema_injection.py` (36 tests)
  - Created `api/payment_simulator/ai_cash_mgmt/prompts/schema_injection.py`
  - All tests pass, mypy passes
- [x] Phase 2 COMPLETE
  - Created `api/tests/ai_cash_mgmt/unit/test_system_prompt_builder.py` (32 tests)
  - Created `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py`
  - All tests pass, mypy passes
- [x] Phase 3 COMPLETE
  - Created `api/tests/ai_cash_mgmt/unit/test_event_filter.py` (39 tests)
  - Created `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py`
  - Created `api/tests/ai_cash_mgmt/unit/test_user_prompt_builder.py` (34 tests)
  - Created `api/payment_simulator/ai_cash_mgmt/prompts/user_prompt_builder.py`
  - All tests pass (73 total), mypy passes
- [ ] Phase 4 pending - Integration with optimization loop
- [ ] Phase 5 pending - Testing and validation

### Phase 1 Summary
Implemented schema injection helpers:
- `get_filtered_policy_schema(constraints)` - Filters Rust policy schema by constraints
- `get_filtered_cost_schema(cost_rates)` - Formats cost documentation
- `format_parameter_bounds(params)` - Formats parameter specs with ranges
- `format_field_list(fields)` - Formats allowed fields
- `format_action_list(tree_type, actions)` - Formats actions per tree

### Phase 2 Summary
Implemented system prompt builder:
- `SystemPromptBuilder` class with fluent API
- `build_system_prompt()` convenience function
- Includes: expert introduction, domain explanation, cost objectives,
  policy architecture, optimization process, checklist, schemas, errors
- Castro mode support for paper alignment experiments

### Phase 3 Summary
Implemented event filtering and user prompt builder:

**Event Filter (`event_filter.py`)**:
- `filter_events_for_agent(agent_id, events)` - Filters events to only those visible to agent
- `format_filtered_output(agent_id, events)` - Formats filtered events as readable text
- Strict agent isolation: Agent X only sees:
  - Outgoing transactions FROM Agent X
  - Incoming liquidity events TO Agent X
  - Agent X's own state changes (collateral, costs, budget)
- Handles 15+ event types with correct filtering logic

**User Prompt Builder (`user_prompt_builder.py`)**:
- `UserPromptBuilder` class with fluent API
- `build_user_prompt()` convenience function
- Sections: Current Policy (JSON), Simulation Output (filtered), Cost Breakdown, Iteration History, Instructions
- Integrates with event filter for strict agent isolation
- Dollar formatting for all cost values

### Next Steps
1. Phase 4: Integration with optimization loop
2. Phase 5: Testing and validation

### Notes
- The Rust side already has comprehensive schema documentation:
  - `simulator/src/policy/tree/schema_docs.rs` - Policy schemas
  - `simulator/src/costs/schema_docs.rs` - Cost schemas
- Python FFI already exposes `get_policy_schema()` and `get_cost_schema()`
- Need to add filtering logic based on `ScenarioConstraints`

### Key Files Reviewed
- `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py` - Current optimizer
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` - Current prompt builder
- `api/payment_simulator/ai_cash_mgmt/constraints/scenario_constraints.py` - Constraints
- `docs/archive/policy_agent_prompt.md` - Archived prompt template (useful reference)
- `docs/archive/constraints.md` - Archived constraints documentation
- `docs/archive/castro_constraints.md` - Castro-specific constraints

### Decisions Made
1. Complete rewrite, no backwards compatibility needed
2. Use dynamic schema filtering based on scenario constraints
3. Maintain strict agent isolation in event filtering
4. Follow TDD for all new code

---

## Previous Sessions

(No previous sessions for this feature)
