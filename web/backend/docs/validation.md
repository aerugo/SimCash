# Validation & Verification

*How we verify that SimCash produces trustworthy results*

A simulator is only useful if you can trust its output. This section documents the
validation methodology we use to ensure SimCash produces accurate, reproducible, and
internally consistent results.

## Replication Results

SimCash replicates the stochastic Experiment 2 from Castro et al. (2025), Table 3. The
table below compares the paper's reported equilibrium liquidity fractions with SimCash's
converged values:

| Agent | Castro et al. (2025) | SimCash | Status |
|-------|---------------------|---------|--------|
| Agent A | 8.5% | ≈ 8.8% | Within 1 SE ✓ |
| Agent B | 6.3% | ≈ 5.2% | Within 1 SE ✓ |

Across 3 independent passes, Agent A converges to 5.7–8.8% and Agent B to 5.2–6.3%.
The variation across passes reflects path-dependence in multi-agent optimization — different
random seeds lead to slightly different equilibria, all within the expected range.

## Determinism Verification

> ℹ️ **Same seed = same output, always.** The Rust simulation engine is fully
> deterministic. All randomness flows through a seeded xorshift64* RNG, and all monetary
> values are 64-bit integers (cents) — never floating point. Running a simulation and
> replaying from checkpoint produce byte-identical output (replay identity). This has been
> verified across platforms and compiler versions.

Determinism is foundational to reproducibility. Any result reported by SimCash can be
independently verified by re-running the same configuration with the same seed. There
are no hidden sources of non-determinism (no floating-point rounding, no hashmap ordering,
no system-clock dependencies).

## Cost Consistency (INV-4)

SimCash enforces a strict accounting invariant on every simulation tick:

```
sum(per_agent_costs) == total_cost    // always holds (INV-4)
```

The sum of all individual agent costs must exactly equal the reported total system cost.
This invariant is checked at the engine level — a violation would indicate a bug in cost
accounting. Since all arithmetic uses 64-bit integers, there are no floating-point
accumulation errors. This invariant has held across every simulation run in testing and
production.

## Engine Independence

> ⚠️ **No LLM involvement during simulation ticks.** The Rust engine executes
> policies exactly as specified — evaluating decision trees, processing payments, accruing
> costs — with zero LLM calls. The LLM is only involved *between* days, when agents
> analyze results and propose policy updates. During simulation, the engine is a pure
> deterministic function: configuration in, results out.

This separation is critical for trust. The simulation results depend only on the policy
trees and scenario configuration, not on any non-deterministic LLM behavior. You can
inspect, replay, and verify any simulation result without access to the LLM.

## Evaluation Methodology

For stochastic scenarios, policy comparison uses a 100-sample bootstrap evaluation with
95% confidence intervals and paired comparison (both old and new policies run on identical
resampled transaction sets). This methodology ensures that:

- **Noise is cancelled:** Paired comparison eliminates sample-to-sample variance — only the policy difference matters
- **Type I errors are controlled:** The 95% CI requirement prevents accepting "improvements" that are just lucky draws
- **Effect size is measurable:** The coefficient of variation (CV) threshold ensures results are consistent, not driven by outliers

Together, these properties mean that when SimCash reports a policy improvement, you can
be confident it reflects a genuine change in expected cost — not statistical noise.
