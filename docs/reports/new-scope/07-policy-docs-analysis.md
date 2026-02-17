# Policy Documentation System Analysis

> Report for new-scope planning · 2025-02-17

## Executive Summary

SimCash has a **remarkably complete and well-documented policy system** — a JSON-based decision tree DSL that lets banks define payment strategies without writing code. The documentation spans 12 reference files covering every aspect of the system. The Rust implementation in `simulator/src/policy/tree/types.rs` maps cleanly to the docs. This is one of the most thoroughly documented parts of the codebase.

---

## 1. Complete Policy Tree JSON Schema (Version 1.0)

The schema version in the actual code and docs is `"1.0"` (despite TOOLS.md mentioning "2.0" — that appears to be a forward reference or naming inconsistency).

```json
{
  "version": "1.0",
  "policy_id": "<string>",
  "description": "<optional string>",
  "parameters": { "<name>": <f64>, ... },
  "bank_tree": <TreeNode | null>,
  "payment_tree": <TreeNode | null>,
  "strategic_collateral_tree": <TreeNode | null>,
  "end_of_tick_collateral_tree": <TreeNode | null>
}
```

**Key design properties:**
- All 4 trees are optional — you can have payment-only, collateral-only, or any combination
- Parameters are always `f64` (even booleans use 1.0/0.0)
- Node IDs must be unique **across all trees** in one policy file
- Max tree depth: 100 levels

---

## 2. Node Types

Only **two** node types exist — the system is elegant in its simplicity:

| Type | Purpose | JSON `type` |
|------|---------|-------------|
| **Condition** | Binary branch: evaluates expression → on_true / on_false | `"condition"` |
| **Action** | Terminal: returns a decision with optional parameters | `"action"` |

There is no sequence/selector/parallel — complex logic is achieved through nested conditions and logical operators (`and`, `or`, `not`) within expressions.

**Condition node** fields: `node_id`, `description` (optional), `condition` (Expression), `on_true` (TreeNode), `on_false` (TreeNode)

**Action node** fields: `node_id`, `action` (ActionType), `parameters` (HashMap<String, ValueOrCompute>)

---

## 3. All Action Types (17 total)

### Payment Actions (payment_tree) — 10 actions
| Action | Purpose | Key Params |
|--------|---------|------------|
| **Release** | Submit full tx to RTGS Queue 2 | `priority_flag`, `timed_for_tick` (optional) |
| **ReleaseWithCredit** | Release, using overdraft if needed | Same as Release |
| **Split** / **PaceAndRelease** | Split into N equal parts, submit all | `num_splits` (required, ≥2) |
| **StaggerSplit** | Split with staggered timing | `num_splits`, `stagger_first_now`, `stagger_gap_ticks`, `priority_boost_children` |
| **Hold** | Keep in Queue 1, re-evaluate next tick | `reason` (optional) |
| **Drop** | Remove from simulation (deprecated) | — |
| **Reprioritize** | Change tx priority in Queue 1 | `new_priority` (required, 0-10) |
| **WithdrawFromRtgs** | Pull tx back from Queue 2 to Queue 1 | — |
| **ResubmitToRtgs** | Change RTGS priority class in Queue 2 | `rtgs_priority` ("HighlyUrgent"/"Urgent"/"Normal") |

### Bank Actions (bank_tree) — 4 actions
| Action | Purpose | Key Params |
|--------|---------|------------|
| **SetReleaseBudget** | Set total/per-counterparty release limits | `max_value_to_release` (required), `focus_counterparties`, `max_per_counterparty` |
| **SetState** | Set a state register to a value | `key` (must start `bank_state_`), `value` |
| **AddState** | Increment/decrement a state register | `key`, `value` (delta) |
| **NoAction** | Do nothing this tick | — |

### Collateral Actions (both collateral trees) — 3 actions
| Action | Purpose | Key Params |
|--------|---------|------------|
| **PostCollateral** | Post collateral to increase liquidity | `amount`, `reason`, `auto_withdraw_after_ticks` |
| **WithdrawCollateral** | Withdraw to reduce opportunity cost | `amount`, `reason` |
| **HoldCollateral** | No change | — |

---

## 4. Condition Predicates

### Comparison Operators (6)
`==`, `!=`, `<`, `<=`, `>`, `>=` — each takes `left` and `right` Values. Equality uses epsilon tolerance (1e-9).

### Logical Operators (3)
- **`and`**: Short-circuit AND over array of conditions
- **`or`**: Short-circuit OR over array of conditions
- **`not`**: Inverts single condition

### Value Sources (4 types)
| Type | JSON | Example |
|------|------|---------|
| Field reference | `{"field": "balance"}` | 140+ context fields |
| Parameter | `{"param": "threshold"}` | User-defined constants |
| Literal | `{"value": 100000}` | Numbers, booleans |
| Computation | `{"compute": {"op": "+", ...}}` | Arithmetic expressions |

### Computation Operators (12)
Binary: `+`, `-`, `*`, `/`
N-ary: `max`, `min`
Unary: `ceil`, `floor`, `round`, `abs`
Ternary: `clamp`, `div0` (safe division)

### Context Fields (140+)
Organized into categories:
- **Transaction** (payment_tree only): `amount`, `remaining_amount`, `ticks_to_deadline`, `priority`, `is_overdue`, `queue_age`, etc.
- **Agent/Balance**: `balance`, `effective_liquidity`, `credit_headroom`, `liquidity_pressure`, etc.
- **Queue 1**: `outgoing_queue_size`, `queue1_total_value`, `queue1_liquidity_gap`, `headroom`
- **Queue 2 (RTGS)**: `rtgs_queue_size`, `queue2_count_for_agent`, `ticks_to_nearest_queue2_deadline`
- **Collateral**: `posted_collateral`, `remaining_collateral_capacity`, `excess_collateral`, `collateral_utilization`
- **Cost rates**: `cost_overdraft_bps_per_tick`, `cost_delay_per_tick_per_cent`, `cost_split_friction`, etc.
- **Time/System**: `current_tick`, `system_tick_in_day`, `day_progress_fraction`, `is_eod_rush`, `ticks_remaining_in_day`
- **LSM-Aware** (payment_tree only): `my_bilateral_net_q2`, `tx_is_top_counterparty`, bilateral flow values
- **Throughput**: `my_throughput_fraction_today`, `throughput_gap`, `expected_throughput_fraction_by_now`
- **State registers**: `bank_state_*` (user-defined, max 10 per agent, reset at EOD)

---

## 5. bank_tree vs payment_tree: Key Differences

| Aspect | bank_tree | payment_tree |
|--------|-----------|--------------|
| **Evaluation frequency** | Once per agent per tick | Once per transaction in Queue 1 |
| **Timing** | Step 1.75 (before payments) | Step 2 (after bank decisions) |
| **Context** | Bank-level only (no tx fields) | Full context including tx fields |
| **Purpose** | Set constraints for the tick | Decide per-transaction actions |
| **Actions** | Budget/state management | Release/hold/split/etc. |
| **Interaction** | Bank decisions constrain payment decisions | Budget enforcement applied after payment tree |

**Critical interaction**: `SetReleaseBudget` in bank_tree creates constraints that **override** Release decisions from payment_tree. If budget is exhausted, Release → Hold automatically.

The two collateral trees bracket the settlement process:
- `strategic_collateral_tree` (Step 1.5): Forward-looking, pre-settlement
- `end_of_tick_collateral_tree` (Step 5.5): Reactive cleanup, post-settlement

---

## 6. Complex Multi-Level Decision Logic

The system expresses complex logic through:

1. **Nested condition chains** (if/else if/else): Chain conditions in `on_false` branches
2. **Compound expressions**: `and`/`or`/`not` with multiple conditions
3. **Computed values**: Inline arithmetic in comparisons and action parameters
4. **Cross-tree coordination**: bank_tree sets budgets → payment_tree makes decisions → budget enforcement overrides
5. **State registers**: `bank_state_*` fields persist within a day, enabling multi-tick strategies (cooldowns, counters, mode switches)
6. **Dynamic parameters**: Action parameters can reference fields and computations, not just literals (e.g., dynamic split counts based on amount/liquidity ratio)

---

## 7. Examples of Complex Policies

### Liquidity-Aware with Buffer Protection
```json
{
  "version": "1.0",
  "policy_id": "liquidity_buffer",
  "parameters": {"urgency_threshold": 5.0, "target_buffer": 100000.0},
  "payment_tree": {
    "type": "condition", "node_id": "N1",
    "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"param": "urgency_threshold"}},
    "on_true": {"type": "action", "node_id": "A1", "action": "Release"},
    "on_false": {
      "type": "condition", "node_id": "N2",
      "condition": {"op": "<", "left": {"compute": {"op": "-", "left": {"field": "balance"}, "right": {"field": "remaining_amount"}}}, "right": {"param": "target_buffer"}},
      "on_true": {"type": "action", "node_id": "A2", "action": "Hold"},
      "on_false": {"type": "action", "node_id": "A3", "action": "Release"}
    }
  }
}
```

### Budget-Constrained with Dynamic Splitting
```json
{
  "version": "1.0",
  "policy_id": "budget_splitter",
  "parameters": {"budget_fraction": 0.5, "max_split_size": 50000.0},
  "bank_tree": {
    "type": "action", "node_id": "B1", "action": "SetReleaseBudget",
    "parameters": {
      "max_value_to_release": {"compute": {"op": "*", "left": {"field": "balance"}, "right": {"param": "budget_fraction"}}}
    }
  },
  "payment_tree": {
    "type": "condition", "node_id": "N1",
    "condition": {"op": ">", "left": {"field": "remaining_amount"}, "right": {"field": "effective_liquidity"}},
    "on_true": {
      "type": "action", "node_id": "A1", "action": "Split",
      "parameters": {
        "num_splits": {"compute": {"op": "max", "values": [
          {"compute": {"op": "ceil", "value": {"compute": {"op": "/", "left": {"field": "remaining_amount"}, "right": {"param": "max_split_size"}}}}},
          {"value": 2}
        ]}}
      }
    },
    "on_false": {"type": "action", "node_id": "A2", "action": "Release"}
  }
}
```

### Full 4-Tree Policy with Collateral Management
See `configuration.md` — the "comprehensive_policy" example includes all four trees with coordinated collateral posting, budget setting, urgency-based payment decisions, and end-of-tick excess withdrawal.

---

## 8. Engine Evaluation at Each Tick

The tick lifecycle has 7 main steps with 4 policy evaluation points:

```
Step 1:   Transaction arrivals → Queue 1
Step 1.5: strategic_collateral_tree (once per agent) — post collateral proactively
Step 1.75: bank_tree (once per agent) — set budgets, state registers
Step 2:   payment_tree (per tx in Queue 1) — release/hold/split decisions
          → Budget enforcement applied after each decision
Step 3:   RTGS settlement attempts (Queue 2, by priority)
Step 4:   LSM cycle detection and atomic settlement
Step 5:   Queue 2 re-processing
Step 5.5: end_of_tick_collateral_tree (once per agent) — withdraw excess
Step 6:   Cost accrual (overdraft, delay, collateral)
Step 7:   Metrics and events
```

**Tree traversal**: Recursive descent from root. At each Condition node, evaluate expression → follow on_true or on_false. Continue until Action node reached. Decision path recorded as `"N1(true) → N2(false) → A3"`.

**Error handling**: If evaluation fails (field not found, division by zero), the engine falls back to a safe default (Hold for payments, HoldCollateral for collateral, NoAction for bank).

---

## 9. Policy Parameter System

### Core Mechanism
- Parameters defined in policy JSON as `HashMap<String, f64>`
- Referenced in trees via `{"param": "name"}`
- Overridable per-agent in simulation YAML config
- YAML overrides win; JSON defaults fill gaps

### Beyond initial_liquidity_fraction
The `initial_liquidity_fraction` parameter (mentioned in TOOLS.md) is actually a simulation-level config, not a policy parameter. Policy parameters are user-defined and arbitrary:

```json
"parameters": {
  "urgency_threshold": 5.0,
  "target_buffer": 100000.0,
  "max_splits": 4.0,
  "budget_fraction": 0.5,
  "crisis_buffer": 500000.0,
  "momentum_threshold": 0.3
}
```

### State Registers (Cross-Tick Memory)
State registers (`bank_state_*`) extend parameters with mutable state:
- Set/incremented via bank_tree actions
- Readable from any tree via field references
- Max 10 per agent, reset at EOD
- Enables: cooldown timers, release counters, mode flags, budget tracking

---

## 10. Policy Editor UI — Visual Builder Requirements

A visual policy builder would need:

### Core Components
1. **Tree canvas**: Drag-and-drop nodes with visual branching (condition nodes as diamonds, action nodes as rectangles)
2. **Expression builder**: Visual predicate construction — dropdown for field, operator, value type
3. **Action configurator**: Form-based parameter entry with field/param/literal/compute selectors
4. **Parameter panel**: Define and manage named constants with defaults
5. **Computation builder**: Nested arithmetic expression editor (tree-within-tree)

### Data Requirements
- **Field catalog**: All 140+ context fields with descriptions, types, units, and tree-type availability
- **Action catalog**: All 17 actions with valid-tree matrix and required/optional parameters
- **Operator catalog**: 6 comparison + 3 logical + 12 computation operators
- **Validation engine**: Real-time validation (duplicate IDs, invalid field refs, depth limits)

### UX Features
- **Tree-type tabs**: Separate editors for bank/payment/strategic_collateral/end_of_tick_collateral
- **Context-aware field filtering**: Only show transaction fields when editing payment_tree
- **Live preview**: Show decision path for sample transactions
- **JSON import/export**: Round-trip between visual and JSON representations
- **Template library**: Pre-built policy patterns (FIFO, liquidity-aware, deadline-based, etc.)
- **Parameter override UI**: Simulate different parameter values without editing tree structure
- **Decision path debugger**: Step through tree evaluation with real or mock context values

### Implementation Approach
The existing JSON schema is clean enough to map directly to a visual representation. React Flow or similar node-graph libraries could render the tree. The main challenge is the expression/computation builder — nested arithmetic needs a sub-editor (expression tree within the policy tree).

---

## Key Observations for Researchers

1. **The docs are excellent** — 12 interlinked reference files covering every aspect. A researcher could write policies from docs alone.

2. **The DSL is deliberately limited** — only conditions and actions, no loops, no sequences, no side effects beyond state registers. This makes it safe for LLM generation.

3. **140+ context fields** give policies rich visibility into simulation state — far more than just "balance vs amount."

4. **Cross-tree coordination** (bank_tree budgets constraining payment_tree decisions) enables sophisticated multi-level strategies without complex single-tree logic.

5. **State registers** are the key to temporal strategies (cooldowns, ramp-ups, phase transitions) but are limited (10 per agent, EOD reset).

6. **The validation system** catches most errors at load time, making the system safe for automated policy generation.

7. **Decision path tracking** provides full transparency into why each decision was made — critical for debugging and LLM learning.

8. **Missing from docs**: No guidance on *strategy design patterns* — how to think about policy design beyond the mechanical reference. A "cookbook" of common strategies with rationale would help researchers.
