# AI Cash Management Architecture Refactor - Work Notes

**Status:** In Progress
**Created:** 2025-12-10
**Last Updated:** 2025-12-10

---

## Purpose

This document tracks progress and notes during the refactor implementation. Each phase has its own TODO checklist and notes section.

---

## Phase TODO Checklists

### Phase 0: Preparation

**Status:** Not Started

- [ ] Create `api/payment_simulator/llm/` directory
- [ ] Create `api/payment_simulator/experiments/` directory structure
- [ ] Create empty `__init__.py` files
- [ ] Create `api/payment_simulator/llm/protocol.py` with protocol stubs
- [ ] Create `api/tests/llm/` directory
- [ ] Create `api/tests/experiments/` directory
- [ ] Create test fixture YAML files in `api/tests/fixtures/experiments/`
- [ ] Verify all existing tests still pass
- [ ] Commit Phase 0 changes

**Notes:**
```
(Add notes as work progresses)
```

---

### Phase 1: LLM Module Extraction

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

### Phase 2: Experiment Configuration Framework

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

### Phase 3: Experiment Runner Framework

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

### Phase 4: CLI Commands

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

### Phase 5: Castro Migration

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

### Phase 6: Documentation

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
| | | |

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

### Phase 0
```
Created:
  - api/payment_simulator/llm/__init__.py
  - api/payment_simulator/llm/protocol.py
  - ...

Modified:
  - (none expected)

Deleted:
  - (none expected)
```

### Phase 1
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

### Phase 2-6
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
