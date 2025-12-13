# Bootstrap Policy Evaluation Methodology

> Statistical justification and design tradeoffs for the policy evaluation system

**Version**: 1.0.0
**Last Updated**: 2025-12-13

---

## Overview

This document explains **why** we evaluate policies the way we do. It covers the statistical foundations, design decisions, alternatives considered, and known limitations.

---

## The Core Problem

**Goal**: Determine whether a candidate policy is better than the current policy.

**Challenge**: Payment system costs are highly variable due to:
- Stochastic transaction arrivals
- Counterparty behavior
- LSM cycle formation
- Initial liquidity conditions

A single simulation comparison is unreliable. We need statistical techniques to make robust comparisons.

---

## Solution: Paired Comparison Bootstrap

We use **paired comparison** on **bootstrap samples**:

1. Generate N bootstrap samples from historical transaction data
2. Run **both** policies on the **same** N samples
3. Compute delta = cost(policy_A) - cost(policy_B) for each sample
4. Accept new policy if mean(delta) > 0

### Why Paired Comparison?

Standard approach (unpaired):
```
policy_A_costs = [simulate(policy_A, sample_i) for i in range(N)]
policy_B_costs = [simulate(policy_B, sample_i) for i in range(N)]
difference = mean(policy_A_costs) - mean(policy_B_costs)
```

Problem: High variance from different samples masks true policy differences.

**Paired approach**:
```
deltas = [
    simulate(policy_A, sample_i) - simulate(policy_B, sample_i)
    for i in range(N)
]
difference = mean(deltas)
```

By evaluating both policies on the **same** sample, we eliminate sample-to-sample variance. The variance of the paired difference is typically much lower than the variance of the unpaired difference.

### Statistical Foundation

For paired comparisons, the variance of the mean difference is:

```
Var(mean(delta)) = Var(delta) / N
```

Where `Var(delta) = Var(A) + Var(B) - 2*Cov(A,B)`

When A and B are positively correlated (same sample → similar challenges), the covariance term **reduces** variance significantly. This is why paired comparison is more powerful than unpaired.

---

## The 3-Agent Sandbox Architecture

### Design

For policy evaluation, we use an **isolated 3-agent sandbox**:

```
SOURCE → AGENT → SINK
  ↓                 ↑
  └─────liquidity───┘
```

- **SOURCE**: Infinite liquidity, sends "incoming settlements" to AGENT
- **AGENT**: Target agent with test policy
- **SINK**: Infinite capacity, receives AGENT's outgoing transactions

### Justification

**Why isolate?** In the full simulation, an agent's cost depends on:
1. Their own policy (what we want to measure)
2. Other agents' policies (confounding)
3. LSM cycles with other agents (confounding)
4. Market-wide liquidity conditions (confounding)

The sandbox removes confounders (2-4), giving us a **clean signal** of policy effect.

**Analogy**: A/B testing in web applications. You don't test a new recommendation algorithm by also changing the UI, pricing, and user demographics simultaneously. You isolate the variable you're testing.

### Tradeoffs

| Aspect | Sandbox | Full Simulation |
|--------|---------|-----------------|
| Confounding | Eliminated | Present |
| Bilateral interactions | Absent | Present |
| LSM cycles | Absent (bilateral only) | Full multilateral |
| Signal clarity | High | Low (noisy) |
| Ecological validity | Lower | Higher |
| Computation cost | Low | Higher |

### When Sandbox Is Appropriate

The sandbox approach is valid when:
- Policy decisions are **local** (about releasing own transactions)
- Agent doesn't need to coordinate with specific counterparties
- Main costs are delay, deadline penalties, overdraft
- LSM multilateral cycles are not the primary cost driver

### Known Limitations

1. **No counterparty feedback**: In reality, releasing a payment may trigger counterparty to release queued payments back, creating bilateral liquidity circulation. The sandbox doesn't model this.

2. **No LSM multilateral cycles**: Sandbox only supports 2-agent bilateral offsets (SOURCE↔AGENT or AGENT↔SINK), not N-agent cycles.

3. **Abundant liquidity assumption**: SOURCE has infinite liquidity, so "incoming settlement timing" doesn't create real liquidity pressure.

---

## Alternative: Bilateral Evaluation (Future)

For scenarios where bilateral feedback matters, we've designed (but not yet implemented) **bilateral evaluation**:

```
BANK_A ←→ BANK_B
(Full simulation with fixed transactions)
```

### Approach

1. Bootstrap resample transactions for **all** agents together
2. Run full simulation with scenario_events (deterministic arrivals)
3. Measure target agent's cost
4. Still use paired comparison

### When to Use

- High bilateral settlement volume between specific pairs
- LSM multilateral cycles are significant
- Testing strategies that depend on counterparty behavior

See `docs/plans/bootstrap/bilateral_evaluation.md` for implementation plan.

---

## Bootstrap vs Monte Carlo

### Monte Carlo (Parametric)

Generate new transactions from the arrival distribution:
```python
for sample in range(N):
    orch = Orchestrator.new(config_with_arrivals)
    orch.run()  # Generates new random transactions
    cost = orch.get_cost()
```

**Problem**: Each sample has different transactions, so we can't do paired comparison. High variance masks policy effects.

### Bootstrap (Non-parametric)

Resample from observed transactions:
```python
# One simulation to collect history
orch = Orchestrator.new(config_with_arrivals)
orch.run()
history = collect_transactions(orch.events)

# Resample from history
for sample in range(N):
    transactions = resample_with_replacement(history)
    # Same transactions used for both policy_A and policy_B
```

**Advantage**: Same transactions → paired comparison → lower variance → faster convergence.

### Comparison

| Aspect | Monte Carlo | Bootstrap |
|--------|-------------|-----------|
| Transaction variance | High (new each time) | Controlled (resampled) |
| Paired comparison | Not possible | Enabled |
| Statistical efficiency | Lower | Higher |
| Computation | N simulations with arrivals | 1 sim + N deterministic evals |
| Captures distribution | Parametric (arrival config) | Empirical (observed history) |

---

## Cost Calculation

### Integer Cents (INV-1)

All costs are computed in integer cents to avoid floating-point errors:

```python
total_cost: int = delay_cost + deadline_penalty + overdraft_cost + collateral_cost
```

### Cost Components

| Component | Formula | Description |
|-----------|---------|-------------|
| Delay cost | `rate_per_tick × ticks_waiting` | Time in queue |
| Deadline penalty | Fixed amount when tx becomes overdue | Missed deadline |
| Overdue multiplier | `delay_rate × 5.0` for overdue ticks | Penalty for late |
| Overdraft cost | `basis_points × negative_balance × ticks` | Daylight overdraft |
| Collateral cost | `rate × posted_collateral × ticks` | Opportunity cost |
| EOD penalty | Large fixed amount | Unsettled at day end |

---

## Implementation Details

### Code Locations

| Component | File |
|-----------|------|
| Bootstrap sampler | `ai_cash_mgmt/bootstrap/sampler.py` |
| Sandbox config builder | `ai_cash_mgmt/bootstrap/sandbox_config.py` |
| Policy evaluator | `ai_cash_mgmt/bootstrap/evaluator.py` |
| Paired delta computation | `evaluator.py:compute_paired_deltas()` |
| Optimization loop | `experiments/runner/optimization.py` |

### Determinism (INV-2)

All evaluation is deterministic given a seed:
- Bootstrap sampling uses seeded xorshift64*
- Sandbox simulations use derived seeds
- Same seed → identical bootstrap samples → identical costs

---

## Validation Strategy

### Replay Identity

The sandbox uses the same Rust engine as full simulations:
- Same RTGS settlement logic
- Same cost calculation
- Same event emission

This ensures evaluation costs are comparable to production costs.

### Test Coverage

Key tests:
- `test_bootstrap_paired_comparison.py` - Paired delta computation
- `test_scheduled_settlement_event.py` - Sandbox settlement correctness
- `test_replay_identity_gold_standard.py` - Event fidelity

---

## Statistical Recommendations

### Sample Size

| Use Case | Recommended N |
|----------|---------------|
| Quick iteration | 10-20 samples |
| Production evaluation | 50-100 samples |
| Research/publication | 200+ samples |

### Acceptance Criterion

Current: Accept if `mean(delta) > 0`

Future consideration: Add significance test (e.g., paired t-test p < 0.05) to guard against accepting noise.

### Confidence Intervals

Bootstrap naturally provides confidence intervals:
```python
sample_deltas = sorted(deltas)
ci_lower = sample_deltas[int(0.025 * N)]
ci_upper = sample_deltas[int(0.975 * N)]
```

---

## References

- Efron, B. (1979). "Bootstrap Methods: Another Look at the Jackknife"
- Castro et al. (2022). "Estimating the Cost of Strategic Delay in Payment Systems"
- `docs/plans/bootstrap/development-plan.md` - Implementation plan
- `docs/plans/bootstrap/bilateral_evaluation.md` - Bilateral approach

---

## Navigation

**Previous**: [Sampling](sampling.md)
**Next**: [Constraints](constraints.md)

---

*Last updated: 2025-12-13*
