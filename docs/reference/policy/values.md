# Value Types

> **Reference: Data Sources for Expressions and Computations**

## Overview

Values are the building blocks of expressions and computations. They represent data sources that evaluate to numeric (`f64`) results.

## Value Type Summary

| Type | JSON Key | Purpose | Example |
|------|----------|---------|---------|
| Field | `field` | Reference simulation state | `{"field": "balance"}` |
| Param | `param` | Reference policy parameter | `{"param": "threshold"}` |
| Literal | `value` | Constant value | `{"value": 100000}` |
| Compute | `compute` | Arithmetic expression | `{"compute": {"op": "+", ...}}` |

---

## 1. Field Reference

### Purpose
References a value from the evaluation context (simulation state). Field availability depends on which tree is being evaluated.

### JSON Syntax
```json
{
  "field": "<field_name>"
}
```

### Examples
```json
{"field": "balance"}
{"field": "remaining_amount"}
{"field": "ticks_to_deadline"}
{"field": "is_overdue"}
{"field": "bank_state_counter"}
```

### Available Fields
See [context-fields.md](context-fields.md) for the complete list of 140+ fields.

### Context Availability

| Tree Type | Available Fields |
|-----------|------------------|
| `payment_tree` | All fields (transaction + bank + system + state registers) |
| `bank_tree` | Bank-level + system + state registers (NO transaction fields) |
| `strategic_collateral_tree` | Bank-level + system + state registers |
| `end_of_tick_collateral_tree` | Bank-level + system + state registers |

### State Registers
Fields starting with `bank_state_` are state registers:
- Default to `0.0` if not set
- Persist within a day, reset at EOD
- Maximum 10 per agent
- Set via `SetState` or `AddState` actions

```json
{"field": "bank_state_cooldown"}
{"field": "bank_state_release_count"}
```

### Error Handling
- `FieldNotFound` error if field doesn't exist
- Validation catches invalid references at load time

### Implementation
```rust
// simulator/src/policy/tree/interpreter.rs:100-103
Value::Field { field } => context
    .get_field(field)
    .map_err(|_| EvalError::FieldNotFound(field.clone()))
```

---

## 2. Parameter Reference

### Purpose
References a named constant defined in the policy's `parameters` object. Allows configuring thresholds without editing tree logic.

### JSON Syntax
```json
{
  "param": "<parameter_name>"
}
```

### Definition in Policy
```json
{
  "version": "1.0",
  "policy_id": "my_policy",
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0,
    "max_splits": 4.0
  },
  "payment_tree": { ... }
}
```

### Usage in Tree
```json
{
  "op": "<=",
  "left": {"field": "ticks_to_deadline"},
  "right": {"param": "urgency_threshold"}
}
```

### Runtime Override
Parameters can be overridden when configuring an agent:
```yaml
agents:
  - id: BANK_A
    policy:
      type: FromJson
      json_path: "simulator/policies/liquidity_aware.json"
      params:
        urgency_threshold: 10.0   # Override default
        target_buffer: 200000.0   # Override default
```

### All Parameters Must Be f64
Parameters are always stored and evaluated as `f64`:
```json
{
  "parameters": {
    "threshold": 5.0,      // Correct
    "count": 3.0,          // Correct (use 3.0 not 3)
    "enabled": 1.0         // Boolean as 1.0/0.0
  }
}
```

### Error Handling
- `ParameterNotFound` error if parameter not defined
- Validation catches missing references at load time

### Implementation
```rust
// simulator/src/policy/tree/interpreter.rs:105-109
Value::Param { param } => params
    .get(param)
    .copied()
    .ok_or_else(|| EvalError::ParameterNotFound(param.clone()))
```

---

## 3. Literal Value

### Purpose
Represents a constant value directly in the expression. Supports numbers, booleans, and integers.

### JSON Syntax
```json
{
  "value": <number | integer | boolean>
}
```

### Examples
```json
{"value": 100000}        // Integer (converted to f64)
{"value": 100000.0}      // Float
{"value": 0.5}           // Decimal
{"value": true}          // Boolean → 1.0
{"value": false}         // Boolean → 0.0
{"value": -50000}        // Negative
{"value": 1e6}           // Scientific notation
```

### Type Conversion
| JSON Type | Result |
|-----------|--------|
| Number (float) | Used directly as f64 |
| Number (integer) | Converted to f64 |
| Boolean `true` | `1.0` |
| Boolean `false` | `0.0` |
| String | **Error**: `InvalidLiteralType` |
| Null | **Error**: `InvalidLiteralType` |
| Array/Object | **Error**: `InvalidLiteralType` |

### Common Literal Patterns

**Threshold comparisons**:
```json
{"op": "<=", "left": {"field": "X"}, "right": {"value": 5}}
```

**Boolean checks**:
```json
{"op": "==", "left": {"field": "is_overdue"}, "right": {"value": 1}}
```

**Zero checks**:
```json
{"op": "==", "left": {"field": "balance"}, "right": {"value": 0}}
```

### Implementation
```rust
// simulator/src/policy/tree/interpreter.rs:112-124
Value::Literal { value: json_value } => {
    if let Some(num) = json_value.as_f64() {
        Ok(num)
    } else if let Some(bool_val) = json_value.as_bool() {
        Ok(if bool_val { 1.0 } else { 0.0 })
    } else if let Some(int_val) = json_value.as_i64() {
        Ok(int_val as f64)
    } else {
        Err(EvalError::InvalidLiteralType)
    }
}
```

---

## 4. Computed Value

### Purpose
Evaluates an arithmetic expression to produce a value. Enables complex calculations inline.

### JSON Syntax
```json
{
  "compute": {
    "op": "<operator>",
    ...
  }
}
```

### Available Operators
See [computations.md](computations.md) for full details:

| Operator | Type | Example |
|----------|------|---------|
| `+` | Binary | `{"op": "+", "left": A, "right": B}` |
| `-` | Binary | `{"op": "-", "left": A, "right": B}` |
| `*` | Binary | `{"op": "*", "left": A, "right": B}` |
| `/` | Binary | `{"op": "/", "left": A, "right": B}` |
| `max` | N-ary | `{"op": "max", "values": [A, B, C]}` |
| `min` | N-ary | `{"op": "min", "values": [A, B, C]}` |
| `ceil` | Unary | `{"op": "ceil", "value": A}` |
| `floor` | Unary | `{"op": "floor", "value": A}` |
| `round` | Unary | `{"op": "round", "value": A}` |
| `abs` | Unary | `{"op": "abs", "value": A}` |
| `clamp` | Ternary | `{"op": "clamp", "value": A, "min": B, "max": C}` |
| `div0` | Ternary | `{"op": "div0", "numerator": A, "denominator": B, "default": C}` |

### Example: Balance After Payment
```json
{
  "compute": {
    "op": "-",
    "left": {"field": "balance"},
    "right": {"field": "remaining_amount"}
  }
}
```

### Example: Nested Computation
```json
{
  "compute": {
    "op": "/",
    "left": {
      "compute": {
        "op": "+",
        "left": {"field": "balance"},
        "right": {"field": "credit_headroom"}
      }
    },
    "right": {"value": 2}
  }
}
```

### Example: Safe Division
```json
{
  "compute": {
    "op": "div0",
    "numerator": {"field": "queue1_total_value"},
    "denominator": {"field": "outgoing_queue_size"},
    "default": {"value": 0}
  }
}
```

### Implementation
```rust
// simulator/src/policy/tree/interpreter.rs:127-128
Value::Compute { compute } => evaluate_computation(compute, context, params)
```

---

## ValueOrCompute Type

Action parameters use `ValueOrCompute`, which is similar to `Value` but with slightly different JSON syntax:

### JSON Syntax Options
```json
// Direct literal
{"value": 100000}

// Field reference
{"field": "balance"}

// Parameter reference
{"param": "threshold"}

// Computation
{"compute": {"op": "+", ...}}
```

### Usage in Action Parameters
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Split",
  "parameters": {
    "num_splits": {"value": 4},
    "some_param": {"field": "queue_size"},
    "calculated": {"compute": {"op": "*", "left": {"value": 2}, "right": {"field": "X"}}}
  }
}
```

### Implementation
```rust
// simulator/src/policy/tree/types.rs:182-196
pub enum ValueOrCompute {
    Direct { value: serde_json::Value },
    Field { field: String },
    Param { param: String },
    Compute { compute: Computation },
}
```

---

## Type System Summary

```
Value
├── Field { field: String }       → Lookup in EvalContext
├── Param { param: String }       → Lookup in parameters HashMap
├── Literal { value: JSON }       → Parse as f64
└── Compute { compute: Box<Computation> } → Recursive evaluation

All paths return f64 (or error)
```

---

## Error Reference

| Error | Cause | Example |
|-------|-------|---------|
| `FieldNotFound` | Field not in context | `{"field": "nonexistent"}` |
| `ParameterNotFound` | Param not in policy | `{"param": "undefined"}` |
| `InvalidLiteralType` | Non-numeric literal | `{"value": "string"}` |
| `DivisionByZero` | Division by zero in compute | `{"op": "/", ..., "right": {"value": 0}}` |

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| Value enum | `simulator/src/policy/tree/types.rs` | 161-177 |
| ValueOrCompute enum | `simulator/src/policy/tree/types.rs` | 182-196 |
| evaluate_value() | `simulator/src/policy/tree/interpreter.rs` | 94-129 |
| evaluate_action_parameter() | `simulator/src/policy/tree/interpreter.rs` | 1316-1358 |
