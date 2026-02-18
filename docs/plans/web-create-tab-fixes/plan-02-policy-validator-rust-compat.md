# Plan 02: Policy Validator — Accept Both Editor and Rust Expression Formats

**Status**: Draft
**Date**: 2026-02-18
**Branch**: feature/interactive-web-sandbox
**Priority**: P2 (downgraded from P1 — formats actually match, but error messages are confusing)

## Goal

Improve the policy validator's error messages and ensure it accepts all expression formats that the Rust engine accepts. Currently the validator and Rust engine both use `{"op": "<=", "left": ..., "right": ...}` format, but the validator's error messages are confusing when users make format mistakes (e.g., it says `invalid operator 'None'` instead of explaining the expected structure).

## Problem

During playtesting, a policy JSON with the wrong expression format (`{"<=": {"left": ..., "right": ...}}` instead of `{"op": "<=", "left": ..., "right": ...}`) produced the confusing error: `invalid operator 'None'`. The user had to guess the correct format.

The Rust engine uses `#[serde(tag = "op")]` on `Expression`, which serializes to `{"op": "<=", "left": ..., "right": ...}`. The web validator already checks for this same format. But:
1. Error messages don't explain the expected structure
2. The validator doesn't handle compound expressions (`and`, `or`, `not`)
3. Value types (`{field: "..."}`, `{param: "..."}`, `{value: N}`, raw numbers) aren't validated

## Web Invariants

- **WEB-INV-1 (Policy Reality)**: Policies validated by the editor MUST be accepted by the Rust engine.

## Files

### Modified

| File | Changes |
|------|---------|
| `web/backend/app/policy_editor.py` | Improve condition validation: better error messages, support `and`/`or`/`not` expressions, validate Value types. |
| `web/backend/tests/test_policy_editor.py` | Add tests for compound expressions, better error message assertions. |

### NOT Modified

| File | Why |
|------|-----|
| `simulator/src/policy/tree/types.rs` | Engine is source of truth |
| Frontend | Validator changes are backend-only |

## Phase 1: Improve Policy Validator

**Est. Time**: 2h

### Backend

In `policy_editor.py`, update `_validate_tree()`:

1. **Better error for missing `op`**: Instead of `invalid operator 'None'`, say:
   ```
   condition object must have an 'op' field with one of: ==, !=, <, >, <=, >=, and, or, not.
   Got keys: ['<=', 'left', 'right']. Did you mean {"op": "<=", "left": ..., "right": ...}?
   ```

2. **Support compound expressions**: Add `"and"`, `"or"`, `"not"` to valid ops. For `and`/`or`, validate the `conditions` array. For `not`, validate the `condition` sub-expression.

3. **Validate Value types**: `left` and `right` can be:
   - `{"field": "balance"}` — context field reference
   - `{"param": "hold_threshold"}` — parameter reference
   - `{"value": 50000}` — literal value
   - `{"compute": {...}}` — computed value
   - Raw number/string — literal

4. **Extract fields from all Value types**: Update `_extract_fields_from_condition()` to handle `param` references and compound expressions.

### Tests

Add to `test_policy_editor.py`:

| Test | What it verifies |
|------|------------------|
| `test_validate_compound_and_expression` | `{"op": "and", "conditions": [...]}` validates |
| `test_validate_compound_or_expression` | `{"op": "or", "conditions": [...]}` validates |
| `test_validate_not_expression` | `{"op": "not", "condition": {...}}` validates |
| `test_validate_wrong_op_format_gives_helpful_error` | Using `{"<=": {...}}` gives a helpful suggestion |
| `test_validate_param_reference` | `{"param": "threshold"}` accepted in left/right |
| `test_validate_value_literal` | `{"value": 50000}` accepted in left/right |
| `test_validate_raw_number` | Raw `50000` accepted in right position |

### Verification

```bash
cd api && .venv/bin/python -m pytest ../web/backend/tests/test_policy_editor.py -v --tb=short
```

## Success Criteria

- [ ] All existing tests pass
- [ ] 7 new tests pass
- [ ] Wrong format produces helpful error with suggestion
- [ ] Compound expressions (and/or/not) validate
- [ ] All Rust-compatible Value types validate
