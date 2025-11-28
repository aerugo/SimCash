# Validation Rules and Constraints

> **Reference: Pre-Execution Safety Checks for Policy Decision Trees**

## Overview

Policy trees are validated before execution to ensure they are well-formed and safe. Validation catches errors early, preventing runtime failures and undefined behavior.

## Validation Categories

| Category | Check | Error Type |
|----------|-------|------------|
| Structural | Node ID uniqueness | `DuplicateNodeId` |
| Structural | Tree depth limits | `ExcessiveDepth` |
| Semantic | Field references | `InvalidFieldReference` |
| Semantic | Parameter references | `InvalidParameterReference` |
| Safety | Division by zero | `DivisionByZeroRisk` |
| Reachability | Unreachable actions | `UnreachableAction` |

---

## Validation Function

```rust
pub fn validate_tree(
    tree: &DecisionTreeDef,
    sample_context: &EvalContext
) -> Result<(), Vec<ValidationError>>
```

**Arguments**:
- `tree` - Decision tree definition to validate
- `sample_context` - Sample context for field validation

**Returns**:
- `Ok(())` - All checks passed
- `Err(Vec<ValidationError>)` - List of all errors found

**Note**: All errors are collected, not just the first one.

---

## 1. Node ID Uniqueness

**Requirement**: Every node ID must be unique across ALL trees in the policy file.

**Scope**: Checks across:
- `payment_tree`
- `bank_tree`
- `strategic_collateral_tree`
- `end_of_tick_collateral_tree`

**Error**:
```
DuplicateNodeId("N1")
```

**Example (Invalid)**:
```json
{
  "payment_tree": {
    "type": "condition",
    "node_id": "N1",           // ❌ Duplicate
    "on_true": {
      "type": "action",
      "node_id": "N1",         // ❌ Same ID
      "action": "Release"
    }
  }
}
```

**Example (Valid)**:
```json
{
  "payment_tree": {
    "type": "condition",
    "node_id": "N1",           // ✅ Unique
    "on_true": {
      "type": "action",
      "node_id": "A1",         // ✅ Unique
      "action": "Release"
    }
  }
}
```

**Implementation**: `validation.rs:141-186`

---

## 2. Tree Depth Limits

**Requirement**: No tree path can exceed 100 levels.

**Maximum Depth**: `MAX_TREE_DEPTH = 100`

**Purpose**: Prevents stack overflow during recursive evaluation.

**Error**:
```
ExcessiveDepth { actual: 105, max: 100 }
```

**Depth Calculation**:
- Root node = depth 0
- Each Condition node's children = parent depth + 1
- Action nodes are terminal (don't increase depth)

**Example (depth = 3)**:
```
N1 (depth 0)
├── N2 (depth 1)
│   ├── A1 (depth 2)
│   └── N3 (depth 2)
│       ├── A2 (depth 3)
│       └── A3 (depth 3)
└── A4 (depth 1)
```

**Implementation**: `validation.rs:193-232`

---

## 3. Field Reference Validation

**Requirement**: All field references must:
1. Exist in the context
2. Be appropriate for the tree type

**Context-Specific Validation**:

| Tree Type | Allowed Fields |
|-----------|----------------|
| `payment_tree` | Transaction + Bank + System + State registers |
| `bank_tree` | Bank + System + State registers (NO transaction fields) |
| `strategic_collateral_tree` | Bank + System + State registers |
| `end_of_tick_collateral_tree` | Bank + System + State registers |

**Error**:
```
InvalidFieldReference("remaining_amount")
```

**Example (Invalid in bank_tree)**:
```json
{
  "bank_tree": {
    "type": "condition",
    "condition": {
      "op": ">",
      "left": {"field": "remaining_amount"},  // ❌ Transaction field
      "right": {"value": 0}
    }
  }
}
```

### Transaction-Only Fields
These fields trigger validation error if used outside `payment_tree`:
- `amount`, `remaining_amount`, `settled_amount`
- `arrival_tick`, `deadline_tick`, `priority`
- `is_split`, `is_past_deadline`, `is_overdue`, `is_in_queue2`
- `overdue_duration`, `ticks_to_deadline`, `queue_age`
- `cost_delay_this_tx_one_tick`, `cost_overdraft_this_amount_one_tick`

### State Register Fields
- Must start with `bank_state_` prefix
- Allowed in ALL tree types
- Example: `bank_state_cooldown`, `bank_state_counter`

**Implementation**: `validation.rs:244-324`

---

## 4. Parameter Reference Validation

**Requirement**: All parameter references must exist in the policy's `parameters` object.

**Error**:
```
InvalidParameterReference("undefined_threshold")
```

**Example (Invalid)**:
```json
{
  "parameters": {
    "urgency_threshold": 5.0
  },
  "payment_tree": {
    "condition": {
      "op": "<",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "undefined_threshold"}  // ❌ Not defined
    }
  }
}
```

**Example (Valid)**:
```json
{
  "parameters": {
    "urgency_threshold": 5.0
  },
  "payment_tree": {
    "condition": {
      "op": "<",
      "left": {"field": "ticks_to_deadline"},
      "right": {"param": "urgency_threshold"}  // ✅ Defined
    }
  }
}
```

**Implementation**: `validation.rs:455-523`

---

## 5. Division Safety

**Requirement**: Division operations should not have constant zero denominators.

**Detection**: Static analysis for literal zero denominators.

**Error**:
```
DivisionByZeroRisk("N1")
```

**Example (Detected)**:
```json
{
  "compute": {
    "op": "/",
    "left": {"field": "balance"},
    "right": {"value": 0}        // ❌ Constant zero
  }
}
```

**Not Detected** (runtime error instead):
```json
{
  "compute": {
    "op": "/",
    "left": {"field": "balance"},
    "right": {"field": "queue_size"}  // May be zero at runtime
  }
}
```

**Recommendation**: Use `div0` operator for safe division:
```json
{
  "compute": {
    "op": "div0",
    "numerator": {"field": "balance"},
    "denominator": {"field": "queue_size"},
    "default": {"value": 0}
  }
}
```

**Implementation**: `validation.rs:556-633`

---

## 6. Action Reachability

**Requirement**: All action nodes should be reachable from the tree root.

**Warning Level**: This is a best-effort static analysis; some cases may not be detected.

**Error**:
```
UnreachableAction("A5")
```

**Detection**: Identifies orphaned action nodes that cannot be reached through any path.

**Implementation**: `validation.rs:660-720`

---

## Runtime Errors

Some errors cannot be detected at validation time:

### Division by Zero (Runtime)
```rust
EvalError::DivisionByZero
```
Occurs when field-based denominator evaluates to zero.

### Field Not Found (Runtime)
```rust
EvalError::FieldNotFound("unknown_field")
```
Should not occur if validation passes.

### Parameter Not Found (Runtime)
```rust
EvalError::ParameterNotFound("missing_param")
```
Should not occur if validation passes.

### Max Depth Exceeded (Runtime)
```rust
EvalError::MaxDepthExceeded
```
Should not occur if validation passes.

---

## Validation Workflow

### 1. Policy Loading
```python
# In Python (policy factory)
policy = TreePolicy.from_json(json_path, override_params)
# Automatically validates on load
```

### 2. Manual Validation
```rust
// In Rust
let tree = serde_json::from_str::<DecisionTreeDef>(json)?;
let sample_ctx = EvalContext::build(&tx, &agent, &state, 0, &costs, 100, 0.8);

match validate_tree(&tree, &sample_ctx) {
    Ok(()) => println!("Valid"),
    Err(errors) => {
        for error in errors {
            println!("Error: {}", error);
        }
    }
}
```

### 3. CLI Validation
```bash
# Validate policy file
payment-sim validate-policy backend/policies/my_policy.json
```

---

## Validation Error Messages

| Error | Message Format | Resolution |
|-------|---------------|------------|
| `DuplicateNodeId` | `"Duplicate node ID: {id}"` | Use unique IDs across all trees |
| `ExcessiveDepth` | `"Tree depth {actual} exceeds maximum {max}"` | Flatten tree structure |
| `InvalidFieldReference` | `"Field reference '{name}' not found in context"` | Check field name or tree type |
| `InvalidParameterReference` | `"Parameter reference '{name}' not found in tree parameters"` | Add to parameters object |
| `DivisionByZeroRisk` | `"Potential division by zero in computation at node {id}"` | Use div0 operator |
| `UnreachableAction` | `"Unreachable action node: {id}"` | Fix tree structure |

---

## Best Practices

### 1. Use Descriptive Node IDs
```json
"node_id": "N1_CheckDeadline"  // ✅ Descriptive
"node_id": "N1"                 // ⚠️ Less clear
```

### 2. Define All Parameters
```json
{
  "parameters": {
    "urgency_threshold": 5.0,
    "target_buffer": 100000.0,
    "max_splits": 4.0
  }
}
```

### 3. Use Safe Division
```json
{
  "op": "div0",
  "numerator": {"field": "total"},
  "denominator": {"field": "count"},
  "default": {"value": 0}
}
```

### 4. Validate Before Deployment
Always validate policies before using in production simulations.

### 5. Test with Edge Cases
Validate policies work when:
- Queue is empty (`outgoing_queue_size = 0`)
- Balance is zero or negative
- No transactions in Queue 2

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| ValidationError enum | `backend/src/policy/tree/validation.rs` | 19-38 |
| validate_tree() | `backend/src/policy/tree/validation.rs` | 95-134 |
| Node ID uniqueness | `backend/src/policy/tree/validation.rs` | 141-186 |
| Tree depth | `backend/src/policy/tree/validation.rs` | 193-232 |
| Field references | `backend/src/policy/tree/validation.rs` | 244-324 |
| is_transaction_only_field() | `backend/src/policy/tree/validation.rs` | 327-353 |
| is_bank_level_field() | `backend/src/policy/tree/validation.rs` | 355-418 |
| Parameter references | `backend/src/policy/tree/validation.rs` | 455-523 |
| Division safety | `backend/src/policy/tree/validation.rs` | 556-633 |
