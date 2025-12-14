# Phase 1: Policy Diff Calculator

## Overview

Create a module for computing human-readable diffs between policy dictionaries.

**Status**: In Progress
**Start Date**: 2025-12-14

---

## Goals

1. Create `compute_policy_diff()` function
2. Create `extract_parameter_changes()` helper function
3. Handle nested policy structures (payment_tree, collateral_tree)
4. Produce clear, human-readable output

---

## TDD Steps

### Step 1.1: Create Test File (RED)

Create `api/tests/experiments/analysis/__init__.py` and `api/tests/experiments/analysis/test_policy_diff.py`

**Test Cases**:
1. `test_compute_policy_diff_detects_parameter_change` - Basic parameter change
2. `test_compute_policy_diff_handles_nested_tree_changes` - Tree structure changes
3. `test_compute_policy_diff_handles_added_fields` - New fields added
4. `test_compute_policy_diff_handles_removed_fields` - Fields removed
5. `test_compute_policy_diff_returns_empty_for_identical` - No diff for same policy
6. `test_compute_policy_diff_handles_none_old_policy` - First iteration (no previous)
7. `test_extract_parameter_changes_returns_structured_diff` - Structured output

### Step 1.2: Create Implementation File (GREEN)

Create `api/payment_simulator/experiments/analysis/__init__.py` and `api/payment_simulator/experiments/analysis/policy_diff.py`

**Functions**:
```python
def compute_policy_diff(
    old_policy: dict[str, Any] | None,
    new_policy: dict[str, Any],
) -> str:
    """Compute human-readable diff between two policies."""
    ...

def extract_parameter_changes(
    old_policy: dict[str, Any] | None,
    new_policy: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Extract structured parameter changes."""
    ...

def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested dictionary with dot-separated keys."""
    ...
```

### Step 1.3: Refactor

- Ensure type safety (no `Any` where avoidable)
- Add docstrings with examples
- Optimize for readability

---

## Implementation Details

### Diff Output Format

```
Changed: parameters.urgency_threshold (5 -> 10)
Changed: payment_tree.on_true.threshold (0.5 -> 0.7)
Added: parameters.new_param = 100
Removed: collateral_tree.old_branch
```

### Algorithm

1. Flatten both policies to dot-notation keys
2. Compare keys: added, removed, changed
3. Format changes into human-readable lines
4. Return empty string if no changes

### Edge Cases

- `old_policy` is `None` (first iteration)
- Nested lists in policy
- Boolean value changes
- Float value changes (format to 2 decimal places)

---

## Files

| File | Action |
|------|--------|
| `api/payment_simulator/experiments/analysis/__init__.py` | CREATE |
| `api/payment_simulator/experiments/analysis/policy_diff.py` | CREATE |
| `api/tests/experiments/analysis/__init__.py` | CREATE |
| `api/tests/experiments/analysis/test_policy_diff.py` | CREATE |

---

## Verification

```bash
# Run tests
cd api
.venv/bin/python -m pytest tests/experiments/analysis/test_policy_diff.py -v

# Type check
.venv/bin/python -m mypy payment_simulator/experiments/analysis/policy_diff.py

# Lint
.venv/bin/python -m ruff check payment_simulator/experiments/analysis/
```

---

## Completion Criteria

- [ ] All test cases pass
- [ ] Type check passes
- [ ] Lint passes
- [ ] Docstrings added
- [ ] Handles all edge cases
