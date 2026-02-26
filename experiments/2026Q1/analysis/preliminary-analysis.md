# Preliminary Analysis — SimCash Three-Model Comparison
**Date:** 2026-02-24
**Status:** 18/20 experiments complete (Lehman Month Pro still running)

---

## 1. Model Performance Trends

### Summary Table

| Scenario | GLM Cost | Flash Cost | Pro Cost | GLM Settl | Flash Settl | Pro Settl | Winner (cost) |
|----------|----------|------------|----------|-----------|-------------|-----------|---------------|
| 2B 3T | 100,909 | **13,660** | 75,886 | 35.3% | **100%** | **100%** | Flash |
| 2B Stress | 194,897 | 164,585 | **68,086** | 84% | 82% | **90%** | Pro |
| 3B 6T | 19,631 | **18,017** | 19,678 | 100% | 100% | 100% | ~Tie |
| 4B 8T | **40,178** | 59,123 | 41,233 | **96.8%** | 95.2% | **96.8%** | GLM |
| Large Network | — | 192.6M | 202.0M | — | 56.4% | 55.6% | Flash* |
| Lehman Month | 246.7M | **233.4M** | (running) | 58.9% | 58.6% | (running) | Flash* |
| Lynx Day | 3 | 3 | 3 | 100% | 100% | 100% | Tie (trivial) |

*Large Network and Lehman are "crisis" scenarios where costs explode — lower is less bad.

### Key Findings

**No single model dominates.** The ranking changes by scenario type:

1. **Flash excels at simple scenarios** — Dramatically better on 2B 3T (86% cost reduction vs GLM's 1%). Flash consistently finds the steepest descent to low-cost equilibria in small networks.

2. **Pro excels under stress** — Best performer on 2B Stress (68K vs Flash 165K, GLM 195K) with highest settlement (90%). Pro's more aggressive optimization pays off when penalty costs are extreme. This is consistent with the browser-era Periodic Shocks finding where Pro also dominated.

3. **GLM wins at medium complexity** — Best on 4B 8T (40K vs Pro 41K, Flash 59K). In moderately complex networks without extreme stress, GLM's approach produces the most efficient equilibria.

4. **All models converge on simple equilibria** — 3B 6T shows near-identical results across all three models (CV=0.04). When the optimal strategy is "obvious" (clear coordinating equilibrium), model choice doesn't matter.

5. **All models fail at large multi-day scenarios** — Both Large Network and Lehman Month show costs exploding from ~100K to ~200M+. The optimization produces a tragedy of the commons: small banks free-ride by cutting liquidity to zero, large banks bear all costs. No model overcomes this.

### Emerging Pattern: Scenario Complexity vs Model Advantage

| Complexity | Best Model | Why |
|-----------|-----------|-----|
| Trivial (Lynx Day) | All equal | LSM dominates, nothing to optimize |
| Simple (2B 3T, 3B 6T) | Flash | Fastest convergence to cooperative equilibrium |
| Medium (4B 8T) | GLM | Most efficient exploration of larger strategy space |
| High Stress (2B Stress) | Pro | Most aggressive cost optimization under penalty pressure |
| Multi-day crisis | Flash (slightly) | More conservative → less catastrophic free-riding |

---

## 2. Decision Tree Complexity

### Which experiments produced the most complex trees?

| Experiment | Max Nodes | Max Depth | Banks w/ Trees | Novel Actions |
|-----------|-----------|-----------|----------------|---------------|
| **Lehman Flash** | 7 | 2 | 2 | Hold, ReleaseWithCredit |
| **Lehman GLM** | 7 | 3 | 5 | Hold |
| **Large Network Pro** | 7 | 3 | 4 | Hold, ReleaseWithCredit, Split |
| **Large Network Flash** | 5 | 2 | 3 | Hold, ReleaseWithCredit |
| 2B 3T GLM | 7 | 2 | 2 | Hold, Split |
| 2B 3T Pro | 7 | 3 | 2 | Hold, Split |
| All 4B 8T | 5 | 2 | 4 | Hold |
| All 2B Stress | 5 | 2 | 2 | Hold |
| Lynx Day (all) | 0 | 0 | 0 | (none — Release only) |

### Key Findings

1. **Multi-day scenarios produce the most complex trees.** Lehman and Large Network are the only scenarios where banks developed `ReleaseWithCredit` strategies — using credit facilities to manage liquidity shortfalls. This only emerges under sustained stress where simple Release/Hold isn't sufficient.

2. **Lehman Flash's CLEARING_HUB developed the richest strategy**: a multi-level urgency-based decision tree that checks `ticks_to_deadline`, then `effective_liquidity` vs `amount`, branching between Release, ReleaseWithCredit, and Hold. This appeared on Day 5 and persisted through Day 25, evolving its structure over time.

3. **Large Network Pro discovered Split actions** — the only experiment where any model learned to split payments into smaller pieces. This is operationally significant: real RTGS systems use payment splitting to manage liquidity.

4. **Small scenarios stay simple.** Even with "full" decision tree mode, the 2-3 bank scenarios rarely develop beyond depth-2 trees with Hold as the only non-trivial action. The strategic space is too small to need complex policies.

5. **Tree complexity correlates with strategic tension, not model capability.** The most complex trees emerge from scenarios with genuine resource scarcity and competing objectives — not from "smarter" models applied to simple problems.

### Conditions Used in Decision Trees

The LLMs discovered and used these context fields for branching:
- `ticks_to_deadline` — urgency-based prioritization (most common)
- `effective_liquidity` vs `amount` — liquidity adequacy checks
- `balance` — balance-based thresholds for non-urgent payments
- `urgency_threshold` (parameter) — learned threshold for urgency classification

This is noteworthy: **the LLMs independently discovered the same prioritization logic used in real RTGS systems** — urgency-first, then liquidity-check, then queue management.

---

## 3. Reliability & Re-run Recommendations

### Coefficient of Variation Across Models

| Scenario | CV | Interpretation |
|----------|-----|---------------|
| Lynx Day | 0.000 | Perfect convergence — no re-runs needed |
| 3B 6T | 0.040 | Very tight — low priority for re-runs |
| Large Network | 0.024 | Tight (but only 2 models so far) |
| Lehman Month | 0.028 | Tight (but only 2 models so far) |
| 4B 8T | 0.186 | Moderate variance — would benefit from re-runs |
| 2B Stress | 0.379 | High variance — re-runs strongly recommended |
| **2B 3T** | **0.578** | **Very high variance — re-runs essential** |

### Re-run Priorities

**Essential (high variance between models — need to distinguish model effect from stochastic noise):**

1. **2B 3T × 3 models × 3 runs each = 9 experiments** — CV of 0.578 is extreme. GLM got 35% settlement while Flash and Pro got 100%. Is this a model capability difference or did GLM get unlucky with the seed? With only seed=42, we can't tell. Run with seeds 42, 43, 44 minimum.

2. **2B Stress × 3 models × 3 runs = 9 experiments** — CV of 0.379. Pro's dramatically better result (68K vs 195K) needs validation. Could be seed-dependent.

3. **4B 8T × 3 models × 3 runs = 9 experiments** — CV of 0.186. GLM winning by 50% over Flash is a strong claim that needs replication.

**Important (complete the dataset):**

4. **Lehman Month Pro** — currently running, will complete the 3-model comparison
5. **Large Network GLM** — we have an API result but it was from the first pipeline run; should verify it matches expectations

**Lower priority (tight convergence already):**

6. **3B 6T** — all three models within 4% of each other. One more run per model would confirm but isn't urgent.
7. **Lynx Day** — trivial equilibrium, no re-runs needed.

### Recommended Next Batch: 27 experiments

Run each of these 3 times with different seeds (if SimCash supports seed control via API):
- 2B 3T × 3 models × 3 seeds
- 2B Stress × 3 models × 3 seeds  
- 4B 8T × 3 models × 3 seeds

If seed control isn't available, the stochastic engine should still produce different random draws per experiment, giving us the variance estimate we need.

---

## Open Questions

1. **Why does GLM catastrophically fail on 2B 3T?** 35% settlement with costs barely improved from Day 1. The other models achieve 100% settlement. Need multiple runs to confirm this isn't a seed artifact.

2. **Is the multi-day cost explosion a model problem or an architecture problem?** All models produce the same tragedy-of-the-commons pattern in Large Network and Lehman. This might be a fundamental limitation of the myopic daily optimization — no model can overcome it because the optimization horizon is 1 day.

3. **Do complex trees actually improve outcomes?** Lehman Flash developed sophisticated urgency-based trees but still ended at 233M cost. The tree complexity may be "activity without impact" if the bootstrap filter rejects most changes anyway.

4. **Can we test forward-looking optimization?** If the LLM received information about upcoming events (shock schedule, scenario timeline), would it pre-position liquidity? This would test whether the myopia is a prompt design issue or a fundamental LLM limitation.
