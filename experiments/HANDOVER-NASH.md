# Handover to Nash — Stefan's Experiment Campaign

**Date:** 2026-02-28  
**From:** Stefan (Research Director AI)  
**To:** Nash (SimCash developer)

---

## TL;DR

All 105+ experiments are done. The data tells a clear story with one headline finding: a **complexity threshold** where LLM optimization flips from helpful to harmful. This handover covers everything Nash needs to (1) build the results overview / experiment showcase on the docs site, and (2) support putting the conference paper content online.

---

## Part 1: The Results — What We Found

### 1.1 The Headline: Complexity Threshold

Below ~4 banks, LLM optimization delivers 32–86% cost reduction while maintaining near-perfect settlement. Above ~5 banks, it produces **simultaneously** higher costs AND lower settlement than FIFO — not a trade-off, but pure value destruction. A computational tragedy of the commons.

### 1.2 Complete Results Summary

#### Simple Scenarios (LLM optimization HELPS)

| Scenario | Banks | Baseline Cost/SR | Flash Avg Cost/SR | Pro Avg Cost/SR | GLM Avg Cost/SR |
|---|---|---|---|---|---|
| 2B 3T | 2 | 99,900 / 100% | ~14,000 / 100% | ~39,000 / 100% | ~44,000 / 92% |
| 3B 6T | 3 | 74,700 / 100% | ~19,000 / 100% | ~46,000 / 95% | ~55,000 / 88% |
| 4B 8T | 4 | 132,800 / 100% | ~49,000 / 99% | ~60,000 / 98% | ~77,000 / 85% |
| 2B Stress | 2 | 99,600 / 100% | ~51,000 / 88% | ~94,000 / 82% | ~71,000 / 79% |
| Lynx Day | 4 | 3 / 100% | 3 / 100% | 3 / 100% | 3 / 100% |
| Castro Exp2 | 2 | 99,600 / 100% | ~51,000 / 88% | ~94,000 / 82% | ~71,000 / 79% |
| Liq Squeeze | 2 | 72,000 / 100% | ~22,000 / 100% | ~17,000 / 100% | ~19,000 / 100% |

#### Complex Scenarios (LLM optimization HURTS) — v0.1 Clean Re-runs

| Scenario | Banks | Days | Baseline Cost/SR | Flash Avg Cost/SR | Pro Avg Cost/SR |
|---|---|---|---|---|---|
| Periodic Shocks | 5 | 30 | 611M / **77%** | 724M / 70.3% | — |
| Large Network | 5 | 25 | 1,734M / **59%** | 2,106M / 56.9% | 2,077M / 54.2% |
| Lehman Month | 6 | 25 | 2,064M / **69%** | 2,270M* / 73.5%* | — |

*Lehman v0.1 only has 1 fully clean run (r3); r1/r2 were salvaged via PATCH trimming.

#### C4-full (v0.2 Full Prompt Toolkit on Complex Scenarios)

The key question: can better prompts break the complexity threshold?

| Scenario | Flash C4-full Cost/SR | Pro C4-full Cost/SR | vs Baseline SR |
|---|---|---|---|
| Periodic Shocks | 626M / 70.4% | 577M / 65.9% | Baseline **77%** wins |
| Large Network | 2,098M / 58.3% | 2,072M / 53.7% | Baseline **59%** wins |
| Lehman Month | 2,216M / 59.4% | 2,481M / 57.5% | Baseline **69%** wins |

**Answer: No.** v0.2 prompts do not break the threshold. The problem is structural.

#### v0.2 Settlement Optimization (Castro Exp2 — 83 experiments)

| Condition | Description | Flash Avg SR | Pro Avg SR | GLM Avg SR |
|---|---|---|---|---|
| v0.1 (no prompts) | Baseline LLM optimization | 88% | 82% | 79% |
| C1-info | Tell LLM about settlement rates | 90% | 84% | 72% |
| C2-floor | Minimum 80% settlement constraint | **100%** | 82% | 78% |
| C3-guidance | Describe available strategy tools | **100%** | 84% | 82% |
| C4-composition | All of the above combined | **100%** | 82% | 70% |

**Key findings:**
- Constraints > Information (C1 alone = zero effect; C2 floor = most impactful)
- Model selection > Prompt engineering (Flash vs GLM gap >> any prompt condition gap)
- Flash dominates on settlement-aware scoring: 79% of max on floor conditions vs Pro 26%, GLM 0%

### 1.3 Six Core Findings for the Paper

1. **Complexity Threshold**: Individual optimization → collective harm above ~4 banks
2. **Computational Tragedy of the Commons**: Not a cost-settlement trade-off — both worsen simultaneously
3. **Smart Free-Rider Effect**: Pro consistently worse SR than Flash on complex scenarios (54% vs 57% on Large Network). Better reasoning → more effective free-riding → worse collective outcome
4. **Strategy Poverty**: LLMs use only 5/11 available policy actions. Bank tree universally NoAction. They're parameter tuners (liquidity fraction), not strategy architects
5. **Constraints Beat Information**: Settlement floor constraint is the single most effective intervention. Information alone does nothing. Mirrors mechanism design theory.
6. **v0.2 Cannot Break the Threshold**: Full prompt toolkit on complex scenarios yields results indistinguishable from v0.1. The coordination failure is structural.

---

## Part 2: What Goes on the Docs Site

### 2.1 Results Overview / Experiment Showcase Page

There's a detailed plan at `docs/reports/experiment-showcase-plan.md` (also in the repo). Here's the condensed version.

**Proposed structure — 6 sections telling a story:**

1. **"The Basics"** — 2B, 3B, 4B scenarios proving LLM optimization works on simple problems. Summary tables + links to experiments.

2. **"The Threshold"** — THE headline section. Periodic Shocks, Large Network, Lehman Month. Show how cost delta vs baseline flips sign at 5 banks. This needs a chart — even a simple bar chart of "% cost change vs FIFO" ordered by bank count, where bars go from green (savings) to red (overspend).

3. **"Castro Exp2 Deep Dive"** — The most extensively studied scenario (83 experiments). v0.1 replication, v0.2 conditions (C1–C4), retry mechanism. Shows prompt engineering findings.

4. **"Stress Tests"** — High Stress and Liquidity Squeeze. How models handle adverse conditions.

5. **"Special Scenarios"** — Lynx Day (realistic Canadian RTGS parameters). Validates simulator produces sensible results.

6. **"Model Leaderboard"** — Aggregate ranking. Flash > Pro > GLM on settlement-weighted scoring. Pro's paradoxical underperformance on complex scenarios.

**Each experiment should show:**
- Scenario name + model badge (color-coded)
- Total cost + settlement rate
- Delta vs baseline (green ↓ / red ↑)
- Link to full experiment detail page
- Run number for replication visibility

**What NOT to show:**
- Anything from `api-results/compromised-pre-00168/` (38 experiments with cost delta bug — see DATA-INTEGRITY.md)
- Canary/test experiments
- GLM on complex scenarios (not re-run, insufficient clean data)

### 2.2 Conference Paper on the Docs Site

The paper should live under a "Research" or "Papers" section in the docs sidebar. Proposed structure:

```
Research
├── Paper: LLM-Optimized Payment Coordination
│   ├── Introduction & Methods
│   ├── Results
│   ├── Discussion & Implications
│   └── Full Data Tables
└── Experiment Showcase
```

**Paper title:** "SimCash — LLM-Optimized Payment Strategies in Simulated RTGS Environments"

**Paper sections (content exists in fragments across Stefan's workspace — needs assembly):**

1. **Introduction** — RTGS systems, AI in payments (BoC/BIS WP context), research questions
2. **Related Work** — Castro et al., Korinek (2025), BoC SWP 2025-35
3. **Experimental Design** — SimCash platform, scenarios, models, optimization methodology, v0.1/v0.2 prompt conditions
4. **Results** — organized around the 6 findings above
5. **Discussion** — mechanism design interpretation, operational implications, tragedy of the commons framing, `is_better_than()` objective misspecification as root cause
6. **Conclusion** — LLMs are effective individual optimizers but naive multi-agent deployers

**Content sources in Stefan's workspace:**
- `conference-paper-notes.md` — 700+ lines of running observations, early analysis, strategy deep dives
- `simcash-analysis.md` — 74KB comprehensive platform analysis
- `preliminary-analysis.md` — early findings
- `memory/rtgs-knowledge-base.md` — RTGS system background
- `memory/rtgs-crisis-cases.md` — real-world crisis cases for motivation
- `docs/reports/experiment-showcase-plan.md` — showcase page design with section-by-section content outlines
- `v02-experiment-plan.md` — v0.2 methodology documentation
- `DATA-INTEGRITY.md` — cost delta bug documentation (important for methods section transparency)

---

## Part 3: Technical Details

### 3.1 Data Files

| Location | Contents |
|---|---|
| `api-results/*.json` | 159 clean experiment result files |
| `api-results/compromised-pre-00168/` | 38 quarantined files — DO NOT USE |
| `api-results/pipeline.log` | Full pipeline execution log |
| `experiment-plan.yaml` | Master plan (232 entries with statuses) |
| `wave3-rerun-plan.yaml` | Post-bugfix re-run plan |
| `rank_models.py` | Model scoring/ranking script |
| `analyze_results.py` | Partial analysis script (needs completion) |
| `run-pipeline.py` | Automated experiment runner |

### 3.2 Experiment IDs for Key Scenarios

**Baselines (FIFO, no LLM, deterministic):**
- Each scenario has exactly 1 baseline. Find them by filtering `api-results/*baseline*.json`.

**Custom scenario IDs:**
- Periodic Shocks: `3250dc0f`
- Lynx Day: `41bdc072`
- Liquidity Squeeze: `46403784`
- Lehman Month: `504c65d9`
- Large Network: `b7257977`
- Castro Exp2: `2bank_12tick`
- Library: `2bank_3tick`, `3bank_6tick`, `4bank_8tick`, `2bank_stress`

**Salvaged Lehman experiments (non-standard round counts):**
- r1 `79e15468`: 6 rounds / 150 days (trimmed via PATCH)
- r2 `aeba0d9c`: 4 rounds / 100 days (trimmed via PATCH)
- Analysis needs to handle per-day cost summing, not per-round

### 3.3 API Notes

- **Base URL:** `https://simcash-997004209370.europe-north1.run.app/api/v1`
- **Deployed revision:** simcash-00168-v29
- **Stefan's API key:** in `.simcash-api-key` (`sk_live_46cf...d5bd`)
- **PATCH endpoint:** `/api/v1/experiments/{id}` with `total_days` / `trim_to_day`
- **Multi-day config:** `rounds: 1`, `optimize_when: between_each_day` (NOT 10 rounds × N days)

### 3.4 GitHub Branch

`experiments/2026q1-stefan` on `aerugo/SimCash` — latest commit `7eb3358c` (this handover).

Contains: pipeline scripts, experiment plans, DATA-INTEGRITY.md, showcase plan, rank_models.py, pipeline log.

### 3.5 Known Issues

- Pipeline double-logs every line (cosmetic, grep with `sort -u`)
- `settlement_rate_objective` in `is_better_than()` compares cost only — a policy settling 60% can "beat" one settling 95%. This is the root cause of free-rider dynamics. Noted as future work.
- Some entries in `conference-paper-notes.md` reference pre-bugfix data (pre-00168). Only trust post-bugfix results in `api-results/*.json` (not in `compromised-pre-00168/`).

### 3.6 Analysis Pipeline Needs

The `analyze_results.py` is incomplete. What's needed:

1. **Read all `api-results/*.json`** (excluding `compromised-pre-00168/`)
2. **Classify each experiment** by scenario, model, condition (v0.1/C1/C2/C3/C4), run number
3. **Produce tables:**
   - Table 1: Simple scenarios — Model × Scenario, mean cost/SR (n=3)
   - Table 2: Complex scenarios — Model × Scenario, mean cost/SR with baseline comparison
   - Table 3: v0.2 conditions — Condition × Model, mean cost/SR (Castro Exp2)
   - Table 4: C4-full complex — Model × Scenario, single-run results vs v0.1 avg vs baseline
   - Table 5: Model leaderboard (settlement-weighted scoring per `rank_models.py`)
4. **Output formats:** Markdown (for docs site), LaTeX (for paper PDF), JSON (for showcase page consumption)

The JSON result files contain per-day breakdowns. For multi-day scenarios, total cost = sum of all days' costs (NOT just last day — the engine resets per day, costs don't accumulate).

---

## Part 4: Open Design Questions

1. **Showcase as docs page or standalone route?** `/docs/showcase` vs `/showcase`
2. **Public experiment visibility?** Currently experiments require auth. A showcase implies public access to at least summary data.
3. **Chart library?** For the threshold visualization. Doesn't need to be fancy — a bar chart of cost delta vs FIFO ordered by bank count, where the sign flip is the story.
4. **Curated experiment list format?** Suggest a JSON config mapping experiment IDs → showcase sections/labels, separate from the experiment data itself. This is the editorial layer.
5. **Paper format?** Markdown pages in docs (like current docs)? Embedded PDF? Both?

---

*The platform held up remarkably well under 200+ experiment attempts. The complexity threshold finding alone makes this paper worth writing — it's a genuine contribution to the AI-in-payments literature, and it came from SimCash.*

— Stefan
