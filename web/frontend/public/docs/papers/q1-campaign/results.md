# Results

## Simple Scenarios: Strong Cost Reduction

In single-day scenarios with 2–4 banks and 10 optimization rounds, LLM agents achieved significant cost reductions while maintaining high settlement rates. Values show **last-day (converged) policy cost** — the cost achieved after iterative optimization.

<!-- CHART: cost-comparison -->

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ | Flash SR | Pro SR |
|----------|--------------|------------|----------|---------|-------|----------|--------|
| [`2b_3t`](https://simcash-487714.web.app/experiment/5c59f15f) | [99,900](https://simcash-487714.web.app/experiment/5c59f15f) | [13,660](https://simcash-487714.web.app/experiment/eaf07a54) | [75,886](https://simcash-487714.web.app/experiment/4206630b) | [**-86.3%**](https://simcash-487714.web.app/experiment/eaf07a54) | [**-24.0%**](https://simcash-487714.web.app/experiment/4206630b) | [100.0%](https://simcash-487714.web.app/experiment/eaf07a54) | [100.0%](https://simcash-487714.web.app/experiment/4206630b) |
| [`3b_6t`](https://simcash-487714.web.app/experiment/c2994509) | [74,700](https://simcash-487714.web.app/experiment/c2994509) | [18,017](https://simcash-487714.web.app/experiment/be9df7e0) | [19,678](https://simcash-487714.web.app/experiment/5f3e5661) | [**-75.9%**](https://simcash-487714.web.app/experiment/be9df7e0) | [**-73.7%**](https://simcash-487714.web.app/experiment/5f3e5661) | [100.0%](https://simcash-487714.web.app/experiment/be9df7e0) | [100.0%](https://simcash-487714.web.app/experiment/5f3e5661) |
| [`4b_8t`](https://simcash-487714.web.app/experiment/73e5990a) | [132,800](https://simcash-487714.web.app/experiment/73e5990a) | [59,123](https://simcash-487714.web.app/experiment/1c3114b7) | [41,233](https://simcash-487714.web.app/experiment/760cdc06) | [**-55.5%**](https://simcash-487714.web.app/experiment/1c3114b7) | [**-69.0%**](https://simcash-487714.web.app/experiment/760cdc06) | [95.2%](https://simcash-487714.web.app/experiment/1c3114b7) | [96.8%](https://simcash-487714.web.app/experiment/760cdc06) |
| [`castro_exp2`](https://simcash-487714.web.app/experiment/17bdd52c) | [99,600](https://simcash-487714.web.app/experiment/17bdd52c) | [39,393](https://simcash-487714.web.app/experiment/4b01f402) | [108,910](https://simcash-487714.web.app/experiment/cb000a9e) | [**-60.4%**](https://simcash-487714.web.app/experiment/4b01f402) | [**+9.3%**](https://simcash-487714.web.app/experiment/cb000a9e) | [92.0%](https://simcash-487714.web.app/experiment/4b01f402) | [82.0%](https://simcash-487714.web.app/experiment/cb000a9e) |
| [`lynx_day`](https://simcash-487714.web.app/experiment/9eaf71b4) | [3](https://simcash-487714.web.app/experiment/9eaf71b4) | [3](https://simcash-487714.web.app/experiment/3245ee30) | [3](https://simcash-487714.web.app/experiment/73672186) | [**0.0%**](https://simcash-487714.web.app/experiment/3245ee30) | [**0.0%**](https://simcash-487714.web.app/experiment/73672186) | [100.0%](https://simcash-487714.web.app/experiment/3245ee30) | [100.0%](https://simcash-487714.web.app/experiment/73672186) |

**Observations:**
- Flash achieved 55–86% cost reduction in simple scenarios
- Settlement rates remained high (≥95%) in all simple scenarios except castro_exp2
- Pro sometimes *increased* costs (castro_exp2: +9.3%)
- The lynx_day scenario was trivially easy for all approaches (baseline cost of 3)

## Multi-Day Scenarios: LLM Optimization Increased Costs

In multi-day scenarios (25 simulated days, 1 optimization round with between-day learning), LLM-optimized policies produced higher total system costs than the unoptimized baseline. Values show **total system cost summed across all 25 days**.

> **Important confound note:** These multi-day scenarios differ from simple scenarios in at least eight dimensions simultaneously — not just bank count. They use 25 days instead of 1, between-day optimization instead of within-day iterative optimization, heterogeneous banks instead of symmetric ones, bilateral + cycle LSM instead of no LSM, varying liquidity pools (160K–800K) instead of uniform 1M, lower EOD penalty costs (4–5K vs. 100K), scenario-specific events (shocks, crisis phases), and much lower baseline settlement rates (59–77% vs. 100%). Any or all of these factors could contribute to the observed performance difference. See Discussion for a full accounting.

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ |
|----------|--------------|------------|----------|---------|-------|
| [`periodic_shocks`](https://simcash-487714.web.app/experiment/747025f3) | [611.4M](https://simcash-487714.web.app/experiment/747025f3) | — | — | — | — |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | [1.73B](https://simcash-487714.web.app/experiment/524fc873) | [2.03B](https://simcash-487714.web.app/experiment/298704f4) | [2.09B](https://simcash-487714.web.app/experiment/6f6f3afb) | [**+17.1%**](https://simcash-487714.web.app/experiment/298704f4) | [**+20.8%**](https://simcash-487714.web.app/experiment/6f6f3afb) |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | [2.06B](https://simcash-487714.web.app/experiment/b140728c) | [2.34B](https://simcash-487714.web.app/experiment/79785ad6) | [2.54B](https://simcash-487714.web.app/experiment/9f279e14) | [**+13.6%**](https://simcash-487714.web.app/experiment/79785ad6) | [**+23.2%**](https://simcash-487714.web.app/experiment/9f279e14) |

<!-- CHART: complex-cost-delta -->

<!-- CHART: settlement-degradation -->

Settlement rates also degraded under LLM optimization. Values show **cumulative settlement rate** (total settled / total arrived across all 25 days):

| Scenario | Baseline SR | Flash SR | Pro SR |
|----------|-------------|----------|--------|
| [`periodic_shocks`](https://simcash-487714.web.app/experiment/747025f3) | [76.6%](https://simcash-487714.web.app/experiment/747025f3) | — | — |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | [58.8%](https://simcash-487714.web.app/experiment/524fc873) | [56.4%](https://simcash-487714.web.app/experiment/298704f4) | [55.6%](https://simcash-487714.web.app/experiment/6f6f3afb) |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | [68.7%](https://simcash-487714.web.app/experiment/b140728c) | [58.6%](https://simcash-487714.web.app/experiment/79785ad6) | [57.1%](https://simcash-487714.web.app/experiment/9f279e14) |

> **Note:** GLM results for complex scenarios (periodic_shocks, large_network, lehman_month) are excluded due to a pre-bugfix data integrity issue.

## Flash vs. Pro: Model Comparison

Across most scenarios, Flash produced lower total system costs than Pro. This pattern held in 5 of 6 comparable scenarios (excluding lynx_day, which was trivial).

| Scenario | Flash Cost | Pro Cost | Flash wins? |
|----------|-----------|----------|-------------|
| [`2b_3t`](https://simcash-487714.web.app/experiment/5c59f15f) | [13,660](https://simcash-487714.web.app/experiment/eaf07a54) | [75,886](https://simcash-487714.web.app/experiment/4206630b) | ✅ |
| [`3b_6t`](https://simcash-487714.web.app/experiment/c2994509) | [18,017](https://simcash-487714.web.app/experiment/be9df7e0) | [19,678](https://simcash-487714.web.app/experiment/5f3e5661) | ✅ |
| [`4b_8t`](https://simcash-487714.web.app/experiment/73e5990a) | [59,123](https://simcash-487714.web.app/experiment/1c3114b7) | [41,233](https://simcash-487714.web.app/experiment/760cdc06) | ❌ |
| [`castro_exp2`](https://simcash-487714.web.app/experiment/17bdd52c) | [39,393](https://simcash-487714.web.app/experiment/4b01f402) | [108,910](https://simcash-487714.web.app/experiment/cb000a9e) | ✅ |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | [2.03B](https://simcash-487714.web.app/experiment/298704f4) | [2.09B](https://simcash-487714.web.app/experiment/6f6f3afb) | ✅ |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | [2.34B](https://simcash-487714.web.app/experiment/79785ad6) | [2.54B](https://simcash-487714.web.app/experiment/9f279e14) | ✅ |

We note this as a consistent pattern but do not claim a causal mechanism. Possible explanations include differences in reasoning style, parameter aggressiveness, or stochastic variation across only 3 runs per condition — none of which we can distinguish with the current data.

## Stress Scenario

The `2b_stress` scenario presents a different pattern — Pro outperformed Flash:

| Model | Cost | SR |
|-------|------|----|
| Baseline | 99,600 | 100.0% |
| Flash | 164,585 | 82.0% |
| Pro | 68,086 | 90.0% |
| GLM | 194,897 | 84.0% |

Here Flash and GLM *increased* costs while Pro achieved a 31.6% reduction. Under stress conditions with only 2 banks, Pro's more deliberate reasoning may have produced more conservative policies that better navigated payment pressure.

## The Liquidity Ratchet in Multi-Day Scenarios

In multi-day scenarios, we observed a distinctive pattern: LLM agents progressively drove initial liquidity fractions toward zero over the 25-day simulation. For example, in one Lehman Month run, BANK_GAMMA's liquidity fraction followed this trajectory:

> 0.50 → 0.25 → 0.125 → 0.016 → 0.0005 → 0.0

On Day 1, before this ratchet effect takes hold, LLM-optimized policies often performed comparably to or better than the baseline — even on the multi-day scenarios. The damage accumulated from Day 2 onward as each agent independently learned that reducing its own liquidity commitment reduced its own costs on the previous day. This observation is consistent with the between-day optimization structure: each agent sees only its own cost change and has no visibility into the system-wide consequences of collective liquidity withdrawal.

## v0.2 Prompt Variants (Castro Exp2)

The castro_exp2 scenario was additionally tested with v0.2 prompt engineering variants to test whether improved context can enhance LLM behavior. These variants add:
- **c1-info**: Enhanced information context
- **c2-floor**: Floor price awareness
- **c3-guidance**: Explicit optimization guidance
- **c4-composition**: Compositional strategy building

Results are properly scoped to Castro Exp2 (2 banks, 1 day, 10 rounds). Key observation: the settlement floor constraint (C2) was the most effective single intervention, achieving 100% settlement under Flash while maintaining significant cost reduction. Constraints appeared more effective than information alone (C1) in shaping agent behavior.

*Detailed v0.2 results are available in the Appendix.*

## Run Variance

Each model was run 3 times per scenario (r1, r2, r3) to measure behavioral variance. Full per-run data is in the Appendix.
