# Tree Node Types

> **Reference: The Two Node Types in Policy Decision Trees**

## Overview

Every decision tree is composed of exactly two types of nodes:
1. **Condition** - Branch points that evaluate boolean expressions
2. **Action** - Terminal nodes that return decisions

## Node Type Summary

| Type | Purpose | Has Children | JSON `type` Field |
|------|---------|--------------|-------------------|
| Condition | Evaluate expression, branch based on result | Yes (on_true, on_false) | `"condition"` |
| Action | Return a decision | No | `"action"` |

---

## 1. Condition Node

### Purpose
Evaluates a boolean expression and branches to either `on_true` or `on_false` child node based on the result.

### JSON Schema
```json
{
  "type": "condition",
  "node_id": "<unique_string>",
  "description": "<optional_human_readable_description>",
  "condition": <Expression>,
  "on_true": <TreeNode>,
  "on_false": <TreeNode>
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"condition"` |
| `node_id` | string | Yes | Unique identifier for this node (across all trees in the policy) |
| `description` | string | No | Human-readable description of what this condition checks |
| `condition` | Expression | Yes | Boolean expression to evaluate (see [expressions.md](expressions.md)) |
| `on_true` | TreeNode | Yes | Node to visit if condition evaluates to true |
| `on_false` | TreeNode | Yes | Node to visit if condition evaluates to false |

### Example: Simple Liquidity Check
```json
{
  "type": "condition",
  "node_id": "N1_LiquidityCheck",
  "description": "Do we have enough liquidity to pay?",
  "condition": {
    "op": ">=",
    "left": {"field": "effective_liquidity"},
    "right": {"field": "remaining_amount"}
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_Release",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "node_id": "A2_Hold",
    "action": "Hold",
    "parameters": {
      "reason": {"value": "InsufficientLiquidity"}
    }
  }
}
```

### Example: Nested Conditions
```json
{
  "type": "condition",
  "node_id": "N1_CheckUrgent",
  "description": "Is transaction urgent?",
  "condition": {
    "op": "<=",
    "left": {"field": "ticks_to_deadline"},
    "right": {"value": 5}
  },
  "on_true": {
    "type": "action",
    "node_id": "A1_ReleaseUrgent",
    "action": "Release"
  },
  "on_false": {
    "type": "condition",
    "node_id": "N2_CheckBuffer",
    "description": "Would payment violate liquidity buffer?",
    "condition": {
      "op": "<",
      "left": {
        "compute": {
          "op": "-",
          "left": {"field": "balance"},
          "right": {"field": "remaining_amount"}
        }
      },
      "right": {"param": "target_buffer"}
    },
    "on_true": {
      "type": "action",
      "node_id": "A2_Hold",
      "action": "Hold"
    },
    "on_false": {
      "type": "action",
      "node_id": "A3_Release",
      "action": "Release"
    }
  }
}
```

### Evaluation Semantics
1. Expression is evaluated using the current context
2. If result is `true` (or non-zero for numeric values), traverse `on_true`
3. If result is `false` (or zero), traverse `on_false`
4. Recursively continue until an Action node is reached

### Implementation Location
- Rust enum: `simulator/src/policy/tree/types.rs:71-89`
- Traversal: `simulator/src/policy/tree/interpreter.rs:518-532`

---

## 2. Action Node

### Purpose
Terminal node that returns a decision. Contains the action type and any parameters needed to execute that action.

### JSON Schema
```json
{
  "type": "action",
  "node_id": "<unique_string>",
  "action": "<ActionType>",
  "parameters": {
    "<param_name>": <ValueOrCompute>,
    ...
  }
}
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | string | Yes | Must be `"action"` |
| `node_id` | string | Yes | Unique identifier for this node |
| `action` | string | Yes | Action type (see [actions.md](actions.md)) |
| `parameters` | object | No | Action-specific parameters (see [actions.md](actions.md)) |

### Minimal Action Node
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Release"
}
```

### Action Node with Parameters
```json
{
  "type": "action",
  "node_id": "A2_Split",
  "action": "Split",
  "parameters": {
    "num_splits": {"value": 4}
  }
}
```

### Action Node with Computed Parameters
```json
{
  "type": "action",
  "node_id": "A3_StaggerSplit",
  "action": "StaggerSplit",
  "parameters": {
    "num_splits": {"value": 5},
    "stagger_first_now": {"value": 2},
    "stagger_gap_ticks": {
      "compute": {
        "op": "/",
        "left": {"field": "ticks_to_deadline"},
        "right": {"value": 4}
      }
    },
    "priority_boost_children": {"value": 2}
  }
}
```

### Action Node with Field Reference Parameters
```json
{
  "type": "action",
  "node_id": "A4_PostCollateral",
  "action": "PostCollateral",
  "parameters": {
    "amount": {"field": "queue1_liquidity_gap"},
    "reason": {"value": "UrgentLiquidityNeed"}
  }
}
```

### Parameter Value Types
Parameters use `ValueOrCompute` type, which can be:

| Type | JSON Syntax | Example |
|------|-------------|---------|
| Literal | `{"value": <number\|string\|boolean>}` | `{"value": 5}` |
| Field reference | `{"field": "<field_name>"}` | `{"field": "balance"}` |
| Parameter reference | `{"param": "<param_name>"}` | `{"param": "threshold"}` |
| Computation | `{"compute": <Computation>}` | `{"compute": {"op": "+", ...}}` |

### Implementation Location
- Rust enum: `simulator/src/policy/tree/types.rs:91-103`
- Decision builder: `simulator/src/policy/tree/interpreter.rs:622-933`

---

## Node ID Requirements

### Uniqueness
- Every node ID must be unique **across all trees** in a policy
- Duplicate IDs trigger validation error: `DuplicateNodeId`

### Naming Conventions (Recommended)
While not enforced, these conventions improve readability:

| Convention | Example | Use For |
|------------|---------|---------|
| `N<num>_<desc>` | `N1_CheckLiquidity` | Condition nodes |
| `A<num>_<desc>` | `A1_Release` | Action nodes |
| `B<num>_<desc>` | `B1_SetBudget` | Bank tree nodes |
| `SC<num>_<desc>` | `SC1_PostCollateral` | Strategic collateral nodes |
| `EOT<num>_<desc>` | `EOT1_Withdraw` | End-of-tick collateral nodes |

### Decision Path Tracking
Node IDs are recorded in the decision path for debugging:
```
N1_CheckUrgent(true) → N2_CheckLiquidity(false) → A3_Hold
```

---

## Tree Depth Limits

- Maximum depth: **100 levels**
- Exceeding this limit triggers: `ExcessiveDepth` validation error
- Designed to prevent stack overflow during evaluation

### Calculating Depth
- Root node is depth 0
- Each Condition node's children are depth + 1
- Action nodes don't increase depth (they're terminal)

---

## Common Patterns

### 1. Binary Decision
```json
{
  "type": "condition",
  "node_id": "N1",
  "condition": {"op": ">=", "left": {"field": "A"}, "right": {"field": "B"}},
  "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
  "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
}
```

### 2. Cascading Conditions (if/else if/else)
```json
{
  "type": "condition",
  "node_id": "N1_First",
  "condition": {"op": "==", "left": {"field": "X"}, "right": {"value": 1}},
  "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
  "on_false": {
    "type": "condition",
    "node_id": "N2_Second",
    "condition": {"op": "==", "left": {"field": "X"}, "right": {"value": 2}},
    "on_true": {"type": "action", "node_id": "A2", "action": "Hold"},
    "on_false": {"type": "action", "node_id": "A3", "action": "Drop"}
  }
}
```

### 3. Multi-Factor Decision (AND logic)
```json
{
  "type": "condition",
  "node_id": "N1",
  "condition": {
    "op": "and",
    "conditions": [
      {"op": ">", "left": {"field": "balance"}, "right": {"field": "amount"}},
      {"op": "<", "left": {"field": "ticks_to_deadline"}, "right": {"value": 10}}
    ]
  },
  "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
  "on_false": {"type": "action", "node_id": "A2", "action": "Hold"}
}
```

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| TreeNode enum | `simulator/src/policy/tree/types.rs` | 69-103 |
| node_id() method | `simulator/src/policy/tree/types.rs` | 354-360 |
| is_condition() method | `simulator/src/policy/tree/types.rs` | 363-365 |
| is_action() method | `simulator/src/policy/tree/types.rs` | 368-370 |
| traverse_node() | `simulator/src/policy/tree/interpreter.rs` | 501-532 |
| Node ID validation | `simulator/src/policy/tree/validation.rs` | 141-186 |
