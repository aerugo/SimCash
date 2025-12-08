# Expression Types

> **Reference: Boolean Expressions for Condition Nodes**

## Overview

Expressions are boolean operations used in Condition nodes. They evaluate to `true` or `false` based on comparing values or combining other expressions.

## Expression Categories

| Category | Operators | Purpose |
|----------|-----------|---------|
| Comparison | `==`, `!=`, `<`, `<=`, `>`, `>=` | Compare two values |
| Logical | `and`, `or`, `not` | Combine expressions |

---

## Comparison Operators

All comparison operators follow the same JSON structure:
```json
{
  "op": "<operator>",
  "left": <Value>,
  "right": <Value>
}
```

### 1. Equal (`==`)

**Purpose**: Tests if two values are equal (with epsilon tolerance for floats).

**JSON Syntax**:
```json
{
  "op": "==",
  "left": {"field": "balance"},
  "right": {"value": 100000}
}
```

**Semantics**:
- Returns `true` if `|left - right| < 1e-9` (epsilon tolerance)
- Handles floating point comparison safely

**Example: Check if payment is exact match**
```json
{
  "op": "==",
  "left": {"field": "remaining_amount"},
  "right": {"field": "amount"}
}
```

### 2. Not Equal (`!=`)

**Purpose**: Tests if two values are different.

**JSON Syntax**:
```json
{
  "op": "!=",
  "left": {"field": "priority"},
  "right": {"value": 0}
}
```

**Semantics**:
- Returns `true` if `|left - right| >= 1e-9`

**Example: Check if transaction has non-default priority**
```json
{
  "op": "!=",
  "left": {"field": "priority"},
  "right": {"value": 5}
}
```

### 3. Less Than (`<`)

**Purpose**: Tests if left value is strictly less than right value.

**JSON Syntax**:
```json
{
  "op": "<",
  "left": {"field": "balance"},
  "right": {"field": "amount"}
}
```

**Semantics**:
- Returns `true` if `left < right`
- No epsilon tolerance (strict comparison)

**Example: Check if insufficient liquidity**
```json
{
  "op": "<",
  "left": {"field": "effective_liquidity"},
  "right": {"field": "remaining_amount"}
}
```

### 4. Less Than or Equal (`<=`)

**Purpose**: Tests if left value is less than or equal to right value.

**JSON Syntax**:
```json
{
  "op": "<=",
  "left": {"field": "ticks_to_deadline"},
  "right": {"param": "urgency_threshold"}
}
```

**Semantics**:
- Returns `true` if `left <= right` OR values are equal within epsilon

**Example: Check if deadline is approaching**
```json
{
  "op": "<=",
  "left": {"field": "ticks_to_deadline"},
  "right": {"value": 5}
}
```

### 5. Greater Than (`>`)

**Purpose**: Tests if left value is strictly greater than right value.

**JSON Syntax**:
```json
{
  "op": ">",
  "left": {"field": "balance"},
  "right": {"value": 0}
}
```

**Semantics**:
- Returns `true` if `left > right`

**Example: Check positive balance**
```json
{
  "op": ">",
  "left": {"field": "balance"},
  "right": {"value": 0}
}
```

### 6. Greater Than or Equal (`>=`)

**Purpose**: Tests if left value is greater than or equal to right value.

**JSON Syntax**:
```json
{
  "op": ">=",
  "left": {"field": "effective_liquidity"},
  "right": {"field": "remaining_amount"}
}
```

**Semantics**:
- Returns `true` if `left >= right` OR values are equal within epsilon

**Example: Standard liquidity check**
```json
{
  "op": ">=",
  "left": {"field": "effective_liquidity"},
  "right": {"field": "remaining_amount"}
}
```

---

## Logical Operators

### 1. AND (`and`)

**Purpose**: Returns true only if ALL conditions are true. Uses short-circuit evaluation.

**JSON Syntax**:
```json
{
  "op": "and",
  "conditions": [
    <Expression>,
    <Expression>,
    ...
  ]
}
```

**Semantics**:
- Evaluates conditions left-to-right
- **Short-circuit**: Stops at first `false` condition
- Returns `true` only if ALL conditions are `true`
- Empty conditions list returns `true`

**Example: Multiple requirements for release**
```json
{
  "op": "and",
  "conditions": [
    {
      "op": ">=",
      "left": {"field": "effective_liquidity"},
      "right": {"field": "remaining_amount"}
    },
    {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 10}
    },
    {
      "op": "==",
      "left": {"field": "is_overdue"},
      "right": {"value": 0}
    }
  ]
}
```

**Short-Circuit Example**:
```json
{
  "op": "and",
  "conditions": [
    {"op": "<", "left": {"field": "balance"}, "right": {"value": 0}},
    {"op": ">", "left": {"field": "nonexistent_field"}, "right": {"value": 0}}
  ]
}
```
If first condition is `false`, second condition is **not evaluated** (avoiding field-not-found error).

### 2. OR (`or`)

**Purpose**: Returns true if ANY condition is true. Uses short-circuit evaluation.

**JSON Syntax**:
```json
{
  "op": "or",
  "conditions": [
    <Expression>,
    <Expression>,
    ...
  ]
}
```

**Semantics**:
- Evaluates conditions left-to-right
- **Short-circuit**: Stops at first `true` condition
- Returns `true` if ANY condition is `true`
- Empty conditions list returns `false`

**Example: Release if urgent OR high priority**
```json
{
  "op": "or",
  "conditions": [
    {
      "op": "<=",
      "left": {"field": "ticks_to_deadline"},
      "right": {"value": 3}
    },
    {
      "op": ">=",
      "left": {"field": "priority"},
      "right": {"value": 9}
    }
  ]
}
```

### 3. NOT (`not`)

**Purpose**: Inverts a boolean expression.

**JSON Syntax**:
```json
{
  "op": "not",
  "condition": <Expression>
}
```

**Semantics**:
- Returns `true` if inner condition is `false`
- Returns `false` if inner condition is `true`

**Example: Check NOT using credit**
```json
{
  "op": "not",
  "condition": {
    "op": "==",
    "left": {"field": "is_using_credit"},
    "right": {"value": 1}
  }
}
```

---

## Complex Expression Examples

### 1. Nested Logical Operators
```json
{
  "op": "or",
  "conditions": [
    {
      "op": "and",
      "conditions": [
        {"op": ">", "left": {"field": "balance"}, "right": {"value": 0}},
        {"op": "<", "left": {"field": "amount"}, "right": {"value": 100000}}
      ]
    },
    {
      "op": "and",
      "conditions": [
        {"op": "<=", "left": {"field": "balance"}, "right": {"value": 0}},
        {"op": ">=", "left": {"field": "priority"}, "right": {"value": 9}}
      ]
    }
  ]
}
```
*Translation: (positive balance AND small amount) OR (zero/negative balance AND high priority)*

### 2. Computed Value Comparisons
```json
{
  "op": "<",
  "left": {
    "compute": {
      "op": "-",
      "left": {"field": "balance"},
      "right": {"field": "remaining_amount"}
    }
  },
  "right": {"param": "target_buffer"}
}
```
*Translation: balance - amount < target_buffer (would violate buffer)*

### 3. Multi-Level Logic
```json
{
  "op": "and",
  "conditions": [
    {
      "op": "not",
      "condition": {
        "op": "==",
        "left": {"field": "is_overdue"},
        "right": {"value": 1}
      }
    },
    {
      "op": "or",
      "conditions": [
        {"op": ">=", "left": {"field": "effective_liquidity"}, "right": {"field": "amount"}},
        {"op": ">", "left": {"field": "credit_headroom"}, "right": {"value": 0}}
      ]
    }
  ]
}
```
*Translation: NOT overdue AND (has liquidity OR has credit headroom)*

---

## Boolean Field Usage

Many context fields are boolean-encoded as `0.0` or `1.0`:

| Field | Meaning when 1.0 |
|-------|------------------|
| `is_split` | Transaction is a split child |
| `is_past_deadline` | Current tick > deadline tick |
| `is_overdue` | Transaction marked overdue |
| `is_in_queue2` | Transaction is in RTGS queue |
| `is_using_credit` | Agent has negative balance |
| `is_eod_rush` | In end-of-day rush period |
| `is_overdraft_capped` | Credit limit is enforced |
| `tx_is_top_counterparty` | Counterparty is top 5 by volume |

**Checking boolean fields**:
```json
{
  "op": "==",
  "left": {"field": "is_overdue"},
  "right": {"value": 1}
}
```

**Alternative (numeric comparison)**:
```json
{
  "op": ">",
  "left": {"field": "is_overdue"},
  "right": {"value": 0.5}
}
```

---

## Floating Point Considerations

### Epsilon Tolerance
- Equality comparisons use `1e-9` epsilon
- This handles floating point rounding errors
- Example: `500000.0 == 500000.0000000001` returns `true`

### Integer-Like Comparisons
- All values are stored as `f64`
- Integer values compare exactly (within epsilon)
- Example: `{"value": 5}` and `{"value": 5.0}` are equivalent

---

## Error Handling

| Error | Cause | Resolution |
|-------|-------|------------|
| `FieldNotFound` | Referenced field doesn't exist in context | Check field name against [context-fields.md](context-fields.md) |
| `ParameterNotFound` | Referenced param not in policy parameters | Add parameter to `parameters` object |
| `DivisionByZero` | Computation divided by zero | Use `div0` operator or check divisor |

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| Expression enum | `simulator/src/policy/tree/types.rs` | 112-152 |
| evaluate_expression() | `simulator/src/policy/tree/interpreter.rs` | 307-378 |
| FLOAT_EPSILON constant | `simulator/src/policy/tree/interpreter.rs` | 268 |
| Short-circuit AND | `simulator/src/policy/tree/interpreter.rs` | 351-360 |
| Short-circuit OR | `simulator/src/policy/tree/interpreter.rs` | 362-371 |
