# Policy System Analysis

> **Generated**: 2026-02-17  
> **Scope**: Complete analysis of the SimCash policy DSL, tree system, actions, conditions, and FFI integration.

---

## 1. Architecture Overview

The policy system is a **JSON-based decision tree DSL** that controls how simulated banks manage payments, collateral, and budgets. Every policy is a `DecisionTreeDef` containing up to four independent decision trees, each evaluated at different simulation phases:

| Tree | Evaluated | Scope | Purpose |
|------|-----------|-------|---------|
| `bank_tree` | Once per agent per tick (STEP 1.75) | Bank-level | Set budgets, state registers |
| `payment_tree` | Per transaction in Queue 1 | Transaction-level | Release/hold/split decisions |
| `strategic_collateral_tree` | Once per agent per tick (STEP 2.5) | Bank-level | Proactive collateral posting |
| `end_of_tick_collateral_tree` | Once per agent per tick (STEP 8) | Bank-level | Reactive collateral cleanup |

All trees share the same node types, expression system, and value resolution—only the available actions differ by context.

---

## 2. Decision Tree Structure

### 2.1 Root Object: `DecisionTreeDef`

```json
{
  "version": "1.0",
  "policy_id": "unique_id",
  "description": "Optional description",
  "parameters": { "threshold": 5.0, "buffer": 100000.0 },
  "bank_tree": { ... },
  "payment_tree": { ... },
  "strategic_collateral_tree": { ... },
  "end_of_tick_collateral_tree": { ... }
}
```

- **version**: Schema version (currently `"1.0"`; Python API wraps as `"2.0"` format with `InlineJson`)
- **policy_id**: Unique string identifier
- **parameters**: Named `f64` constants referenced via `{"param": "name"}` in expressions
- All four trees are optional (defaults: NoAction for bank, Hold for collateral, no-op for payment)

**Source**: `simulator/src/policy/tree/types.rs` — `DecisionTreeDef`

### 2.2 Tree Nodes

Two variants, tagged by `"type"`:

#### Condition Node
```json
{
  "type": "condition",
  "node_id": "N1",
  "description": "optional",
  "condition": { /* Expression */ },
  "on_true": { /* TreeNode */ },
  "on_false": { /* TreeNode */ }
}
```

#### Action Node (terminal)
```json
{
  "type": "action",
  "node_id": "A1",
  "action": "Release",
  "parameters": { "key": { /* ValueOrCompute */ } }
}
```

Trees are binary decision trees of arbitrary depth (max 100 levels enforced at runtime). Every path from root must terminate at an action node.

---

## 3. Expression System

### 3.1 Boolean Expressions (`Expression`)

Tagged by `"op"`:

| Op | Type | Fields |
|----|------|--------|
| `==` | Comparison | `left`, `right` (Value) |
| `!=` | Comparison | `left`, `right` |
| `<` | Comparison | `left`, `right` |
| `<=` | Comparison | `left`, `right` |
| `>` | Comparison | `left`, `right` |
| `>=` | Comparison | `left`, `right` |
| `and` | Logical | `conditions` (Vec<Expression>) — short-circuit |
| `or` | Logical | `conditions` (Vec<Expression>) — short-circuit |
| `not` | Logical | `condition` (Expression) |

Float equality uses epsilon tolerance.

### 3.2 Values (`Value`)

Untagged enum, resolved by structure:

| Form | Example | Resolves to |
|------|---------|-------------|
| Field reference | `{"field": "balance"}` | Context field lookup |
| Parameter reference | `{"param": "threshold"}` | Tree parameter lookup |
| Literal | `{"value": 100}` | Constant (number, bool→0/1, int→f64) |
| Computation | `{"compute": {...}}` | Arithmetic expression |

### 3.3 Computations (`Computation`)

Tagged by `"op"`:

| Op | Fields | Notes |
|----|--------|-------|
| `+` | `left`, `right` | Addition |
| `-` | `left`, `right` | Subtraction |
| `*` | `left`, `right` | Multiplication |
| `/` | `left`, `right` | Division (error on zero) |
| `max` | `values` (Vec) | Maximum of N values |
| `min` | `values` (Vec) | Minimum of N values |
| `ceil` | `value` | Ceiling |
| `floor` | `value` | Floor |
| `round` | `value` | Round to nearest integer |
| `abs` | `value` | Absolute value |
| `clamp` | `value`, `min`, `max` | Clamp to range |
| `div0` | `numerator`, `denominator`, `default` | Safe division (default on zero) |

Computations nest recursively—any `Value` can contain a `Computation` which contains `Value`s.

### 3.4 Action Parameters (`ValueOrCompute`)

Same as `Value` but used in action parameter maps. Supports `{"value": ...}`, `{"field": ...}`, `{"param": ...}`, `{"compute": {...}}`.

---

## 4. All Available Actions

### 4.1 Payment Tree Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| **Release** | Submit transaction in full to RTGS | `priority_override` (opt), `target_tick` (opt) |
| **ReleaseWithCredit** | Submit using intraday credit if needed | — |
| **Hold** | Keep in Queue 1 for re-evaluation | `reason` (opt) |
| **Drop** | Remove from queue (deprecated) | — |
| **Split** | Split into N children, submit all immediately | `num_splits` |
| **PaceAndRelease** | Split and pace transaction | `num_splits` |
| **StaggerSplit** | Split with staggered release timing | `num_splits`, `stagger_first_now`, `stagger_gap_ticks`, `priority_boost_children` |
| **Reprioritize** | Change transaction priority without moving | `new_priority` |
| **WithdrawFromRtgs** | Pull transaction back from RTGS Queue 2 | — |
| **ResubmitToRtgs** | Change RTGS priority of Queue 2 transaction | `rtgs_priority` ("HighlyUrgent"/"Urgent"/"Normal") |

### 4.2 Bank Tree Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| **SetReleaseBudget** | Set per-tick release limits | `max_value_to_release`, `focus_cpty_list` (opt), `max_per_cpty` (opt) |
| **SetState** | Write a state register value | `key` (must start with `bank_state_`), `value`, `reason` |
| **AddState** | Increment/decrement a state register | `key`, `value`, `reason` |
| **NoAction** | Do nothing this tick | — |

### 4.3 Collateral Tree Actions

| Action | Description | Parameters |
|--------|-------------|------------|
| **PostCollateral** | Post collateral to increase liquidity | `amount`, `reason`, `auto_withdraw_after_ticks` (opt) |
| **WithdrawCollateral** | Withdraw collateral to reduce costs | `amount`, `reason` |
| **HoldCollateral** | Keep current collateral level | — |

---

## 5. Evaluation Context Fields

The `EvalContext` provides ~80+ fields to expressions. All are `f64`.

### 5.1 Transaction Fields
`amount`, `remaining_amount`, `settled_amount`, `arrival_tick`, `deadline_tick`, `priority`, `is_split` (0/1), `is_past_deadline` (0/1), `is_overdue` (0/1), `overdue_duration`, `is_in_queue2` (0/1)

### 5.2 Agent Fields
`balance`, `credit_limit`, `available_liquidity`, `credit_used`, `effective_liquidity` (balance + unused credit), `is_using_credit` (0/1), `liquidity_buffer`, `outgoing_queue_size`, `incoming_expected_count`, `liquidity_pressure`, `credit_headroom`, `is_overdraft_capped` (always 1.0)

### 5.3 Derived Fields
`ticks_to_deadline` (can be negative), `queue_age`

### 5.4 System Fields
`current_tick`, `rtgs_queue_size`, `rtgs_queue_value`, `total_agents`

### 5.5 Collateral Fields
`posted_collateral`, `max_collateral_capacity`, `remaining_collateral_capacity`, `collateral_utilization`, `credit_used`, `allowed_overdraft_limit`, `overdraft_headroom`, `collateral_haircut`, `unsecured_cap`, `required_collateral_for_usage`, `excess_collateral`, `overdraft_utilization`

### 5.6 Queue Fields
`queue1_liquidity_gap`, `queue1_total_value`, `headroom`, `queue2_size`, `queue2_count_for_agent`, `queue2_nearest_deadline`, `ticks_to_nearest_queue2_deadline`

### 5.7 Cost Fields
`cost_overdraft_bps_per_tick`, `cost_delay_per_tick_per_cent`, `cost_collateral_bps_per_tick`, `cost_split_friction`, `cost_deadline_penalty`, `cost_eod_penalty`, `cost_delay_this_tx_one_tick`, `cost_overdraft_this_amount_one_tick`

### 5.8 Time/Day Fields
`system_ticks_per_day`, `system_current_day`, `system_tick_in_day`, `ticks_remaining_in_day`, `day_progress_fraction` (0.0–1.0), `is_eod_rush` (0/1)

### 5.9 LSM-Aware Fields
`my_q2_out_value_to_counterparty`, `my_q2_in_value_from_counterparty`, `my_bilateral_net_q2`, `my_q2_out_value_top_1..5`, `my_q2_in_value_top_1..5`, `my_bilateral_net_q2_top_1..5`

### 5.10 Public Signal Fields
`system_queue2_pressure_index` (0–1), `lsm_run_rate_last_10_ticks`, `system_throughput_guidance_fraction_by_tick`

### 5.11 Throughput Progress Fields
`my_throughput_fraction_today`, `expected_throughput_fraction_by_now`, `throughput_gap`

### 5.12 Counterparty Fields
`tx_counterparty_id` (hash), `tx_is_top_counterparty` (0/1)

### 5.13 State Registers
Any field starting with `bank_state_` — defaults to 0.0 if not set. Max 10 per agent. Reset at end of day.

### 5.14 Bank-Level Context
`EvalContext::bank_level()` provides all agent, system, collateral, queue, cost, time, and state register fields but **no transaction fields** (no `amount`, `ticks_to_deadline`, etc.).

---

## 6. Built-in Policy Files

Located in `simulator/policies/`:

### 6.1 Core Policies (mapped to `PolicyConfig` enum)

| File | PolicyConfig | Parameters | Logic |
|------|-------------|------------|-------|
| `fifo.json` | `Fifo` | None | Always Release |
| `deadline.json` | `Deadline` | `urgency_threshold` | Release if near deadline, else Hold |
| `liquidity_aware.json` | `LiquidityAware` | `target_buffer`, `urgency_threshold` | Balance check + urgency override |
| `liquidity_splitting.json` | `LiquiditySplitting` | `max_splits`, `min_split_amount` | Split large payments when liquidity tight |
| `mock_splitting.json` | `MockSplitting` | `num_splits` | Always split (test-only) |

### 6.2 Advanced Policies (used via `FromJson`)

| File | Key Features |
|------|-------------|
| `sophisticated_adaptive_bank.json` | Bank budgets, state registers (cooldowns), 4-tree policy |
| `adaptive_liquidity_manager.json` | Dynamic liquidity management |
| `aggressive_market_maker.json` | High-throughput market making |
| `balanced_cost_optimizer.json` | Cost-aware decisions |
| `cautious_liquidity_preserver.json` | Conservative approach |
| `smart_splitter.json` | Intelligent splitting |
| `efficient_splitting.json` | Optimized split logic |
| `efficient_proactive.json` | Proactive release strategy |
| `efficient_memory_adaptive.json` | Memory-based adaptive |
| `momentum_investment_bank.json` | Momentum-based strategy |
| `memory_driven_strategist.json` | State register driven |
| `deadline_driven_trader.json` | Deadline-focused |
| `smart_budget_manager.json` | Budget optimization |
| `cost_aware_test.json` | Cost field testing |
| `time_aware_test.json` | Time field testing |

### 6.3 TARGET2-Specific Policies

| File | Strategy |
|------|----------|
| `target2_aggressive_settler.json` | Aggressive settlement |
| `target2_conservative_offsetter.json` | Conservative LSM offsetting |
| `target2_crisis_proactive_manager.json` | Crisis proactive management |
| `target2_crisis_risk_denier.json` | Risk denial strategy |
| `target2_limit_aware.json` | Credit limit aware |
| `target2_priority_aware.json` | RTGS priority management |
| `target2_priority_escalator.json` | Priority escalation |

---

## 7. Policy Loading & FFI

### 7.1 PolicyConfig Enum (Rust)

```rust
pub enum PolicyConfig {
    Fifo,
    Deadline { urgency_threshold: usize },
    LiquidityAware { target_buffer: i64, urgency_threshold: usize },
    LiquiditySplitting { max_splits: usize, min_split_amount: i64 },
    MockSplitting { num_splits: usize },
    MockStaggerSplit { num_splits, stagger_first_now, stagger_gap_ticks, priority_boost_children },
    FromJson { json: String },
}
```

### 7.2 Factory: `create_policy(config) → TreePolicy`

**Source**: `simulator/src/policy/tree/factory.rs`

- Named configs (`Fifo`, `Deadline`, etc.) → load from `simulator/policies/{name}.json` + inject parameters
- `FromJson { json }` → parse inline JSON string directly via `TreePolicy::from_json()`
- Policy directory resolution tries: `simulator/policies/`, `policies/`, `../simulator/policies/`, `../../simulator/policies/`

### 7.3 FFI Entry (Python → Rust via PyO3)

**Source**: `simulator/src/ffi/types.rs` — `parse_policy_config()`

Python passes a dict:
```python
# Named policy
{"type": "Deadline", "urgency_threshold": 5}

# Inline JSON policy (the "InlineJson" / "FromJson" path)
{"type": "FromJson", "json": '{"version":"1.0", "policy_id":"...", ...}'}
```

The Python API's `SimulationConfig.from_dict()` maps `"InlineJson"` → `"FromJson"` internally:
```python
agent_config = {
    "policy": {
        "type": "InlineJson",
        "json_string": '{"version":"2.0", "policy_id":"...", ...}'
    }
}
```

### 7.4 Version 2.0 JSON Format

The Python layer uses version `"2.0"` to signal the full policy format. The Rust `DecisionTreeDef` accepts any version string. The version field is informational — there is no behavioral difference between `"1.0"` and `"2.0"`. The `"2.0"` label is a Python-side convention indicating LLM-generated policies with the complete schema (all four trees, parameters, etc.).

---

## 8. payment_tree vs bank_tree

| Aspect | `payment_tree` | `bank_tree` |
|--------|---------------|-------------|
| **Granularity** | Per-transaction | Per-agent, once per tick |
| **Context** | Full context (tx + agent + system) | Bank-level context (no tx fields) |
| **Timing** | During Queue 1 evaluation | STEP 1.75 (before payment processing) |
| **Available actions** | Release, Hold, Split, StaggerSplit, etc. | SetReleaseBudget, SetState, AddState, NoAction |
| **Purpose** | Decide what to do with each payment | Set tick-wide budgets and state |
| **Budget enforcement** | Release decisions checked against budget | Sets the budget that payment_tree must obey |

The `bank_tree` runs first, potentially setting a `SetReleaseBudget` that caps how much the `payment_tree` can release. The `payment_tree` may return `Release` but the orchestrator converts it to `Hold` if the budget is exhausted.

---

## 9. State Registers (Policy Micro-Memory)

- Keys must start with `bank_state_` prefix
- Max 10 registers per agent
- Reset at end of day
- Set via `SetState` action, incremented via `AddState` action
- Readable in any tree via `{"field": "bank_state_cooldown"}`
- Default to 0.0 if never set

**Use cases**: Cooldown timers, counters, running totals, mode flags.

---

## 10. Decision Path Tracking

Every tree traversal records a `DecisionPath`: the sequence of node IDs visited and condition results.

Format: `"N1:CheckLiquidity(true) → N2:QueueSize(false) → A3:Release"`

This provides full transparency into why a policy made a specific decision.

---

## 11. Validation

**Source**: `simulator/src/policy/tree/validation.rs`

Trees are validated lazily on first use against a sample `EvalContext`:
- All field references must resolve
- All parameter references must exist in `parameters` map
- All paths must terminate at action nodes
- Max depth 100
- Node IDs should be unique (warning, not error)

---

## 12. Expressiveness Summary

The policy DSL can express:

1. **Simple rules**: "Always release" (FIFO)
2. **Threshold conditions**: "Release if balance > X"
3. **Multi-factor decisions**: Nested conditions combining liquidity, urgency, time-of-day, counterparty, queue pressure
4. **Arithmetic**: Compute values inline (`balance * 0.5 + buffer`)
5. **Cost-aware logic**: Compare delay cost vs overdraft cost
6. **Time-aware behavior**: EOD rush detection, day progress fractions
7. **Stateful strategies**: Cooldown timers, counters via state registers
8. **Budget control**: Bank-level budgets constraining per-transaction decisions
9. **Collateral management**: Two-phase (strategic + reactive) collateral posting/withdrawal
10. **LSM coordination**: Bilateral net position awareness for offset feeding
11. **Queue 2 management**: Withdraw/resubmit with priority changes (TARGET2 dual priority)
12. **Splitting strategies**: Fixed splits, staggered splits with timing control
13. **Counterparty awareness**: Top counterparty identification, bilateral flow tracking

**Limitations**:
- No loops or iteration (pure binary decision tree)
- No string operations (counterparty IDs are hashed to f64)
- No cross-agent communication (only public signals)
- Max depth 100
- No randomness (deterministic given context)
- State registers reset daily (no multi-day memory)
