# Experiment Showcase Page — Design Report

**Author:** Stefan (Research Director)  
**Date:** 2026-02-27  
**For:** SimCash docs at `https://simcash-487714.web.app/docs`

## Purpose

A single page that lets visitors see the breadth of SimCash experiments at a glance — grouped to tell a story, with summary metrics and direct links to each full experiment. This is the page we point people to when introducing SimCash. It should work as both a showcase ("look what this platform can do") and a research summary ("here's what we found").

## Proposed Location in Docs

Add under **Research Papers** in the sidebar navigation:

```
Research Papers
  SimCash: LLM-Optimized Payment Coordination
    📄 Introduction & Methods
    📊 Results
    💬 Discussion & Conclusion
    📋 Detailed Data
  🔬 Experiment Showcase    ← NEW
```

Alternatively, it could be a top-level section between "Research Papers" and "Advanced Topics" if we want more prominence. A top-level placement says "this is a living gallery" rather than "this is part of one paper."

## Page Structure

### Title & Intro

**Title:** "Experiment Gallery: 150+ LLM Optimization Runs Across 9 Scenarios"

Opening paragraph (2-3 sentences): What visitors are looking at, how many experiments, which models, what the key finding is. Something like:

> *We ran over 150 experiments testing whether general-purpose LLMs can discover effective payment strategies in simulated RTGS environments. Three models (Gemini 2.5 Flash, Gemini 2.5 Pro, GLM-4.7) competed across 9 scenarios ranging from simple (2 banks, 1 day) to complex (6 banks, 30 days of crisis). The headline finding: LLM optimization delivers 30–85% cost reduction on simple scenarios but produces collectively worse outcomes on complex ones — a computational tragedy of the commons.*

### Key Metrics Bar

A compact visual strip at the top showing aggregate stats:
- **Total experiments:** 150+
- **Models tested:** 3 (Flash, Pro, GLM-4.7)
- **Scenarios:** 9
- **Optimization rounds:** 10 per experiment
- **Key finding:** Complexity threshold at ~4 banks

---

### Section 1: "The Basics — Can LLMs Optimize at All?"
**Story:** Start with the simplest scenarios to prove the concept works.

#### 1a. Two Banks, One Day (2B 3T)
- **Baseline:** $99,900 / 100% SR
- **What to show:** All 3 models achieve 100% settlement while reducing costs. LLM optimization works in the simplest case.
- **Experiments:** 1 baseline + 9 optimized (3 models × 3 runs)
- **Link format:** Each experiment links to its full detail page (`/experiment/{id}`)
- **Summary table:** Model | Avg Cost | Avg SR | Best Run | Worst Run

#### 1b. Three Banks (3B 6T)
- Same structure. Shows optimization scales to 3 banks — still near-perfect settlement.
- **Experiments:** 1 baseline + 9 optimized

#### 1c. Four Banks (4B 8T)
- Transition zone. First hints of settlement degradation in some runs.
- **Experiments:** 1 baseline + 9 v0.1 + 6 C4-full
- Note: Include both v0.1 and C4-full results to show prompt improvement effects

**Section insight callout:** *"On simple scenarios (2–4 banks), LLM optimization consistently reduces system costs by 30–85% while maintaining near-perfect settlement. All three models perform well, though with different cost profiles."*

---

### Section 2: "The Threshold — Where Cooperation Breaks Down"
**Story:** As networks grow, individual optimization becomes collective destruction.

#### 2a. Periodic Liquidity Shocks (5 banks, 30 days)
- **Baseline:** $611M / 77% SR
- **The finding:** LLM optimization makes BOTH cost and settlement WORSE
- **Experiments:** 1 baseline + 3 Flash reruns (+ Pro reruns when complete)
- **Summary table** with delta vs baseline (show the +9% to +32% cost increase)
- **Callout:** "The LLM agents individually hoard liquidity to minimize their own costs. When a shock hits and everyone is hoarding, the system has no buffer — costs spike and payments fail."

#### 2b. Large Network Steady State (5 banks, 25 days)
- Same pattern without the shocks — proves it's network size, not volatility
- **Experiments:** 1 baseline + 3 Flash + 3 Pro reruns

#### 2c. Lehman Month (6 banks, 25 days of escalating crisis)
- The hardest scenario. Largest network + stress dynamics
- **Experiments:** 1 baseline + results when complete

**Section insight callout:** *"Above ~4 banks, LLM optimization produces a tragedy of the commons. Each agent's individually rational strategy (hold liquidity, wait for incoming payments) is collectively destructive. The smarter the model, the worse the collective outcome — Pro consistently achieves lower settlement than Flash."*

---

### Section 3: "The Two-Bank Deep Dive — Castro Experiment 2"
**Story:** The most extensively studied scenario, replicating a published paper's setup.

#### 3a. Baseline Comparison (v0.1)
- **Castro Exp2 (2bank_12tick):** 2 banks, 12 ticks, 10 optimization rounds
- **Experiments:** 1 baseline + 9 (3 models × 3 runs)
- **Relevance:** Replicates the setup from BoC/BIS Working Paper on AI cash management

#### 3b. Prompt Engineering Experiment (v0.2)
- **The question:** Can we improve LLM behavior through prompt design?
- **Four conditions tested:**
  - C1: Information only (tell the LLM about settlement rates)
  - C2: Settlement floor (minimum 80% settlement constraint)
  - C3: Guidance (describe available strategy tools)
  - C4: Full composition (all of the above)
- **Experiments:** 48 (4 conditions × 3 models × ~4 runs each)
- **Key finding:** Constraints (C2) >> Information (C1). Adding information alone has zero effect. Adding a settlement floor constraint is the single most impactful intervention.
- **Model comparison table:** Flash dominates under constraints (79% of max score)

#### 3c. Retry Mechanism (Phase C)
- **The question:** Does giving the LLM a second chance after rejection improve convergence?
- **Experiments:** 36 (4 conditions × 3 models × 3 runs, all with max_policy_proposals=2)
- **Finding:** Retries help Pro more than others but don't dramatically change the ranking

**Section insight callout:** *"Model selection matters more than prompt engineering. The gap between Flash and GLM under identical conditions exceeds the gap between any two prompt conditions for a single model. But when you combine the right model (Flash) with the right constraint (settlement floor), you get near-optimal outcomes."*

---

### Section 4: "Stress Tests"
**Story:** How do the models handle adverse conditions?

#### 4a. High Stress (2B Stress)
- 2 banks under elevated payment pressure
- **Experiments:** 1 baseline + 9 optimized

#### 4b. Liquidity Squeeze (5 banks, sudden liquidity drain)
- Custom scenario with a mid-day liquidity shock
- **Experiments:** 1 baseline + (results when re-runs complete)

**Section insight callout:** *"Under stress, model differences amplify. Flash maintains robustness; GLM struggles with settlement; Pro is inconsistent but occasionally brilliant."*

---

### Section 5: "Special Scenarios"
**Story:** Edge cases and design explorations

#### 5a. Lynx Day (realistic Canadian RTGS profile)
- Based on Bank of Canada's Lynx system parameters
- **Finding:** All models achieve optimal cost ($3) and 100% settlement — the scenario is too simple to differentiate
- **Experiments:** 1 baseline + 9 optimized

---

### Section 6: "Model Leaderboard"
A sortable summary table across ALL experiments:

| Model | Total Runs | Avg Cost Reduction | Avg SR | Best Scenario | Worst Scenario |
|---|---|---|---|---|---|
| Flash | ~50 | ... | ... | ... | ... |
| Pro | ~45 | ... | ... | ... | ... |
| GLM | ~45 | ... | ... | ... | ... |

Plus the v0.2 scoring breakdown (settlement + cost ranking).

---

## Design Notes

### Experiment Cards
Each experiment should have a compact card showing:
- Scenario name + model badge (color-coded: Flash=blue, Pro=purple, GLM=green)
- Total cost + settlement rate
- Delta vs baseline (green/red)
- Link to full experiment detail page
- Run number (r1/r2/r3) for replication visibility

### Visual Elements
- **Cost vs SR scatter plot** per section — each dot is one experiment, colored by model
- **Baseline reference line** on all charts
- **Complexity threshold visualization** — a single chart showing cost delta vs baseline across all scenarios, ordered by bank count. The sign flip from negative (good) to positive (bad) at 5 banks IS the headline chart.

### Linking Strategy
Every experiment should deep-link to its full detail page on SimCash (`/experiment/{id}`). This lets visitors drill into any result — see the policy trees, per-bank costs, optimization trajectory, balance charts.

For this to work, we need a mapping from experiment IDs to the showcase groupings. The API can provide this via `GET /experiments?user=stefan@sensestack.xyz`.

### What NOT to Include
- Compromised pre-00168 experiments (moved to `api-results/compromised-pre-00168/`)
- Canary/test experiments (IDs: c39e6ef1, b772b210, 03500ad5, f5c3c63c, 6f896b8e)
- GLM results on complex scenarios (not re-run, insufficient data)
- Any experiment where `num_ticks=0` on all days (checkpoint-restored, potentially corrupted)

### Page Length
This will be a long page. Consider:
- Collapsible sections (expand/collapse per scenario group)
- Sticky section navigation on the left (like the existing docs sidebar)
- "Jump to" links at the top
- Default: show summary tables, click to expand individual experiment cards

## Implementation Path

This page should be implemented in the SimCash frontend (Svelte), not as static markdown, because:
1. It needs to link to live experiment pages
2. Experiment data should be pulled from the API (not hardcoded)
3. Charts require JavaScript
4. The page should auto-update as new experiments complete

**Suggested approach:**
1. Create a curated experiment list (JSON config mapping experiment IDs to sections/labels)
2. Build a Svelte component that fetches experiment summaries from the API
3. Render grouped cards with summary stats
4. Add the page to the docs sidebar navigation

The curated list is the editorial layer — it decides what's shown and how it's grouped. The API provides the data. This separation means we can add new experiments to the showcase by updating one config file.

## Experiment Count Summary

| Section | Scenario | Experiments | Status |
|---|---|---|---|
| 1a | 2B 3T | 10 | ✅ Complete |
| 1b | 3B 6T | 10 | ✅ Complete |
| 1c | 4B 8T | 16 | ✅ Complete |
| 2a | Periodic Shocks | 4+ | 🏃 Re-runs in progress |
| 2b | Large Network | 6+ | 🏃 Re-runs in progress |
| 2c | Lehman Month | 1+ | 🏃 Re-runs in progress |
| 3a | Castro Exp2 v0.1 | 10 | ✅ Complete |
| 3b | Castro Exp2 v0.2 | 48 | ✅ Complete |
| 3c | Castro Exp2 retry | 36 | ✅ Complete |
| 4a | 2B Stress | 10 | ✅ Complete |
| 4b | Liq Squeeze | 1 | ⏳ Baseline only (re-runs deferred) |
| 5a | Lynx Day | 10 | ✅ Complete |
| 6 | Leaderboard | — | Aggregate |
| **Total** | | **~160+** | |

## Open Questions for Hugi/Nash

1. **Should this be a docs page or a standalone route?** (e.g., `/showcase` vs `/docs/showcase`)
2. **Do we want public experiment links?** Currently experiments require auth. A showcase page implies public visibility.
3. **Chart library preference?** The existing docs don't seem to use charts. Chart.js? D3? Simple SVG?
4. **Should the curated list be a separate API endpoint?** e.g., `GET /api/v1/showcase` returning the grouped experiment config.
