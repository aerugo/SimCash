# Decision Path Tracking Implementation Plan

## Goal
Show the decision tree path that led to state register updates, so users can understand WHY a policy made a particular decision.

## Current State
`StateRegisterSet` event has:
- agent_id, register_key, old_value, new_value, reason
- NO decision path information

## Implementation Steps

### 1. Rust: Track Decision Path (backend/src/policy/tree/executor.rs)

Add path tracking to tree execution:

```rust
pub struct DecisionPath {
    pub nodes: Vec<DecisionNode>,
}

pub struct DecisionNode {
    pub node_id: String,
    pub node_type: String,  // "condition" | "action"
    pub result: Option<bool>,  // true/false for conditions, None for actions
}

impl TreePolicy {
    fn evaluate_with_path(&mut self, ...) -> (Decision, DecisionPath) {
        let mut path = DecisionPath { nodes: vec![] };
        
        // Track each node visited
        match node {
            TreeNode::Condition { node_id, condition, on_true, on_false } => {
                let result = self.evaluate_condition(condition, ...);
                path.nodes.push(DecisionNode {
                    node_id: node_id.clone(),
                    node_type: "condition".to_string(),
                    result: Some(result),
                });
                
                if result {
                    let (decision, sub_path) = self.evaluate_with_path(on_true, ...);
                    path.nodes.extend(sub_path.nodes);
                    (decision, path)
                } else {
                    let (decision, sub_path) = self.evaluate_with_path(on_false, ...);
                    path.nodes.extend(sub_path.nodes);
                    (decision, path)
                }
            }
            TreeNode::Action { node_id, action, parameters } => {
                path.nodes.push(DecisionNode {
                    node_id: node_id.clone(),
                    node_type: "action".to_string(),
                    result: None,
                });
                (self.execute_action(action, parameters, ...), path)
            }
        }
    }
}
```

### 2. Rust: Add Path to Event (backend/src/models/event.rs)

```rust
StateRegisterSet {
    tick: usize,
    agent_id: String,
    register_key: String,
    old_value: f64,
    new_value: f64,
    reason: String,
    decision_path: Option<Vec<String>>,  // ["N1:CheckLiquidity(true)", "N2:CheckQueue(false)", "A3:SetState"]
}
```

### 3. Rust: FFI Serialization (backend/src/ffi/orchestrator.rs)

```rust
Event::StateRegisterSet { decision_path, .. } => {
    dict.set_item("decision_path", decision_path)?;
}
```

### 4. Python: Display Path (api/payment_simulator/cli/output.py)

```python
def log_state_register_events(events, quiet=False):
    # ... existing code ...
    
    for event in agent_events:
        register_key = event.get("register_key", "unknown")
        old_value = event.get("old_value", 0.0)
        new_value = event.get("new_value", 0.0)
        reason = event.get("reason", "no reason")
        decision_path = event.get("decision_path", [])
        
        display_key = register_key.replace("bank_state_", "")
        
        # Show value change
        if new_value > old_value:
            console.print(f"   • [green]{display_key}: {old_value} → {new_value}[/green] ({reason})")
        elif new_value < old_value:
            console.print(f"   • [yellow]{display_key}: {old_value} → {new_value}[/yellow] ({reason})")
        else:
            console.print(f"   • {display_key}: {old_value} → {new_value} ({reason})")
        
        # Show decision path if available
        if decision_path:
            path_str = " → ".join(decision_path)
            console.print(f"     [dim]Path: {path_str}[/dim]")
```

## Example Output

**Before:**
```
🧠 Agent Memory Updates (1):
   REGIONAL_TRUST:
   • mode: 1.0 → 0.0 (enter_conservative_mode)
```

**After:**
```
🧠 Agent Memory Updates (1):
   REGIONAL_TRUST:
   • mode: 1.0 → 0.0 (enter_conservative_mode)
     Path: N1:CheckLiquidity(true) → N2:QueueSizeCheck(false) → A3:EnterConservative
```

## Complexity Estimate

- **Rust changes:** Medium complexity (~4 hours)
  - Add path tracking to executor
  - Thread path through all policy evaluations
  - Add to event structure
  
- **FFI changes:** Low complexity (~1 hour)
  - Serialize Vec<String> to Python list
  
- **Python changes:** Low complexity (~1 hour)
  - Update display to show path
  
**Total:** ~6 hours of focused development

## Testing Strategy

1. Unit test: Verify path tracking captures all nodes
2. Integration test: Verify path appears in events
3. Display test: Verify path renders correctly
4. Manual test: Run policy with verbose output, verify paths make sense

## Benefits

- **Policy debugging:** Understand why decisions were made
- **Policy optimization:** Identify frequently-taken paths
- **Policy validation:** Verify expected paths are taken
- **User transparency:** Clear audit trail of decision logic

## Phase

This would be a **Phase 4.6** enhancement: "Decision Path Auditing"

It builds on Phase 4.5 (State Registers) by providing transparency into 
how state values are set.
