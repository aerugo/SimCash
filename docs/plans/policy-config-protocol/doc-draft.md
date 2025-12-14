# PolicyConfigBuilder Documentation Draft

**Created**: 2025-12-14
**Status**: Applied to docs/reference/patterns-and-conventions.md

---

## Changes Made

### 1. Added INV-9: Policy Evaluation Identity

**Location**: `docs/reference/patterns-and-conventions.md` (after INV-8)

New invariant ensuring policy parameter extraction produces identical results
regardless of code path (deterministic vs bootstrap evaluation).

### 2. Added Pattern 7: PolicyConfigBuilder

**Location**: `docs/reference/patterns-and-conventions.md` (after Pattern 6)

New pattern documenting the `PolicyConfigBuilder` protocol and `StandardPolicyConfigBuilder`
implementation. Includes:
- Protocol definition
- Usage examples
- Key features
- Anti-patterns

### 3. Updated Key Source Files Table

Added row for `PolicyConfigBuilder` → `config/policy_config_builder.py`

### 4. Updated Version

- Version: 2.0 → 2.1
- Last Updated: 2025-12-11 → 2025-12-14

---

## Summary

The PolicyConfigBuilder pattern ensures that all code paths that apply policies
to agents use the same extraction logic. This is critical for the Policy
Evaluation Identity invariant (INV-9), which guarantees that the same policy
produces identical behavior in:

1. Deterministic evaluation (optimization.py)
2. Bootstrap evaluation (sandbox_config.py)

The key implementation file is `api/payment_simulator/config/policy_config_builder.py`.
