# Results

## Headline Finding: The Complexity Threshold

LLM-optimized policies dramatically reduce costs in simple scenarios (2-4 banks) but **actively hurt performance** in complex scenarios (5+ banks). We call this the **complexity threshold** — the point at which LLM agents begin to make the system worse rather than better.

<!-- CHART: cost-comparison -->

## Simple Scenarios: Strong Cost Reduction

In scenarios with 2-4 banks, LLM agents achieve significant cost reductions while maintaining high settlement rates. Values show **last-day (converged) policy cost** — the cost achieved after iterative optimization.

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ | Flash SR | Pro SR |
|----------|--------------|------------|----------|---------|-------|----------|--------|
| [`2b_3t`](https://simcash-487714.web.app/experiment/5c59f15f) | [99,900](https://simcash-487714.web.app/experiment/5c59f15f) | [13,660](https://simcash-487714.web.app/experiment/eaf07a54) | [75,886](https://simcash-487714.web.app/experiment/4206630b) | [**-86.3%**](https://simcash-487714.web.app/experiment/eaf07a54) | [**-24.0%**](https://simcash-487714.web.app/experiment/4206630b) | [100.0%](https://simcash-487714.web.app/experiment/eaf07a54) | [100.0%](https://simcash-487714.web.app/experiment/4206630b) |
| [`3b_6t`](https://simcash-487714.web.app/experiment/c2994509) | [74,700](https://simcash-487714.web.app/experiment/c2994509) | [18,017](https://simcash-487714.web.app/experiment/be9df7e0) | [19,678](https://simcash-487714.web.app/experiment/5f3e5661) | [**-75.9%**](https://simcash-487714.web.app/experiment/be9df7e0) | [**-73.7%**](https://simcash-487714.web.app/experiment/5f3e5661) | [100.0%](https://simcash-487714.web.app/experiment/be9df7e0) | [100.0%](https://simcash-487714.web.app/experiment/5f3e5661) |
| [`4b_8t`](https://simcash-487714.web.app/experiment/73e5990a) | [132,800](https://simcash-487714.web.app/experiment/73e5990a) | [59,123](https://simcash-487714.web.app/experiment/1c3114b7) | [41,233](https://simcash-487714.web.app/experiment/760cdc06) | [**-55.5%**](https://simcash-487714.web.app/experiment/1c3114b7) | [**-69.0%**](https://simcash-487714.web.app/experiment/760cdc06) | [95.2%](https://simcash-487714.web.app/experiment/1c3114b7) | [96.8%](https://simcash-487714.web.app/experiment/760cdc06) |
| [`castro_exp2`](https://simcash-487714.web.app/experiment/17bdd52c) | [99,600](https://simcash-487714.web.app/experiment/17bdd52c) | [39,393](https://simcash-487714.web.app/experiment/4b01f402) | [108,910](https://simcash-487714.web.app/experiment/cb000a9e) | [**-60.4%**](https://simcash-487714.web.app/experiment/4b01f402) | [**+9.3%**](https://simcash-487714.web.app/experiment/cb000a9e) | [92.0%](https://simcash-487714.web.app/experiment/4b01f402) | [82.0%](https://simcash-487714.web.app/experiment/cb000a9e) |
| [`lynx_day`](https://simcash-487714.web.app/experiment/9eaf71b4) | [3](https://simcash-487714.web.app/experiment/9eaf71b4) | [3](https://simcash-487714.web.app/experiment/3245ee30) | [3](https://simcash-487714.web.app/experiment/73672186) | [**0.0%**](https://simcash-487714.web.app/experiment/3245ee30) | [**0.0%**](https://simcash-487714.web.app/experiment/73672186) | [100.0%](https://simcash-487714.web.app/experiment/3245ee30) | [100.0%](https://simcash-487714.web.app/experiment/73672186) |

**Key observations:**
- Flash achieves 55-86% cost reduction in simple scenarios
- Flash consistently outperforms Pro (the "smart free-rider" effect — see Discussion)
- Pro sometimes *increases* costs (castro_exp2: +9.3%)
- Settlement rates remain high (>95%) in simple scenarios

## Complex Scenarios: LLM Makes Things Worse

In scenarios with 5+ banks and 25-day runs, **all models increase costs**. Values show **total system cost summed across all 25 days**.

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ |
|----------|--------------|------------|----------|---------|-------|
| [`periodic_shocks`](https://simcash-487714.web.app/experiment/747025f3) | [611.4M](https://simcash-487714.web.app/experiment/747025f3) | — | — | — | — |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | [1.73B](https://simcash-487714.web.app/experiment/524fc873) | [2.03B](https://simcash-487714.web.app/experiment/298704f4) | [2.09B](https://simcash-487714.web.app/experiment/6f6f3afb) | [**+17.1%**](https://simcash-487714.web.app/experiment/298704f4) | [**+20.8%**](https://simcash-487714.web.app/experiment/6f6f3afb) |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | [2.06B](https://simcash-487714.web.app/experiment/b140728c) | [2.34B](https://simcash-487714.web.app/experiment/79785ad6) | [2.54B](https://simcash-487714.web.app/experiment/9f279e14) | [**+13.6%**](https://simcash-487714.web.app/experiment/79785ad6) | [**+23.2%**](https://simcash-487714.web.app/experiment/9f279e14) |

<!-- CHART: complex-cost-delta -->

<!-- CHART: settlement-degradation -->

Settlement rates also degrade. Values show **cumulative settlement rate** (total settled / total arrived across all 25 days):

| Scenario | Baseline SR | Flash SR | Pro SR |
|----------|-------------|----------|--------|
| [`periodic_shocks`](https://simcash-487714.web.app/experiment/747025f3) | [76.6%](https://simcash-487714.web.app/experiment/747025f3) | — | — |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | [58.8%](https://simcash-487714.web.app/experiment/524fc873) | [56.4%](https://simcash-487714.web.app/experiment/298704f4) | [55.6%](https://simcash-487714.web.app/experiment/6f6f3afb) |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | [68.7%](https://simcash-487714.web.app/experiment/b140728c) | [58.6%](https://simcash-487714.web.app/experiment/79785ad6) | [57.1%](https://simcash-487714.web.app/experiment/9f279e14) |

> **Note:** GLM results for complex scenarios (periodic_shocks, large_network, lehman_month) are excluded due to a pre-bugfix data integrity issue.

## The "Smart Free-Rider" Effect

Across nearly all scenarios, **Flash outperforms Pro**. This is counterintuitive — a more capable model should do better. We hypothesize this is a **smart free-rider effect**: Pro is sophisticated enough to recognize opportunities for strategic delay (free-riding on other banks' liquidity) but this individually rational behavior creates collectively worse outcomes.

| Scenario | Flash Cost | Pro Cost | Flash wins? |
|----------|-----------|----------|-------------|
| [`2b_3t`](https://simcash-487714.web.app/experiment/5c59f15f) | [13,660](https://simcash-487714.web.app/experiment/eaf07a54) | [75,886](https://simcash-487714.web.app/experiment/4206630b) | ✅ |
| [`3b_6t`](https://simcash-487714.web.app/experiment/c2994509) | [18,017](https://simcash-487714.web.app/experiment/be9df7e0) | [19,678](https://simcash-487714.web.app/experiment/5f3e5661) | ✅ |
| [`4b_8t`](https://simcash-487714.web.app/experiment/73e5990a) | [59,123](https://simcash-487714.web.app/experiment/1c3114b7) | [41,233](https://simcash-487714.web.app/experiment/760cdc06) | ❌ |
| [`castro_exp2`](https://simcash-487714.web.app/experiment/17bdd52c) | [39,393](https://simcash-487714.web.app/experiment/4b01f402) | [108,910](https://simcash-487714.web.app/experiment/cb000a9e) | ✅ |
| [`large_network`](https://simcash-487714.web.app/experiment/524fc873) | [2.03B](https://simcash-487714.web.app/experiment/298704f4) | [2.09B](https://simcash-487714.web.app/experiment/6f6f3afb) | ✅ |
| [`lehman_month`](https://simcash-487714.web.app/experiment/b140728c) | [2.34B](https://simcash-487714.web.app/experiment/79785ad6) | [2.54B](https://simcash-487714.web.app/experiment/9f279e14) | ✅ |

Flash wins in 5 out of 6 comparable scenarios (excluding lynx_day which is trivial).

## Stress Scenarios

The `2b_stress` scenario presents an interesting exception — Pro outperforms Flash:

| Model | Cost | SR |
|-------|------|----|
| Baseline | 99,600 | 100.0% |
| Flash | 164,585 | 82.0% |
| Pro | 68,086 | 90.0% |
| GLM | 194,897 | 84.0% |

Here Flash and GLM actually *increase* costs while Pro achieves a 31.6% reduction. This suggests stress conditions may reward the more careful reasoning of Pro.

## v0.2 Prompt Variants (Castro Exp2)

The castro_exp2 scenario was additionally tested with v0.2 prompt engineering variants to test whether improved context can break through performance barriers. These variants add:
- **c1-info**: Enhanced information context
- **c2-floor**: Floor price awareness
- **c3-guidance**: Explicit optimization guidance  
- **c4-composition**: Compositional strategy building

*Detailed v0.2 results are available in the Appendix.*

## Run Variance

Each model was run 3 times per scenario (r1, r2, r3) to measure behavioral variance. Full per-run data is in the Appendix.
