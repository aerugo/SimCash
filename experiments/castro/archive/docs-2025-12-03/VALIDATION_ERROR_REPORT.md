# LLM Policy Validation Error Analysis Report

**Date**: 2025-12-03
**Model**: GPT-5.1 with high reasoning effort
**Experiments Analyzed**: exp1 (2-period), exp2 (12-period), exp3 (joint)

## Executive Summary

Analysis of 70+ validation errors across three experiments reveals **three primary failure modes**:

| Error Type | Count | % of Total |
|------------|-------|------------|
| CUSTOM_PARAM | 64 | 91% |
| UNKNOWN_FIELD | 4 | 6% |
| SCHEMA_ERROR | 2 | 3% |

**Key Finding**: The LLM overwhelmingly fails by **inventing custom parameters** that don't exist in the schema. This accounts for 91% of all validation errors.

---

## Error Category 1: Custom Parameters (91% of errors)

### Problem Description

The LLM invents new parameter names that don't exist in the policy schema. The schema only supports three parameters:
- `urgency_threshold`
- `initial_liquidity_fraction`
- `liquidity_buffer_factor`

### Invented Parameters (19 unique)

The LLM created these non-existent parameters:

**Liquidity Management:**
- `min_liquidity_reserve_fraction`
- `max_intraday_liquidity_fraction`
- `min_intraday_liquidity_fraction`
- `topup_target_fraction`
- `topup_queue_multiplier`
- `emergency_topup_fraction`

**Risk/Thresholds:**
- `max_total_collateral_fraction`
- `overdraft_topup_threshold`
- `near_deadline_ticks`
- `soft_urgency_threshold`
- `hard_urgency_threshold`
- `emergency_urgency_threshold`

**Sensitivity Parameters:**
- `backlog_sensitivity`
- `overdraft_sensitivity`

**Context-Specific:**
- `liquidity_buffer_factor_small`
- `liquidity_buffer_factor_large`
- `large_payment_threshold_fraction`
- `late_day_tick_threshold`
- `late_day_start_tick_fraction`

**Action Parameters:**
- `amount` (in action nodes - should not be at top level)
- `reason` (in action nodes - should not be at top level)

### Root Cause

The LLM is **generalizing from the parameter concept** and inventing semantically reasonable but non-existent parameters. This indicates:
1. The prompt does NOT clearly enumerate allowed parameters
2. The LLM assumes a more flexible schema than actually exists
3. GPT-5.1's "creativity" in designing parameters backfires

### Solution

1. **Explicit Parameter Enumeration**: Prompt must state "ONLY these parameters exist: [list]"
2. **Schema Validation in Prompt**: Include JSON schema snippet showing allowed parameters
3. **Negative Examples**: Show examples of INVALID parameter names

---

## Error Category 2: Unknown Context Fields (6% of errors)

### Problem Description

The LLM references context fields that don't exist in the simulation state.

### Invented Fields Found

- `projected_min_balance_until_eod` (Exp1, Iter 3)
- `expected_remaining_net_outflows` (Exp1, Iter 4)

### Root Cause

The LLM is inventing "reasonable" fields based on domain knowledge but these don't exist in the actual context. The LLM is:
1. Inferring what fields SHOULD exist based on financial domain knowledge
2. Not constrained to the actual available fields list

### Solution

1. **Complete Field List in Prompt**: Include ALL available context fields
2. **Field Categories**: Group fields by category (balance, queue, timing, etc.)
3. **Validation Tool**: Add field name validation before LLM response is accepted

---

## Error Category 3: Schema Structure Errors (3% of errors)

### Problem Description

The LLM uses incorrect JSON structure for logical operators.

### Specific Error

**Wrong (LLM output):**
```json
{
  "op": "and",
  "left": {...},
  "right": {...}
}
```

**Correct (required schema):**
```json
{
  "op": "and",
  "conditions": [
    {...},
    {...}
  ]
}
```

### Root Cause

Schema confusion between:
- **Comparison operators** (`>`, `<`, `==`, etc.): Use `left`/`right`
- **Logical operators** (`and`, `or`): Use `conditions` array
- **Unary operators** (`not`): Use `condition`

The LLM is applying the binary operator pattern (`left`/`right`) universally.

### Solution

1. **Explicit Schema Examples**: Show correct structure for EACH operator type
2. **Structured Output**: Use PydanticAI to enforce schema at generation time
3. **Type-Specific Templates**: Provide templates for each operator type

---

## Recommendations for Robust Policy Generator

### 1. Use Structured Output (PydanticAI)

Instead of free-form JSON generation, use Pydantic models:

```python
class Condition(BaseModel):
    op: Literal["and", "or"]
    conditions: list[Expression]  # Forces correct structure

class Comparison(BaseModel):
    op: Literal["==", "!=", "<", "<=", ">", ">="]
    left: ValueSource
    right: ValueSource
```

This prevents schema structure errors entirely.

### 2. Constrained Parameter Generation

```python
class PolicyParameters(BaseModel):
    urgency_threshold: float = Field(ge=0, le=20)
    initial_liquidity_fraction: float = Field(ge=0, le=1)
    liquidity_buffer_factor: float = Field(ge=0.5, le=3)
    # NO other fields allowed
```

### 3. Field Name Validation

Create an enum of valid field names:

```python
class ContextField(str, Enum):
    balance = "balance"
    effective_liquidity = "effective_liquidity"
    queued_payments_total = "queued_payments_total"
    ticks_to_deadline = "ticks_to_deadline"
    # ... all valid fields
```

### 4. Two-Stage Generation

1. **Stage 1**: Generate policy STRUCTURE (tree topology)
2. **Stage 2**: Generate policy VALUES (parameters, thresholds)

This separates structural correctness from value optimization.

### 5. Schema-Aware Prompting

Include in system prompt:

```
CRITICAL SCHEMA CONSTRAINTS:
1. Parameters MUST be one of: urgency_threshold, initial_liquidity_fraction, liquidity_buffer_factor
2. Logical operators (and, or) use: {"op": "and", "conditions": [...]}
3. Comparison operators use: {"op": ">", "left": {...}, "right": {...}}
4. Available context fields: balance, effective_liquidity, ...
```

---

## Implementation Priority

| Priority | Fix | Impact | Effort |
|----------|-----|--------|--------|
| P0 | Use PydanticAI structured output | Eliminates 94% of errors | Medium |
| P1 | Enumerate allowed parameters | Eliminates CUSTOM_PARAM errors | Low |
| P1 | Enumerate allowed fields | Eliminates UNKNOWN_FIELD errors | Low |
| P2 | Provide schema examples | Reduces SCHEMA_ERROR | Low |
| P3 | Two-stage generation | Improves optimization | High |

---

## Appendix: Full Error Log by Experiment

### Experiment 1 (2-period)
- Iter 3: Both banks - `projected_min_balance_until_eod`, custom params
- Iter 4: Both banks - `expected_remaining_net_outflows`, custom params

### Experiment 2 (12-period)
- Iter 1: Both banks - 3 custom params (`min_liquidity_reserve_fraction`, etc.)
- Iter 3: Both banks - 5 custom params (liquidity buffer variants)
- Iter 4: Both banks - 3 custom params (`max_total_collateral_fraction`, etc.)
- Iter 5: Both banks - 5+ custom params (sensitivity parameters)

### Experiment 3 (joint)
- Iter 4: Both banks - `and` schema error + 2 custom params

---

*Report generated: 2025-12-03*
*Analysis by: Claude (Opus 4)*
