# AI Policy Optimization

*LLM-driven optimization of full policy decision trees for autonomous bank cash management*

## Overview

SimCash uses large language models to iteratively optimize **complete policy trees** that govern how simulated banks manage payments, liquidity, and collateral. The optimization target is not a single parameter — it is a set of up to four JSON decision trees containing arbitrarily deep condition/action logic over 140+ context fields.

Each iteration follows a closed loop: **simulate → evaluate → propose → validate → accept/reject**. The LLM receives rich diagnostic context (cost breakdowns, simulation traces, iteration history) and proposes a structurally modified policy tree. The proposal is validated against scenario constraints, evaluated via paired bootstrap comparison against the current baseline, and accepted only if it demonstrates statistically meaningful improvement.

---

## Policy Trees: The Optimization Target

A policy consists of up to **four independent decision trees**, each evaluated at a different point in the tick lifecycle:

| Tree | Timing | Frequency | Purpose |
|------|--------|-----------|---------|
| `bank_tree` | Step 1.75 | Once per agent per tick | Bank-level budgeting and state management |
| `payment_tree` | Step 2 | Per transaction in Queue 1 | Payment release/hold/split decisions |
| `strategic_collateral_tree` | Step 1.5 | Once per agent per tick | Forward-looking collateral posting |
| `end_of_tick_collateral_tree` | Step 5.5 | Once per agent per tick | Reactive collateral withdrawal/cleanup |

### Actions

Each tree type supports specific actions:

**Payment tree** — `Release`, `ReleaseWithCredit`, `Split`/`PaceAndRelease`, `StaggerSplit`, `Hold`, `Drop`, `Reprioritize`, `WithdrawFromRtgs`, `ResubmitToRtgs`

**Bank tree** — `SetReleaseBudget`, `SetState`, `AddState`, `NoAction`

**Collateral trees** — `PostCollateral`, `WithdrawCollateral`, `HoldCollateral`

### Condition Nodes

Each non-leaf node in a tree is a **condition node** that branches on a boolean expression over context fields. The `payment_tree` has access to the full evaluation context (140+ fields) including transaction-specific fields (`amount`, `remaining_amount`, `ticks_to_deadline`, `priority`, `is_overdue`, etc.) plus all bank-level fields. The other three trees operate on bank-level context only (balances, queue state, collateral positions, time, cost rates, state registers).

Conditions can reference:
- **Fields** — runtime values from the simulation state (e.g. `effective_liquidity`, `queue1_total_value`, `day_progress_fraction`)
- **Parameters** — named constants defined in the policy's `parameters` block (e.g. `urgency_threshold`, `liquidity_buffer`)
- **Literals** — fixed numeric values
- **Computations** — arithmetic expressions over any of the above (`+`, `-`, `*`, `/`, `min`, `max`, `ceil`, `floor`, `abs`)

This means the LLM is not tuning a handful of scalars. It is constructing and restructuring decision trees — adding/removing branches, changing condition thresholds, swapping actions, introducing new parameters — across all four tree types simultaneously.

---

## The Optimization Loop

```
┌──────────────────────────────────────────────────────────────┐
│                     Iteration N                               │
│                                                               │
│  1. SIMULATE   Run context simulation with iteration seed     │
│                → Produces transaction history                  │
│                                                               │
│  2. EVALUATE   Bootstrap paired evaluation of current policy  │
│                → Baseline cost distribution                    │
│                                                               │
│  3. PROPOSE    LLM generates candidate policy from 50k+      │
│                token prompt (cost breakdowns, best/worst       │
│                seed traces, iteration history, trajectories)   │
│                                                               │
│  4. VALIDATE   Constraint validation (structural + domain)    │
│                → If invalid: retry with error feedback (≤3x)  │
│                                                               │
│  5. EVALUATE   Bootstrap paired evaluation of candidate       │
│                → On the SAME samples as baseline               │
│                                                               │
│  6. ACCEPT/    Paired comparison: accept iff candidate        │
│     REJECT     outperforms baseline on bootstrap deltas       │
│                                                               │
│  7. UPDATE     If accepted → candidate becomes new baseline   │
│                If rejected → baseline unchanged               │
└──────────────────────────────────────────────────────────────┘
```

### Information Isolation

Each agent sees **only its own** costs, events, and transaction history. No counterparty balances, policies, or internal state. The only signal about other agents comes from incoming payment timing — mirroring real RTGS systems where participants observe settlement messages but not others' positions.

Agents are not told the environment is stationary. Any regularity in the data-generating process must be inferred from observations.

---

## Bootstrap Paired Evaluation

This is the statistical core of the accept/reject decision. The goal is to determine whether a candidate policy is genuinely better than the baseline, controlling for the high variance inherent in payment system simulation (stochastic arrivals, counterparty behavior, LSM cycle formation, liquidity conditions).

### Why Paired Comparison

A naïve approach runs each policy on independent samples and compares means. This fails because sample-to-sample variance dominates, masking true policy differences.

The paired approach evaluates **both policies on the same bootstrap samples**. By pairing, the variance of the difference collapses:

```
Var(δ) = Var(cost_old) + Var(cost_new) − 2·Cov(cost_old, cost_new)
```

Since both policies face identical transaction sequences (same amounts, timing, deadlines), their costs are highly positively correlated. The covariance term eliminates most of the noise.

### The Procedure

For a given iteration:

1. **Run a context simulation** with the iteration's deterministic seed. This produces a transaction history reflecting that iteration's stochastic arrivals.

2. **Generate N bootstrap samples** by resampling with replacement from the transaction history. Each sample preserves `settlement_offset` (the observed time between arrival and settlement), which encodes the liquidity environment the agent historically faced.

3. **Evaluate the baseline policy** on all N samples. Each sample is run as an isolated 3-agent sandbox simulation (SOURCE → AGENT → SINK), producing `cost_baseline[i]` for i = 1..N.

4. **Evaluate the candidate policy** on the **same** N samples with the **same** seeds, producing `cost_candidate[i]` for i = 1..N.

5. **Compute paired deltas**:
   ```
   δ[i] = cost_baseline[i] − cost_candidate[i]    for i = 1..N
   ```
   A positive δ means the candidate is cheaper (better) on that sample.

6. **Accept if `mean(δ) > 0`** — the candidate policy has lower mean cost across the paired bootstrap samples.

### Statistical Properties

The paired delta `mean(δ)` is an unbiased estimator of the true expected cost difference. Its standard error is:

```
SE = std(δ) / √N
```

A 95% confidence interval for the true improvement is `mean(δ) ± 1.96 · SE`. The current acceptance criterion is `mean(δ) > 0` (no significance threshold). This favors exploration over conservatism — the LLM can accept marginal improvements, which compound across iterations.

Bootstrap naturally provides confidence intervals via the percentile method:
```
CI_lower = δ_(⌊0.025·N⌋)
CI_upper = δ_(⌊0.975·N⌋)
```

### Sample Size Guidance

| Use Case | Recommended N |
|----------|---------------|
| Rapid iteration | 10–20 |
| Production evaluation | 50–100 |
| High-confidence assessment | 200+ |

### Sandbox Architecture

Each bootstrap sample is evaluated in an isolated 3-agent sandbox:

```
SOURCE → AGENT → SINK
```

- **SOURCE**: Infinite liquidity, provides incoming settlements at historically-observed times
- **AGENT**: The bank under test, running the policy being evaluated
- **SINK**: Infinite capacity, absorbs outgoing payments

This abstraction is justified by the agent's information set: from any single agent's perspective, the liquidity environment is fully characterized by settlement timing, which is preserved in the bootstrap samples via `settlement_offset`. The agent cannot observe (and therefore cannot optimize for) other agents' internal state.

### Deterministic Evaluation Modes

For scenarios with fixed transaction arrivals (no stochastic generation), two simpler modes are available:

**Deterministic-pairwise**: Runs old and new policy on the same seed within a single iteration. Accepts if `new_cost < old_cost`. 3 simulations per iteration.

**Deterministic-temporal**: Always accepts the LLM's proposal. Convergence is defined by policy stability (all agents' policies unchanged for N consecutive iterations), approximating a Nash equilibrium. 1 simulation per iteration.

---

## Constraint Validation

Every LLM-generated policy is validated before evaluation. Validation has two layers:

### Structural Constraints

- Valid JSON tree structure (condition nodes have `condition`, `on_true`, `on_false`; action nodes have `action`)
- Unique `node_id` across all trees in the policy
- Tree depth ≤ 100
- Required action parameters present (e.g. `Split` requires `num_splits ≥ 2`)

### Domain Constraints (ScenarioConstraints)

Each experiment defines a `ScenarioConstraints` object specifying:

- **Allowed parameters**: Named parameters with type (`int`, `float`, `enum`) and range bounds. E.g. `urgency_threshold: int [0, 20]`, `liquidity_buffer: float [0.5, 3.0]`.
- **Allowed fields**: Context fields the LLM may reference in conditions. Restricts the search space to relevant signals.
- **Allowed actions per tree**: Which actions are valid in each tree type. E.g. a simple scenario might permit only `Release`/`Hold` in `payment_tree` and `NoAction` in `bank_tree`.

If validation fails, the errors are appended to the prompt and the LLM retries (up to 3 attempts). If all retries fail, the iteration keeps the current baseline policy.

### Constraint Presets

SimCash includes several constraint presets:

- **Minimal**: Only `Release`/`Hold`, 5 basic fields, single parameter
- **Castro**: Aligned with Castro et al. (2022) experiment design — constrained to `Release`/`Hold`/`PostCollateral`/`HoldCollateral`, ~15 fields
- **Standard**: Adds `Split`, `Borrow`/`Repay`, `WithdrawCollateral`, broader field set
- **Full**: All actions, all 140+ fields, maximum flexibility

---

## Convergence

Optimization terminates when either:

1. **Cost stability**: Mean cost changes by less than `stability_threshold` for `stability_window` consecutive iterations. Because evaluation is deterministic (same seed → same cost), this effectively means "no policy was accepted for N consecutive iterations."

2. **Max iterations**: Hard cap reached.

To distinguish true convergence (LLM cannot find improvements) from false positives (LLM generating invalid proposals), check the `was_accepted` field in iteration records. Consecutive rejections with stable costs indicate the LLM is hitting constraint boundaries rather than finding a local optimum.

---

## Cost Function

All costs are computed in **integer cents** to avoid floating-point drift. The total cost aggregated across bootstrap samples includes:

| Component | Description |
|-----------|-------------|
| Delay cost | `rate_per_tick × ticks_waiting` for queued transactions |
| Deadline penalty | Fixed penalty when a transaction becomes overdue |
| Overdue multiplier | `delay_rate × 5.0` for each tick past deadline |
| Overdraft cost | `basis_points × negative_balance × ticks` |
| Collateral cost | `rate × posted_collateral × ticks` (opportunity cost) |
| EOD penalty | Large fixed penalty for unsettled transactions at day end |

The LLM receives a full breakdown of these components to guide its optimization strategy — e.g., high deadline penalties suggest more aggressive release timing, while high collateral costs suggest more conservative posting.

---

## The LLM Prompt

The `PolicyOptimizer` builds a **50,000+ token prompt** containing:

- Current policy JSON and performance metrics
- Cost breakdown by component
- Verbose simulation output from the best-performing and worst-performing seeds (showing tick-by-tick decisions)
- Full iteration history with acceptance status and cost trajectories
- Parameter value trajectories across iterations
- Scenario constraints (allowed fields, actions, parameter ranges)
- Policy JSON schema

The LLM outputs a complete replacement policy JSON. It can restructure trees (add/remove branches, change nesting), adjust thresholds, introduce new parameters within allowed ranges, or swap actions — any modification that passes constraint validation.
