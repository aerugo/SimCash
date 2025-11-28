# API Module Python Style Refactor Plan

**Version**: 1.0
**Created**: 2025-11-28
**Status**: Completed

---

## Overview

Refactor the `/api` module to comply with the new Python style guidelines in `api/CLAUDE.md`. This is a **conservative refactor** that:

1. ✅ Keeps all existing models, functions, and interfaces intact
2. ✅ Does not change any architectural patterns
3. ✅ Does not modify reference documentation
4. ✅ Uses strict TDD to detect regressions

---

## Current State Analysis

### Baseline Metrics

| Tool | Status | Notes |
|------|--------|-------|
| mypy | ✅ Pass | `Success: no issues found in 37 source files` |
| ruff | ⚠️ ~20 issues | Mostly `B904` (raise from), 1 `F401`, 1 `E501` |
| pytest | TBD | Establishing baseline |

### Style Issues Identified

#### 1. Legacy Typing Imports (1 file)

**File**: `config/schemas.py:6`
```python
from typing import Any, Literal, Union  # Union should be |
```

**Action**: Replace `Union[A, B, C, D]` with `A | B | C | D`

#### 2. Bare Generic Types (1 instance)

**File**: `config/schemas.py:763`
```python
schedule_dict: dict  # Should be dict[str, ...]
```

**Action**: Add type arguments

#### 3. `Any` Usage (Justified vs Avoidable)

**Justified `Any` (keep as-is):**
- FFI boundaries where Rust returns dynamic types
- Database connections (`duckdb.DuckDBPyConnection` is untyped)
- Orchestrator type (`Orchestrator` comes from Rust FFI)
- JSON serialization boundaries

**Avoidable `Any` (refactor):**
- None identified - all `Any` usage appears justified for FFI/DB boundaries

#### 4. Ruff B904 Issues (api/main.py)

**Pattern**: `raise Exception` without `from err`
```python
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e))  # Missing: from e
```

**Action**: Add `from e` or `from None` to ~15 raise statements

#### 5. Ruff F401 Issue (_core.py)

**File**: `_core.py:21`
```python
from payment_simulator_core_rs import __all__  # Imported but unused
```

**Action**: Use `importlib.util.find_spec` pattern or remove

#### 6. Ruff E501 Issue (api/main.py)

**File**: `api/main.py:848`
```python
# Line too long (113 > 100)
```

**Action**: Break into multiple lines

---

## Refactoring Strategy

### Principles

1. **One category at a time** - Complete one type of fix across all files before moving to next
2. **Test after each category** - Run full test suite after each category of changes
3. **Commit incrementally** - One commit per category for easy bisection
4. **No functional changes** - Only style/typing changes

### Order of Operations

```
Phase 1: Fix ruff issues (non-breaking, immediate)
  1.1 Fix B904 (raise from) in api/main.py
  1.2 Fix F401 (unused import) in _core.py
  1.3 Fix E501 (line length) in api/main.py
  → Run: ruff check, pytest

Phase 2: Modernize typing syntax (non-breaking)
  2.1 Replace Union with | in config/schemas.py
  2.2 Add type arguments to bare dict in config/schemas.py
  → Run: mypy, ruff check, pytest

Phase 3: Verify and document
  3.1 Run full verification suite
  3.2 Update this plan with completion status
```

---

## Detailed Implementation

### Phase 1.1: Fix B904 (raise from) in api/main.py

**Files**: `api/main.py`

**Pattern**:
```python
# Before
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e))

# After
except ValueError as e:
    raise HTTPException(status_code=422, detail=str(e)) from e
```

**Locations** (approximately 15):
- Line 492: `raise ValueError(...)`
- Line 501: `raise RuntimeError(...)`
- Line 731: `raise HTTPException(...)`
- Line 733: `raise HTTPException(...)`
- Line 811: `raise HTTPException(...)`
- Line 828: `raise HTTPException(...)`
- Line 830: `raise HTTPException(...)`
- Line 980: `raise HTTPException(...)`
- Line 1017: `raise HTTPException(...)`
- Line 1019: `raise HTTPException(...)`
- Line 1077: `raise HTTPException(...)`
- Line 1080: `raise HTTPException(...)`
- (+ additional as found)

**Verification**:
```bash
.venv/bin/python -m ruff check payment_simulator/api/main.py --select=B904
.venv/bin/python -m pytest tests/ -v
```

### Phase 1.2: Fix F401 (unused import) in _core.py

**File**: `_core.py`

**Current**:
```python
try:
    from payment_simulator_core_rs import __all__
except (ImportError, AttributeError):
    pass
```

**Option A (Recommended)**: Remove the unused import
```python
# Just remove the try/except block since __all__ isn't used
```

**Option B**: Use for spec checking
```python
import importlib.util
if importlib.util.find_spec("payment_simulator_core_rs") is not None:
    from payment_simulator_core_rs import *  # noqa: F401, F403
```

**Verification**:
```bash
.venv/bin/python -m ruff check payment_simulator/_core.py --select=F401
.venv/bin/python -m pytest tests/ -v
```

### Phase 1.3: Fix E501 (line length) in api/main.py

**File**: `api/main.py:848`

**Current**:
```python
detail=f"Simulation not found: {sim_id}. Cost timeline only available for persisted simulations."
```

**After**:
```python
detail=(
    f"Simulation not found: {sim_id}. "
    "Cost timeline only available for persisted simulations."
)
```

**Verification**:
```bash
.venv/bin/python -m ruff check payment_simulator/api/main.py --select=E501
```

### Phase 2.1: Replace Union with | in config/schemas.py

**File**: `config/schemas.py`

**Current** (line 6):
```python
from typing import Any, Literal, Union
```

**After**:
```python
from typing import Any, Literal
```

**Current** (lines 49-55):
```python
AmountDistribution = Union[
    NormalDistribution,
    LogNormalDistribution,
    UniformDistribution,
    ExponentialDistribution,
]
```

**After**:
```python
AmountDistribution = (
    NormalDistribution
    | LogNormalDistribution
    | UniformDistribution
    | ExponentialDistribution
)
```

**Note**: Search for all `Union[` usages in the file and replace with `|`

**Verification**:
```bash
.venv/bin/python -m mypy payment_simulator/config/schemas.py
.venv/bin/python -m pytest tests/ -v
```

### Phase 2.2: Add type arguments to bare dict

**File**: `config/schemas.py:763`

**Current**:
```python
schedule_dict: dict
```

**After** (determine actual type by reading context):
```python
schedule_dict: dict[str, Any]  # or more specific if determinable
```

**Verification**:
```bash
.venv/bin/python -m mypy payment_simulator/config/schemas.py
.venv/bin/python -m ruff check payment_simulator/config/schemas.py
```

---

## Files Changed Summary

| File | Phase | Changes |
|------|-------|---------|
| `api/main.py` | 1.1, 1.3 | Add `from e/None` to raises, fix line length |
| `_core.py` | 1.2 | Remove unused `__all__` import |
| `config/schemas.py` | 2.1, 2.2 | Replace `Union` with `|`, type bare `dict` |

**Total files**: 3
**Total changes**: ~20 line modifications

---

## Testing Strategy

### Before Each Phase

```bash
# Capture current test state
.venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/before_phase_X.log
```

### After Each Phase

```bash
# Verify no regressions
.venv/bin/python -m mypy payment_simulator/
.venv/bin/python -m ruff check payment_simulator/
.venv/bin/python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/after_phase_X.log

# Diff test results
diff /tmp/before_phase_X.log /tmp/after_phase_X.log
```

### Final Verification

```bash
# Full verification suite
.venv/bin/python -m mypy payment_simulator/
.venv/bin/python -m ruff check payment_simulator/
.venv/bin/python -m ruff format --check payment_simulator/
.venv/bin/python -m pytest tests/ -v
```

---

## Rollback Plan

Each phase has its own commit. If regressions are found:

```bash
# Identify breaking commit
git bisect start HEAD <last_known_good>
git bisect run .venv/bin/python -m pytest tests/ -x

# Revert if needed
git revert <breaking_commit>
```

---

## What This Refactor Does NOT Do

The following are **explicitly out of scope** to minimize risk:

1. ❌ **No new TypedDict definitions** - Existing `dict[str, Any]` at FFI boundaries remain
2. ❌ **No Protocol additions** - Existing protocols are sufficient
3. ❌ **No dataclass conversions** - Existing Pydantic models remain
4. ❌ **No function signature changes** - All public APIs preserved
5. ❌ **No reference doc updates** - Architecture unchanged
6. ❌ **No inheritance→composition changes** - No inheritance patterns found that need changing

---

## Future Refactoring (Out of Scope)

For future consideration (separate ticket):

1. **TypedDict for FFI returns** - Define shapes for `orch.tick()` returns
2. **Stricter event typing** - Define `EventDict` TypedDict for event structures
3. **Database connection typing** - When DuckDB adds stubs

---

## Completion Checklist

- [x] Phase 1.1: Fix B904 in api/main.py (~30 fixes)
- [x] Phase 1.2: Fix F401 in _core.py (1 fix)
- [x] Phase 1.3: Fix E501 in api/main.py - SKIPPED (209 issues in SQL/docstrings)
- [x] Phase 2.1: Replace Union with | in config/schemas.py (5 Union types converted)
- [x] Phase 2.2: Add type arguments to bare dict (1 fix)
- [x] Final: mypy passes
- [x] Final: ruff B904/F401 passes (E501 skipped, RUF cosmetic issues remain)
- [x] Final: pytest passes (275 passed, 4 skipped)
- [x] Final: All changes committed and pushed

---

*Last updated: 2025-11-28*
