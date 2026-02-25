# Handover: Settlement Optimization Work

**From:** Nash (with Hugi)  
**To:** Stefan  
**Date:** 2026-02-25  
**Branch:** `feature/interactive-web-sandbox`

---

## TL;DR

We found that SimCash agents optimize cost but **ignore settlement rate entirely** — a policy that settles 60% of payments can beat one that settles 95% if it's cheaper. We wrote a diagnosis report, then implemented a 4-phase fix across the prompt pipeline and acceptance logic. Everything's committed and tests pass, but nothing's been run in a real experiment yet.

---

## The Problem

Stefan, you nailed this in your earlier feedback: the LLMs are parameter optimizers, not strategy architects. We dug into *why* and found something more fundamental than prompt quality:

**Settlement rate has zero influence on policy acceptance.**

- `EvaluationResult.is_better_than()` → compares `mean_cost` only
- `optimization.py` acceptance → `total_cost` only  
- `bootstrap_gate.py` → cost deltas only
- `streaming_optimizer.py` → same

So the entire optimization loop rewards cost reduction with no floor on settlement. An agent can "improve" by just not attempting payments (lower delay costs, lower collateral costs — because nothing's queuing). The settlement rate metric exists in results but nobody checks it.

On top of that, the prompts give the LLM no quantitative context about the RTGS balance — no pool size, no demand ratio, no balance trajectory. The LLM tunes `initial_liquidity_fraction` by pure trial-and-error on cost numbers.

---

## What We Did

### 1. Diagnosis Report

`docs/reports/prompt-improvement-recommendations.md` — 7 gaps identified, with Dennis's and your feedback incorporated (feasibility ratio, iteration depth variable, `target_tick` as diagnostic). This is the analytical foundation.

### 2. Implementation Plan

`docs/reports/settlement-optimization-plan.md` — 4-phase plan. Committed as `7700b0cb`.

### 3. Code (4 phases, all in `e31ea220`, test fix in `654a8914`)

**Phase 1 — Information fixes** (so the LLM can *see* the problem):
- **1a**: Liquidity context in user prompt — pool size, committed amount, demand/committed ratio (`single_agent_context.py`)
- **1b**: Per-tick balance trajectory with `available_liquidity` column and feasibility ratio (`event_filter.py` → `extract_balance_trajectory()`)
- **1c**: Deferred crediting emphasis in system prompt — conditional on scenario having deferred crediting enabled (`system_prompt_builder.py`)

**Phase 2 — Settlement floor** (so the loop *enforces* settlement):
- **2a**: Bootstrap gate rejects policies below `min_settlement_rate` (default 0.95, configurable via `bootstrap_thresholds`)
- **2b**: Experiment runner's `_should_accept_policy` checks settlement rate
- **2c**: System prompt tells the LLM about the constraint; user prompt shows urgent warning when settlement drops below floor

**Phase 3 — Search guidance** (help the LLM navigate the tradeoff):
- **3a**: Crunch tradeoff detection — when both delay >20% and liquidity opportunity >20% of costs, explains the RTGS balance tension
- **3b**: Worst-seed summary with critical failure moments

**Phase 4 — Tree composition** (your experimental variable idea):
- **4a**: Toggleable prompt block describing `SetReleaseBudget`, `bank_state_*` fields, evaluation order
- **4b**: Wired through `prompt_config.tree_composition` in game settings, defaults OFF

**Stats:** 701 lines added across 11 files. 17 new tests + all 594 existing ai_cash_mgmt tests passing. Frontend builds clean.

---

## What's NOT Done

1. **No experiments run yet.** All code is committed but untested against real LLM optimization runs.
2. **Callers need wiring.** The new `SingleAgentContext` fields (`liquidity_pool`, `expected_daily_demand`, `balance_trajectory`, `worst_seed_summary`) need their data passed in from experiment configs. The extraction functions exist but the experiment runner doesn't populate them yet for all scenarios.
3. **Your iteration depth idea** (10 vs 25 rounds) — noted in the report as an experimental variable but not implemented as a preset.

---

## What To Try Next

The experimental design from the report:

| Run | Gaps Enabled | Rounds | Purpose |
|-----|-------------|--------|---------|
| Baseline | None (current prompts) | 10 | Control |
| Info-only | 1-3 | 10 | Does seeing the balance help? |
| Info + Floor | 1-3 + settlement floor | 10 | Does the constraint change behavior? |
| Full (no composition) | 1-3 + floor | 25 | Your iteration depth question |
| Full + composition | 1-3 + floor + Gap 5 | 25 | Does tree composition guidance help? |

Your `target_tick` diagnostic prediction: if Gap 3 works, agents should discover `target_tick`-based scheduling as their first structural innovation. If they don't, it's evidence of an understanding→action gap. Worth watching for in the logs.

---

## Key Files

- Report: `docs/reports/prompt-improvement-recommendations.md`
- Plan: `docs/reports/settlement-optimization-plan.md`  
- Balance trajectory: `api/payment_simulator/ai_cash_mgmt/prompts/event_filter.py` (`extract_balance_trajectory`)
- Liquidity context: `api/payment_simulator/ai_cash_mgmt/prompts/single_agent_context.py` (`_build_liquidity_context`)
- Settlement floor: `web/backend/app/bootstrap_gate.py` + `streaming_optimizer.py`
- Tree composition toggle: `system_prompt_builder.py` (`_build_policy_architecture`)
- Tests: `tests/ai_cash_mgmt/unit/test_settlement_optimization.py`

---

## Commits (chronological)

```
db27b96b docs: prompt improvement recommendations for liquidity crunch discovery
91c021b8 docs: revise prompt recommendations with Dennis's feedback
7d71ab87 docs: incorporate Stefan's feedback on prompt recommendations
7700b0cb docs: phased implementation plan for settlement optimization
e31ea220 feat: implement settlement optimization phases 1-4
654a8914 fix: repair test breakage from settlement optimization changes
```

All on `feature/interactive-web-sandbox`.
