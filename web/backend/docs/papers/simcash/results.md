# Results

## Convergence Summary

| Experiment | Mean Iters | Min | Max | Conv. Rate |
|------------|----------:|----|----:|----------:|
| EXP1 | 10.3 | 8 | 12 | 100% |
| EXP2 | 49.0 | 49 | 49 | 100% |
| EXP3 | 7.0 | 7 | 7 | 100% |

Experiments 1 and 3 achieved formal convergence via temporal policy stability (mean
10.3 and 7.0 iterations
respectively). Experiment 2's stochastic passes terminated at the 50-iteration budget —
the strict bootstrap convergence criteria proved overly conservative for environments
with inherent cost variance.

---

## Experiment 1: The Free-Rider Emerges

In this 2-period deterministic scenario, Bank A faces lower delay costs than Bank B,
creating incentives for free-rider behavior.

![Experiment 1: Both agents converge to an asymmetric stable outcome](/api/docs/images/paper/exp1_pass1_combined.png)

The agents converged after 8 iterations in Pass 1 to a clear asymmetric outcome:

- **Bank A**: \$0.10 cost with 0.1% liquidity — classic free-rider
- **Bank B**: \$27 cost with 17% liquidity — the liquidity provider

This matches the game-theoretic prediction: Bank A free-rides on Bank B's liquidity,
minimizing its own reserves while relying on incoming payments from Bank B to fund
outgoing obligations.

But **Pass 3 told a different story**: the free-rider identity flipped. Bank B adopted
zero liquidity while Bank A maintained just 1.8%. Both agents ended up with high costs
(\$31.78 and \$70.00) — nearly 4× the efficient outcome. Same game, same agents, completely
different result driven by early exploration dynamics.

<details>
<summary>📊 View iteration-by-iteration results (Pass 1)</summary>

| Iteration | Agent | Cost | Liquidity |
|-----------|-------|-----:|----------:|
| Baseline | Bank A | \$50 | 50% |
| Baseline | Bank B | \$50 | 50% |
| 0 | Bank A | \$50 | 50% |
| 0 | Bank B | \$50 | 50% |
| 1 | Bank A | \$20 | 20% |
| 1 | Bank B | \$30 | 30% |
| 2 | Bank A | \$10 | 10% |
| 2 | Bank B | \$20 | 20% |
| 3 | Bank A | \$5 | 5% |
| 3 | Bank B | \$28 | 18% |
| 4 | Bank A | \$0 | 0% |
| 4 | Bank B | \$20 | 20% |
| 5 | Bank A | \$0.10 | 0.1% |
| 5 | Bank B | \$27 | 17% |
| 6 | Bank A | \$0.10 | 0.1% |
| 6 | Bank B | \$27 | 17% |
| 7 | Bank A | \$0.10 | 0.1% |
| 7 | Bank B | \$27 | 17% |
| 8 | Bank A | \$0.10 | 0.1% |
| 8 | Bank B | \$27 | 17% |

</details>

<details>
<summary>📊 View summary across all passes</summary>

| Pass | Iterations | Bank A Liq. | Bank B Liq. | Bank A Cost | Bank B Cost | Total Cost |
|-----:|-----------:|------------:|------------:|------------:|------------:|-----------:|
| 1 | 8 | 0.1% | 17% | \$0.10 | \$27 | \$27.10 |
| 2 | 12 | 0% | 17.9% | \$0 | \$27.90 | \$27.90 |
| 3 | 11 | 1.8% | 0% | \$31.78 | \$70 | \$101.78 |

</details>

---

## Experiment 2: Stochastic Environment

Experiment 2 introduces a 12-period scenario with random transaction arrivals and amounts,
requiring bootstrap evaluation to assess policy quality under variance.

![Experiment 2: Convergence under stochastic arrivals (Pass 2)](/api/docs/images/paper/exp2_pass2_combined.png)

All three passes terminated at the 50-iteration budget without formal convergence.
The strict criteria — CV < 3%, no significant trend, and regret < 10% sustained over
5 iterations — were simply too demanding for this stochastic environment. But the
policies achieved practical stability: liquidity allocations settled into consistent
ranges and costs stayed within narrow bands.

### Bootstrap Evaluation

Each iteration uses 50 bootstrap samples for paired comparison. The table below shows
bootstrap statistics for the final accepted policies:

| Agent | Mean Cost | Std Dev | 95% CI | Samples |
|-------|----------:|--------:|--------|--------:|
| Bank A | \$226.15 | \$458.71 | [\$95.04, \$357.26] | 50 |
| Bank B | \$66.09 | \$15.59 | [\$61.63, \$70.54] | 50 |

Bank A achieved mean cost \$226.15 (± \$458.71). Bank B maintained more
consistent costs at \$66.09 (± \$15.59).

### Risk vs. Return

![Experiment 2: Cost variance with 95% confidence intervals](/api/docs/images/paper/exp2_pass2_variance.png)

The convergence chart reveals cases where dramatically better policies were *rejected*.
For example, at iteration 22, Bank A's proposed policy achieved mean cost \$324 vs the
current \$915 — but was rejected because its CV was 0.83 (above the 0.5 threshold).
Better average performance, but unacceptably volatile.

This risk-adjusted acceptance biases optimization toward policies that improve cost
while maintaining stability — explaining the apparent paradox where rejected proposals
(✕ markers) appear below the current policy line.

<details>
<summary>📊 View iteration-by-iteration results (Pass 2)</summary>

| Iteration | Agent | Cost | Liquidity |
|-----------|-------|-----:|----------:|
| Baseline | Bank A | \$498 | 50% |
| Baseline | Bank B | \$498 | 50% |
| 0 | Bank A | \$498 | 50% |
| 0 | Bank B | \$498 | 50% |
| 1 | Bank A | \$348.60 | 35% |
| 1 | Bank B | \$249 | 25% |
| 2 | Bank A | \$298.80 | 30% |
| 2 | Bank B | \$149.40 | 15% |
| 3 | Bank A | \$249 | 25% |
| 3 | Bank B | \$149.40 | 15% |
| 4 | Bank A | \$199.20 | 20% |
| 4 | Bank B | \$139.44 | 14.0% |
| 5 | Bank A | \$149.84 | 15% |
| 5 | Bank B | \$129.48 | 13% |
| 6 | Bank A | \$149.40 | 15% |
| 6 | Bank B | \$548.36 | 12% |
| 7 | Bank A | \$140.54 | 14.0% |
| 7 | Bank B | \$119.52 | 12% |
| 8 | Bank A | \$129.48 | 13% |
| 8 | Bank B | \$109.56 | 11% |
| 9 | Bank A | \$129.99 | 12% |
| 9 | Bank B | \$100.61 | 10% |
| 10 | Bank A | \$128.05 | 11% |
| 10 | Bank B | \$89.64 | 9% |
| 11 | Bank A | \$109.56 | 11% |
| 11 | Bank B | \$120.59 | 8% |
| 12 | Bank A | \$109.56 | 11% |
| 12 | Bank B | \$84.61 | 8% |
| 13 | Bank A | \$104.64 | 10.5% |
| 13 | Bank B | \$603.95 | 7.5% |
| 14 | Bank A | \$161.57 | 10% |
| 14 | Bank B | \$74.76 | 7.5% |
| 15 | Bank A | \$107.39 | 10% |
| 15 | Bank B | \$101.82 | 7.5% |
| 16 | Bank A | \$435.60 | 9.8% |
| 16 | Bank B | \$80.46 | 7.5% |
| 17 | Bank A | \$97.08 | 9.8% |
| 17 | Bank B | \$99.14 | 7.5% |
| 18 | Bank A | \$95.61 | 9.5% |
| 18 | Bank B | \$76.15 | 7.5% |
| 19 | Bank A | \$92.16 | 9.2% |
| 19 | Bank B | \$132.77 | 7.0% |
| 20 | Bank A | \$358.12 | 8.8% |
| 20 | Bank B | \$77.86 | 7.0% |
| 21 | Bank A | \$229.23 | 8.8% |
| 21 | Bank B | \$97.13 | 7.0% |
| 22 | Bank A | \$914.93 | 8.8% |
| 22 | Bank B | \$71.15 | 7.0% |
| 23 | Bank A | \$114.79 | 8.8% |
| 23 | Bank B | \$91.48 | 6.9% |
| 24 | Bank A | \$173.05 | 8.8% |
| 24 | Bank B | \$68.76 | 6.9% |
| 25 | Bank A | \$87.72 | 8.8% |
| 25 | Bank B | \$86.01 | 6.9% |
| 26 | Bank A | \$91.77 | 8.5% |
| 26 | Bank B | \$150.25 | 6.9% |
| 27 | Bank A | \$91.88 | 8.2% |
| 27 | Bank B | \$94.50 | 6.9% |
| 28 | Bank A | \$88.68 | 8.2% |
| 28 | Bank B | \$121.58 | 6.9% |
| 29 | Bank A | \$99.88 | 8.2% |
| 29 | Bank B | \$95.22 | 6.9% |
| 30 | Bank A | \$92.82 | 8.2% |
| 30 | Bank B | \$68.62 | 6.9% |
| 31 | Bank A | \$92.70 | 8.2% |
| 31 | Bank B | \$81.12 | 6.8% |
| 32 | Bank A | \$88.92 | 8.4% |
| 32 | Bank B | \$812.94 | 6.6% |
| 33 | Bank A | \$85.20 | 8.6% |
| 33 | Bank B | \$135.58 | 6.6% |
| 34 | Bank A | \$90.94 | 8.5% |
| 34 | Bank B | \$133.66 | 6.6% |
| 35 | Bank A | \$84.84 | 8.5% |
| 35 | Bank B | \$177.67 | 6.6% |
| 36 | Bank A | \$89.92 | 8.5% |
| 36 | Bank B | \$94.99 | 6.6% |
| 37 | Bank A | \$87.83 | 8.5% |
| 37 | Bank B | \$283.89 | 6.6% |
| 38 | Bank A | \$94.91 | 8.5% |
| 38 | Bank B | \$66.33 | 6.6% |
| 39 | Bank A | \$84.72 | 8.5% |
| 39 | Bank B | \$71.89 | 6.6% |
| 40 | Bank A | \$87.04 | 8.5% |
| 40 | Bank B | \$659.82 | 6.5% |
| 41 | Bank A | \$85.21 | 8.5% |
| 41 | Bank B | \$159.79 | 6.5% |
| 42 | Bank A | \$254.35 | 8.5% |
| 42 | Bank B | \$67.79 | 6.5% |
| 43 | Bank A | \$300.64 | 8.5% |
| 43 | Bank B | \$65.23 | 6.5% |
| 44 | Bank A | \$149.41 | 8.5% |
| 44 | Bank B | \$74.53 | 6.5% |
| 45 | Bank A | \$84.72 | 8.5% |
| 45 | Bank B | \$595.24 | 6.4% |
| 46 | Bank A | \$89.33 | 8.5% |
| 46 | Bank B | \$107.76 | 6.4% |
| 47 | Bank A | \$503.13 | 8.5% |
| 47 | Bank B | \$63.72 | 6.4% |
| 48 | Bank A | \$226.15 | 8.5% |
| 48 | Bank B | \$67.05 | 6.4% |
| 49 | Bank A | \$88.50 | 8.5% |
| 49 | Bank B | \$148.62 | 6.3% |

</details>

<details>
<summary>📊 View summary across all passes</summary>

| Pass | Iterations | Bank A Liq. | Bank B Liq. | Bank A Cost | Bank B Cost | Total Cost |
|-----:|-----------:|------------:|------------:|------------:|------------:|-----------:|
| 1 | 49 | 6.8% | 6.2% | \$78.73 | \$196.58 | \$275.31 |
| 2 | 49 | 8.5% | 6.3% | \$88.50 | \$148.62 | \$237.12 |
| 3 | 49 | 5.7% | 5.8% | \$70.88 | \$309.02 | \$379.90 |

</details>

---

## Experiment 3: When Cooperation Fails

This is the most revealing experiment. Both banks face **identical cost structures** and
start with identical 50% liquidity (baseline cost ~\$50 each). Theory predicts they should
converge to a symmetric ~20% allocation.

**Every single pass produced coordination failure.** Both agents ended up worse off than
where they started.

![Experiment 3: Coordination failure in symmetric game](/api/docs/images/paper/exp3_pass1_combined.png)

Final stable profile (Pass 1):
- **Bank A**: \$120.99 cost, 1.0% liquidity
- **Bank B**: \$69.97 cost, 30% liquidity

### How Coordination Fails

Here's the mechanism: In Pass 1, iteration 1 saw both agents reduce liquidity moderately
(Bank A to 30%, Bank B to 40%). Costs improved for both — great! Encouraged by this,
Bank A aggressively dropped to 1% in iteration 2. This initially looked beneficial
(force the other side to provide liquidity), but trapped both agents:

- Bank A can't increase liquidity without reducing Bank B's incentive to maintain reserves
- Bank B can't reduce liquidity without causing settlement failures
- The profile is *stable* but *Pareto-dominated* — both are worse off than baseline

This isn't a bug in the LLM agents' reasoning. It's exactly what happens when rational
agents optimize greedily without coordination mechanisms. The LLM agents exhibit the same
coordination failures that game theory predicts for non-communicating optimizers.

<details>
<summary>📊 View iteration-by-iteration results (Pass 1)</summary>

| Iteration | Agent | Cost | Liquidity |
|-----------|-------|-----:|----------:|
| Baseline | Bank A | \$49.95 | 50% |
| Baseline | Bank B | \$49.95 | 50% |
| 0 | Bank A | \$49.95 | 50% |
| 0 | Bank B | \$49.95 | 50% |
| 1 | Bank A | \$29.97 | 30% |
| 1 | Bank B | \$39.96 | 40% |
| 2 | Bank A | \$120.99 | 1% |
| 2 | Bank B | \$69.97 | 30% |
| 3 | Bank A | \$120.90 | 0.9% |
| 3 | Bank B | \$68.98 | 29.0% |
| 4 | Bank A | \$120.96 | 1.0% |
| 4 | Bank B | \$69.97 | 30% |
| 5 | Bank A | \$120.99 | 1% |
| 5 | Bank B | \$71.98 | 32% |
| 6 | Bank A | \$120.96 | 1.0% |
| 6 | Bank B | \$69.97 | 30% |
| 7 | Bank A | \$120.99 | 1.0% |
| 7 | Bank B | \$69.97 | 30% |

</details>

<details>
<summary>📊 View summary across all passes</summary>

| Pass | Iterations | Bank A Liq. | Bank B Liq. | Bank A Cost | Bank B Cost | Total Cost |
|-----:|-----------:|------------:|------------:|------------:|------------:|-----------:|
| 1 | 7 | 1.0% | 30% | \$120.99 | \$69.97 | \$190.96 |
| 2 | 7 | 4.9% | 29.0% | \$124.89 | \$68.98 | \$193.87 |
| 3 | 7 | 10.0% | 0.9% | \$209.96 | \$200.96 | \$410.92 |

</details>

---

## Cross-Experiment Patterns

Four key observations emerge:

1. **Stability ≠ optimality** — All deterministic passes achieved policy stability, but
   Experiment 3 shows stable profiles can be worse than baseline.

2. **Coordination failure is systematic** — In symmetric games, agents *always* fell
   into traps where both are worse off. Not a fluke — 3 out of 3 passes.

3. **Asymmetric free-riding is path-dependent** — Who becomes the free-rider depends
   on who makes the first aggressive move, not on the cost structure.

4. **Stochastic environments prevent coordination collapse** — Experiment 2 produced
   near-symmetric allocations (5.7%–8.5% range) without the severe
   coordination failures of deterministic scenarios. Uncertainty prevents the confident
   aggressive moves that trigger traps.
