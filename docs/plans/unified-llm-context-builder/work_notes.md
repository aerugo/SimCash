# Unified LLM Context Builder - Work Notes

**Project**: Unify LLM context building across evaluation modes
**Started**: 2025-12-18
**Branch**: claude/simcash-paper-draft-6AIrp

---

## Session Log

### 2025-12-18 - Initial Analysis and Planning

**Context Review Completed**:
- Read `docs/reference/patterns-and-conventions.md` - identified applicable invariants: INV-9, INV-10, INV-11
- Read `experiments/runner/optimization.py` - understood the split between bootstrap and temporal modes
- Read `ai_cash_mgmt/prompts/single_agent_context.py` - understood context building
- Read `ai_cash_mgmt/bootstrap/context_builder.py` - understood EnrichedBootstrapContextBuilder
- Used `--audit` flag to see actual LLM prompts - confirmed temporal mode receives NO simulation output

**Applicable Invariants**:
- INV-9: Policy Evaluation Identity - context building must be consistent
- INV-10: Scenario Config Interpretation Identity - scenario extraction must be consistent
- INV-11: Agent Isolation - LLM must only see Agent X's data

**Key Insights**:
1. `deterministic-temporal` mode passes `None` for all simulation outputs (line 2357)
2. `bootstrap` mode provides full 3-stream context and works well (Exp2 matches Castro)
3. The fix is NOT about changing evaluation logic, but ensuring LLM gets simulation visibility
4. Exp2 uses bootstrap mode → A=11%, B=11% → Matches Castro
5. Exp1 uses temporal mode → A=80%, B=40% → Inverted from Castro

**Root Cause Confirmed**:
```python
# In optimization.py, temporal mode optimization:
opt_result = await self._policy_optimizer.optimize(
    ...
    events=None,  # Temporal mode doesn't use event trace
    best_seed_output=None,  # ← PROBLEM: No simulation output!
    worst_seed_output=None,  # ← PROBLEM: No simulation output!
    ...
)
```

**Completed**:
- [x] Identified root cause of Castro experiment divergence
- [x] Analyzed current context builder architecture
- [x] Created development plan
- [x] Proposed INV-12: LLM Context Identity

**Next Steps**:
1. Create Phase 1 detailed plan
2. Define LLMContextBuilderProtocol
3. Define LLMAgentContext dataclass
4. Write failing tests

---

## Phase Progress

### Phase 1: Protocol and Data Types
**Status**: Pending
**Started**:
**Completed**:

---

## Key Decisions

### Decision 1: Use Protocol Pattern (not inheritance)
**Rationale**: Follows existing project patterns (INV-9, INV-10 use Protocol). Allows different implementations while enforcing contract. Supports runtime type checking with `@runtime_checkable`.

### Decision 2: Single simulation output field (not 3 streams)
**Rationale**: For deterministic modes, there's only one simulation result. The "3 streams" (initial, best, worst) are bootstrap-specific. The unified builder should produce a single `simulation_output` that represents the relevant simulation(s).

### Decision 3: Mode-specific metadata as separate field
**Rationale**: Allows the core simulation output to be identical across modes while still providing mode-specific context (e.g., "best of 50 samples" vs "single deterministic run").

---

## Issues Encountered

(None yet)

---

## Files Modified

### Created
- `docs/plans/unified-llm-context-builder/development-plan.md` - Development plan
- `docs/plans/unified-llm-context-builder/work_notes.md` - This file

### Modified
(None yet)

---

## Documentation Updates Required

### patterns-and-conventions.md Changes
- [ ] Add INV-12: LLM Context Identity

### Other Documentation
- [ ] `api/CLAUDE.md` - Document unified context builder pattern
