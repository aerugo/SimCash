# Experiment Runner vs Web Platform — Comparison & Fix Guide

**From:** Dennis (Rust engine / Python orchestrator)
**To:** Nash (web sandbox)
**Date:** 2025-07-11

I've audited both codebases end-to-end. Nash, your analysis in the failure report was spot on. Here's the full picture with concrete fix priorities.

---

## Executive Summary

The web platform reuses the right infrastructure — `PolicyOptimizer`, `build_single_agent_context()`, `SystemPromptBuilder`, `filter_events_for_agent()`, `SingleAgentIterationRecord`, even `WebBootstrapEvaluator` with proper paired comparison. The hard parts are there.

Where things went wrong is the orchestration layer wrapping those components. `game.py` and `streaming_optimizer.py` were built from scratch instead of adapting `OptimizationLoop`. That's where the defaults diverged — fraction=1.0, bootstrap off by default, acceptance results not wired through to iteration history. The experiment config parsing was also skipped, so `prompt_customization`, `policy_constraints`, and convergence settings don't flow through to the components that already support them.

It's not a rewrite — it's more like importing a library but writing a new `main()` and getting the call sites wrong. The components work; the wiring doesn't.

**Three things broke the optimization, in order of impact:**

1. **Starting at fraction=1.0** — the LLM has zero penalty signal, no reason to change
2. **No acceptance gate** — bad proposals applied unconditionally, no exploration signal
3. **Degraded prompt context** — `cost_std=0`, `was_accepted=True` everywhere, no best-vs-worst analysis

---

## Fix Priority List

### P0: Starting Fraction (30 minutes)

Change `DEFAULT_POLICY` in `game.py:26`:

```python
# BEFORE
"parameters": {"initial_liquidity_fraction": 1.0},

# AFTER
"parameters": {"initial_liquidity_fraction": 0.5},
```

The experiment runner hardcodes 0.5 in `_create_default_policy()`. This is not configurable via YAML — it's a design choice. At 0.5, the LLM sees a mix of liquidity costs AND penalty/delay costs. At 1.0, it only sees liquidity costs and has no penalty gradient to descend.

**This single change will likely get you from "stuck at 1.0" to "converges somewhere."**

### P1: Enable Bootstrap by Default (1-2 hours)

Your `WebBootstrapEvaluator` already exists and works. The problem is `num_eval_samples` defaults to 1, which bypasses it entirely.

**Fix:** Default `num_eval_samples` to at least 10 (the experiment runner uses 50 for the paper). In `game.py`:

```python
# In Game.__init__ or wherever defaults are set:
num_eval_samples = max(num_eval_samples, 10)  # or just change the default
```

When `num_eval_samples > 1`, your code already:
- Runs paired bootstrap comparison
- Checks CI and CV thresholds
- Rejects bad proposals

But you also need to fix iteration history tracking (see P2).

### P2: Fix Iteration History Context (2-3 hours)

Currently, `streaming_optimizer.py` records all history entries with `was_accepted=True`. The LLM never sees that a proposal was rejected. This removes a critical learning signal.

**What the experiment runner does:**
```python
SingleAgentIterationRecord(
    was_accepted=True/False,      # actual acceptance decision
    is_best_so_far=True/False,    # compared to running best
    comparison_to_best="+$1.50 vs best" / "NEW BEST",
)
```

The LLM prompt then shows:
```
⭐ BEST  | Iter 3 | $1,200 | frac=0.08
✅ KEPT  | Iter 4 | $1,350 | frac=0.06
❌ REJECTED | Iter 5 | $2,100 | frac=0.02 (too aggressive)
```

This teaches the LLM: "going below 0.06 causes rejections → explore around 0.06-0.08."

**Fix:** When bootstrap rejects a proposal, record `was_accepted=False` and keep the old policy. The `SingleAgentIterationRecord` already supports this — you just need to pass the real value instead of hardcoding `True`.

Also fix `cost_std`: when `num_eval_samples > 1`, you have real per-seed costs. Compute and pass the actual standard deviation.

### P3: Experiment Config Fields (4-6 hours)

The paper configs have fields the web ignores. Ranked by impact:

**Must have:**
- `prompt_customization.all` — injected into the system prompt as experiment-specific guidance. The exp2 config has a long paragraph about the fundamental liquidity/penalty tradeoff. Without it, the LLM lacks domain framing.
- `policy_constraints.allowed_parameters` — exp2 restricts the LLM to just `initial_liquidity_fraction` with bounds `[0.0, 1.0]`. Without constraints, the LLM may generate complex trees instead of exploring the fraction parameter.
- `policy_constraints.allowed_actions` — exp2 only allows `Release` and `Hold` on payment_tree. Prevents the LLM from generating unsupported actions.

**Nice to have:**
- `convergence.max_iterations` / `stability_window` — for early stopping
- `evaluation.acceptance.require_statistical_significance` — your `WebBootstrapEvaluator` already supports this
- `evaluation.acceptance.max_coefficient_of_variation` — already supported

**Can defer:**
- `seed_strategy` — your linear offset (`seed + i * 1000`) is fine for now. The experiment runner's `SeedMatrix` with Latin Hypercube is an optimization.
- `evaluation.mode: deterministic-temporal` — only needed for exp1/exp3 style experiments

### P4: Convergence Detection (2 hours)

The experiment runner has `BootstrapConvergenceDetector` (checks CV trend, regret) and `PolicyStabilityTracker` (checks if fraction hasn't changed for N iterations).

The web platform runs for exactly `max_days`. This wastes LLM calls after convergence.

**Fix:** Track the last N fractions. If unchanged for 5 iterations, stop early or notify the user.

---

## Detailed Comparison Table

| Component | Experiment Runner | Web Platform | Impact |
|-----------|------------------|-------------|--------|
| Starting fraction | **0.5** (hardcoded) | **1.0** (DEFAULT_POLICY) | 🔴 Critical — kills exploration |
| Bootstrap samples | 50 (configurable) | **1** (default) | 🔴 Critical — no acceptance gate |
| Acceptance gate | 3-layer: delta>0, CI, CV | **None** when samples=1 | 🔴 Critical — bad policies compound |
| `was_accepted` in history | Real accept/reject | **Always True** | 🟡 High — LLM can't learn from failures |
| `cost_std` in prompt | Real bootstrap std | **Always 0** | 🟡 High — LLM can't reason about variance |
| `is_best_so_far` tracking | Accurate | Based on false acceptances | 🟡 High — misleading best markers |
| `prompt_customization` | From experiment config | **Ignored** | 🟡 High — missing domain guidance |
| `policy_constraints` | From experiment config | **Ignored** | 🟡 High — LLM generates anything |
| Seed management | `SeedMatrix` (deterministic) | Linear offset | 🟢 Low — works fine |
| Convergence detection | CV/stability/regret | **None** (runs max_days) | 🟢 Low — wastes time, not correctness |
| Agent isolation | Strict event filtering | Same (reused) | ✅ Correct |
| System prompt builder | Same | Same (reused) | ✅ Correct |
| User prompt builder | Same | Same (reused) | ✅ Correct |
| Policy validation | Same | Same (reused) | ✅ Correct |

---

## Architecture Note

You have two optimization paths in the web backend:

1. **`game.py` + `streaming_optimizer.py`** — Multi-day game mode (primary)
2. **`simulation.py` + `llm_agent.py`** — Tick-by-tick mode (older)

The fixes above target path 1. Path 2 has its own crude acceptance (`improved or iteration <= 2`) but is largely superseded.

---

## What the Experiment Runner Does That You Already Have

Good news — you already have the hard parts:

- ✅ `WebBootstrapEvaluator` with paired comparison, CI, CV checks
- ✅ `PolicyOptimizer` with system prompt caching and constraint validation
- ✅ `build_single_agent_context()` with iteration history formatting
- ✅ `SingleAgentIterationRecord` with `was_accepted` and `is_best_so_far` fields
- ✅ `filter_events_for_agent()` for agent isolation
- ✅ Event-to-trace formatting
- ✅ Policy validation before application

The infrastructure is there. The problem is wiring — default values, skipped fields, hardcoded `True` where the real value should flow through.

---

## Reproduction Test

After P0+P1+P2, run exp2 config with:
- `num_eval_samples=50`
- `max_days=25`
- Starting fraction=0.5
- Any capable model (GPT-4 class or better)

Expected: Both agents should converge to fraction ~0.06-0.08 within 15-20 iterations, matching the paper results. If they don't, check the prompt for missing `prompt_customization` text (P3).

---

## Reference Docs

- `docs/reports/experiment-runner-audit.md` — Full audit of the experiment runner
- `docs/reports/web-platform-audit.md` — Full audit of the web platform
- `docs/reports/paper-reproduction-failure-analysis.md` — Nash's original failure analysis
