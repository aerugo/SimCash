# Policy Integration with Simulation

> **Reference: How Policies Are Loaded, Evaluated, and Executed**

## Overview

Policies integrate with the simulation through:
1. **Factory pattern** - Loading and instantiation
2. **Trait interface** - Standardized evaluation API
3. **Tick lifecycle** - Timing of evaluations
4. **Decision execution** - Converting decisions to actions

---

## Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                        Simulation Orchestrator                         │
│                                                                        │
│  ┌────────────────┐    ┌────────────────┐    ┌────────────────┐      │
│  │ Policy Factory │───►│  TreePolicy    │───►│ EvalContext    │      │
│  │                │    │ (CashManager)  │    │ Builder        │      │
│  └────────────────┘    └────────────────┘    └────────────────┘      │
│                               │                      │                │
│                               ▼                      ▼                │
│                        ┌────────────────┐    ┌────────────────┐      │
│                        │  Interpreter   │◄───│  Agent State   │      │
│                        │ (Tree Traversal│    │  Transaction   │      │
│                        └────────────────┘    │  System State  │      │
│                               │              └────────────────┘      │
│                               ▼                                       │
│                        ┌────────────────┐                            │
│                        │ ReleaseDecision│                            │
│                        │ BankDecision   │                            │
│                        │ Collateral-    │                            │
│                        │ Decision       │                            │
│                        └────────────────┘                            │
│                               │                                       │
│                               ▼                                       │
│                        ┌────────────────┐                            │
│                        │ Settlement     │                            │
│                        │ Engine         │                            │
│                        └────────────────┘                            │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Policy Trait Interface

### CashManagerPolicy Trait

```rust
pub trait CashManagerPolicy: Send + Sync {
    /// Evaluate Queue 1 and decide releases
    fn evaluate_queue(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
        ticks_per_day: usize,
        eod_rush_threshold: f64,
    ) -> Vec<ReleaseDecision>;

    /// Evaluate single transaction (for Queue 2 management)
    fn evaluate_single(
        &mut self,
        tx: &Transaction,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
        ticks_per_day: usize,
        eod_rush_threshold: f64,
    ) -> ReleaseDecision;

    /// Evaluate collateral decisions
    fn evaluate_collateral(
        &mut self,
        agent: &Agent,
        state: &SimulationState,
        tick: usize,
        cost_rates: &CostRates,
    ) -> CollateralDecision;

    /// Enable downcasting
    fn as_any_mut(&mut self) -> &mut dyn std::any::Any;
}
```

**Implementation**: `simulator/src/policy/mod.rs:560-678`

---

## TreePolicy Implementation

### Structure

```rust
pub struct TreePolicy {
    tree_def: DecisionTreeDef,
    override_params: HashMap<String, f64>,
    budget_state: Option<BudgetState>,      // Per-tick budget tracking
}
```

### Key Methods

#### evaluate_queue()
```rust
fn evaluate_queue(&mut self, agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold) {
    // 1. Evaluate bank_tree (if present)
    if let Some(ref bank_tree) = self.tree_def.bank_tree {
        let bank_ctx = EvalContext::bank_level(agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold);
        let (bank_node, path) = traverse_bank_tree_with_path(&self.tree_def, &bank_ctx)?;
        let bank_decision = build_bank_decision_with_path(bank_node, &bank_ctx, &params, Some(path));

        // Apply bank decision (set budget)
        self.apply_bank_decision(bank_decision);
    }

    // 2. Evaluate payment_tree for each transaction
    let mut decisions = Vec::new();
    for tx_id in agent.outgoing_queue() {
        let tx = state.get_transaction(tx_id)?;
        let ctx = EvalContext::build(tx, agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold);

        let action_node = traverse_tree(&self.tree_def, &ctx)?;
        let decision = build_decision(action_node, tx_id.clone(), &ctx, &params)?;

        // Apply budget constraints
        let final_decision = self.apply_budget_constraints(decision);
        decisions.push(final_decision);
    }

    decisions
}
```

#### evaluate_strategic_collateral()
```rust
fn evaluate_strategic_collateral(&mut self, agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold) {
    if let Some(ref tree) = self.tree_def.strategic_collateral_tree {
        let ctx = EvalContext::bank_level(agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold);
        let action_node = traverse_strategic_collateral_tree(&self.tree_def, &ctx)?;
        build_collateral_decision(action_node, &ctx, &params)
    } else {
        CollateralDecision::Hold
    }
}
```

#### evaluate_end_of_tick_collateral()
```rust
fn evaluate_end_of_tick_collateral(&mut self, agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold) {
    if let Some(ref tree) = self.tree_def.end_of_tick_collateral_tree {
        let ctx = EvalContext::bank_level(agent, state, tick, cost_rates, ticks_per_day, eod_rush_threshold);
        let action_node = traverse_end_of_tick_collateral_tree(&self.tree_def, &ctx)?;
        build_collateral_decision(action_node, &ctx, &params)
    } else {
        CollateralDecision::Hold
    }
}
```

**Implementation**: `simulator/src/policy/tree/executor.rs`

---

## Tick Lifecycle Integration

### Complete Tick Flow

```
Tick N
│
├─► Step 1: Transaction Arrivals
│   └─ New transactions added to sender's Queue 1
│
├─► Step 1.5: Strategic Collateral Evaluation
│   └─ For each agent:
│      └─ policy.evaluate_strategic_collateral()
│      └─ Execute PostCollateral/WithdrawCollateral/Hold
│
├─► Step 1.75: Bank Tree Evaluation
│   └─ For each agent:
│      └─ Evaluate bank_tree
│      └─ Set release budgets and state registers
│
├─► Step 2: Payment Tree Evaluation
│   └─ For each agent:
│      └─ policy.evaluate_queue()
│      └─ Returns Vec<ReleaseDecision>
│      └─ Execute: Release → Queue 2, Hold → stays, Split → create children
│
├─► Step 3: RTGS Settlement Attempts
│   └─ Process Queue 2 by priority
│   └─ Settle if sender has liquidity
│
├─► Step 4: LSM Cycle Detection
│   └─ Find bilateral/multilateral offsets
│   └─ Settle cycles atomically
│
├─► Step 5: Queue 2 Processing Continues
│   └─ Re-attempt settlements after LSM
│
├─► Step 5.5: End-of-Tick Collateral Evaluation
│   └─ For each agent:
│      └─ policy.evaluate_end_of_tick_collateral()
│      └─ Execute collateral decisions
│
├─► Step 6: Cost Accrual
│   └─ Charge overdraft costs
│   └─ Charge delay costs
│   └─ Charge collateral costs
│
├─► Step 7: Metrics and Events
│   └─ Record events
│   └─ Update metrics
│
└─► End of Tick N
```

---

## Decision Execution

### ReleaseDecision Execution

| Decision | Execution |
|----------|-----------|
| `SubmitFull` | Move tx from Queue 1 → Queue 2 |
| `SubmitPartial` | Split tx, move children to Queue 2 |
| `StaggerSplit` | Split tx, schedule staggered releases |
| `Hold` | Keep tx in Queue 1 |
| `Drop` | Remove tx from simulation |
| `Reprioritize` | Update tx.priority |
| `WithdrawFromRtgs` | Move tx from Queue 2 → Queue 1 |
| `ResubmitToRtgs` | Update tx.rtgs_priority |

### BankDecision Execution

| Decision | Execution |
|----------|-----------|
| `SetReleaseBudget` | Store budget in TreePolicy.budget_state |
| `SetState` | Update agent.state_registers[key] = value |
| `AddState` | Update agent.state_registers[key] += delta |
| `NoAction` | No-op |

### CollateralDecision Execution

| Decision | Execution |
|----------|-----------|
| `Post` | agent.post_collateral(amount) |
| `Withdraw` | agent.withdraw_collateral(amount) |
| `Hold` | No-op |

---

## Budget Enforcement

### Budget State Tracking

```rust
struct BudgetState {
    max_value_to_release: i64,
    focus_counterparties: Option<Vec<String>>,
    max_per_counterparty: Option<i64>,
    value_released_so_far: i64,
    value_per_counterparty: HashMap<String, i64>,
}
```

### Constraint Application

```rust
fn apply_budget_constraints(&mut self, decision: ReleaseDecision) -> ReleaseDecision {
    match decision {
        ReleaseDecision::SubmitFull { tx_id, .. } => {
            let tx = get_transaction(&tx_id);
            let amount = tx.remaining_amount();
            let counterparty = tx.receiver_id();

            // Check total budget
            if self.budget_state.value_released_so_far + amount > self.budget_state.max_value_to_release {
                return ReleaseDecision::Hold { tx_id, reason: HoldReason::Custom("BudgetExhausted") };
            }

            // Check counterparty focus list
            if let Some(ref focus) = self.budget_state.focus_counterparties {
                if !focus.contains(&counterparty) {
                    return ReleaseDecision::Hold { tx_id, reason: HoldReason::Custom("NotInFocusList") };
                }
            }

            // Check per-counterparty limit
            if let Some(max_per_cpty) = self.budget_state.max_per_counterparty {
                let released_to_cpty = self.budget_state.value_per_counterparty.get(&counterparty).unwrap_or(&0);
                if released_to_cpty + amount > max_per_cpty {
                    return ReleaseDecision::Hold { tx_id, reason: HoldReason::Custom("CounterpartyLimitExceeded") };
                }
            }

            // Update tracking and allow release
            self.budget_state.value_released_so_far += amount;
            *self.budget_state.value_per_counterparty.entry(counterparty).or_insert(0) += amount;
            decision
        }
        _ => decision
    }
}
```

---

## State Register Management

### Register Lifecycle

1. **Initialization**: All registers start at 0.0
2. **Setting**: `SetState` action overwrites value
3. **Incrementing**: `AddState` action adds to value
4. **Reading**: Via `bank_state_*` fields in context
5. **Reset**: All registers reset to 0.0 at end of day

### Agent State Storage

```rust
// In Agent struct
struct Agent {
    state_registers: HashMap<String, f64>,
    // ...
}

impl Agent {
    fn set_state_register(&mut self, key: &str, value: f64) {
        // Validate prefix
        if !key.starts_with("bank_state_") {
            return Err("Invalid register key prefix");
        }
        // Enforce maximum
        if self.state_registers.len() >= 10 && !self.state_registers.contains_key(key) {
            return Err("Maximum 10 registers exceeded");
        }
        self.state_registers.insert(key.to_string(), value);
    }

    fn add_state_register(&mut self, key: &str, delta: f64) {
        let current = self.state_registers.get(key).unwrap_or(&0.0);
        self.set_state_register(key, current + delta);
    }

    fn reset_state_registers(&mut self) {
        self.state_registers.clear();
    }
}
```

---

## Event Generation

### Policy Decision Events

```rust
Event::PolicyDecision {
    tick: usize,
    agent_id: String,
    tx_id: String,
    decision_type: String,  // "Release", "Hold", "Split", etc.
    decision_path: String,  // "N1(true) → N2(false) → A3"
    parameters: HashMap<String, Value>,
}
```

### Bank Decision Events

```rust
Event::BankDecision {
    tick: usize,
    agent_id: String,
    decision_type: String,  // "SetReleaseBudget", "SetState", etc.
    decision_path: String,
    parameters: HashMap<String, Value>,
}
```

### Collateral Decision Events

```rust
Event::CollateralDecision {
    tick: usize,
    agent_id: String,
    decision_type: String,  // "Post", "Withdraw", "Hold"
    amount: Option<i64>,
    reason: Option<String>,
}
```

---

## FFI Integration (Python ↔ Rust)

### Python Side

```python
from payment_simulator.backends import Orchestrator

# Create orchestrator with policy config
orch = Orchestrator.new({
    "agents": [...],
    "policies": {...},
    "ticks_per_day": 100,
})

# Run tick (policies evaluated internally)
orch.tick()

# Get policy events
events = orch.get_tick_events(orch.current_tick())
policy_decisions = [e for e in events if e['event_type'] == 'policy_decision']
```

### Rust FFI Exports

```rust
#[pyclass]
impl Orchestrator {
    #[pyo3(name = "tick")]
    pub fn py_tick(&mut self) -> PyResult<()> {
        self.tick()?;
        Ok(())
    }

    #[pyo3(name = "get_tick_events")]
    pub fn py_get_tick_events(&self, tick: usize) -> PyResult<Vec<HashMap<String, Value>>> {
        let events = self.get_events_for_tick(tick)?;
        Ok(events.iter().map(event_to_dict).collect())
    }
}
```

---

## Decision Path Tracking

### Path Format

```
N1_CheckUrgent(true) → N2_CheckLiquidity(false) → A3_Hold
```

### Path Recording

```rust
struct DecisionPath {
    nodes: Vec<DecisionPathNode>,
}

struct DecisionPathNode {
    node_id: String,
    node_type: String,  // "condition" or "action"
    result: Option<bool>,  // For conditions: the evaluation result
}

impl DecisionPath {
    fn push_condition(&mut self, node_id: String, result: bool) {
        self.nodes.push(DecisionPathNode {
            node_id,
            node_type: "condition".to_string(),
            result: Some(result),
        });
    }

    fn push_action(&mut self, node_id: String) {
        self.nodes.push(DecisionPathNode {
            node_id,
            node_type: "action".to_string(),
            result: None,
        });
    }

    fn format(&self) -> String {
        self.nodes.iter()
            .map(|n| match n.result {
                Some(r) => format!("{}({})", n.node_id, r),
                None => n.node_id.clone(),
            })
            .collect::<Vec<_>>()
            .join(" → ")
    }
}
```

---

## Source Code Reference

| Component | File | Line |
|-----------|------|------|
| CashManagerPolicy trait | `simulator/src/policy/mod.rs` | 560-678 |
| TreePolicy struct | `simulator/src/policy/tree/executor.rs` | 50-100 |
| TreePolicy::evaluate_queue() | `simulator/src/policy/tree/executor.rs` | 150-300 |
| BudgetState | `simulator/src/policy/tree/executor.rs` | 30-45 |
| DecisionPath | `simulator/src/policy/tree/types.rs` | 360-400 |
| Agent.state_registers | `simulator/src/models/agent.rs` | 45-50 |
| Orchestrator tick flow | `simulator/src/orchestrator/mod.rs` | 200-400 |
| FFI exports | `simulator/src/ffi/orchestrator.rs` | 100-300 |
