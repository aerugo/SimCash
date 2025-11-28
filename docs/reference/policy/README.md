# Policy System Reference Documentation

> **Complete Technical Reference for the Payment Simulator Policy System**

This directory contains exhaustive documentation of every component in the policy system. Use this as the authoritative reference for policy development, debugging, and understanding implementation details.

## Document Index

| Document | Description |
|----------|-------------|
| [**trees.md**](trees.md) | The 4 policy tree types and their evaluation contexts |
| [**nodes.md**](nodes.md) | TreeNode types: Condition and Action |
| [**expressions.md**](expressions.md) | Boolean expressions: comparisons and logical operators |
| [**values.md**](values.md) | Value types: Field, Param, Literal, Compute |
| [**computations.md**](computations.md) | Arithmetic operations and math functions |
| [**actions.md**](actions.md) | All action types with parameters and constraints |
| [**context-fields.md**](context-fields.md) | All 140+ evaluation context fields |
| [**validation.md**](validation.md) | Validation rules and error types |
| [**configuration.md**](configuration.md) | Policy configuration in YAML and JSON |
| [**integration.md**](integration.md) | How policies integrate with the simulation |
| [**index.md**](index.md) | Cross-reference index |

## Quick Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Policy JSON File                              │
│  ┌──────────────┬──────────────┬───────────────┬──────────────┐ │
│  │  bank_tree   │ payment_tree │  strategic_   │ end_of_tick_ │ │
│  │              │              │  collateral_  │ collateral_  │ │
│  │              │              │  tree         │ tree         │ │
│  └──────┬───────┴──────┬───────┴───────┬───────┴──────┬───────┘ │
│         │              │               │              │         │
│  Step 1.75       Step 2          Step 1.5       Step 5.5       │
│  (Budget)        (Payments)      (Pre-settle)   (Post-settle)   │
└─────────────────────────────────────────────────────────────────┘

Each tree consists of:
  • TreeNode (Condition or Action)
  • Expression (boolean logic for conditions)
  • Value (data sources: fields, params, literals, computations)
  • Computation (arithmetic operations)
```

## Source Code Locations

| Component | File |
|-----------|------|
| Type definitions | `backend/src/policy/tree/types.rs` |
| Evaluation context | `backend/src/policy/tree/context.rs` |
| Interpreter | `backend/src/policy/tree/interpreter.rs` |
| Validation | `backend/src/policy/tree/validation.rs` |
| Executor | `backend/src/policy/tree/executor.rs` |
| Factory | `backend/src/policy/tree/factory.rs` |
| Policy trait | `backend/src/policy/mod.rs` |
| Example policies | `backend/policies/*.json` |

## Key Design Principles

### 1. JSON DSL Safety
- All policies are defined in JSON (no code execution)
- LLM-editable without security risks
- Pre-execution validation catches errors

### 2. Deterministic Evaluation
- Same inputs always produce same outputs
- All values stored as `f64` for uniform arithmetic
- No system time or external state access

### 3. Context Separation
- Each tree type has appropriate context fields
- Transaction fields only available in `payment_tree`
- Bank-level fields available in all trees
- State registers (`bank_state_*`) persist within day

### 4. Type Safety via Validation
- Node IDs must be unique across all trees
- Field/parameter references validated against known sets
- Tree depth limited to 100 to prevent stack overflow
- Division-by-zero detected where possible

## Version History

| Version | Changes |
|---------|---------|
| 1.0 | Initial DSL with payment_tree only |
| 1.1 | Added strategic_collateral_tree and end_of_tick_collateral_tree |
| 1.2 | Added bank_tree for budget management |
| 1.3 | Added state registers (bank_state_*) |
| 1.4 | Added math helper functions (ceil, floor, round, abs, clamp, div0) |
| 1.5 | Added TARGET2 dual priority support (WithdrawFromRtgs, ResubmitToRtgs) |

---

*Last updated: 2025-11-28*
