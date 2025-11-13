# Policy System Enhancements - Version 2.0

**Created**: 2025-11-12
**Status**: Planning
**Priority**: High
**Goal**: Enhance policy system to enable more realistic cash manager behavior while preserving information privacy constraints

---

## Executive Summary

The current policy system provides a strong foundation with the right economic levers (delay vs. liquidity vs. penalties), appropriate system frictions (two queues + LSM), and a clean DSL that's safe and easy to edit. However, agents lack several capabilities that real cash managers use to optimize intraday liquidity:

**Key Gaps Identified**:
1. **Limited LSM awareness** - Agents can't see their own LSM-relevant signals (Queue 2 composition by counterparty)
2. **No pacing control** - Split always releases all children immediately
3. **Per-transaction only** - No bank-level budget/quota decisions
4. **Ambiguous overdraft regime** - Unclear if credit limits are enforced or just priced
5. **Missing throughput management** - No way to track/adjust against daily settlement targets
6. **Limited counterparty logic** - Can't prioritize corridors likely to trigger recycling

**Approach**: Incremental enhancements that preserve the core design (declarative DSL, two queues + LSM, information privacy) while adding capabilities real cash managers use. All additions use only own-bank information or coarse public signals.

**Impact**: Policies will be able to:
- **Feed LSM intentionally** by releasing to counterparties where bilateral offset is likely
- **Pace releases** without flooding Queue 2
- **Manage throughput** against daily targets
- **Exercise clear credit discipline** with proper headroom calculations
- **Explain decisions** with emitted reasons and costs

---

## Current State Analysis

### What Works Well

**Economic Framework**:
- Cost-aware optimization (Phase 9.5.1) with delay vs. overdraft tradeoffs
- Time-based strategies (Phase 9.5.2) with EOD rush and day progress tracking
- Dynamic action parameters (Phase 9.5.3) for adaptive splitting and collateral

**System Design**:
- Three decision trees: `payment_tree`, `strategic_collateral_tree`, `end_of_tick_collateral_tree`
- 60+ context fields covering transaction, agent, queue, collateral, cost, and time data
- LSM bilateral offsets and cycles working correctly
- Replay identity maintained through unified architecture

**Developer Experience**:
- JSON DSL is declarative, safe, and LLM-editable
- Clear separation of concerns across decision hooks
- Comprehensive documentation with examples
- Validation and error reporting

### What's Missing for Realistic Cash Management

**1. Engine/Realism Issues**
- **Overdraft regime ambiguity**: Logs show `credit_used > credit_limit` (e.g., $344k used vs. $120k limit). Is this priced-unbounded or a bug?
- **No LSM visibility for own bank**: Agents can't see their own Queue 2 composition by counterparty to time releases
- **No public signals**: System pressure, LSM run rate, throughput guidance not exposed

**2. DSL Field Gaps**
- **No throughput tracking**: Can't measure "I'm behind daily target" to adjust aggression
- **No counterparty fields**: Can't identify "this payment is to my top bilateral partner"
- **No basic math helpers**: Missing `ceil`, `floor`, `clamp`, safe division

**3. DSL Action Limitations**
- **Split pacing**: All children released immediately; can't stagger over time
- **No RTGS flags**: Can't upgrade priority or time releases
- **No bank-level budgets**: Can't express "release max $X this tick, focus on counterparties A/B"
- **No collateral timers**: Can't "post temporarily then auto-withdraw"

**4. Policy Structure Issues**
- **Action vocabulary confusion**: `ReleaseWithCredit` used in examples but semantics unclear
- **No decision explanations**: Logs don't show which node/costs drove Hold decisions
- **No counterparty heuristics**: Can't express "prioritize corridors with inbound match"
- **No state memory**: Can't implement cool-downs or multi-tick strategies

**5. Metrics/Diagnostics**
- **Settlement rate broken**: Shows >1.0 (e.g., 3.303 from 327 settlements / 99 arrivals)
- **LSM logging incomplete**: Missing tx IDs and before/after states
- **No reason tracking**: Hold decisions don't emit explanatory data

### Behavioral Observations (Ticks 280–290)

From replay logs:

**LSM is effective**:
- Bilateral offsets between CORRESPONDENT_HUB and REGIONAL_TRUST saving $30-45k per cycle
- Heavy Queue 2, scarce headroom → LSM doing intended work

**Over-eager late-day releases**:
- REGIONAL_TRUST in overdraft (~-$92k to -$100k) still releasing broadly from Queue 1
- EOD panic mode too unconditional; should be more targeted

**Splitting is rare**:
- Design forces splits on Day 2; late Day 3 shows only SUBMIT
- All split children released immediately (no drip-feeding)

**Credit limits appear soft**:
- HUB shows credit_used=$330-344k vs. limit=$120k
- Either intentionally unbounded (priced) or enforcement bug

---

## Implementation Plan

### Phase 1: Engine Realism Fixes (Week 1, 3-4 days)

**Goal**: Resolve overdraft regime ambiguity and expose LSM-relevant own-bank signals.

#### 1.1: Clarify Overdraft Regime

**Decision Required**: Choose one:
- **Option A**: Unbounded priced overdraft (current behavior)
- **Option B**: Enforce `credit_used ≤ credit_limit` at settlement

**If Option A** (priced unbounded):
- Rename display "Credit Limit" → "Reference Limit (not enforced)"
- Add field `is_overdraft_capped: 0.0` (always false)
- Document clearly in policy guide

**If Option B** (enforced cap):
- Add settlement check: reject if `credit_used + amount > credit_limit`
- Expose `credit_headroom = credit_limit - credit_used`
- Add field `is_overdraft_capped: 1.0` (always true)
- Update all examples to use `effective_liquidity` and `credit_headroom`

**Files**:
- `backend/src/settlement/rtgs.rs` - Add cap enforcement if Option B
- `backend/src/policy/tree/context.rs` - Add `is_overdraft_capped`, `credit_headroom` fields
- `docs/policy_dsl_guide.md` - Document regime choice

**Tests**:
- `backend/tests/settlement_tests.rs::test_overdraft_cap_enforcement` (if Option B)
- `api/tests/integration/test_policy_context.py::test_overdraft_fields`

#### 1.2: Add Own-Bank LSM-Relevant Fields

**New context fields** (own-bank only, no privacy violation):

```rust
// In EvalContext::build()
fields.insert("my_q2_out_value_to_counterparty", calculate_my_q2_out_by_cpty(agent, tx.receiver()));
fields.insert("my_q2_in_value_from_counterparty", calculate_my_q2_in_by_cpty(agent, tx.receiver()));
fields.insert("my_bilateral_net_q2", my_q2_out - my_q2_in);
```

**Aggregate fields** (top 5 counterparties):
- `my_q2_out_value_top_1` through `my_q2_out_value_top_5`
- `my_q2_in_value_top_1` through `my_q2_in_value_top_5`
- `my_bilateral_net_q2_top_1` through `my_bilateral_net_q2_top_5`
- `top_cpty_1_id` through `top_cpty_5_id` (categorical)

**Files**:
- `backend/src/policy/tree/context.rs` - Add helper functions and fields
- `backend/src/models/agent.rs` - Add method `get_q2_value_by_counterparty()`
- `docs/policy_dsl_guide.md` - Document new fields

**Tests**:
- `api/tests/integration/test_lsm_awareness_fields.py` - Verify calculations
- `backend/tests/policy_context_tests.rs::test_counterparty_q2_fields`

#### 1.3: Add Public Signal Fields

**New system-level fields**:

```rust
// System pressure indicator (0-1 normalized)
fields.insert("system_queue2_pressure_index", calculate_pressure_index(state));

// LSM activity rate (events per tick, last 10 ticks)
fields.insert("lsm_run_rate_last_10_ticks", state.lsm_event_rate(10));

// Throughput guidance (optional, from config)
fields.insert("system_throughput_guidance_fraction_by_tick",
    config.throughput_guidance.get(system_tick_in_day).unwrap_or(0.0));
```

**Files**:
- `backend/src/policy/tree/context.rs` - Add fields
- `backend/src/models/state.rs` - Add `lsm_event_rate()` method
- `backend/src/config/mod.rs` - Add optional `throughput_guidance: Vec<f64>` to config
- `docs/policy_dsl_guide.md` - Document fields

**Tests**:
- `backend/tests/policy_context_tests.rs::test_public_signal_fields`

---

### Phase 2: DSL Field Enhancements (Week 1-2, 2-3 days)

**Goal**: Add throughput tracking, counterparty info, and math helpers.

#### 2.1: Throughput Progress Fields

**New fields**:

```rust
// Agent's throughput today
fields.insert("my_throughput_fraction_today",
    state.agent_throughput_today(agent.id()) / state.agent_total_due_today(agent.id()));

// Expected progress from guidance curve
fields.insert("expected_throughput_fraction_by_now",
    config.throughput_guidance.get(system_tick_in_day).unwrap_or(0.0));

// Gap (negative = behind, positive = ahead)
fields.insert("throughput_gap",
    my_throughput_fraction_today - expected_throughput_fraction_by_now);
```

**Files**:
- `backend/src/models/state.rs` - Add throughput tracking methods
- `backend/src/policy/tree/context.rs` - Add fields
- `docs/policy_dsl_guide.md` - Document with examples

**Tests**:
- `backend/tests/throughput_tracking_tests.rs`
- `api/tests/integration/test_throughput_aware_policies.py`

#### 2.2: Counterparty Fields at Transaction Level

**New fields**:

```rust
// Transaction-specific
fields.insert("tx_counterparty_id", tx.receiver().clone()); // categorical
fields.insert("tx_is_top_counterparty",
    if agent.top_counterparties(5).contains(tx.receiver()) { 1.0 } else { 0.0 });
```

**Files**:
- `backend/src/models/agent.rs` - Add `top_counterparties()` method (based on 30-day flow)
- `backend/src/policy/tree/context.rs` - Add fields
- `docs/policy_dsl_guide.md` - Document

**Tests**:
- `backend/tests/policy_context_tests.rs::test_counterparty_fields`

#### 2.3: Math Helper Functions

**New computation operators**:

```rust
// In Computation enum
#[serde(rename = "ceil")]
Ceil { value: Value },

#[serde(rename = "floor")]
Floor { value: Value },

#[serde(rename = "round")]
Round { value: Value },

#[serde(rename = "clamp")]
Clamp { value: Value, min: Value, max: Value },

#[serde(rename = "div0")]
SafeDiv { numerator: Value, denominator: Value, default: Value },

#[serde(rename = "abs")]
Abs { value: Value },
```

**Files**:
- `backend/src/policy/tree/types.rs` - Add enum variants
- `backend/src/policy/tree/interpreter.rs` - Implement evaluation
- `docs/policy_dsl_guide.md` - Document with examples

**Tests**:
- `backend/tests/policy_computation_tests.rs::test_math_helpers`

---

### Phase 3: DSL Action Extensions (Week 2, 4-5 days)

**Goal**: Add pacing, RTGS flags, bank-level budgets, collateral timers.

#### 3.1: Staggered Split Action

**New action type**:

```json
{
  "type": "action",
  "node_id": "A_StaggerSplit",
  "action": "StaggerSplit",
  "parameters": {
    "num_splits": {"value": 4.0},
    "stagger_first_now": {"value": 2.0},
    "stagger_gap_ticks": {"value": 3.0},
    "priority_boost_children": {"value": 0.0}
  }
}
```

**Semantics**:
- Split transaction into `num_splits` children
- Submit `stagger_first_now` children immediately
- Queue remaining children with `stagger_gap_ticks` delay between each
- Optionally boost priority of children

**Files**:
- `backend/src/policy/tree/types.rs` - Add `StaggerSplit` variant
- `backend/src/policy/mod.rs` - Add `StaggerSplitDecision` with schedule
- `backend/src/orchestrator/engine.rs` - Implement staggered release logic
- `docs/policy_dsl_guide.md` - Document with examples

**Tests**:
- `backend/tests/stagger_split_tests.rs`
- `api/tests/integration/test_stagger_split_behavior.py`

#### 3.2: Release with RTGS Flags

**Extend Release action**:

```json
{
  "type": "action",
  "node_id": "A_ReleaseTimed",
  "action": "Release",
  "parameters": {
    "priority_flag": {"value": "HIGH"},
    "timed_for_tick": {"compute": {"op": "+", "left": {"field": "current_tick"}, "right": {"value": 2.0}}}
  }
}
```

**Semantics**:
- `priority_flag`: Override transaction priority ("HIGH", "MEDIUM", "LOW")
- `timed_for_tick`: Target tick for settlement (for LSM timing)

**Files**:
- `backend/src/policy/tree/types.rs` - Add optional parameters to Release
- `backend/src/policy/mod.rs` - Extend `ReleaseDecision` struct
- `backend/src/settlement/rtgs.rs` - Use flags in settlement logic
- `docs/policy_dsl_guide.md` - Document

**Tests**:
- `backend/tests/release_flags_tests.rs`

#### 3.3: Bank-Level Budget Actions

**New tree type**: `bank_tree` (evaluated once per tick before per-tx trees)

**New action**:

```json
{
  "version": "1.0",
  "policy_id": "budget_manager",
  "bank_tree": {
    "type": "action",
    "node_id": "B1_SetBudget",
    "action": "SetReleaseBudget",
    "parameters": {
      "max_value_to_release_this_tick": {"compute": {"op": "*", "left": {"field": "effective_liquidity"}, "right": {"value": 0.3}}},
      "focus_cpty_list": {"value": ["METRO_CENTRAL", "CORRESPONDENT_HUB"]},
      "max_per_cpty": {"value": 100000.0}
    }
  }
}
```

**Semantics**:
- Evaluated once per agent per tick
- Sets budget state that `Release` actions check
- When budget exhausted, `Release` → `Hold` with reason `BudgetExhausted`

**Files**:
- `backend/src/policy/tree/types.rs` - Add `SetReleaseBudget` action, extend `DecisionTreeDef`
- `backend/src/models/agent.rs` - Add `budget_state` field
- `backend/src/policy/mod.rs` - Add budget tracking
- `backend/src/orchestrator/engine.rs` - Evaluate bank_tree before payment_tree
- `docs/policy_dsl_guide.md` - Document with examples

**Tests**:
- `backend/tests/budget_enforcement_tests.rs`
- `api/tests/integration/test_bank_level_budgets.py`

#### 3.4: Collateral with Auto-Withdraw Timer

**Extend PostCollateral**:

```json
{
  "type": "action",
  "node_id": "SC_PostTemporary",
  "action": "PostCollateral",
  "parameters": {
    "amount": {"value": 200000.0},
    "reason": {"value": "TemporaryBoost"},
    "auto_withdraw_after_ticks": {"value": 10.0}
  }
}
```

**Semantics**:
- Post collateral as normal
- Automatically schedule `WithdrawCollateral` after N ticks
- Avoids need for separate end-of-tick rule

**Files**:
- `backend/src/policy/tree/types.rs` - Add optional parameter
- `backend/src/models/agent.rs` - Add collateral timer tracking
- `backend/src/orchestrator/engine.rs` - Process timers
- `docs/policy_dsl_guide.md` - Document

**Tests**:
- `backend/tests/collateral_timer_tests.rs`

---

### Phase 4: Policy Structure Improvements (Week 3, 3-4 days)

**Goal**: Resolve action vocabulary, add explanations, improve pattern support.

#### 4.1: Resolve ReleaseWithCredit Semantics

**Decision Required**: Define clear semantics or remove from examples.

**Option A - Define Semantics**:
```
ReleaseWithCredit:
1. If effective_liquidity >= amount → Release
2. Else if collateral_available > 0 → PostCollateral(gap), then Release
3. Else if !is_overdraft_capped → Release (accept priced overdraft)
4. Else → Hold with reason "InsufficientCapacity"
```

**Option B - Remove**:
- Delete from examples, use explicit logic in trees instead

**Recommendation**: Option A (more ergonomic for common case)

**Files**:
- `backend/src/policy/tree/types.rs` - Keep or remove `ReleaseWithCredit`
- `backend/src/policy/mod.rs` - Implement semantics if keeping
- `docs/policy_dsl_guide.md` - Document clearly or remove references

#### 4.2: Add Decision Explanation Logging

**Extend Hold action**:

```json
{
  "type": "action",
  "node_id": "A_Hold",
  "action": "Hold",
  "parameters": {
    "reason": {"value": "DelayMoreEconomical"},
    "explain_costs": {"value": 1.0}  // Emit cost breakdown
  }
}
```

**Logging output**:
```
HOLD: TX 4cda913e  reason=DelayMoreEconomical
  liquidity: eff_liq=8,200 vs amt=3,967
  costs: delay_one_tick=12.5 < overdraft_one_tick=23.4 → true
  node=N5_CostBenefitHold
```

**Files**:
- `backend/src/policy/mod.rs` - Extend `HoldDecision` to carry explanation data
- `backend/src/models/event.rs` - Add explanation to PolicyHold event
- `api/payment_simulator/cli/display/verbose_output.py` - Display explanations
- `docs/policy_dsl_guide.md` - Document

**Tests**:
- `api/tests/integration/test_policy_explanations.py`

#### 4.3: Per-Counterparty Heuristic Patterns

**Add reusable pattern snippets to docs**:

```json
{
  "type": "condition",
  "node_id": "N_CorridorPush",
  "description": "Prefer releasing to counterparties with inbound match",
  "condition": {
    "op": ">",
    "left": {"field": "my_q2_in_value_from_counterparty"},
    "right": {"value": 0.0}
  },
  "on_true": {
    "type": "action",
    "node_id": "A_ReleaseToFeedLSM",
    "action": "Release"
  },
  "on_false": {
    "type": "action",
    "node_id": "A_HoldNoMatch",
    "action": "Hold",
    "parameters": {"reason": {"value": "NoInboundMatch"}}
  }
}
```

**Files**:
- `docs/policy_dsl_guide.md` - Add "LSM-Aware Patterns" section
- `backend/policies/lsm_aware_example.json` - New example policy

#### 4.4: Progress-Aware Aggression Patterns

**Add throughput-gap pattern**:

```json
{
  "type": "condition",
  "node_id": "N_BehindTarget",
  "description": "Loosen gates if behind throughput target",
  "condition": {
    "op": ">",
    "left": {"field": "throughput_gap"},
    "right": {"value": -0.1}
  },
  "on_true": {
    "type": "action",
    "node_id": "A_NormalBudget",
    "action": "SetReleaseBudget",
    "parameters": {
      "max_value_to_release_this_tick": {"compute": {"op": "*", "left": {"field": "effective_liquidity"}, "right": {"value": 0.3}}}
    }
  },
  "on_false": {
    "type": "action",
    "node_id": "A_WidenGates",
    "action": "SetReleaseBudget",
    "parameters": {
      "max_value_to_release_this_tick": {"compute": {"op": "*", "left": {"field": "effective_liquidity"}, "right": {"value": 0.6}}}
    }
  }
}
```

**Files**:
- `docs/policy_dsl_guide.md` - Add "Throughput Management Patterns" section
- `backend/policies/throughput_aware_example.json` - New example

#### 4.5: Stateful Micro-Memory (Simple Registers)

**New bank-level state registers** (ephemeral, reset each day):

```json
{
  "type": "action",
  "node_id": "A_SetCooldown",
  "action": "SetState",
  "parameters": {
    "key": {"value": "last_stagger_tick"},
    "value": {"field": "current_tick"}
  }
}
```

**Access in conditions**:

```json
{
  "op": ">",
  "left": {
    "compute": {
      "op": "-",
      "left": {"field": "current_tick"},
      "right": {"field": "bank_state_last_stagger_tick"}
    }
  },
  "right": {"value": 5.0}
}
```

**Constraints**:
- Max 10 registers per agent
- Keys prefixed with `bank_state_`
- Reset at EOD
- No complex logic (just reads/writes)

**Files**:
- `backend/src/models/agent.rs` - Add `state_registers: HashMap<String, f64>`
- `backend/src/policy/tree/types.rs` - Add `SetState`, `AddState` actions
- `backend/src/policy/tree/context.rs` - Expose registers as fields
- `docs/policy_dsl_guide.md` - Document with cool-down example

**Tests**:
- `backend/tests/state_register_tests.rs`

---

### Phase 5: Metrics & Diagnostics (Week 3, 2-3 days)

**Goal**: Fix settlement rate, improve LSM logging, enhance metrics.

#### 5.1: Fix Settlement Rate Definition

**Current bug**: `327 settlements / 99 arrivals = 3.303` (wrong)

**Correct definition**:
```rust
settlement_rate = min(1.0, settled_value / total_value_due)
```

**Alternative metric** (more useful):
```rust
throughput_efficiency = settled_count / (settled_count + queued_count)
```

**Files**:
- `backend/src/models/metrics.rs` - Fix calculation
- `api/payment_simulator/persistence/query.py` - Fix query
- `docs/metrics.md` - Document definitions

**Tests**:
- `backend/tests/metrics_tests.rs::test_settlement_rate_capped_at_one`

#### 5.2: Enhanced LSM Event Logging

**Add to LSM events**:
- Transaction IDs for all payments in cycle
- Before/after balances for each agent
- Before/after credit usage
- Liquidity saved calculation

**Example**:
```
LSM Bilateral Offset: CORRESPONDENT_HUB ↔ REGIONAL_TRUST
  Transactions: tx_abc123 ($45k) ↔ tx_def456 ($50k)
  Net: HUB pays $5k
  Before: HUB bal=-$335k | TRUST bal=-$92k
  After:  HUB bal=-$340k | TRUST bal=-$42k
  Liquidity saved: $45k (would have needed credit for full amounts)
```

**Files**:
- `backend/src/models/event.rs` - Extend LSM event variants
- `backend/src/settlement/lsm.rs` - Emit richer events
- `api/payment_simulator/cli/display/verbose_output.py` - Display enhancements

**Tests**:
- `api/tests/integration/test_lsm_event_logging.py`

#### 5.3: Add Decision Audit Trail

**New metric**: Policy decision distribution

```json
{
  "agent_id": "CORRESPONDENT_HUB",
  "tick": 280,
  "decisions": {
    "Release": 45,
    "Hold": 12,
    "Split": 3,
    "Drop": 0
  },
  "hold_reasons": {
    "DelayMoreEconomical": 7,
    "BudgetExhausted": 3,
    "NoInboundMatch": 2
  }
}
```

**Files**:
- `backend/src/models/metrics.rs` - Add decision tracking
- `backend/src/ffi/orchestrator.rs` - Expose via FFI
- `api/payment_simulator/persistence/persistence.py` - Store in DB
- `docs/metrics.md` - Document

**Tests**:
- `api/tests/integration/test_decision_metrics.py`

---

## Testing Strategy

### Unit Tests (Rust)

**Coverage targets**:
- [ ] Context field calculations (all new fields)
- [ ] Math helper functions (ceil, floor, clamp, div0, abs)
- [ ] StaggerSplit scheduling logic
- [ ] Budget enforcement (SetReleaseBudget)
- [ ] Collateral auto-withdraw timers
- [ ] State register read/write
- [ ] Overdraft cap enforcement (if Option B)

**Location**: `backend/tests/`

### Integration Tests (Python)

**Coverage targets**:
- [ ] LSM-aware policies (release to counterparties with inbound matches)
- [ ] Throughput-aware policies (adjust aggression based on gap)
- [ ] Bank-level budget enforcement
- [ ] Staggered split behavior (verify drip-feed)
- [ ] ReleaseWithCredit semantics (if keeping)
- [ ] Decision explanation logging
- [ ] Metrics accuracy (settlement rate, throughput efficiency)

**Location**: `api/tests/integration/`

### Scenario Tests

**Coverage targets**:
- [ ] LSM feeding: Policy that intentionally triggers bilateral offsets
- [ ] Throughput recovery: Policy that catches up when behind target
- [ ] Credit discipline: Policy respects enforced cap (if Option B)
- [ ] Stagger pacing: Large payment split and dripped over time
- [ ] Cool-down: State registers prevent rapid-fire splits

**Location**: `backend/src/policy/tree/scenario_tests.rs`

### Replay Identity Tests

**Coverage targets**:
- [ ] All new event types replay correctly
- [ ] LSM enhanced events display identically
- [ ] Decision explanations appear in both run and replay
- [ ] Metrics match between run and replay

**Location**: `api/tests/integration/test_replay_identity_gold_standard.py`

---

## Documentation Updates

### Policy DSL Guide

**New sections**:
1. **LSM-Aware Patterns** - Using Q2 counterparty fields
2. **Throughput Management Patterns** - Adjusting aggression based on progress
3. **Bank-Level Budget Patterns** - SetReleaseBudget examples
4. **Staggered Split Patterns** - Drip-feeding liquidity
5. **Stateful Strategies** - Using state registers for cool-downs
6. **Math Helpers Reference** - ceil, floor, clamp, div0, abs

**Updated sections**:
- Available Data Reference (add ~20 new fields)
- Action Summary (add StaggerSplit, SetReleaseBudget, SetState)
- Advanced Features (ReleaseWithCredit semantics if keeping)

**File**: `docs/policy_dsl_guide.md`

### Architecture Documentation

**New sections**:
- Overdraft regime choice and implications
- Bank-level vs. per-transaction decision flow
- Budget enforcement mechanism
- State register lifecycle

**File**: `docs/architecture.md`

### Example Policies

**New files**:
- `backend/policies/lsm_aware_bilateral.json` - Feed LSM intentionally
- `backend/policies/throughput_manager.json` - Daily target tracking
- `backend/policies/budget_enforced.json` - Bank-level quotas
- `backend/policies/stagger_pacer.json` - Drip-feed splits
- `backend/policies/comprehensive_v2.json` - All Phase 2 features

**Updated files**:
- `backend/policies/adaptive_liquidity_manager.json` - Use new fields

---

## Migration & Compatibility

### Breaking Changes

**None expected** - All additions are opt-in:
- New fields: Existing policies ignore them
- New actions: Existing policies don't use them
- New tree type (bank_tree): Optional
- Math helpers: New computation operators

### Configuration Changes

**Optional additions**:
```yaml
# In simulation config
cost_config:
  overdraft_capped: true  # New: Enforce credit limit (default: false)

throughput_guidance:  # New: Optional daily target curve
  - 0.0   # tick 0: 0% settled
  - 0.4   # tick 50: 40% settled
  - 0.6   # tick 70: 60% settled
  - 1.0   # tick 100: 100% settled
```

### Deprecations

**Soft deprecations** (warn but still work):
- `available_liquidity` → use `effective_liquidity` instead
- `ReleaseWithCredit` → use explicit logic (if Option B chosen)

---

## Rollout Plan

### Week 1: Foundation
- [ ] Phase 1.1: Clarify overdraft regime
- [ ] Phase 1.2: Add LSM-relevant fields
- [ ] Phase 1.3: Add public signal fields
- [ ] Phase 2.1: Throughput progress fields
- [ ] Phase 2.2: Counterparty fields
- [ ] Write unit tests for new context fields

### Week 2: Actions
- [ ] Phase 2.3: Math helper functions
- [ ] Phase 3.1: StaggerSplit action
- [ ] Phase 3.2: Release with RTGS flags
- [ ] Phase 3.3: Bank-level budget actions
- [ ] Write integration tests for new actions

### Week 3: Polish
- [ ] Phase 3.4: Collateral timers
- [ ] Phase 4.1: Resolve ReleaseWithCredit
- [ ] Phase 4.2: Decision explanation logging
- [ ] Phase 4.5: State registers
- [ ] Phase 5: Fix metrics & LSM logging
- [ ] Update documentation

### Week 4: Examples & Testing
- [ ] Write example policies
- [ ] Phase 4.3-4.4: Add pattern documentation
- [ ] Comprehensive scenario tests
- [ ] Replay identity verification
- [ ] User acceptance testing

---

## Success Criteria

### Functional Requirements
- [ ] All 60+ new fields calculate correctly
- [ ] StaggerSplit drips children over time as specified
- [ ] Bank-level budgets enforce correctly
- [ ] LSM-aware policies trigger more bilateral offsets
- [ ] Throughput-aware policies catch up when behind target
- [ ] ReleaseWithCredit semantics clear and working (if kept)
- [ ] Decision explanations appear in logs

### Performance Requirements
- [ ] No degradation in tick execution speed
- [ ] Context building <5% overhead from new fields
- [ ] Budget tracking adds <1ms per agent per tick

### Quality Requirements
- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] Replay identity maintained (run vs. replay output identical)
- [ ] No breaking changes to existing policies
- [ ] Documentation complete and accurate
- [ ] Example policies demonstrate all new features

### Behavioral Improvements
- [ ] Policies can feed LSM intentionally (measure bilateral offset rate)
- [ ] Policies can pace releases (measure Queue 2 pressure reduction)
- [ ] Policies can manage throughput (measure target adherence)
- [ ] Policies can exercise credit discipline (measure cap violations if enforced)
- [ ] Policies explain decisions (measure log clarity)

---

## Open Questions

### For Decision
1. **Overdraft regime**: Option A (priced unbounded) or Option B (enforced cap)?
2. **ReleaseWithCredit**: Keep with clear semantics or remove?
3. **Throughput guidance**: Required or optional in config?
4. **State registers**: Max limit (10? 20?) and scope (agent-level? system-level?)

### For Research
1. **Top counterparties**: 30-day window or configurable?
2. **LSM run rate**: 10-tick window or adaptive?
3. **Budget exhaustion**: Hard stop or soft warning?
4. **Stagger scheduling**: FIFO queue or priority queue?

---

## Dependencies

### Internal
- Replay identity architecture must be stable (currently is)
- Event system must support enriched data (currently does)
- Config system must support optional fields (currently does)

### External
- None (self-contained within simulator)

---

## Risk Assessment

### Low Risk
- **New context fields**: Isolated to context builder, well-tested
- **Math helpers**: Simple arithmetic, easy to validate
- **Documentation**: Low impact, high value

### Medium Risk
- **StaggerSplit**: Complex scheduling logic, needs careful testing
- **Bank-level budgets**: New execution flow, cross-transaction state
- **State registers**: Potential for misuse if not constrained

### High Risk
- **Overdraft regime change**: Could break existing scenarios if Option B chosen
- **ReleaseWithCredit semantics**: Implicit collateral posting could surprise users

### Mitigation
- Comprehensive unit tests for all new logic
- Integration tests covering realistic scenarios
- Extensive documentation with examples
- Replay identity verification for all changes
- Staged rollout (opt-in features first)

---

## Future Enhancements (Not in Scope)

### Policy System 3.0 (Potential)
- Multi-tick lookahead (predict inflows)
- Machine learning policy optimization
- Game-theoretic equilibrium finding
- Network topology awareness
- Dynamic coalition formation

### Advanced Features
- Conditional collateral (post only if condition met at future tick)
- Batch settlement optimization (LP solver for Queue 1)
- Counterparty credit limits (bilateral exposure caps)
- Time-varying cost rates (intraday pricing)

These are deliberately excluded to keep Version 2.0 focused and deliverable.

---

## Appendix: Example Policy Snippets

### A.1: LSM-Aware Bilateral Feeding

```json
{
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_CheckUrgency",
    "condition": {"op": "<=", "left": {"field": "ticks_to_deadline"}, "right": {"value": 5.0}},
    "on_true": {
      "type": "action",
      "node_id": "A1_ReleaseUrgent",
      "action": "Release"
    },
    "on_false": {
      "type": "condition",
      "node_id": "N2_CheckInboundMatch",
      "description": "Prefer counterparties with inbound Queue 2 items",
      "condition": {
        "op": ">",
        "left": {"field": "my_q2_in_value_from_counterparty"},
        "right": {"value": 0.0}
      },
      "on_true": {
        "type": "condition",
        "node_id": "N3_CheckNetPosition",
        "description": "Release if would reduce net outflow",
        "condition": {
          "op": ">",
          "left": {"field": "my_bilateral_net_q2"},
          "right": {"value": 0.0}
        },
        "on_true": {
          "type": "action",
          "node_id": "A2_ReleaseToFeedLSM",
          "action": "Release"
        },
        "on_false": {
          "type": "action",
          "node_id": "A3_HoldBalanced",
          "action": "Hold",
          "parameters": {"reason": {"value": "BalancedPosition"}}
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "A4_HoldNoMatch",
        "action": "Hold",
        "parameters": {"reason": {"value": "NoInboundMatch"}}
      }
    }
  }
}
```

### A.2: Throughput-Aware Budget Management

```json
{
  "bank_tree": {
    "type": "condition",
    "node_id": "B1_CheckProgress",
    "description": "Adjust budget based on throughput gap",
    "condition": {
      "op": ">",
      "left": {"field": "throughput_gap"},
      "right": {"value": -0.1}
    },
    "on_true": {
      "type": "action",
      "node_id": "B2_NormalBudget",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release_this_tick": {
          "compute": {
            "op": "*",
            "left": {"field": "effective_liquidity"},
            "right": {"value": 0.3}
          }
        }
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "B3_WidenGates",
      "action": "SetReleaseBudget",
      "parameters": {
        "max_value_to_release_this_tick": {
          "compute": {
            "op": "*",
            "left": {"field": "effective_liquidity"},
            "right": {"value": 0.6}
          }
        }
      }
    }
  }
}
```

### A.3: Staggered Split with Cool-down

```json
{
  "payment_tree": {
    "type": "condition",
    "node_id": "N1_CheckCooldown",
    "description": "Prevent rapid-fire splits",
    "condition": {
      "op": ">",
      "left": {
        "compute": {
          "op": "-",
          "left": {"field": "current_tick"},
          "right": {"field": "bank_state_last_split_tick"}
        }
      },
      "right": {"value": 5.0}
    },
    "on_true": {
      "type": "condition",
      "node_id": "N2_CheckSize",
      "condition": {
        "op": ">",
        "left": {"field": "remaining_amount"},
        "right": {"value": 200000.0}
      },
      "on_true": {
        "type": "action",
        "node_id": "A1_StaggerSplit",
        "action": "StaggerSplit",
        "parameters": {
          "num_splits": {
            "compute": {
              "op": "ceil",
              "value": {
                "compute": {
                  "op": "/",
                  "left": {"field": "remaining_amount"},
                  "right": {"value": 50000.0}
                }
              }
            }
          },
          "stagger_first_now": {"value": 2.0},
          "stagger_gap_ticks": {"value": 3.0}
        }
      },
      "on_false": {
        "type": "action",
        "node_id": "A2_ReleaseFull",
        "action": "Release"
      }
    },
    "on_false": {
      "type": "action",
      "node_id": "A3_HoldCooldown",
      "action": "Hold",
      "parameters": {"reason": {"value": "SplitCooldown"}}
    }
  }
}
```

---

*Last updated: 2025-11-12*
*Version: 2.0*
*Next review: After Phase 1 completion*
