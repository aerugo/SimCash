# Policy Evaluation Methodology

> Statistical justification and design tradeoffs for the policy evaluation system

**Version**: 1.1.0
**Last Updated**: 2025-12-16

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

### Justification: The Agent's Information Set

The sandbox design follows from a fundamental constraint: **agents cannot observe the internal state of other agents**.

#### What an Agent Observes

From any single agent's perspective, they can only observe:
1. **Their own policy** and decision state
2. **Outgoing transaction outcomes**: When their payments settle (or fail)
3. **Incoming settlement timing**: When liquidity arrives from counterparties

They **cannot observe**:
- Other agents' policies or decision rules
- Other agents' queue states or liquidity positions
- LSM cycle formation dynamics
- Market-wide liquidity conditions

#### Settlement Timing as a Sufficient Statistic

This information asymmetry leads to a key insight: **settlement timing is a sufficient statistic** for the liquidity environment.

When an agent sends a payment to counterparty B:
- If B has abundant liquidity → payment settles quickly
- If B is liquidity-constrained → payment queues, settles later (or via LSM)
- If system-wide gridlock occurs → settlement delays further

The **settlement time encapsulates** all of this complexity. The agent doesn't need to know *why* settlement took 5 ticks — only that it did. From their perspective, "the market" is an abstract entity characterized by settlement timing distributions.

#### Why the Sandbox Is the Correct Abstraction

Given that agents cannot simulate the full system (they lack the information), we abstract:
- **All counterparties** → SOURCE (incoming liquidity) and SINK (outgoing payments)
- **Liquidity environment** → Encoded in `settlement_offset` of historical transactions

When we resample from historical data, we preserve `settlement_offset` (the time between transaction arrival and settlement). This means **resampled scenarios present the agent with statistically equivalent liquidity conditions** to what they experienced historically.

```
Historical: Agent sends tx at tick 5, settles at tick 12 → settlement_offset = 7
Resampled:  Agent sends tx at tick 2, settles at tick 9 → settlement_offset = 7 (preserved)
```

The agent faces the same "market response" to their actions, even though the absolute timing differs.

#### Formal Argument

Let:
- π = agent's policy
- X = transaction characteristics (amount, priority, deadline)
- T = settlement timing (the sufficient statistic)
- C = agent's cost

The agent's optimization problem is:
```
minimize E[C | π, X, T]
```

Note that C depends on T (settlement timing), not on the underlying market state M that produces T. Since T is observable and M is not, T is a **sufficient statistic** for the agent's decision problem.

The sandbox correctly models this: SOURCE provides incoming liquidity at the historically-observed settlement times, preserving the sufficient statistic T.

### Confounding Elimination (Secondary Benefit)

Beyond the information-theoretic justification, the sandbox also eliminates confounders:

| Aspect | Sandbox | Full Simulation |
|--------|---------|-----------------|
| Confounding | Eliminated | Present |
| Bilateral interactions | Absent | Present |
| LSM cycles | Absent (bilateral only) | Full multilateral |
| Signal clarity | High | Low (noisy) |
| Ecological validity | Lower | Higher |
| Computation cost | Low | Higher |

### When the Sufficient Statistic Assumption Holds

The sandbox approach is valid when settlement timing T is **exogenous** to the agent's policy π:

```
P(T | π) ≈ P(T)  (agent's policy doesn't significantly affect market settlement times)
```

This holds when:
- **Agent is small**: Their transaction volume doesn't materially affect system liquidity
- **Policy decisions are local**: About releasing own transactions, not coordinating with counterparties
- **No strategic counterparty response**: Counterparties don't condition their behavior on this agent's actions
- **Diverse counterparty set**: Liquidity comes from many sources, not a single bilateral relationship

### When the Assumption Breaks Down

The sufficient statistic assumption **fails** when the agent's policy affects the liquidity environment they face:

1. **Large market share**: If the agent controls significant transaction volume, their release timing affects system-wide liquidity, which affects their own settlement times. The historical T was generated under the *old* policy — a new policy might produce different T.

2. **Bilateral concentration**: If most transactions are with a single counterparty (e.g., correspondent banking), releasing payments affects that counterparty's liquidity, which affects when they send payments back. This creates a **feedback loop** not captured by the sandbox.

3. **Strategic counterparties**: If counterparties explicitly condition on the agent's behavior (game-theoretic setting), the sufficient statistic breaks down entirely.

4. **LSM multilateral cycles**: The agent's release timing affects which N-agent cycles form, which affects settlement for all participants.

### Known Limitations (Implications)

Given the above, the sandbox has these specific limitations:

1. **No bilateral feedback loop**: When agent A releases payment to B, this gives B liquidity to release payments back to A. The sandbox doesn't model this circulation — SOURCE provides liquidity at fixed times regardless of when AGENT sends payments.

2. **Settlement timing is fixed**: The `settlement_offset` from historical data is preserved, but in reality a different policy might produce different settlement times. The sandbox evaluates "how would this policy perform in the *historical* liquidity environment" not "how would this policy perform in the *induced* liquidity environment."

3. **No multilateral LSM**: The sandbox supports bilateral offsets (SOURCE↔AGENT, AGENT↔SINK) but not N-agent cycle formation, which depends on the queue states of all participants.

### Validity for Castro-Style Experiments

For experiments like Castro et al. (2022) with:
- 2 symmetric agents
- Moderate transaction volumes
- Focus on timing optimization (not strategic coordination)

The sandbox is a reasonable approximation because:
- Each agent is ~50% of the system (not "small" but symmetric)
- Bilateral feedback exists but is also captured in historical settlement times
- The optimization goal is to improve timing given the observed liquidity pattern

For larger networks or asymmetric configurations, bilateral evaluation (see below) may be more appropriate.

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

## Deterministic Evaluation Modes

For scenarios with no random elements (fixed transaction arrivals), deterministic modes provide simpler, faster evaluation.

### Deterministic-Pairwise

The default deterministic mode compares old vs new policy on the **same seed within the same iteration**:

```
Iteration N:
  seed = derive_iteration_seed(N, agent_id)

  1. Run current policy with seed → cost_display (for LLM context)
  2. LLM generates new_policy
  3. Run old_policy with seed → old_cost
  4. Run new_policy with same seed → new_cost
  5. Accept if new_cost < old_cost
```

**Statistical Basis**: The pairing eliminates variance from seed differences. If `new_cost < old_cost` on the same seed, the new policy is unambiguously better for that scenario.

**Cost**: 3 simulations per iteration (context + old + new evaluation).

### Deterministic-Temporal

Uses **policy stability** for multi-agent convergence:

```
Iteration N:
  seed = derive_iteration_seed(N, agent_id)

  For each agent:
    1. Run current policy with seed → cost_N
    2. Track agent's initial_liquidity_fraction in stability tracker
    3. LLM generates new_policy
    4. Always accept new_policy (no cost-based rejection)

  After all agents optimized:
    5. Check multi-agent convergence:
       - If ALL agents' initial_liquidity_fraction unchanged for
         stability_window iterations → CONVERGED
       - Else continue to iteration N+1
```

**Convergence Criterion**: Policy stability, not cost. All agents must have the same `initial_liquidity_fraction` for `stability_window` (default 5) consecutive iterations.

**Cost**: 1 simulation per iteration (efficient).

**Why Policy Stability?**: In multi-agent scenarios, the cost landscape changes as counterparty policies evolve. A policy that was "optimal" for Agent A given Agent B's old policy may become suboptimal when Agent B changes. Cost-based rejection would cause oscillation. Policy stability indicates the LLM has converged on its best answer given the counterparty's current policy.

**Multi-Agent Equilibrium**: Convergence when ALL agents are stable approximates a Nash equilibrium - no agent wants to unilaterally change their strategy.

### When to Use Each Mode

| Mode | Best For | Simulations/Iteration | Convergence |
|------|----------|----------------------|-------------|
| `bootstrap` | Stochastic scenarios, statistical rigor | N samples × 2 | Cost improvement |
| `deterministic-pairwise` | Single-agent deterministic, precise comparison | 3 | Cost improvement |
| `deterministic-temporal` | Multi-agent deterministic, equilibrium finding | 1 | Policy stability |

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

*Last updated: 2025-12-16*
