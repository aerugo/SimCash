# Starlark Policy System Implementation Plan

**Document Version**: 2.0
**Date**: October 30, 2025
**Status**: Planning Complete → Ready for Implementation
**Related**: [grand_plan.md](grand_plan.md), [policy_dsl_design.md](policy_dsl_design.md), [persistence_implementation_plan.md](persistence_implementation_plan.md)

---

## Executive Summary

### Purpose

Replace the current JSON DSL policy system with **Starlark**, a Python-like sandboxed scripting language that enables stateful, expressive policies while maintaining determinism and safety for LLM-generated code execution.

### Strategic Context

**Current System (JSON DSL) - Phase 9 Complete**:
- ✅ Safe sandboxing, LLM-editable, validation pipeline
- ❌ **Cannot express**: Stateful logic, queue iteration, moving averages, adaptive strategies
- ❌ **Verbose**: Complex logic requires deeply nested JSON

**Proposed System (Starlark)**:
- ✅ Full programming language with Python-like syntax
- ✅ **Stateful policies**: Track history, learn, adapt
- ✅ **Deterministic by design**: Cannot introduce non-determinism
- ✅ **Database-backed state**: Persistent across simulations
- ✅ **LLM-friendly**: 10-100x more training data than alternatives

### What This Enables

```python
# JSON DSL: Cannot express this
# ❌ No loops, no state, no moving averages

# Starlark: Natural expression
def evaluate_queue(transactions, agent, system, state):
    """Adaptive policy that learns optimal thresholds."""

    # Initialize state on first call
    if "threshold" not in state:
        state["threshold"] = 50000
        state["success_history"] = []

    # Calculate 10-tick moving average
    if len(state["success_history"]) >= 10:
        recent_success = sum(state["success_history"][-10:]) / 10

        # Adapt threshold based on performance
        if recent_success > 0.9:
            state["threshold"] = min(state["threshold"] * 1.1, 200000)
        elif recent_success < 0.5:
            state["threshold"] = max(state["threshold"] * 0.9, 10000)

    # Find optimal transaction subset
    decisions = []
    for tx in transactions:
        if tx.amount < state["threshold"]:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})

    return decisions
```

**Timeline**: 24-32 days (6-8 weeks) for complete implementation

---

## Part I: Starlark Syntax and Policy Patterns

### 1.1 Starlark Language Overview

Starlark is a **dialect of Python** designed for configuration and embedded scripting. Key characteristics:

**Similarities to Python**:
- Same syntax for functions, loops, conditionals
- Lists, dicts, strings, numbers work identically
- List comprehensions, lambda functions supported
- `for`, `if/elif/else`, function definitions

**Differences from Python**:
- **No mutation of globals**: Can only mutate local variables and `state` dict
- **No `while` loops**: Only `for` loops over iterables (prevents infinite loops)
- **No imports**: Hermetic execution, no external modules
- **No I/O**: No `open()`, `print()`, network access
- **Deterministic**: No `random()`, `time()`, `hash()` with undefined order

**Why Starlark?**:
1. **Safety**: Hermetic by design, cannot escape sandbox
2. **Determinism**: Language-level guarantees
3. **LLM Training**: Extensive Python training data applies
4. **Battle-tested**: Used by Google (Bazel), Meta, Dropbox

### 1.2 Entry Point Signatures

Starlark policies define up to **three entry point functions**:

#### Payment Release Decisions (Required)

```python
def evaluate_queue(transactions, agent, system, state):
    """Called during STEP 2 of tick loop.

    Args:
        transactions: List[Transaction] - Agent's Queue 1 contents
        agent: Agent - Balance, liquidity, queues, collateral
        system: System - Current tick, global metrics
        state: Dict - Persistent state (mutable)

    Returns:
        List[Dict] - Decisions with actions

    Decision Format:
        {"action": "Release", "tx_id": "TX_001"}
        {"action": "Hold", "tx_id": "TX_002"}
        {"action": "Split", "tx_id": "TX_003", "splits": 4}
        {"action": "Drop", "tx_id": "TX_004"}
    """
    decisions = []
    for tx in transactions:
        # Your logic here
        decisions.append({"action": "Release", "tx_id": tx.id})
    return decisions
```

#### Strategic Collateral (Optional)

```python
def evaluate_strategic_collateral(agent, system, state):
    """Called BEFORE policy evaluation (STEP 1.5).

    Has visibility into Queue 1 (queue1_liquidity_gap available).
    Use for: Forward-looking collateral to enable settlements.

    Returns:
        Dict - Single collateral decision

    Decision Format:
        {"action": "Post", "amount": 100000, "reason": "Cover queue gap"}
        {"action": "Withdraw", "amount": 50000, "reason": "Excess capacity"}
        {"action": "Hold"}
    """
    if agent.queue1_liquidity_gap > 0:
        return {"action": "Post", "amount": agent.queue1_liquidity_gap}
    return {"action": "Hold"}
```

#### End-of-Tick Collateral (Optional)

```python
def evaluate_end_of_tick_collateral(agent, system, state):
    """Called AFTER settlements and LSM (STEP 8).

    No Queue 1 visibility (queue1_liquidity_gap = None).
    Use for: Cleanup excess collateral, respond to final state.

    Returns:
        Dict - Same format as strategic collateral
    """
    # Withdraw excess if utilization low
    if agent.collateral_utilization < 0.3 and agent.posted_collateral > 0:
        withdraw = int(agent.posted_collateral * 0.5)
        return {"action": "Withdraw", "amount": withdraw}
    return {"action": "Hold"}
```

**Design Notes**:
- All three share the same `state` dict
- Only `evaluate_queue` is required
- Two-layer collateral matches Phase 8 architecture

### 1.3 API Surface - Available Fields

#### Transaction Object

```python
tx.id                    # str: "TX_001"
tx.amount                # int: Total amount in cents (100000 = $1000)
tx.remaining_amount      # int: Unsettled portion (for partial settlements)
tx.priority              # int: 1-10 (10 = highest)
tx.ticks_to_deadline     # int: Can be negative if past deadline
tx.is_split              # bool: True if created from splitting
tx.is_past_deadline      # bool: True if deadline expired
tx.sender_id             # str: "BANK_A"
tx.receiver_id           # str: "BANK_B"
```

#### Agent Object

```python
# Core Fields
agent.id                        # str: "BANK_A"
agent.balance                   # int: Current balance in cents
agent.available_liquidity       # int: Balance - reserved amounts
agent.queue_size                # int: Number of txs in Queue 1
agent.queue_total_value         # int: Sum of all queued amounts

# Collateral Fields
agent.posted_collateral         # int: Currently posted collateral
agent.collateral_capacity       # int: Maximum capacity
agent.remaining_capacity        # int: Unused capacity
agent.collateral_utilization    # float: 0.0-1.0 (posted/capacity)

# Strategic Layer Only (None in end-of-tick)
agent.queue1_liquidity_gap      # int|None: Shortfall to release all Queue 1
agent.queue1_total_value        # int|None: Total value of Queue 1
```

#### System Object

```python
system.current_tick         # int: Current simulation tick
system.total_agents         # int: Number of agents in simulation
system.rtgs_queue_size      # int: Size of global RTGS queue (Queue 2)
```

#### State Dict (Persistent)

```python
# State is a mutable dict that persists across calls
# Initialize on first use, modify freely

if "my_metric" not in state:
    state["my_metric"] = 0
    state["history"] = []
    state["thresholds"] = {"low": 1000, "high": 10000}

state["my_metric"] += 1
state["history"].append(agent.balance)
```

### 1.4 Common Policy Patterns

#### Pattern 1: Simple Threshold

```python
THRESHOLD = 50000

def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if tx.amount < THRESHOLD:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
```

#### Pattern 2: Deadline-Aware

```python
URGENCY_TICKS = 5

def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if tx.ticks_to_deadline <= URGENCY_TICKS:
            # Urgent - release immediately
            decisions.append({"action": "Release", "tx_id": tx.id})
        elif agent.available_liquidity >= tx.amount:
            # Have liquidity - release
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            # Hold until liquidity arrives
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
```

#### Pattern 3: Liquidity Buffer Management

```python
TARGET_BUFFER = 100000

def evaluate_queue(transactions, agent, system, state):
    decisions = []
    current_liquidity = agent.available_liquidity

    for tx in transactions:
        # Check if we can maintain buffer after release
        liquidity_after = current_liquidity - tx.amount

        if liquidity_after >= TARGET_BUFFER:
            decisions.append({"action": "Release", "tx_id": tx.id})
            current_liquidity -= tx.amount  # Update tracking
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})

    return decisions
```

#### Pattern 4: Priority-Based Sorting

```python
def evaluate_queue(transactions, agent, system, state):
    # Sort by urgency score (priority * deadline pressure)
    def urgency_score(tx):
        deadline_pressure = max(1, 10 - tx.ticks_to_deadline)
        return tx.priority * deadline_pressure

    sorted_txs = sorted(transactions, key=urgency_score, reverse=True)

    # Release top N that fit in budget
    decisions = []
    budget = agent.available_liquidity

    for tx in sorted_txs:
        if budget >= tx.amount:
            decisions.append({"action": "Release", "tx_id": tx.id})
            budget -= tx.amount
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})

    return decisions
```

#### Pattern 5: Stateful Adaptive Threshold

```python
def evaluate_queue(transactions, agent, system, state):
    # Initialize state
    if "threshold" not in state:
        state["threshold"] = 50000
        state["settled_count"] = 0
        state["held_count"] = 0
        state["last_adjustment_tick"] = 0

    # Adapt threshold every 10 ticks
    if system.current_tick - state["last_adjustment_tick"] >= 10:
        total = state["settled_count"] + state["held_count"]
        if total > 0:
            success_rate = state["settled_count"] / total

            if success_rate > 0.8:
                # Too conservative - increase threshold
                state["threshold"] = min(state["threshold"] * 1.2, 200000)
            elif success_rate < 0.4:
                # Too aggressive - decrease threshold
                state["threshold"] = max(state["threshold"] * 0.8, 10000)

        # Reset counters
        state["settled_count"] = 0
        state["held_count"] = 0
        state["last_adjustment_tick"] = system.current_tick

    # Apply threshold
    decisions = []
    for tx in transactions:
        if tx.amount < state["threshold"]:
            decisions.append({"action": "Release", "tx_id": tx.id})
            state["settled_count"] += 1
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
            state["held_count"] += 1

    return decisions
```

#### Pattern 6: Moving Average Tracking

```python
def evaluate_queue(transactions, agent, system, state):
    # Initialize state
    if "balance_history" not in state:
        state["balance_history"] = []
        state["avg_balance"] = agent.balance

    # Track balance history
    state["balance_history"].append(agent.balance)

    # Keep only last 20 ticks
    if len(state["balance_history"]) > 20:
        state["balance_history"] = state["balance_history"][-20:]

    # Calculate moving average
    state["avg_balance"] = sum(state["balance_history"]) / len(state["balance_history"])

    # Be more conservative if balance trending down
    is_declining = agent.balance < state["avg_balance"] * 0.9

    decisions = []
    for tx in transactions:
        if is_declining:
            # Stricter when declining
            if tx.ticks_to_deadline <= 3:
                decisions.append({"action": "Release", "tx_id": tx.id})
            else:
                decisions.append({"action": "Hold", "tx_id": tx.id})
        else:
            # Normal operation
            if agent.available_liquidity >= tx.amount:
                decisions.append({"action": "Release", "tx_id": tx.id})
            else:
                decisions.append({"action": "Hold", "tx_id": tx.id})

    return decisions
```

#### Pattern 7: Three-Layer Policy (Complete)

```python
"""Complete policy with payment + collateral decisions."""

# Constants
PAYMENT_THRESHOLD = 50000
COLLATERAL_BUFFER = 100000
URGENCY_TICKS = 5

def evaluate_queue(transactions, agent, system, state):
    """Payment release logic."""
    decisions = []

    for tx in transactions:
        if tx.ticks_to_deadline <= URGENCY_TICKS:
            decisions.append({"action": "Release", "tx_id": tx.id})
        elif tx.amount < PAYMENT_THRESHOLD:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})

    return decisions

def evaluate_strategic_collateral(agent, system, state):
    """Forward-looking collateral to enable settlements."""

    # If we have a liquidity gap in Queue 1, post collateral to cover it
    if agent.queue1_liquidity_gap > 0:
        # Post enough to cover gap plus buffer
        amount = agent.queue1_liquidity_gap + COLLATERAL_BUFFER

        # Don't exceed remaining capacity
        amount = min(amount, agent.remaining_capacity)

        if amount > 0:
            return {
                "action": "Post",
                "amount": amount,
                "reason": "Cover queue gap"
            }

    return {"action": "Hold"}

def evaluate_end_of_tick_collateral(agent, system, state):
    """Cleanup excess collateral after settlements."""

    # If utilization is low, withdraw half
    if agent.collateral_utilization < 0.3 and agent.posted_collateral > 0:
        withdraw = int(agent.posted_collateral * 0.5)
        return {
            "action": "Withdraw",
            "amount": withdraw,
            "reason": "Low utilization cleanup"
        }

    # If utilization very high, consider posting more (proactive)
    if agent.collateral_utilization > 0.9 and agent.remaining_capacity > 0:
        post = min(agent.remaining_capacity, 50000)
        return {
            "action": "Post",
            "amount": post,
            "reason": "Proactive capacity expansion"
        }

    return {"action": "Hold"}
```

### 1.5 Starlark Reference Examples

**Canonical References** (for LLM training and developer reference):

1. **Bazel Rules** (starlark-lang.org)
   - Official Starlark specification
   - Language syntax and semantics
   - Built-in functions reference

2. **Google Bazel Documentation**
   - Extensive real-world Starlark usage
   - Complex rule definitions
   - Pattern library

3. **starlark-rust Documentation**
   - Rust-specific API we're using
   - Performance characteristics
   - Resource limiting mechanisms

4. **Buck2 Starlark Rules** (Meta)
   - Modern Starlark usage
   - Large-scale examples
   - Best practices

**Example Policy References** (to create):

```
examples/policies/
├── 01_simple_threshold.star          # Basic threshold policy
├── 02_deadline_aware.star             # Deadline pressure handling
├── 03_liquidity_buffer.star           # Buffer management
├── 04_priority_based.star             # Priority sorting
├── 05_adaptive_threshold.star         # Stateful learning
├── 06_moving_average.star             # Historical tracking
├── 07_three_layer_complete.star       # Payment + collateral
├── 08_queue_optimization.star         # Optimal subset selection
├── 09_risk_adjusted.star              # Risk-based scoring
└── 10_multi_agent_response.star       # Respond to system state
```

---

## Part II: JSON to Starlark Conversion

### 2.1 Conversion Principles

**JSON DSL Structure**:
- Decision trees represented as nested JSON
- Conditions check fields and compare values
- Actions are leaf nodes (Release, Hold, Drop)
- No iteration, no state, limited arithmetic

**Starlark Equivalent**:
- If/else chains replace tree traversal
- Direct field access replaces path navigation
- Loops enable batch processing
- State dict replaces parameters

### 2.2 Conversion Algorithm

#### Step 1: Identify Tree Structure

```python
# JSON DSL Pattern
{
  "condition": {
    "field": "tx.amount",
    "operator": "<",
    "value": 50000
  },
  "true_branch": {"action": "Release"},
  "false_branch": {"action": "Hold"}
}
```

**Starlark Equivalent**:
```python
def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if tx.amount < 50000:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
```

#### Step 2: Flatten Nested Conditions

```python
# JSON DSL: Nested tree
{
  "condition": {"field": "tx.ticks_to_deadline", "operator": "<=", "value": 5},
  "true_branch": {"action": "Release"},
  "false_branch": {
    "condition": {"field": "tx.amount", "operator": "<", "value": 50000},
    "true_branch": {"action": "Release"},
    "false_branch": {"action": "Hold"}
  }
}
```

**Starlark Equivalent**:
```python
def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if tx.ticks_to_deadline <= 5:
            decisions.append({"action": "Release", "tx_id": tx.id})
        elif tx.amount < 50000:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
```

#### Step 3: Convert Parameters to State

```python
# JSON DSL: Parameters (static)
{
  "parameters": {
    "threshold": 50000,
    "urgency_ticks": 5
  },
  "tree": { ... }
}
```

**Starlark Equivalent**:
```python
# Option 1: Constants (if truly static)
THRESHOLD = 50000
URGENCY_TICKS = 5

# Option 2: State (if should be adaptive)
def evaluate_queue(transactions, agent, system, state):
    if "threshold" not in state:
        state["threshold"] = 50000
        state["urgency_ticks"] = 5

    # Can now adapt these over time
    # ...
```

#### Step 4: Handle Field Paths

```python
# JSON DSL: Dot-separated paths
{"field": "agent.available_liquidity", "operator": ">", "value": 100000}
{"field": "tx.ticks_to_deadline", "operator": "<=", "value": 5}
```

**Starlark Equivalent**:
```python
# Direct attribute access
if agent.available_liquidity > 100000:
    # ...

if tx.ticks_to_deadline <= 5:
    # ...
```

### 2.3 Complete Conversion Examples

#### Example 1: Simple Threshold Policy

**JSON DSL**:
```json
{
  "name": "simple_threshold",
  "parameters": {
    "threshold": 50000
  },
  "tree": {
    "condition": {
      "field": "tx.amount",
      "operator": "<",
      "value": {"param": "threshold"}
    },
    "true_branch": {"action": "Release"},
    "false_branch": {"action": "Hold"}
  }
}
```

**Starlark**:
```python
THRESHOLD = 50000

def evaluate_queue(transactions, agent, system, state):
    return [
        {"action": "Release", "tx_id": tx.id} if tx.amount < THRESHOLD
        else {"action": "Hold", "tx_id": tx.id}
        for tx in transactions
    ]
```

#### Example 2: Multi-Factor Decision

**JSON DSL**:
```json
{
  "name": "multi_factor",
  "tree": {
    "condition": {
      "field": "tx.ticks_to_deadline",
      "operator": "<=",
      "value": 5
    },
    "true_branch": {"action": "Release"},
    "false_branch": {
      "condition": {
        "field": "tx.priority",
        "operator": ">=",
        "value": 8
      },
      "true_branch": {
        "condition": {
          "field": "agent.available_liquidity",
          "operator": ">=",
          "value": {"field": "tx.amount"}
        },
        "true_branch": {"action": "Release"},
        "false_branch": {"action": "Hold"}
      },
      "false_branch": {
        "condition": {
          "field": "tx.amount",
          "operator": "<",
          "value": 50000
        },
        "true_branch": {"action": "Release"},
        "false_branch": {"action": "Hold"}
      }
    }
  }
}
```

**Starlark**:
```python
def evaluate_queue(transactions, agent, system, state):
    decisions = []

    for tx in transactions:
        # Urgent transactions always release
        if tx.ticks_to_deadline <= 5:
            decisions.append({"action": "Release", "tx_id": tx.id})

        # High priority with liquidity
        elif tx.priority >= 8 and agent.available_liquidity >= tx.amount:
            decisions.append({"action": "Release", "tx_id": tx.id})

        # Small transactions
        elif tx.amount < 50000:
            decisions.append({"action": "Release", "tx_id": tx.id})

        # Default: hold
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})

    return decisions
```

### 2.4 Automated Conversion Tool

**Location**: `api/payment_simulator/policy/converter.py`

```python
"""Convert JSON DSL decision trees to Starlark policies."""

from typing import Any, Dict, List
import json


class JSONToStarlarkConverter:
    """Converts JSON decision trees to equivalent Starlark code."""

    def __init__(self, json_tree: Dict[str, Any]):
        self.tree = json_tree
        self.parameters = json_tree.get("parameters", {})
        self.indent_level = 0

    def convert(self) -> str:
        """Main conversion entry point."""
        lines = []

        # Add header comment
        lines.append('"""Converted from JSON DSL decision tree."""')
        lines.append("")

        # Add parameters as constants
        if self.parameters:
            lines.append("# Parameters")
            for name, value in self.parameters.items():
                const_name = name.upper()
                lines.append(f"{const_name} = {value}")
            lines.append("")

        # Generate function
        lines.append("def evaluate_queue(transactions, agent, system, state):")
        lines.append("    decisions = []")
        lines.append("    ")
        lines.append("    for tx in transactions:")

        # Convert tree to if/elif/else chain
        self.indent_level = 2
        tree_code = self._convert_node(self.tree.get("tree", {}))
        lines.extend(tree_code)

        lines.append("    ")
        lines.append("    return decisions")

        return "\n".join(lines)

    def _convert_node(self, node: Dict[str, Any]) -> List[str]:
        """Recursively convert tree nodes to Starlark code."""
        lines = []
        indent = "    " * self.indent_level

        if "action" in node:
            # Leaf node - emit action
            action = node["action"]
            lines.append(f'{indent}decisions.append({{"action": "{action}", "tx_id": tx.id}})')
            return lines

        if "condition" in node:
            # Branch node - emit if/else
            condition = self._convert_condition(node["condition"])

            lines.append(f"{indent}if {condition}:")
            self.indent_level += 1
            lines.extend(self._convert_node(node.get("true_branch", {})))
            self.indent_level -= 1

            if "false_branch" in node:
                lines.append(f"{indent}else:")
                self.indent_level += 1
                lines.extend(self._convert_node(node["false_branch"]))
                self.indent_level -= 1

        return lines

    def _convert_condition(self, condition: Dict[str, Any]) -> str:
        """Convert condition dict to Starlark boolean expression."""
        field = condition["field"]
        operator = condition["operator"]
        value = condition["value"]

        # Handle parameter references
        if isinstance(value, dict) and "param" in value:
            param_name = value["param"].upper()
            value_str = param_name
        elif isinstance(value, dict) and "field" in value:
            value_str = value["field"]
        else:
            value_str = repr(value)

        return f"{field} {operator} {value_str}"


def convert_json_to_starlark(json_path: str, output_path: str) -> None:
    """Convert JSON DSL file to Starlark policy file."""
    with open(json_path, 'r') as f:
        tree = json.load(f)

    converter = JSONToStarlarkConverter(tree)
    starlark_code = converter.convert()

    with open(output_path, 'w') as f:
        f.write(starlark_code)

    print(f"✅ Converted {json_path} → {output_path}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python converter.py <input.json> <output.star>")
        sys.exit(1)

    convert_json_to_starlark(sys.argv[1], sys.argv[2])
```

**Usage**:
```bash
# Convert existing JSON policy
python api/payment_simulator/policy/converter.py \
    policies/my_policy.json \
    policies/my_policy.star

# Verify converted policy
payment-sim test-policy policies/my_policy.star --scenario test.yaml
```

---

## Part III: Implementation Phases (TDD Approach)

### Overview: Test-Driven Development Philosophy

**TDD Cycle** for each feature:
1. **RED**: Write failing test first
2. **GREEN**: Implement minimal code to pass
3. **REFACTOR**: Clean up while keeping tests green
4. **REPEAT**: Next test

**Test Pyramid**:
- **Unit tests** (100+): Fast, isolated, Rust-only
- **Integration tests** (30-40): Cross-boundary, FFI
- **E2E tests** (10-15): Full simulation runs

### Phase 1: Foundation (3-4 days) - TDD

**Goal**: Set up Starlark integration with failing tests first

#### Day 1: Dependencies & Structure (TDD)

**STEP 1: Write Test (RED)**

```rust
// backend/tests/starlark_foundation_test.rs
#[test]
fn test_starlark_policy_creation() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    return []
    "#;

    let policy = StarlarkPolicy::new(script.to_string());
    assert!(policy.is_ok(), "Should create policy from valid script");
}

#[test]
fn test_starlark_syntax_error_detection() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state)  # Missing colon
    return []
    "#;

    let policy = StarlarkPolicy::new(script.to_string());
    assert!(policy.is_err(), "Should reject invalid syntax");
    assert!(policy.unwrap_err().contains("syntax"));
}
```

**STEP 2: Implement (GREEN)**

```rust
// backend/Cargo.toml
[dependencies]
starlark = "0.12"
allocative = "0.3"

// backend/src/policy/starlark/mod.rs
pub mod executor;
pub mod api;

pub use executor::StarlarkPolicy;

// backend/src/policy/starlark/executor.rs
use starlark::syntax::{AstModule, Dialect};
use std::sync::Arc;

pub struct StarlarkPolicy {
    script: String,
    compiled: Arc<AstModule>,
}

impl StarlarkPolicy {
    pub fn new(script: String) -> Result<Self, String> {
        let compiled = AstModule::parse(
            "policy.star",
            script.clone(),
            &Dialect::Standard
        ).map_err(|e| format!("Syntax error: {}", e))?;

        Ok(Self {
            script,
            compiled: Arc::new(compiled),
        })
    }
}
```

**STEP 3: Run Tests (GREEN)**

```bash
cargo test --no-default-features test_starlark_foundation
# Expected: 2 passed
```

#### Day 2-3: API Surface (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_transaction_fields_accessible() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    result = []
    for tx in transactions:
        # Access all transaction fields
        _ = tx.id
        _ = tx.amount
        _ = tx.remaining_amount
        _ = tx.priority
        _ = tx.ticks_to_deadline
        _ = tx.is_split
        _ = tx.is_past_deadline
        result.append({"action": "Release", "tx_id": tx.id})
    return result
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let agent = create_test_agent_with_queue(3);
    let state = create_test_state();

    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());
    assert_eq!(decisions.len(), 3, "Should process all transactions");
}

#[test]
fn test_agent_fields_accessible() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    # Access all agent fields
    _ = agent.id
    _ = agent.balance
    _ = agent.available_liquidity
    _ = agent.queue_size
    _ = agent.queue_total_value
    return []
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let result = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());
    assert!(result.is_empty());
}
```

**STEP 2: Implement (GREEN)**

```rust
// backend/src/policy/starlark/api.rs
use allocative::Allocative;
use serde::{Deserialize, Serialize};
use starlark::values::{
    AllocValue, Heap, ProvidesStaticType, StarlarkValue, Value,
    ValueLike,
};
use starlark_derive::{starlark_value, NoSerialize};

#[derive(Debug, Clone, ProvidesStaticType, NoSerialize, Allocative)]
pub struct StarTransaction {
    pub id: String,
    pub amount: i64,
    pub remaining_amount: i64,
    pub priority: u8,
    pub ticks_to_deadline: i64,
    pub is_split: bool,
    pub is_past_deadline: bool,
}

#[starlark_value(type = "Transaction")]
impl<'v> StarlarkValue<'v> for StarTransaction {
    fn get_attr(&self, name: &str, _heap: &'v Heap) -> Option<Value<'v>> {
        match name {
            "id" => Some(_heap.alloc(self.id.clone())),
            "amount" => Some(_heap.alloc(self.amount)),
            "remaining_amount" => Some(_heap.alloc(self.remaining_amount)),
            "priority" => Some(_heap.alloc(self.priority as i32)),
            "ticks_to_deadline" => Some(_heap.alloc(self.ticks_to_deadline)),
            "is_split" => Some(_heap.alloc(self.is_split)),
            "is_past_deadline" => Some(_heap.alloc(self.is_past_deadline)),
            _ => None,
        }
    }

    fn has_attr(&self, name: &str, _heap: &'v Heap) -> bool {
        matches!(name, "id" | "amount" | "remaining_amount" | "priority" |
                       "ticks_to_deadline" | "is_split" | "is_past_deadline")
    }
}

impl<'v> AllocValue<'v> for StarTransaction {
    fn alloc_value(self, heap: &'v Heap) -> Value<'v> {
        heap.alloc_complex(self)
    }
}

// Similar implementations for StarAgent, StarSystem
```

**STEP 3: Run Tests (GREEN)**

```bash
cargo test --no-default-features test_transaction_fields
cargo test --no-default-features test_agent_fields
```

#### Day 4: Basic Executor (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_simple_release_all() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    return [{"action": "Release", "tx_id": tx.id} for tx in transactions]
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let agent = create_test_agent_with_queue(5);
    let state = create_test_state();

    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    assert_eq!(decisions.len(), 5);
    for decision in decisions {
        assert!(matches!(decision, ReleaseDecision::SubmitFull { .. }));
    }
}
```

**STEP 2: Implement (GREEN)**

```rust
// backend/src/policy/starlark/executor.rs
use starlark::environment::{GlobalsBuilder, Module};
use starlark::eval::Evaluator;
use starlark::values::list::ListOf;
use super::api::{StarTransaction, StarAgent, StarSystem};

impl CashManagerPolicy for StarlarkPolicy {
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        _cost_rates: &CostRates,
    ) -> Vec<ReleaseDecision> {
        match self.execute(agent, state, tick) {
            Ok(decisions) => decisions,
            Err(e) => {
                eprintln!("Starlark execution error: {}", e);
                vec![] // Safe fallback
            }
        }
    }
}

impl StarlarkPolicy {
    fn execute(
        &self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
    ) -> Result<Vec<ReleaseDecision>, String> {
        // Create evaluation context
        let module = Module::new();
        let globals = GlobalsBuilder::standard().build();
        let mut eval = Evaluator::new(&module);

        // Set resource limits
        eval.set_max_steps(100_000)
            .map_err(|e| format!("Failed to set limits: {}", e))?;

        // Execute module to define functions
        eval.eval_module(self.compiled.clone(), &globals)
            .map_err(|e| format!("Module error: {}", e))?;

        // Build context
        let transactions = self.build_transactions(agent, state, tick, eval.heap());
        let agent_view = self.build_agent(agent, state, eval.heap());
        let system_view = self.build_system(state, tick, eval.heap());
        let state_dict = eval.heap().alloc(Dict::new());

        // Get function
        let func = module.get("evaluate_queue")
            .ok_or("evaluate_queue function not found")?;

        // Call function
        let result = eval.eval_function(
            func,
            &[transactions, agent_view, system_view, state_dict],
            &[]
        ).map_err(|e| format!("Execution error: {}", e))?;

        // Parse result
        self.parse_decisions(result)
    }

    fn parse_decisions(&self, result: Value) -> Result<Vec<ReleaseDecision>, String> {
        let list = ListOf::<Dict>::from_value(result)
            .ok_or("Expected list of decision dicts")?;

        let mut decisions = Vec::new();

        for dict in list.iter() {
            let action = dict.get("action")
                .ok_or("Missing 'action' field")?
                .unpack_str()
                .ok_or("'action' must be string")?;

            let tx_id = dict.get("tx_id")
                .ok_or("Missing 'tx_id' field")?
                .unpack_str()
                .ok_or("'tx_id' must be string")?
                .to_string();

            let decision = match action {
                "Release" => ReleaseDecision::SubmitFull { tx_id },
                "Hold" => ReleaseDecision::Hold {
                    tx_id,
                    reason: HoldReason::Custom("Starlark".to_string())
                },
                "Drop" => ReleaseDecision::Drop { tx_id },
                "Split" => {
                    let splits = dict.get("splits")
                        .ok_or("'Split' requires 'splits' field")?
                        .unpack_int()
                        .ok_or("'splits' must be int")? as usize;
                    ReleaseDecision::SubmitPartial { tx_id, num_splits: splits }
                },
                _ => return Err(format!("Unknown action: {}", action)),
            };

            decisions.push(decision);
        }

        Ok(decisions)
    }
}
```

**STEP 3: Run Tests (GREEN)**

```bash
cargo test --no-default-features test_simple_release_all
```

### Phase 2: Core Executor (4-5 days) - TDD

**Goal**: Complete execution engine with context building

#### Day 1-2: Context Builders (TDD)

**STEP 1: Write Tests (RED)**

```rust
#[test]
fn test_conditional_release_by_amount() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if tx.amount < 50000:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let mut agent = create_test_agent("BANK_A");

    // Add transactions: 2 small, 2 large
    add_transaction(&mut agent, "TX_1", 30000);
    add_transaction(&mut agent, "TX_2", 70000);
    add_transaction(&mut agent, "TX_3", 40000);
    add_transaction(&mut agent, "TX_4", 90000);

    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    // Should release TX_1 and TX_3 (small), hold TX_2 and TX_4 (large)
    assert_eq!(count_releases(&decisions), 2);
    assert_eq!(count_holds(&decisions), 2);
}

#[test]
fn test_deadline_awareness() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if tx.ticks_to_deadline <= 5:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let mut agent = create_test_agent("BANK_A");

    // Add transactions with different deadlines
    add_transaction_with_deadline(&mut agent, "TX_1", 50000, tick + 3);  // Urgent
    add_transaction_with_deadline(&mut agent, "TX_2", 50000, tick + 10); // Not urgent

    let decisions = policy.evaluate_queue(&agent, &state, tick, &CostRates::default());

    assert_eq!(count_releases(&decisions), 1); // Only TX_1
}

#[test]
fn test_liquidity_check() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    decisions = []
    for tx in transactions:
        if agent.available_liquidity >= tx.amount:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let mut agent = create_test_agent_with_balance("BANK_A", 100000);

    add_transaction(&mut agent, "TX_1", 50000);  // Can afford
    add_transaction(&mut agent, "TX_2", 150000); // Cannot afford

    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    assert_eq!(count_releases(&decisions), 1);
}
```

**STEP 2: Implement (GREEN)**

Implement `build_transactions()`, `build_agent()`, `build_system()` methods.

**STEP 3: Run Tests (GREEN)**

#### Day 3-4: Resource Limits (TDD)

**STEP 1: Write Tests (RED)**

```rust
#[test]
fn test_instruction_limit_enforcement() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    # Try to exceed instruction limit
    total = 0
    for i in range(1000000):
        total += i
    return []
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    // Should return empty (safe fallback on limit exceeded)
    assert_eq!(decisions.len(), 0);
}

#[test]
fn test_reasonable_complexity_allowed() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    # Reasonable complexity should work
    decisions = []
    for tx in transactions:
        score = tx.priority * max(1, 10 - tx.ticks_to_deadline)
        if score > 50:
            decisions.append({"action": "Release", "tx_id": tx.id})
        else:
            decisions.append({"action": "Hold", "tx_id": tx.id})
    return decisions
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let agent = create_test_agent_with_queue(50); // 50 transactions

    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    // Should successfully process all
    assert_eq!(decisions.len(), 50);
}
```

**STEP 2: Implement (GREEN)**

Tune instruction limits, add timeout handling.

#### Day 5: Error Handling (TDD)

**STEP 1: Write Tests (RED)**

```rust
#[test]
fn test_runtime_error_safe_fallback() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    # Will cause runtime error (division by zero)
    x = 1 / 0
    return []
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    // Should return empty (safe fallback), not panic
    assert_eq!(decisions.len(), 0);
}

#[test]
fn test_missing_function_error() {
    let script = r#"
def wrong_function_name(transactions, agent, system, state):
    return []
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    assert_eq!(decisions.len(), 0); // Safe fallback
}

#[test]
fn test_invalid_return_type() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    return "not a list"  # Wrong return type
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let decisions = policy.evaluate_queue(&agent, &state, 0, &CostRates::default());

    assert_eq!(decisions.len(), 0); // Safe fallback
}
```

**STEP 2: Implement (GREEN)**

Add comprehensive error handling.

### Phase 3: Integration (2-3 days) - TDD

**Goal**: Integrate with orchestrator and configuration system

#### Day 1: Policy Factory (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_create_starlark_policy_from_config() {
    let config = PolicyConfig::Starlark {
        script: r#"
def evaluate_queue(transactions, agent, system, state):
    return [{"action": "Release", "tx_id": tx.id} for tx in transactions]
        "#.to_string()
    };

    let policy = create_policy(&config);
    assert!(policy.is_ok());
}

#[test]
fn test_backward_compatibility_json_dsl() {
    let config = PolicyConfig::Tree {
        json: r#"{"action": "Release"}"#.to_string()
    };

    let policy = create_policy(&config);
    assert!(policy.is_ok()); // JSON DSL still works
}
```

**STEP 2: Implement (GREEN)**

```rust
// backend/src/policy/mod.rs
pub enum PolicyConfig {
    Fifo,
    Deadline,
    Tree { json: String },
    Starlark { script: String }, // NEW
}

pub fn create_policy(config: &PolicyConfig) -> Result<Box<dyn CashManagerPolicy>, String> {
    match config {
        PolicyConfig::Fifo => Ok(Box::new(FifoPolicy::new())),
        PolicyConfig::Deadline => Ok(Box::new(DeadlinePolicy::new())),
        PolicyConfig::Tree { json } => {
            let tree = DecisionTreeDef::from_json(json)?;
            Ok(Box::new(TreePolicy::new(tree)))
        },
        PolicyConfig::Starlark { script } => {
            let policy = StarlarkPolicy::new(script.clone())?;
            Ok(Box::new(policy))
        },
    }
}
```

#### Day 2: Configuration Parsing (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_parse_inline_starlark_config() {
    let yaml = r#"
simulation:
  ticks_per_day: 10
  num_days: 1
  seed: 42
agents:
  - id: BANK_A
    initial_balance: 1000000
    policy:
      starlark: |
        def evaluate_queue(transactions, agent, system, state):
            return []
    "#;

    let config = parse_config(yaml);
    assert!(config.is_ok());
}

#[test]
fn test_parse_file_based_starlark_config() {
    let yaml = r#"
agents:
  - id: BANK_A
    policy:
      starlark: "file://examples/policies/simple.star"
    "#;

    // Create test file
    std::fs::write("examples/policies/simple.star",
        "def evaluate_queue(transactions, agent, system, state):\n    return []"
    ).unwrap();

    let config = parse_config(yaml);
    assert!(config.is_ok());
}
```

**STEP 2: Implement (GREEN)**

Update configuration parser to handle `starlark` field.

#### Day 3: Orchestrator Integration (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_full_simulation_with_starlark() {
    let config = r#"
simulation:
  ticks_per_day: 10
  num_days: 1
  seed: 42
agents:
  - id: BANK_A
    initial_balance: 1000000
    policy:
      starlark: |
        def evaluate_queue(transactions, agent, system, state):
            return [{"action": "Release", "tx_id": tx.id} for tx in transactions]
    - id: BANK_B
    initial_balance: 1000000
    "#;

    let mut orch = Orchestrator::new(config).unwrap();

    // Run 10 ticks
    for _ in 0..10 {
        let result = orch.tick();
        assert!(result.is_ok());
    }

    // Verify simulation completed successfully
    let state = orch.get_state();
    assert_eq!(state.current_tick, 10);
}
```

**STEP 2: Implement (GREEN)**

Ensure orchestrator works with Starlark policies.

### Phase 4: Examples & Testing (1-2 days) - TDD

**Goal**: Comprehensive test coverage and example policies

#### Create Example Policies

```bash
examples/policies/
├── 01_simple_threshold.star
├── 02_deadline_aware.star
├── 03_liquidity_buffer.star
├── 04_priority_based.star
└── 05_adaptive_threshold.star
```

#### Write Comprehensive Tests

```rust
// 40+ unit tests covering:
// - All transaction fields
// - All agent fields
// - All system fields
// - All decision types
// - Error conditions
// - Edge cases

// 15+ integration tests covering:
// - FFI boundary
// - Configuration parsing
// - Full simulation runs
// - Determinism validation
```

### Phase 5: Documentation (1 day)

Create:
- `docs/starlark_policies.md` - User guide
- `docs/starlark_api_reference.md` - Complete API
- `docs/starlark_examples.md` - Annotated examples
- Update `CLAUDE.md` with Starlark guidance

### Phase 6: Collateral Support (4-5 days) - TDD

**Goal**: Three entry points for complete policy control

#### Day 1-2: Extend API (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_strategic_collateral_decision() {
    let script = r#"
def evaluate_strategic_collateral(agent, system, state):
    if agent.queue1_liquidity_gap > 0:
        return {"action": "Post", "amount": agent.queue1_liquidity_gap}
    return {"action": "Hold"}
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();
    let agent = create_agent_with_queue_gap(50000);

    let decision = policy.evaluate_collateral(&agent, &state, 0, true);

    assert!(matches!(decision, CollateralDecision::Post { amount: 50000, .. }));
}
```

**STEP 2: Implement (GREEN)**

Add collateral fields to `StarAgent`, implement `evaluate_collateral()`.

#### Day 3-4: Three-Layer Integration (TDD)

Test that payment + strategic + end-of-tick work together.

#### Day 5: Example Policies

Create complete three-layer policies.

### Phase 7: Static Analysis (3-4 days) - TDD

**Goal**: Catch common errors before execution

#### Features to Implement (TDD)

1. **Field Name Validation**
```rust
#[test]
fn test_detect_typo_in_field_name() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    for tx in transactions:
        if tx.amnout < 50000:  # Typo: "amnout" instead of "amount"
            pass
    return []
    "#;

    let analyzer = StaticAnalyzer::new();
    let result = analyzer.analyze(script);

    assert!(result.has_errors());
    assert!(result.errors[0].contains("amnout"));
    assert!(result.suggestions[0].contains("amount"));
}
```

2. **Missing Entry Point Detection**
3. **Return Type Validation**
4. **Dangerous Pattern Detection**

### Phase 8: Persistent State (3-4 days) - TDD

**Goal**: State survives across days and simulation restarts

#### Day 1-2: State Management (TDD)

**STEP 1: Write Test (RED)**

```rust
#[test]
fn test_state_persists_across_ticks() {
    let script = r#"
def evaluate_queue(transactions, agent, system, state):
    if "counter" not in state:
        state["counter"] = 0
    state["counter"] += 1
    return []
    "#;

    let mut policy = StarlarkPolicy::new(script.to_string()).unwrap();

    // Call 3 times
    for _ in 0..3 {
        policy.evaluate_queue(&agent, &state, 0, &CostRates::default());
    }

    // Verify counter incremented
    let state = policy.get_state("BANK_A");
    assert_eq!(state["counter"], 3);
}
```

**STEP 2: Implement (GREEN)**

Add state management to `StarlarkPolicy`.

#### Day 3-4: Database Integration (TDD)

**STEP 1: Write Test (RED)**

```python
def test_state_persists_to_database():
    """Test policy state written to database at EOD."""
    orch = Orchestrator.new(config_with_starlark_policy())

    # Run day 0
    for _ in range(10):
        orch.tick()

    # Get state snapshot
    states = orch.get_policy_states(day=0)

    assert len(states) == 2  # 2 agents
    assert states[0]["agent_id"] == "BANK_A"
    assert "state_json" in states[0]

    # Write to database
    db.write_policy_states(states)

    # Verify persisted
    loaded = db.query_policy_states(simulation_id="sim_001", day=0)
    assert len(loaded) == 2
```

**STEP 2: Implement (GREEN)**

Integrate with Phase 10 `policy_states` table.

### Phase 9: Final Testing (2-3 days) - TDD

**Goal**: Comprehensive validation before production

#### Determinism Tests

```rust
#[test]
fn test_determinism_100_runs() {
    let script = load_example_policy("adaptive_threshold");

    let results: Vec<_> = (0..100)
        .map(|_| run_full_simulation(script.clone(), seed=42))
        .collect();

    // All results must be identical
    assert!(results.windows(2).all(|w| w[0] == w[1]));
}
```

#### Performance Tests

```rust
#[test]
fn test_maintains_throughput() {
    let orch = create_orchestrator_with_starlark(agents=10);

    let start = Instant::now();
    for _ in 0..1000 {
        orch.tick();
    }
    let elapsed = start.elapsed();

    let ticks_per_sec = 1000.0 / elapsed.as_secs_f64();
    assert!(ticks_per_sec > 1000.0, "Must maintain >1000 ticks/sec");
}
```

#### Integration Tests

```python
def test_full_e2e_with_persistence():
    """Complete workflow: configure → run → persist → query → verify."""
    # ... (complete E2E test)
```

---

## Part IV: Testing Strategy Summary

### Test Coverage Targets

| Component | Target | Tests |
|-----------|--------|-------|
| **Core Executor** | >90% | 30+ unit tests |
| **API Surface** | >95% | 20+ unit tests |
| **Static Analyzer** | >85% | 15+ unit tests |
| **State Management** | >90% | 10+ unit tests |
| **Integration** | >80% | 30+ integration tests |
| **E2E** | Complete | 15+ E2E tests |
| **Overall** | >85% | 120+ total tests |

### TDD Checklist for Each Feature

- [ ] Write failing test first (RED)
- [ ] Implement minimal code to pass (GREEN)
- [ ] Refactor while keeping green (REFACTOR)
- [ ] Add edge case tests
- [ ] Add error case tests
- [ ] Verify determinism
- [ ] Check performance
- [ ] Update documentation

---

## Part V: Risk Mitigation

### Technical Risks

**Risk 1: Performance Regression**
- Mitigation: Benchmark every PR, instruction limits, caching
- Gate: Must maintain >1000 ticks/sec

**Risk 2: Non-Determinism**
- Mitigation: Comprehensive determinism tests, static analysis
- Gate: 100 runs with same seed must be identical

**Risk 3: LLM Generation Quality**
- Mitigation: Static analysis, shadow replay, guardrails
- Gate: Manual review for major changes

### Integration Risks

**Risk 4: Breaking JSON DSL**
- Mitigation: Backward compatibility tests, separate modules
- Gate: All 107+ existing tests must pass

**Risk 5: Database Schema Drift**
- Mitigation: Follow Phase 10 patterns, Pydantic models
- Gate: Schema validation at runtime

---

## Part VI: Rollout Plan

### Week-by-Week Schedule

| Week | Phases | Gate Criteria |
|------|--------|---------------|
| **1** | Phase 1-2 | Can execute simple policy, all tests pass |
| **2** | Phase 3-5 | Integration works, examples complete, docs written |
| **3** | Phase 6 | Three entry points work, collateral decisions functional |
| **4** | Phase 7 | Static analysis catches errors, provides suggestions |
| **5-6** | Phase 8 | State persists to DB, loads on restart |
| **7** | Phase 9 | All tests pass, determinism validated, performance maintained |
| **8** | Buffer | Bug fixes, polish, final validation |

### Go/No-Go Checkpoints

**After Week 2**: Basic functionality complete?
- ✅ Starlark policies work
- ✅ No regressions
- ✅ Performance acceptable
- **Decision**: Continue or pause?

**After Week 4**: Advanced features complete?
- ✅ Collateral support works
- ✅ Static analysis functional
- ✅ LLM can generate policies
- **Decision**: Add state persistence or deploy MVP?

**After Week 7**: Production ready?
- ✅ All tests pass
- ✅ Determinism validated
- ✅ Performance targets met
- ✅ Documentation complete
- **Decision**: Deploy or iterate?

---

## Conclusion

This plan provides a **test-driven**, **phased approach** to implementing Starlark policies while maintaining backward compatibility, safety, and performance. The emphasis on TDD ensures each feature is validated before moving forward.

**Key Success Factors**:
1. ✅ **TDD discipline**: Red → Green → Refactor for every feature
2. ✅ **Backward compatibility**: JSON DSL continues working
3. ✅ **Safety preserved**: Starlark's hermetic design
4. ✅ **Comprehensive examples**: 10+ reference policies
5. ✅ **Automated conversion**: JSON → Starlark tool

**Next Steps**:
1. Review and approve plan
2. Begin Phase 1: Foundation with TDD (Week 1)
3. Daily stand-ups to review test results
4. Weekly progress reviews against gates

---

**Document Status**: ✅ **Ready for Implementation**
**Last Updated**: October 30, 2025
**Approach**: Test-Driven Development (TDD)
**Total Tests Expected**: 120+ tests across all layers
