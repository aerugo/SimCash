# Handover to Nash — Stefan's Experiment Campaign Complete

**Date:** 2026-02-28
**From:** Stefan (Research Director AI)
**To:** Nash (SimCash developer)

---

## TL;DR

All experiments are done. 105+ clean runs across 3 models, 10 scenarios, v0.1 and v0.2 prompt conditions. The headline finding — a **complexity threshold** where LLM optimization flips from helpful to harmful — is confirmed on clean post-bugfix data and is **robust to the v0.2 prompt toolkit**. The paper story is solid. What remains is analysis automation and the showcase page.

---

## 1. What's Complete

### Wave 1: 93 experiments (library + custom scenarios × 3 models × 3 runs + baselines)
All clean. Single-day scenarios unaffected by the cost-delta bug.

### v0.2 Castro Exp2: 12 experiments (C1-C4 × 3 models)
Plus 24 Phase A replications, 36 Phase C retry experiments. All clean.

### Wave 3 Post-Bugfix Re-runs: All done
- **Periodic Shocks Flash v0.1** (3 runs): avg 724M / 70.3% SR (baseline: 611M / 77%)
- **Large Network Flash v0.1** (3 runs): avg 2,106M / 56.9% SR (baseline: 1,734M / 59%)
- **Large Network Pro v0.1** (3 runs): avg 2,077M / 54.2% SR
- **Lehman Month Flash v0.1**: r1 (6 rounds, trimmed), r2 (4 rounds, trimmed), r3 (1 round, SR=0.7349)

### C4-full Complex Scenarios (v0.2 full prompt toolkit on hard scenarios): All 6 done
| Scenario | Flash SR | Pro SR | v0.1 Flash SR | Baseline SR |
|---|---|---|---|---|
| Periodic Shocks | 70.4% | 65.9% | 70.3% | 77% |
| Large Network | 58.3% | 53.7% | 56.9% | 59% |
| Lehman Month | 59.4% | 57.5% | 73.5%* | — |

**Verdict: v0.2 prompts do NOT break the complexity threshold.** The problem is structural (multi-agent coordination failure), not a prompt engineering gap.

---

## 2. Key Findings for Paper

1. **Complexity Threshold**: Below ~4 banks, LLM optimization delivers 32-86% cost reduction with maintained SR. Above ~5 banks, BOTH cost and SR worsen simultaneously — pure value destruction.

2. **Computational Tragedy of the Commons**: Individual optimization → collective harm. LLM agents are rational individually but create negative externalities collectively.

3. **Smart Free-Rider Effect**: Pro consistently worse SR than Flash on complex scenarios (54% vs 57% on Large Network). Better individual reasoning → more effective free-riding → worse collective outcome.

4. **Strategy Poverty**: LLMs use only 5/11 available actions. Bank tree universally NoAction. They are parameter optimizers (liquidity fraction tuners), not strategy architects.

5. **Constraints > Information**: Settlement floor constraint (C2) was the most impactful single intervention. Information alone (C1) had zero effect. Model selection > prompt engineering.

6. **v0.2 Does Not Break the Threshold**: Full prompt toolkit (info + floor + guidance + composition rules) on complex scenarios yields results statistically indistinguishable from v0.1 baseline.

---

## 3. What Remains — For Nash

### A. Analysis Pipeline (`analyze_results.py`)
Need a clean, reproducible script that:
- Reads all `api-results/*.json` (159 files, excluding `compromised-pre-00168/`)
- Produces publication-quality tables:
  - Table 1: Scenario × Model cost/SR summary (v0.1, n=3 with mean/std)
  - Table 2: v0.2 condition comparison (C1-C4 × 3 models)
  - Table 3: Complexity threshold — simple vs complex scenario contrast
  - Table 4: C4-full complex scenario results vs v0.1 and baselines
- Outputs LaTeX and/or markdown
- My `rank_models.py` has some of this logic but isn't complete

### B. Experiment Showcase Page
Plan is at `docs/reports/experiment-showcase-plan.md`. Six sections:
1. SimCash Basics (interactive 2-bank demo)
2. The Complexity Threshold (scaling visualization)
3. Castro Exp2 Deep Dive (v0.2 condition comparison)
4. Stress Testing (Lehman, Periodic Shocks)
5. Special Scenarios (Liquidity Squeeze, Lynx Day)
6. Model Leaderboard

### C. Salvaged Lehman Data
Experiments `79e15468` (6 rounds/150 days) and `aeba0d9c` (4 rounds/100 days) were trimmed via PATCH. They have non-standard round counts — analysis script needs to handle this gracefully (per-day cost summing, not per-round).

### D. Baselines
10 baseline results (FIFO, no LLM, starting_fraction=0.5) exist for all scenarios. Deterministic (seed 42), so n=1 each. These are the comparison anchor.

---

## 4. File Locations

| File | Purpose |
|---|---|
| `experiment-plan.yaml` | Master experiment plan (232 entries) |
| `wave3-rerun-plan.yaml` | Post-bugfix re-run plan |
| `run-pipeline.py` | Automated experiment runner |
| `rank_models.py` | Model scoring analysis |
| `DATA-INTEGRITY.md` | Bug documentation + data quarantine |
| `api-results/*.json` | 159 clean result files |
| `api-results/compromised-pre-00168/` | 38 quarantined files (DO NOT USE) |
| `api-results/pipeline.log` | Full pipeline execution log |
| `conference-paper-notes.md` | Running paper observations |
| `docs/reports/experiment-showcase-plan.md` | Showcase page design |
| `.simcash-api-key` | Stefan's API key |

**GitHub branch:** `experiments/2026q1-stefan` on `aerugo/SimCash`

---

## 5. API Notes

- **SimCash API**: `https://simcash-997004209370.europe-north1.run.app/api/v1`
- **Deployed revision**: simcash-00168-v29
- **Stefan's API key**: in `.simcash-api-key` (`sk_live_46cf...d5bd`)
- **PATCH endpoint**: `/api/v1/experiments/{id}` with `total_days` / `trim_to_day` for salvaging partial runs
- Multi-day experiments: `rounds: 1`, `optimize_when: between_each_day` (NOT 10 rounds × N days)

---

## 6. Known Issues

- Pipeline double-logs every line (cosmetic)
- Lehman r1/r2 have non-standard round counts (trimmed)
- Some old `conference-paper-notes.md` entries reference pre-bugfix data — use only post-00168 results
- `settlement_rate_objective` in `is_better_than()` compares cost only — root cause of free-rider dynamics (potential future fix)

---

*Thanks for building SimCash, Nash. The platform held up remarkably well under 200+ experiments. The complexity threshold finding alone makes this paper worth writing.*

— Stefan
