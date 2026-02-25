# Phased Implementation Plan: Improving Agent Settlement Optimization

**Author:** Nash  
**Date:** 2026-02-25  
**Status:** Implementation plan  
**Depends on:** `docs/reports/prompt-improvement-recommendations.md`  
**Context:** Concrete plan for making LLM agents more likely to optimize for settlement, not just minimize individual cost.

---

## Problem Statement

LLM agents in SimCash optimize for **individual cost minimization** as defined by the objective function. Settlement rate is reported as a metric but has no direct weight in the optimization objective or the bootstrap acceptance gate. The rational individual response to falling settlement is often to post *less* liquidity — since you're paying for liquidity you're not using effectively — which creates a free-rider dynamic.

Meanwhile, the prompts tell the LLM "settlement rate should be 100%" but the actual acceptance mechanism only checks whether `mean_cost` decreased. A policy that drops settlement from 100% to 80% but lowers cost will be accepted. The LLM learns that settlement is aspirational, not binding.

The RTGS settlement balance is the mechanism that determines whether payments clear. The agent commits a fraction of its liquidity pool to the RTGS settlement account at day start. Payments settle if and only if this balance (plus available credit headroom) covers the payment amount. The balance evolves intraday as outflows deplete it and inflows (delayed one tick by deferred crediting) replenish it.

**Goal:** Make agents more likely to discover and maintain strategies that achieve high settlement, without changing the fundamental game-theoretic structure.

---

## Phased Approach

### Phase 1: Give the Agent Eyes (Information Fixes)
*Effort: Low | Risk: None | No engine changes*

These fix genuine information deficits — the LLM literally cannot see the data it needs to reason about settlement. This is not hand-holding; it's giving the agent access to the state it operates on.

#### 1a. RTGS Balance Context Section

Add a new section to the user prompt showing:

```
### RTGS Settlement Account Context
- Liquidity pool (maximum committable): $1,000,000
- Committed to RTGS account: $450,000 (initial_liquidity_fraction: 0.45)
- Expected daily payment demand: ~$240,000
- Demand / committed ratio: 53%
- Settlement feasibility: available_liquidity / largest_queued = 2.3× (healthy)
```

**Why this matters for settlement:** The agent needs to know whether its RTGS balance is sized appropriately for the payment volume. Without this, it tunes `initial_liquidity_fraction` by gradient on cost alone and may settle on a fraction that's individually cheap but causes payments to queue.

**Implementation:**
- Compute expected daily demand from scenario config: `rate_per_tick × mean_amount × ticks_per_day`
- Pool size from `agent.liquidity_pool` or `agent.max_collateral_capacity`
- Committed amount = `initial_liquidity_fraction × pool`
- Add to `SingleAgentContext` dataclass and `_build_current_state_summary()`

**Files:**
- `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` — add `liquidity_pool`, `expected_daily_demand` fields
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` — new `_build_liquidity_context()` section
- Callers: `streaming_optimizer.py`, `optimization.py` — pass pool/demand data

#### 1b. RTGS Balance Trajectory

Add per-tick balance summary to simulation trace:

```
### RTGS Balance Trajectory (Seed #42)
Tick | Balance    | Avail Liq  | Feasibility | Out      | In       | Queued
-----|------------|------------|-------------|----------|----------|-------
  0  | $450,000   | $650,000   | 4.2×        | $0       | $0       | 0
  5  | $120,000   | $320,000   | 1.1×        | $98,000  | $40,000  | 1
  7  | $98,000    | $298,000   | 0.8×        | $22,000  | $35,000  | 4  ⚠️
```

The **Feasibility** column (`available_liquidity / largest_queued_payment`) is the crunch indicator. When it drops below 1.0, the agent physically cannot settle its next payment. This is the moment the RTGS balance becomes the binding constraint on settlement.

**Implementation:**
- Post-process simulation events to extract per-tick: balance, available_liquidity, net outflows, net inflows, queue count
- Compute largest queued payment amount per tick for feasibility ratio
- New function `extract_balance_trajectory()` in `event_filter.py`
- Inject into simulation trace section of user prompt

**Files:**
- `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py` — new `extract_balance_trajectory()`
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` — insert before simulation trace

#### 1c. Deferred Crediting Emphasis

Add to domain explanation in system prompt:

```
### ⚠️ DEFERRED CREDITING (Critical for RTGS Balance Management)

Incoming payments that settle at tick T do NOT increase your RTGS settlement
account balance until tick T+1.

Your RTGS balance at any tick = opening balance - cumulative outflows + inflows
from PREVIOUS ticks only. You cannot rely on same-tick inflows to fund releases.

In tight liquidity, this one-tick lag is the primary cause of payment queuing.
A payment released at tick 5 drains your balance immediately, but the incoming
payment you expect at tick 5 won't replenish it until tick 6.
```

**Implementation:**
- Modify `_build_domain_explanation_base()` in `system_prompt_builder.py`
- Conditional on `deferred_crediting` being True in scenario config (already available as a flag)

---

### Phase 2: Align the Objective (Settlement-Aware Acceptance)
*Effort: Medium | Risk: Low | Changes acceptance logic only, not the cost function*

This is the critical structural change. Currently the bootstrap gate accepts any policy with lower mean cost, regardless of settlement rate. This means a policy that tanks settlement but saves money gets accepted — and the LLM learns that settlement doesn't matter.

#### 2a. Settlement Floor in Bootstrap Gate

Add a settlement rate constraint to the bootstrap acceptance logic:

```python
# In bootstrap_gate.py evaluate():
settlement_rate = result.get("settlement_rate", 1.0)
min_settlement = thresholds.get("min_settlement_rate", 0.95)

if settlement_rate < min_settlement:
    accepted = False
    rejection_reason = (
        f"Settlement rate {settlement_rate:.1%} below minimum {min_settlement:.0%}. "
        f"A policy that reduces cost by failing to settle payments is not acceptable."
    )
```

**Why a floor, not a weight:** Adding settlement as a cost-function term changes the game's economics (now the agent is optimizing a synthetic objective, not real costs). A floor preserves the cost-minimization objective while constraining the feasible set: "minimize your costs *subject to* settling at least 95% of payments."

This is also more realistic. In real RTGS systems, regulators set minimum throughput requirements. Banks don't get to choose a 50% settlement rate because it's cheaper.

**Configuration:** The floor should be configurable per scenario:
```yaml
bootstrap_thresholds:
  min_settlement_rate: 0.95  # Default: 95%
```

**Files:**
- `web/backend/app/bootstrap_gate.py` — add settlement check after cost comparison
- `api/payment_simulator/experiments/runner/optimization.py` — add settlement check to `_is_variance_acceptable()` or acceptance flow
- `api/payment_simulator/ai_cash_mgmt/optimization/policy_evaluator.py` — `is_better_than()` could incorporate settlement

#### 2b. Communicate the Constraint to the LLM

The LLM needs to know the settlement floor exists and is enforced. Add to system prompt:

```
### Settlement Constraint
Your policy MUST maintain a settlement rate above the scenario minimum (typically 95%).
Policies that reduce cost by failing to settle payments will be REJECTED by the
evaluation gate, regardless of cost improvement. 

This reflects real-world regulatory requirements: banks in RTGS systems must meet
minimum throughput targets. The cost optimization must occur WITHIN this constraint.
```

And in the user prompt guidance, when settlement is below the floor:

```
🚨 **SETTLEMENT BELOW MINIMUM** — Current: 82%, Required: 95%
Your next policy proposal WILL BE REJECTED unless settlement improves.
The most direct fix: increase initial_liquidity_fraction to ensure your RTGS
balance can cover more payments. Then optimize costs within that constraint.
```

**Files:**
- `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` — add to cost objectives section
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` — add to `_build_optimization_guidance()`

---

### Phase 3: Guide the Search (Prompt Improvements)
*Effort: Low-Medium | Risk: Low*

With Phase 1 providing information and Phase 2 enforcing the constraint, Phase 3 helps the LLM navigate the tighter optimization space.

#### 3a. Crunch Tradeoff Detection

When both delay costs and liquidity opportunity costs are significant, detect the tension and explain:

```python
if delay_pct > 20 and liquidity_opp_pct > 20:
    guidance.append(
        "⚡ **RTGS BALANCE TRADEOFF**\n"
        "You're paying for both idle liquidity AND payment delays. "
        "This means your initial_liquidity_fraction is in the critical zone — "
        "small changes cause large cost swings.\n\n"
        "The root cause: your RTGS settlement account balance runs low mid-day, "
        "causing payments to queue, but your committed amount includes capital "
        "that sits idle early/late in the day.\n\n"
        "Approaches:\n"
        "- Condition payment releases on current RTGS balance (balance field)\n"
        "- Pace outflows: don't release everything at once when balance is high\n"
        "- Accept slightly higher liquidity cost to avoid deadline penalties"
    )
```

**Files:**
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` — `_build_optimization_guidance()`

#### 3b. Worst-Case Seed Summary

Show critical failure moments from the worst bootstrap seed:

```
### Worst-Case Analysis (Seed #99, Cost: $180,000)
- Tick 5: RTGS balance dropped to $12,000 (feasibility: 0.08×)
  → 4 payments queued, 2 approaching deadline
- Tick 8: 2 deadline penalties ($100,000 total)
- Tick 11: 1 payment unsettled at EOD ($100,000 penalty)
- Root cause: 3-tick drought with no incoming payments
```

**Implementation:** Extract from worst-seed simulation: minimum balance tick, deadline breaches, EOD penalties. Format as narrative.

**Files:**
- `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` — new `_build_worst_case_section()`
- `api/payment_simulator/ai_cash_mgmt/prompts/context_types.py` — add `worst_seed_summary` to context

---

### Phase 4: Enable Structural Discovery (Experimental)
*Effort: Low | Risk: Must be configurable — this is an experimental variable*

#### 4a. Tree Composition Capabilities (Configurable Prompt Block)

Describe bank tree → payment tree interaction as capabilities (not strategies):

```
### Tree Interaction Capabilities

- The bank tree's SetReleaseBudget action sets a per-tick spending limit.
  The payment tree reads release_budget_remaining to check remaining budget.
- The bank tree's SetStateRegister stores values in bank_state_* fields
  that the payment tree can read.
- The bank tree evaluates ONCE per tick (before transactions). The payment
  tree evaluates for EACH pending transaction.
```

**This block must be toggleable** via experiment config. It's an experimental variable for the paper.

**Files:**
- `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` — new optional block in `_build_policy_architecture()`
- Experiment config: `prompt_blocks.tree_composition: true/false`

#### 4b. target_tick as Diagnostic

After implementing deferred crediting emphasis (1c), monitor whether any model discovers `target_tick` scheduling — delaying release to a future tick when inflows are expected. This requires no code change, just observation. If no model uses `target_tick` even with deferred crediting explained, that's evidence of the understanding→action gap.

---

## Phase Summary

| Phase | What | Effort | Changes | Settlement Impact |
|-------|------|--------|---------|-------------------|
| **1** | Information fixes (balance context, trajectory, deferred crediting) | Low | Prompt only | Indirect: agent can reason about RTGS balance |
| **2** | Settlement floor in acceptance gate + communicate constraint | Medium | Acceptance logic + prompt | Direct: policies that tank settlement are rejected |
| **3** | Search guidance (tradeoff detection, worst-case analysis) | Low-Med | Prompt only | Indirect: agent understands cost-settlement tradeoff |
| **4** | Tree composition (experimental, configurable) | Low | Prompt block | Enables structural strategies for maintaining settlement |

**Recommended order:** Phase 1 → Phase 2 → Phase 3 → Phase 4

Phase 1 and 2 can be parallelized. Phase 2 is the highest-impact single change — without the settlement floor, the objective function actively rewards abandoning settlement. Phases 1 and 3 make the agent smarter; Phase 2 makes the game fair.

---

## What We're NOT Changing

1. **The cost function itself.** We don't add settlement as a cost term. The cost function represents real economic costs. Settlement is a constraint, not a cost.

2. **The engine.** No Rust changes. Everything is prompt engineering and Python-level acceptance logic.

3. **The game-theoretic structure.** Agents still optimize individually, still can't see each other's policies, still face the coordination problem. The settlement floor is a *regulatory* constraint, not a cooperative mechanism — it mirrors real RTGS throughput requirements.

4. **The default prompts for existing experiments.** All changes are additive (new prompt sections) or configurable (Phase 4). Existing experiment configs continue to work unchanged unless explicitly updated.

---

## Success Criteria

| Metric | Current | Target (Phase 1-2) | Target (Phase 1-3) |
|--------|---------|---------------------|---------------------|
| Settlement rate in crunch scenarios | Often < 90% | ≥ 95% (enforced) | ≥ 95% with lower cost |
| LLM references RTGS balance in reasoning | Rarely | Frequently | Frequently |
| Bank tree usage | Almost never | No change expected | Possible with Phase 4 |
| Policy rejection for low settlement | Never (not checked) | Active | Active |
| Convergence speed (iterations to stable policy) | ~5-8 | May increase slightly | ~5-8 |

---

## Risk Assessment

**Phase 1 risk: None.** Adding information to prompts can only help. If the LLM ignores it, no harm done.

**Phase 2 risk: Low, but monitor.** The settlement floor creates a constrained optimization space. If the floor is set too high (e.g., 100%), the LLM may struggle to find any policy that's both cost-improving and fully settling — especially in genuinely hard scenarios where 100% settlement requires over-committing liquidity. Start with 95% and make it configurable.

**Phase 2 interaction with free-rider dynamics:** The floor prevents the most extreme free-riding (posting near-zero liquidity). But agents can still settle at 95% while posting minimal liquidity if the *other* agent provides enough incoming payments. The floor doesn't solve coordination — it prevents collapse.

**Phase 3 risk: None.** Better diagnostics in prompts.

**Phase 4 risk: Over-prompting.** If we tell the LLM about `SetReleaseBudget` and it uses `SetReleaseBudget`, we've shown it can follow instructions, not that it can discover strategies. This is why Phase 4 must be configurable and compared against a baseline without it.
