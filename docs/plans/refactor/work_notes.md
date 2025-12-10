# AI Cash Management Architecture Refactor - Work Notes

**Status:** In Progress
**Created:** 2025-12-10
**Last Updated:** 2025-12-10

---

## Purpose

This document tracks progress and notes during the refactor implementation. Each phase has its own TODO checklist and notes section.

---

## Phase TODO Checklists

### Phase 0: Fix Bootstrap Paired Comparison Bug (Critical)

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/experiments/castro/test_bootstrap_paired_comparison.py`
- [x] Test: same samples used for old and new policy (`test_compute_paired_deltas_returns_matching_indices`)
- [x] Test: acceptance based on paired delta, not absolute costs (`test_acceptance_based_on_paired_delta_not_absolute`)
- [x] Test: evaluator is deterministic (`test_evaluate_same_sample_twice_returns_identical_results`)
- [x] Test: order preserved (`test_evaluate_samples_preserves_order`)
- [x] All 7 tests pass

**Implementation:**
- [x] Modify `runner.py` to store bootstrap samples after generation (line 748: `samples_per_agent` dict)
- [x] Modify `_evaluate_policies()` return type to include samples (5-tuple now)
- [x] Modify `runner.py` to use SAME samples for new policy evaluation
- [x] Use `compute_paired_deltas()` for policy comparison (line 437)
- [x] Accept based on mean delta > 0 (positive delta = old costs more than new)
- [x] Verify all tests pass (98 bootstrap tests + 7 new tests)
- [ ] Run `castro run exp1 --verbose-monte-carlo` to verify paired deltas shown (DEFERRED - needs LLM API key)
- [ ] Commit Phase 0 changes

**Notes:**
```
2025-12-10: BUG IDENTIFIED AND FIXED
- The compute_paired_deltas() method EXISTED in evaluator.py but was NEVER called
- runner.py was generating NEW samples for each _evaluate_policies() call
- This broke statistical validity of policy comparisons

FIX IMPLEMENTED:
1. Modified _evaluate_policies() to return samples_per_agent dict
2. Modified policy comparison logic to use compute_paired_deltas()
3. Policy acceptance now based on mean_delta > 0 (positive = new policy cheaper)
4. Old buggy code: re-called _evaluate_policies() which generated NEW samples
5. New correct code: passes stored samples to compute_paired_deltas()

KEY CODE CHANGES:
- runner.py lines 704-835: _evaluate_policies() now returns 5-tuple including samples
- runner.py lines 421-503: Policy comparison now uses compute_paired_deltas()
- Console output now shows "mean delta" for paired comparison

TEST RESULTS:
- api/tests/experiments/castro/test_bootstrap_paired_comparison.py: 7/7 passed
- api/tests/ai_cash_mgmt/unit/bootstrap/: 98/98 passed
```

---

### Phase 0.5: Add Event Tracing to Bootstrap Sandbox

**Status:** COMPLETED (2025-12-10)

**Tests First (TDD):**
- [x] Write `tests/ai_cash_mgmt/unit/bootstrap/test_enriched_evaluation.py`
- [x] Test: `BootstrapEvent` is frozen (immutable)
- [x] Test: `CostBreakdown.total` sums all costs
- [x] Test: All costs are integer cents (INV-1)
- [x] Test: `EnrichedEvaluationResult` contains event trace
- [x] Write `experiments/castro/tests/test_bootstrap_context.py`
- [x] Test: `get_best_result()` returns lowest cost
- [x] Test: `get_worst_result()` returns highest cost
- [x] Test: `format_event_trace_for_llm()` limits events
- [x] Test: `build_agent_context()` returns AgentSimulationContext

**Implementation:**
- [x] Create `api/payment_simulator/ai_cash_mgmt/bootstrap/enriched_models.py`
  - [x] Add `BootstrapEvent` dataclass
  - [x] Add `CostBreakdown` dataclass
  - [x] Add `EnrichedEvaluationResult` dataclass
- [x] Update `bootstrap/__init__.py` with exports
- [x] Create `experiments/castro/castro/bootstrap_context.py`
  - [x] Implement `BootstrapContextBuilder` class
  - [x] Implement `get_best_result()` and `get_worst_result()`
  - [x] Implement `format_event_trace_for_llm()` with event prioritization
  - [x] Implement `build_agent_context()` returning AgentSimulationContext
- [ ] Add `evaluate_sample_enriched()` to `bootstrap/evaluator.py` (DEFERRED - optional enhancement)
- [ ] Update `runner.py` to use enriched evaluation (DEFERRED - optional enhancement)

**Notes:**
```
2025-12-10: PHASE 0.5 COMPLETE
Session 1:
- Created enriched_models.py with BootstrapEvent, CostBreakdown, EnrichedEvaluationResult
- All 12 enriched model tests pass
- Total bootstrap tests: 110 (98 original + 12 new)

Session 2:
- Created BootstrapContextBuilder in castro
- All 10 context builder tests pass
- Context builder features:
  * get_best_result() / get_worst_result() - find best/worst samples
  * format_event_trace_for_llm() - priority-based event filtering
  * build_agent_context() - compatible with existing prompt system
  * Event prioritization (PolicyDecision > Cost > Settlement > Arrival)

DEFERRED TO PHASE 1+:
- evaluate_sample_enriched() method (requires deeper evaluator refactor)
- Wiring up runner.py to use enriched evaluation

The foundation is now in place:
- BootstrapEvent, CostBreakdown, EnrichedEvaluationResult models
- BootstrapContextBuilder for transforming results to LLM context
- Can be integrated incrementally into runner.py later
```

---

### Phase 1: Preparation (Pre-Refactor)

**Status:** COMPLETED (2025-12-10)

- [x] Create `api/payment_simulator/llm/` directory
- [x] Create `api/payment_simulator/experiments/` directory structure
- [x] Create empty `__init__.py` files
- [x] Create `api/payment_simulator/llm/protocol.py` with protocol stubs
- [x] Create `api/tests/llm/` directory
- [x] Create `api/tests/experiments/` directory
- [ ] Create test fixture YAML files in `api/tests/fixtures/experiments/` (DEFERRED to Phase 3)
- [x] Verify all existing tests still pass
- [x] Commit Phase 1 changes

**Notes:**
```
2025-12-10: PHASE 1 COMPLETE
- Created api/payment_simulator/llm/ module with:
  - __init__.py - exports LLMClientProtocol
  - protocol.py - LLMClientProtocol with @runtime_checkable
    * generate_structured_output() method
    * generate_text() method

- Created api/payment_simulator/experiments/ module with:
  - __init__.py
  - config/__init__.py - placeholder for experiment config loader
  - runner/__init__.py - placeholder for experiment runner
  - persistence/__init__.py - placeholder for experiment persistence

- Created test structure:
  - api/tests/llm/test_protocol.py - 6 tests for LLMClientProtocol
  - api/tests/experiments/test_module_structure.py - 4 tests for module imports

TEST RESULTS:
- LLM protocol tests: 6/6 passed
- Experiments module structure tests: 4/4 passed
- All existing tests continue to pass

Note: Test fixture YAML files deferred to Phase 3 (Experiment Config Framework)
since they require the ExperimentConfig schema to be defined first.
```

---

### Phase 2: LLM Module Extraction

**Status:** Not Started

**Tests First (TDD):**
- [ ] Write `tests/llm/test_config.py`
- [ ] Write `tests/llm/test_pydantic_client.py`
- [ ] Write `tests/llm/test_audit_wrapper.py`
- [ ] Verify tests fail (as expected before implementation)

**Implementation:**
- [ ] Create `api/payment_simulator/llm/config.py` - LLMConfig dataclass
- [ ] Create `api/payment_simulator/llm/pydantic_client.py` - PydanticAI implementation
- [ ] Create `api/payment_simulator/llm/audit_wrapper.py` - Audit capture wrapper
- [ ] Update `api/payment_simulator/llm/__init__.py` with exports
- [ ] Verify all LLM tests pass
- [ ] Verify mypy type checking passes
- [ ] Commit Phase 1 changes

**Notes:**
```
(Add notes as work progresses)
```

---

### Phase 3: Experiment Configuration Framework

**Status:** Not Started

**Tests First (TDD):**
- [ ] Write `tests/experiments/config/test_experiment_config.py`
- [ ] Create valid YAML test fixtures
- [ ] Create invalid YAML test fixtures (for error cases)
- [ ] Verify tests fail (as expected before implementation)

**Implementation:**
- [ ] Create `api/payment_simulator/experiments/config/experiment_config.py`
- [ ] Implement `ExperimentConfig.from_yaml()` method
- [ ] Implement `EvaluationConfig` dataclass
- [ ] Implement `OutputConfig` dataclass
- [ ] Implement `load_constraints()` method for dynamic import
- [ ] Update `api/payment_simulator/experiments/__init__.py`
- [ ] Verify all config tests pass
- [ ] Verify mypy passes
- [ ] Commit Phase 2 changes

**Notes:**
```
(Add notes as work progresses)
```

---

### Phase 4: Experiment Runner Framework

**Status:** Not Started

**Tests First (TDD):**
- [ ] Write `tests/experiments/runner/test_protocol.py`
- [ ] Write `tests/experiments/runner/test_base_runner.py`
- [ ] Write `tests/experiments/runner/test_output.py`
- [ ] Create mock evaluator and LLM client for testing
- [ ] Verify tests fail (as expected before implementation)

**Implementation:**
- [ ] Create `api/payment_simulator/experiments/runner/protocol.py`
- [ ] Create `api/payment_simulator/experiments/runner/output.py`
- [ ] Create `api/payment_simulator/experiments/runner/base_runner.py`
- [ ] Implement core optimization loop
- [ ] Implement `RichConsoleOutput` handler
- [ ] Implement `SilentOutput` handler (for testing)
- [ ] Integration test with mock components
- [ ] Verify all runner tests pass
- [ ] Commit Phase 3 changes

**Notes:**
```
(Add notes as work progresses)
```

---

### Phase 5: CLI Commands

**Status:** Not Started

**Tests First (TDD):**
- [ ] Write `tests/cli/test_experiment_commands.py`
- [ ] Test `run` command with mock runner
- [ ] Test `validate` command
- [ ] Test `list` command
- [ ] Test `info` command
- [ ] Test `template` command

**Implementation:**
- [ ] Create `api/payment_simulator/cli/commands/experiment.py`
- [ ] Implement `run` command
- [ ] Implement `validate` command
- [ ] Implement `list` command
- [ ] Implement `info` command
- [ ] Implement `template` command
- [ ] Register commands in main CLI app
- [ ] Test CLI manually
- [ ] Commit Phase 4 changes

**Notes:**
```
(Add notes as work progresses)
```

---

### Phase 6: Castro Migration

**Status:** Not Started

**Preparation:**
- [ ] Audit current Castro code for dependencies
- [ ] Document current experiment definitions (exp1, exp2, exp3)
- [ ] Create migration checklist for each experiment

**YAML Creation:**
- [ ] Create `experiments/castro/experiments/exp1.yaml`
- [ ] Create `experiments/castro/experiments/exp2.yaml`
- [ ] Create `experiments/castro/experiments/exp3.yaml`
- [ ] Validate YAML files with experiment framework

**Code Migration:**
- [ ] Update Castro CLI to use `payment_simulator.llm`
- [ ] Update Castro CLI to use experiment config loader
- [ ] Simplify `castro/runner.py` to use `BaseExperimentRunner`
- [ ] Remove `castro/pydantic_llm_client.py` (use llm module)
- [ ] Remove `castro/model_config.py` (merged into llm module)
- [ ] Update `castro/experiments.py` to load from YAML

**Verification:**
- [ ] Run `castro run exp1` - verify works
- [ ] Run `castro run exp2` - verify works
- [ ] Run `castro run exp3` - verify works
- [ ] Run `castro replay` - verify works
- [ ] All Castro tests pass
- [ ] Commit Phase 5 changes

**Notes:**
```
(Add notes as work progresses)
```

---

### Phase 7: Documentation

**Status:** Not Started

**LLM Module Docs:**
- [ ] Create `docs/reference/llm/index.md`
- [ ] Create `docs/reference/llm/configuration.md`
- [ ] Create `docs/reference/llm/protocols.md`
- [ ] Create `docs/reference/llm/providers.md`
- [ ] Create `docs/reference/llm/audit.md`

**Experiments Module Docs:**
- [ ] Create `docs/reference/experiments/index.md`
- [ ] Create `docs/reference/experiments/configuration.md`
- [ ] Create `docs/reference/experiments/runner.md`
- [ ] Create `docs/reference/experiments/cli.md`
- [ ] Create `docs/reference/experiments/persistence.md`
- [ ] Create `docs/reference/experiments/extending.md`

**Updates:**
- [ ] Update `docs/reference/ai_cash_mgmt/index.md`
- [ ] Update `docs/reference/castro/index.md` (simplify)
- [ ] Create `docs/reference/architecture/XX-experiment-framework.md`
- [ ] Update main `CLAUDE.md` with new module info

**Verification:**
- [ ] All docs render correctly
- [ ] Code examples work
- [ ] Cross-references valid
- [ ] Commit Phase 6 changes

**Notes:**
```
(Add notes as work progresses)
```

---

## General Notes

### Decisions Made

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-12-10 | Split into 3 modules (ai_cash_mgmt, llm, experiments) | Clean separation of concerns |
| 2025-12-10 | YAML-driven experiment configs | Enable non-programmer experiment definition |
| 2025-12-10 | Keep Castro lightweight | Only Castro-specific constraints and YAML |

### Issues Encountered

| Date | Issue | Resolution |
|------|-------|------------|
| 2025-12-10 | runner.py generated NEW samples for each _evaluate_policies() call | Fixed by returning samples from _evaluate_policies() and using compute_paired_deltas() |
| 2025-12-10 | Test policy had duplicate node_id "hold" in both trees | Fixed by using unique node_ids: "hold_payment" and "hold_collateral" |

### Performance Notes

| Date | Observation | Action |
|------|-------------|--------|
| | | |

### Test Coverage Notes

| Phase | Target | Actual | Notes |
|-------|--------|--------|-------|
| Phase 1 | 90% | - | |
| Phase 2 | 90% | - | |
| Phase 3 | 90% | - | |
| Phase 4 | 80% | - | |
| Phase 5 | 85% | - | |

---

## Integration Testing Log

### Pre-Refactor Baseline

Before starting refactor, capture baseline metrics:

```bash
# Run full test suite and record results
cd api && .venv/bin/python -m pytest --tb=short 2>&1 | tee ../docs/plans/refactor/baseline_tests.log

# Record test counts
# Date:
# Total tests:
# Passed:
# Failed:
# Duration:
```

### Post-Phase Verification

After each phase, verify no regressions:

```bash
# Phase X verification
# Date:
# Total tests:
# Passed:
# Failed:
# New tests added:
```

---

## Files Changed Log

Track all files changed during refactor for review:

### Phase 0: Bootstrap Bug Fix
```
Created:
  - api/tests/experiments/castro/test_bootstrap_paired_comparison.py

Modified:
  - experiments/castro/castro/runner.py (store and reuse samples)
  - api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py (verify compute_paired_deltas)

Deleted:
  - (none)
```

### Phase 0.5: Event Tracing
```
Created:
  - api/payment_simulator/ai_cash_mgmt/bootstrap/models.py
  - experiments/castro/castro/bootstrap_context.py
  - api/tests/ai_cash_mgmt/bootstrap/test_enriched_evaluation.py
  - api/tests/experiments/castro/test_bootstrap_context.py

Modified:
  - api/payment_simulator/ai_cash_mgmt/bootstrap/evaluator.py (add evaluate_sample_enriched)
  - experiments/castro/castro/runner.py (use enriched evaluation)

Deprecated:
  - experiments/castro/castro/context_builder.py (replaced by bootstrap_context.py)
```

### Phase 1: Preparation
```
Created:
  - api/payment_simulator/llm/__init__.py
  - api/payment_simulator/llm/protocol.py
  - api/payment_simulator/experiments/__init__.py
  - api/payment_simulator/experiments/config/__init__.py
  - api/payment_simulator/experiments/runner/__init__.py
  - api/payment_simulator/experiments/persistence/__init__.py
  - api/tests/llm/__init__.py
  - api/tests/experiments/__init__.py
  - api/tests/fixtures/experiments/test_experiment.yaml

Modified:
  - (none expected)

Deleted:
  - (none expected)
```

### Phase 2: LLM Module
```
Created:
  - api/payment_simulator/llm/config.py
  - api/payment_simulator/llm/pydantic_client.py
  - api/payment_simulator/llm/audit_wrapper.py
  - api/tests/llm/test_config.py
  - api/tests/llm/test_pydantic_client.py
  - api/tests/llm/test_audit_wrapper.py

Modified:
  - api/payment_simulator/llm/__init__.py

Deleted:
  - (none expected)
```

### Phases 3-7
```
(Fill in as work progresses)
```

---

## Quick Reference

### Running Tests

```bash
# All tests
cd api && .venv/bin/python -m pytest

# LLM module tests
.venv/bin/python -m pytest tests/llm/ -v

# Experiments module tests
.venv/bin/python -m pytest tests/experiments/ -v

# Type checking
.venv/bin/python -m mypy payment_simulator/llm/
.venv/bin/python -m mypy payment_simulator/experiments/

# Lint checking
.venv/bin/python -m ruff check payment_simulator/llm/
.venv/bin/python -m ruff check payment_simulator/experiments/
```

### Key File Locations

| Component | Location |
|-----------|----------|
| LLM Module | `api/payment_simulator/llm/` |
| Experiments Module | `api/payment_simulator/experiments/` |
| Castro Experiments | `experiments/castro/` |
| Test Fixtures | `api/tests/fixtures/experiments/` |
| Reference Docs | `docs/reference/` |

---

*Last updated: 2025-12-10*
