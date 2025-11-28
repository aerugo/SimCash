# Cross-Reference Index

> **Quick lookup for policy system components**

## By JSON Keyword

| Keyword | Type | Documentation |
|---------|------|---------------|
| `"type": "condition"` | Node | [nodes.md](nodes.md#1-condition-node) |
| `"type": "action"` | Node | [nodes.md](nodes.md#2-action-node) |
| `"op": "=="` | Expression | [expressions.md](expressions.md#1-equal-) |
| `"op": "!="` | Expression | [expressions.md](expressions.md#2-not-equal-) |
| `"op": "<"` | Expression | [expressions.md](expressions.md#3-less-than-) |
| `"op": "<="` | Expression | [expressions.md](expressions.md#4-less-than-or-equal-) |
| `"op": ">"` | Expression | [expressions.md](expressions.md#5-greater-than-) |
| `"op": ">="` | Expression | [expressions.md](expressions.md#6-greater-than-or-equal-) |
| `"op": "and"` | Expression | [expressions.md](expressions.md#1-and-and) |
| `"op": "or"` | Expression | [expressions.md](expressions.md#2-or-or) |
| `"op": "not"` | Expression | [expressions.md](expressions.md#3-not-not) |
| `"op": "+"` | Computation | [computations.md](computations.md#addition-) |
| `"op": "-"` | Computation | [computations.md](computations.md#subtraction--) |
| `"op": "*"` | Computation | [computations.md](computations.md#multiplication-) |
| `"op": "/"` | Computation | [computations.md](computations.md#division-) |
| `"op": "max"` | Computation | [computations.md](computations.md#maximum-max) |
| `"op": "min"` | Computation | [computations.md](computations.md#minimum-min) |
| `"op": "ceil"` | Computation | [computations.md](computations.md#ceiling-ceil) |
| `"op": "floor"` | Computation | [computations.md](computations.md#floor-floor) |
| `"op": "round"` | Computation | [computations.md](computations.md#round-round) |
| `"op": "abs"` | Computation | [computations.md](computations.md#absolute-value-abs) |
| `"op": "clamp"` | Computation | [computations.md](computations.md#clamp-clamp) |
| `"op": "div0"` | Computation | [computations.md](computations.md#safe-division-div0) |
| `"field": "..."` | Value | [values.md](values.md#1-field-reference) |
| `"param": "..."` | Value | [values.md](values.md#2-parameter-reference) |
| `"value": ...` | Value | [values.md](values.md#3-literal-value) |
| `"compute": {...}` | Value | [values.md](values.md#4-computed-value) |
| `"action": "Release"` | Action | [actions.md](actions.md#release) |
| `"action": "Hold"` | Action | [actions.md](actions.md#hold) |
| `"action": "Split"` | Action | [actions.md](actions.md#split--paceandrelease) |
| `"action": "Drop"` | Action | [actions.md](actions.md#drop) |

---

## By Field Name

### Transaction Fields (payment_tree only)
| Field | Description | Documentation |
|-------|-------------|---------------|
| `amount` | Original transaction amount | [context-fields.md](context-fields.md#amount) |
| `remaining_amount` | Amount still to settle | [context-fields.md](context-fields.md#remaining_amount) |
| `settled_amount` | Amount already settled | [context-fields.md](context-fields.md#settled_amount) |
| `arrival_tick` | When transaction arrived | [context-fields.md](context-fields.md#arrival_tick) |
| `deadline_tick` | Settlement deadline | [context-fields.md](context-fields.md#deadline_tick) |
| `priority` | Transaction priority (0-10) | [context-fields.md](context-fields.md#priority) |
| `is_split` | Is a split child | [context-fields.md](context-fields.md#is_split) |
| `is_past_deadline` | Deadline has passed | [context-fields.md](context-fields.md#is_past_deadline) |
| `is_overdue` | Marked overdue | [context-fields.md](context-fields.md#is_overdue) |
| `is_in_queue2` | In RTGS Queue 2 | [context-fields.md](context-fields.md#is_in_queue2) |
| `overdue_duration` | Ticks since overdue | [context-fields.md](context-fields.md#overdue_duration) |
| `ticks_to_deadline` | Ticks until deadline | [context-fields.md](context-fields.md#ticks_to_deadline) |
| `queue_age` | Ticks in Queue 1 | [context-fields.md](context-fields.md#queue_age) |

### Agent/Balance Fields (all trees)
| Field | Description | Documentation |
|-------|-------------|---------------|
| `balance` | Current account balance | [context-fields.md](context-fields.md#balance) |
| `credit_limit` | Maximum overdraft | [context-fields.md](context-fields.md#credit_limit) |
| `available_liquidity` | Positive balance portion | [context-fields.md](context-fields.md#available_liquidity) |
| `credit_used` | Current overdraft | [context-fields.md](context-fields.md#credit_used) |
| `effective_liquidity` | Total available capacity | [context-fields.md](context-fields.md#effective_liquidity) |
| `credit_headroom` | Remaining credit capacity | [context-fields.md](context-fields.md#credit_headroom) |
| `is_using_credit` | Balance is negative | [context-fields.md](context-fields.md#is_using_credit) |
| `liquidity_pressure` | Stress indicator (0-1) | [context-fields.md](context-fields.md#liquidity_pressure) |

### Collateral Fields (all trees)
| Field | Description | Documentation |
|-------|-------------|---------------|
| `posted_collateral` | Currently posted | [context-fields.md](context-fields.md#posted_collateral) |
| `max_collateral_capacity` | Maximum postable | [context-fields.md](context-fields.md#max_collateral_capacity) |
| `remaining_collateral_capacity` | Room to post more | [context-fields.md](context-fields.md#remaining_collateral_capacity) |
| `collateral_utilization` | Posted/max ratio | [context-fields.md](context-fields.md#collateral_utilization) |
| `excess_collateral` | Withdrawable amount | [context-fields.md](context-fields.md#excess_collateral) |

### Time Fields (all trees)
| Field | Description | Documentation |
|-------|-------------|---------------|
| `current_tick` | Current simulation tick | [context-fields.md](context-fields.md#current_tick) |
| `system_ticks_per_day` | Ticks in a day | [context-fields.md](context-fields.md#system_ticks_per_day) |
| `system_tick_in_day` | Tick within day | [context-fields.md](context-fields.md#system_tick_in_day) |
| `day_progress_fraction` | Progress through day (0-1) | [context-fields.md](context-fields.md#day_progress_fraction) |
| `is_eod_rush` | In end-of-day rush | [context-fields.md](context-fields.md#is_eod_rush) |

---

## By Action Type

### Payment Actions (payment_tree)
| Action | Required Params | Documentation |
|--------|-----------------|---------------|
| `Release` | - | [actions.md](actions.md#release) |
| `ReleaseWithCredit` | - | [actions.md](actions.md#releasewithcredit) |
| `Split` | `num_splits` | [actions.md](actions.md#split--paceandrelease) |
| `PaceAndRelease` | `num_splits` | [actions.md](actions.md#split--paceandrelease) |
| `StaggerSplit` | `num_splits`, `stagger_first_now`, `stagger_gap_ticks`, `priority_boost_children` | [actions.md](actions.md#staggersplit) |
| `Hold` | - | [actions.md](actions.md#hold) |
| `Drop` | - | [actions.md](actions.md#drop) |
| `Reprioritize` | `new_priority` | [actions.md](actions.md#reprioritize) |
| `WithdrawFromRtgs` | - | [actions.md](actions.md#withdrawfromrtgs) |
| `ResubmitToRtgs` | `rtgs_priority` | [actions.md](actions.md#resubmittortgs) |

### Bank Actions (bank_tree)
| Action | Required Params | Documentation |
|--------|-----------------|---------------|
| `SetReleaseBudget` | `max_value_to_release` | [actions.md](actions.md#setreleasebudget) |
| `SetState` | `key`, `value` | [actions.md](actions.md#setstate) |
| `AddState` | `key`, `value` | [actions.md](actions.md#addstate) |
| `NoAction` | - | [actions.md](actions.md#noaction) |

### Collateral Actions (collateral trees)
| Action | Required Params | Documentation |
|--------|-----------------|---------------|
| `PostCollateral` | `amount` | [actions.md](actions.md#postcollateral) |
| `WithdrawCollateral` | `amount` | [actions.md](actions.md#withdrawcollateral) |
| `HoldCollateral` | - | [actions.md](actions.md#holdcollateral) |

---

## By Error Type

| Error | Cause | Documentation |
|-------|-------|---------------|
| `DuplicateNodeId` | Node IDs not unique | [validation.md](validation.md#1-node-id-uniqueness) |
| `ExcessiveDepth` | Tree too deep (>100) | [validation.md](validation.md#2-tree-depth-limits) |
| `InvalidFieldReference` | Unknown or invalid field | [validation.md](validation.md#3-field-reference-validation) |
| `InvalidParameterReference` | Unknown parameter | [validation.md](validation.md#4-parameter-reference-validation) |
| `DivisionByZeroRisk` | Constant zero divisor | [validation.md](validation.md#5-division-safety) |
| `FieldNotFound` | Runtime field lookup failed | [validation.md](validation.md#runtime-errors) |
| `ParameterNotFound` | Runtime param lookup failed | [validation.md](validation.md#runtime-errors) |
| `DivisionByZero` | Runtime division by zero | [validation.md](validation.md#runtime-errors) |

---

## By Source File

### Rust Backend
| File | Contents | Documentation |
|------|----------|---------------|
| `policy/mod.rs` | Trait definitions, enums | [actions.md](actions.md), [integration.md](integration.md) |
| `policy/tree/types.rs` | JSON schema types | [nodes.md](nodes.md), [expressions.md](expressions.md), [values.md](values.md), [computations.md](computations.md) |
| `policy/tree/context.rs` | EvalContext builder | [context-fields.md](context-fields.md) |
| `policy/tree/interpreter.rs` | Tree evaluation | [integration.md](integration.md#treepolicy-implementation) |
| `policy/tree/validation.rs` | Validation logic | [validation.md](validation.md) |
| `policy/tree/executor.rs` | TreePolicy impl | [integration.md](integration.md#treepolicy-implementation) |
| `policy/tree/factory.rs` | Policy loading | [configuration.md](configuration.md#policy-loading-process) |

### Python API
| File | Contents | Documentation |
|------|----------|---------------|
| `config/schemas.py` | Pydantic models | [configuration.md](configuration.md#pydantic-validation-models) |

### Policy Files
| File | Description |
|------|-------------|
| `backend/policies/fifo.json` | Simple FIFO |
| `backend/policies/liquidity_aware.json` | Liquidity buffer |
| `backend/policies/liquidity_splitting.json` | Auto-splitting |
| `backend/policies/balanced_cost_optimizer.json` | Cost optimization |

---

## By Use Case

### "Can I afford this payment?"
- Field: `effective_liquidity` ([docs](context-fields.md#effective_liquidity))
- Comparison: `{"op": ">=", "left": {"field": "effective_liquidity"}, "right": {"field": "remaining_amount"}}`

### "Is this urgent?"
- Field: `ticks_to_deadline` ([docs](context-fields.md#ticks_to_deadline))
- Comparison: `{"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "urgency_threshold"}}`

### "Is it end of day?"
- Field: `is_eod_rush` ([docs](context-fields.md#is_eod_rush))
- Comparison: `{"op": "==", "left": {"field": "is_eod_rush"}, "right": {"value": 1}}`

### "Should I post collateral?"
- Field: `queue1_liquidity_gap` ([docs](context-fields.md#queue1_liquidity_gap))
- Action: `PostCollateral` ([docs](actions.md#postcollateral))

### "Should I split this payment?"
- Condition: Amount > liquidity
- Action: `Split` ([docs](actions.md#split--paceandrelease))

### "How do I track state across ticks?"
- Action: `SetState`, `AddState` ([docs](actions.md#setstate))
- Field: `bank_state_*` ([docs](context-fields.md#state-register-fields))

### "How do I limit releases per tick?"
- Action: `SetReleaseBudget` ([docs](actions.md#setreleasebudget))
- Tree: `bank_tree` ([docs](trees.md#1-bank_tree))

---

## Quick Reference Card

### Minimal Policy
```json
{
  "version": "1.0",
  "policy_id": "basic",
  "payment_tree": {
    "type": "action",
    "node_id": "A1",
    "action": "Release"
  }
}
```

### Common Condition Pattern
```json
{
  "type": "condition",
  "node_id": "N1",
  "condition": {
    "op": ">=",
    "left": {"field": "effective_liquidity"},
    "right": {"field": "remaining_amount"}
  },
  "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
  "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
}
```

### Common Action Patterns
```json
// Release
{"type": "action", "node_id": "A1", "action": "Release"}

// Hold with reason
{"type": "action", "node_id": "A2", "action": "Hold", "parameters": {"reason": {"value": "InsufficientLiquidity"}}}

// Split
{"type": "action", "node_id": "A3", "action": "Split", "parameters": {"num_splits": {"value": 4}}}

// Post collateral
{"type": "action", "node_id": "SC1", "action": "PostCollateral", "parameters": {"amount": {"field": "queue1_liquidity_gap"}, "reason": {"value": "UrgentLiquidityNeed"}}}
```

---

*Last updated: 2025-11-28*
