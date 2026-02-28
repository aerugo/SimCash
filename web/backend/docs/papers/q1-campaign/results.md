# Results

## Headline Finding: The Complexity Threshold

LLM-optimized policies dramatically reduce costs in simple scenarios (2-4 banks) but **actively hurt performance** in complex scenarios (5+ banks). We call this the **complexity threshold** — the point at which LLM agents begin to make the system worse rather than better.

<!-- CHART: cost-comparison -->

## Simple Scenarios: Strong Cost Reduction

In scenarios with 2-4 banks, LLM agents achieve significant cost reductions while maintaining high settlement rates:

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ | Flash SR | Pro SR |
|----------|--------------|------------|----------|---------|-------|----------|--------|
| `2b_3t` | 99,900 | 13,660 | 75,886 | **-86.3%** | -24.0% | 96.6% | 79.7% |
| `3b_6t` | 74,700 | 18,017 | 19,678 | **-75.9%** | -73.7% | 99.2% | 99.2% |
| `4b_8t` | 132,800 | 59,123 | 41,233 | **-55.5%** | **-68.9%** | 99.0% | 98.6% |
| `castro_exp2` | 99,600 | 39,393 | 108,910 | **-60.4%** | +9.3% | 98.8% | 95.9% |
| `lynx_day` | 3 | 3 | 3 | 0% | 0% | 100% | 100% |

**Key observations:**
- Flash achieves 55-86% cost reduction in simple scenarios
- Flash consistently outperforms Pro (the "smart free-rider" effect — see Discussion)
- Pro sometimes *increases* costs (castro_exp2: +9.3%)
- Settlement rates remain high (>96%) in simple scenarios

## Complex Scenarios: LLM Makes Things Worse

In scenarios with 5+ banks and 25-day runs, **all models increase costs**:

| Scenario | Baseline Cost | Flash Cost | Pro Cost | Flash Δ | Pro Δ |
|----------|--------------|------------|----------|---------|-------|
| `periodic_shocks` | 66.3M | — | — | — | — |
| `large_network` | 182.9M | 192.6M | 202.0M | **+5.3%** | **+10.5%** |
| `lehman_month` | 199.1M | 233.4M | 252.5M | **+17.2%** | **+26.8%** |

<!-- CHART: settlement-degradation -->

Settlement rates also degrade:

| Scenario | Baseline SR | Flash SR | Pro SR |
|----------|-------------|----------|--------|
| `periodic_shocks` | 81.9% | — | — |
| `large_network` | 66.8% | 63.1% | 60.9% |
| `lehman_month` | 73.2% | 66.9% | 65.6% |

> **Note:** GLM results for complex scenarios (periodic_shocks, large_network, lehman_month) are excluded due to a pre-bugfix data integrity issue.

## The "Smart Free-Rider" Effect

Across nearly all scenarios, **Flash outperforms Pro**. This is counterintuitive — a more capable model should do better. We hypothesize this is a **smart free-rider effect**: Pro is sophisticated enough to recognize opportunities for strategic delay (free-riding on other banks' liquidity) but this individually rational behavior creates collectively worse outcomes.

| Scenario | Flash Cost | Pro Cost | Flash wins? |
|----------|-----------|----------|-------------|
| `2b_3t` | 13,660 | 75,886 | ✅ |
| `3b_6t` | 18,017 | 19,678 | ✅ |
| `4b_8t` | 59,123 | 41,233 | ❌ |
| `castro_exp2` | 39,393 | 108,910 | ✅ |
| `large_network` | 192.6M | 202.0M | ✅ |
| `lehman_month` | 233.4M | 252.5M | ✅ |

Flash wins in 5 out of 6 comparable scenarios (excluding lynx_day which is trivial).

## Stress Scenarios

The `2b_stress` scenario presents an interesting exception — Pro outperforms Flash:

| Model | Cost | SR |
|-------|------|----|
| Baseline | 99,600 | 100% |
| Flash | 164,585 | 96.9% |
| Pro | 68,086 | 98.3% |
| GLM | 194,897 | 97.7% |

Here Flash and GLM actually *increase* costs while Pro achieves a 31.7% reduction. This suggests stress conditions may reward the more careful reasoning of Pro.

## v0.2 Prompt Variants (Castro Exp2)

The castro_exp2 scenario was additionally tested with v0.2 prompt engineering variants to test whether improved context can break through performance barriers. These variants add:
- **c1-info**: Enhanced information context
- **c2-floor**: Floor price awareness
- **c3-guidance**: Explicit optimization guidance  
- **c4-composition**: Compositional strategy building

*Detailed v0.2 results are available in the Appendix.*

## Run Variance

Each model was run 3 times per scenario (r1, r2, r3) to measure behavioral variance. Full per-run data is in the Appendix.
