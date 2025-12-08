# Policy Reference

> JSON-based decision tree DSL for programmable bank payment strategies

This reference documents every component of the policy system, which allows banks to define strategic payment behaviors through JSON decision trees that are both human-readable and LLM-editable.

## Documentation

| Document | Description |
|----------|-------------|
| [trees](trees.md) | The 4 policy tree types and their evaluation contexts |
| [nodes](nodes.md) | TreeNode types: Condition and Action |
| [expressions](expressions.md) | Boolean expressions: comparisons and logical operators |
| [values](values.md) | Value types: Field, Param, Literal, Compute |
| [computations](computations.md) | Arithmetic operations and math functions |
| [actions](actions.md) | All action types with parameters and constraints |
| [context-fields](context-fields.md) | All 140+ evaluation context fields |
| [validation](validation.md) | Validation rules and error types |
| [configuration](configuration.md) | Policy configuration in YAML and JSON |
| [integration](integration.md) | How policies integrate with the simulation |
| [cross-reference](cross-reference.md) | Quick lookup index by keyword |

## Quick Overview

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
| Type definitions | `simulator/src/policy/tree/types.rs` |
| Evaluation context | `simulator/src/policy/tree/context.rs` |
| Interpreter | `simulator/src/policy/tree/interpreter.rs` |
| Validation | `simulator/src/policy/tree/validation.rs` |
| Executor | `simulator/src/policy/tree/executor.rs` |
| Factory | `simulator/src/policy/tree/factory.rs` |
| Policy trait | `simulator/src/policy/mod.rs` |
| Example policies | `simulator/policies/*.json` |

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

## Related Documentation

- [Scenario Policies](../scenario/policies.md) - Policy configuration in scenarios
- [CLI validate-policy](../cli/commands/validate-policy.md) - Policy validation command
- [Architecture: Policy System](../architecture/07-policy-system.md) - Implementation details

---

*Last updated: 2025-11-28*
