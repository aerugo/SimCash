# Computation Types

> **Reference: Arithmetic Operations and Math Functions**

## Overview

Computations are arithmetic operations that transform values into new values. They can be nested to build complex calculations.

## Computation Categories

| Category | Operators | Description |
|----------|-----------|-------------|
| Binary | `+`, `-`, `*`, `/` | Two-operand arithmetic |
| N-ary | `max`, `min` | Multiple-value operations |
| Unary | `ceil`, `floor`, `round`, `abs` | Single-value transformations |
| Ternary | `clamp`, `div0` | Three-operand operations |

---

## Binary Operators

### Addition (`+`)

**Purpose**: Adds two values.

**JSON Syntax**:
```json
{
  "op": "+",
  "left": <Value>,
  "right": <Value>
}
```

**Example: Total liquidity**
```json
{
  "compute": {
    "op": "+",
    "left": {"field": "balance"},
    "right": {"field": "credit_headroom"}
  }
}
```

**Semantics**: `result = left + right`

---

### Subtraction (`-`)

**Purpose**: Subtracts right value from left value.

**JSON Syntax**:
```json
{
  "op": "-",
  "left": <Value>,
  "right": <Value>
}
```

**Example: Balance after payment**
```json
{
  "compute": {
    "op": "-",
    "left": {"field": "balance"},
    "right": {"field": "remaining_amount"}
  }
}
```

**Semantics**: `result = left - right`

---

### Multiplication (`*`)

**Purpose**: Multiplies two values.

**JSON Syntax**:
```json
{
  "op": "*",
  "left": <Value>,
  "right": <Value>
}
```

**Example: Overdraft cost calculation**
```json
{
  "compute": {
    "op": "*",
    "left": {"field": "remaining_amount"},
    "right": {
      "compute": {
        "op": "/",
        "left": {"field": "cost_overdraft_bps_per_tick"},
        "right": {"value": 10000}
      }
    }
  }
}
```

**Semantics**: `result = left × right`

---

### Division (`/`)

**Purpose**: Divides left value by right value.

**JSON Syntax**:
```json
{
  "op": "/",
  "left": <Value>,
  "right": <Value>
}
```

**Example: Average transaction size**
```json
{
  "compute": {
    "op": "/",
    "left": {"field": "queue1_total_value"},
    "right": {"field": "outgoing_queue_size"}
  }
}
```

**Semantics**: `result = left ÷ right`

**Division by Zero**:
- Returns `DivisionByZero` error if `|right| < 1e-9`
- Use `div0` operator for safe division

---

## N-ary Operators

### Maximum (`max`)

**Purpose**: Returns the largest value from a list.

**JSON Syntax**:
```json
{
  "op": "max",
  "values": [<Value>, <Value>, ...]
}
```

**Example: Larger of two values**
```json
{
  "compute": {
    "op": "max",
    "values": [
      {"field": "balance"},
      {"value": 0}
    ]
  }
}
```

**Example: Maximum of three values**
```json
{
  "compute": {
    "op": "max",
    "values": [
      {"field": "amount"},
      {"field": "queue1_total_value"},
      {"param": "min_threshold"}
    ]
  }
}
```

**Semantics**: `result = max(v1, v2, ..., vn)`

**Error**: `EmptyValueList` if values array is empty

---

### Minimum (`min`)

**Purpose**: Returns the smallest value from a list.

**JSON Syntax**:
```json
{
  "op": "min",
  "values": [<Value>, <Value>, ...]
}
```

**Example: Cap at maximum**
```json
{
  "compute": {
    "op": "min",
    "values": [
      {"field": "remaining_amount"},
      {"field": "effective_liquidity"}
    ]
  }
}
```

**Semantics**: `result = min(v1, v2, ..., vn)`

**Error**: `EmptyValueList` if values array is empty

---

## Unary Math Functions

### Ceiling (`ceil`)

**Purpose**: Rounds up to nearest integer.

**JSON Syntax**:
```json
{
  "op": "ceil",
  "value": <Value>
}
```

**Example: Round up split count**
```json
{
  "compute": {
    "op": "ceil",
    "value": {
      "compute": {
        "op": "/",
        "left": {"field": "remaining_amount"},
        "right": {"param": "max_per_split"}
      }
    }
  }
}
```

**Semantics**: `result = ⌈value⌉`

---

### Floor (`floor`)

**Purpose**: Rounds down to nearest integer.

**JSON Syntax**:
```json
{
  "op": "floor",
  "value": <Value>
}
```

**Example: Whole ticks remaining**
```json
{
  "compute": {
    "op": "floor",
    "value": {"field": "ticks_to_deadline"}
  }
}
```

**Semantics**: `result = ⌊value⌋`

---

### Round (`round`)

**Purpose**: Rounds to nearest integer.

**JSON Syntax**:
```json
{
  "op": "round",
  "value": <Value>
}
```

**Example: Round calculated splits**
```json
{
  "compute": {
    "op": "round",
    "value": {
      "compute": {
        "op": "/",
        "left": {"field": "remaining_amount"},
        "right": {"value": 50000}
      }
    }
  }
}
```

**Semantics**: `result = round(value)` (0.5 rounds away from zero)

---

### Absolute Value (`abs`)

**Purpose**: Returns absolute (non-negative) value.

**JSON Syntax**:
```json
{
  "op": "abs",
  "value": <Value>
}
```

**Example: Magnitude of net position**
```json
{
  "compute": {
    "op": "abs",
    "value": {"field": "my_bilateral_net_q2"}
  }
}
```

**Semantics**: `result = |value|`

---

## Ternary Operators

### Clamp (`clamp`)

**Purpose**: Constrains a value to a range [min, max].

**JSON Syntax**:
```json
{
  "op": "clamp",
  "value": <Value>,
  "min": <Value>,
  "max": <Value>
}
```

**Example: Constrain priority boost**
```json
{
  "compute": {
    "op": "clamp",
    "value": {
      "compute": {
        "op": "+",
        "left": {"field": "priority"},
        "right": {"value": 3}
      }
    },
    "min": {"value": 0},
    "max": {"value": 10}
  }
}
```

**Semantics**: `result = max(min_val, min(max_val, value))`

---

### Safe Division (`div0`)

**Purpose**: Division that returns a default value instead of error when dividing by zero.

**JSON Syntax**:
```json
{
  "op": "div0",
  "numerator": <Value>,
  "denominator": <Value>,
  "default": <Value>
}
```

**Example: Average with fallback**
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

**Semantics**:
```
if |denominator| < 1e-9:
    result = default
else:
    result = numerator / denominator
```

**Use Cases**:
- Averages where count might be zero
- Ratios where divisor might be zero
- Any division with uncertain denominator

---

## Nested Computations

Computations can be nested arbitrarily:

### Example: Complex Cost Calculation
```json
{
  "compute": {
    "op": "+",
    "left": {
      "compute": {
        "op": "*",
        "left": {"field": "remaining_amount"},
        "right": {"field": "cost_delay_per_tick_per_cent"}
      }
    },
    "right": {
      "compute": {
        "op": "*",
        "left": {"field": "remaining_amount"},
        "right": {
          "compute": {
            "op": "/",
            "left": {"field": "cost_overdraft_bps_per_tick"},
            "right": {"value": 10000}
          }
        }
      }
    }
  }
}
```
*Translation: (amount × delay_cost) + (amount × overdraft_rate/10000)*

### Example: Safe Ratio with Clamp
```json
{
  "compute": {
    "op": "clamp",
    "value": {
      "compute": {
        "op": "div0",
        "numerator": {"field": "credit_used"},
        "denominator": {"field": "credit_limit"},
        "default": {"value": 0}
      }
    },
    "min": {"value": 0},
    "max": {"value": 1}
  }
}
```
*Translation: clamp(credit_used / credit_limit, 0, 1) with zero-safe division*

---

## Common Patterns

### 1. Balance After Action
```json
{
  "op": "-",
  "left": {"field": "balance"},
  "right": {"field": "remaining_amount"}
}
```

### 2. Percentage Calculation
```json
{
  "op": "*",
  "left": {"field": "balance"},
  "right": {"value": 0.1}
}
```

### 3. Basis Points to Decimal
```json
{
  "op": "/",
  "left": {"param": "rate_bps"},
  "right": {"value": 10000}
}
```

### 4. Safe Average
```json
{
  "op": "div0",
  "numerator": {"field": "total"},
  "denominator": {"field": "count"},
  "default": {"value": 0}
}
```

### 5. Constrained Addition
```json
{
  "op": "min",
  "values": [
    {
      "compute": {
        "op": "+",
        "left": {"field": "value"},
        "right": {"param": "increment"}
      }
    },
    {"param": "maximum"}
  ]
}
```

### 6. Non-Negative Result
```json
{
  "op": "max",
  "values": [
    {
      "compute": {
        "op": "-",
        "left": {"field": "a"},
        "right": {"field": "b"}
      }
    },
    {"value": 0}
  ]
}
```

---

## Error Handling

| Error | Operator | Cause |
|-------|----------|-------|
| `DivisionByZero` | `/` | Denominator ≈ 0 |
| `EmptyValueList` | `max`, `min` | Empty values array |
| `FieldNotFound` | Any | Unknown field reference |
| `ParameterNotFound` | Any | Unknown parameter reference |

---

## Numerical Precision

- All computations use `f64` (IEEE 754 double precision)
- Epsilon threshold for zero: `1e-9`
- Integer values maintain exact representation up to ~2^53
- Money values stored as cents (i64) but computed as f64

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| Computation enum | `backend/src/policy/tree/types.rs` | 205-266 |
| evaluate_computation() | `backend/src/policy/tree/interpreter.rs` | 146-261 |
| Add | `backend/src/policy/tree/interpreter.rs` | 152-156 |
| Subtract | `backend/src/policy/tree/interpreter.rs` | 158-162 |
| Multiply | `backend/src/policy/tree/interpreter.rs` | 164-168 |
| Divide | `backend/src/policy/tree/interpreter.rs` | 170-180 |
| Max | `backend/src/policy/tree/interpreter.rs` | 182-195 |
| Min | `backend/src/policy/tree/interpreter.rs` | 197-210 |
| Ceil | `backend/src/policy/tree/interpreter.rs` | 213-216 |
| Floor | `backend/src/policy/tree/interpreter.rs` | 218-221 |
| Round | `backend/src/policy/tree/interpreter.rs` | 223-226 |
| Abs | `backend/src/policy/tree/interpreter.rs` | 228-231 |
| Clamp | `backend/src/policy/tree/interpreter.rs` | 233-240 |
| SafeDiv (div0) | `backend/src/policy/tree/interpreter.rs` | 242-259 |
