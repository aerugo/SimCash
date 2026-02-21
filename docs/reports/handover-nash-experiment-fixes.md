# Handover: Experiment Reproduction Fixes — for Nash

**From:** Dennis (Rust engine / Python orchestrator)
**To:** Nash (web sandbox)
**Date:** 2025-07-11

Hey Nash 👋

I've audited both codebases end-to-end — the experiment runner you were trying to replicate and your web implementation. Your failure analysis was accurate. Here's what I found and what to fix.

---

## The Good News

You reused the right components. `PolicyOptimizer`, `build_single_agent_context()`, `SystemPromptBuilder`, `filter_events_for_agent()`, `SingleAgentIterationRecord`, `WebBootstrapEvaluator` — the hard parts are all there and they work. The event filtering and agent isolation are correct. The prompt structure is correct.

## The Problem

You built `game.py` and `streaming_optimizer.py` from scratch instead of adapting `OptimizationLoop`. The components are solid but the wiring around them has three issues that together kill the optimization:

1. **Wrong starting point** — `DEFAULT_POLICY` uses fraction=1.0. The experiment runner hardcodes 0.5 in `_create_default_policy()`. At 1.0 everything settles perfectly, the LLM sees zero penalty signal, and it has no reason to change. It's stuck at a local optimum with no gradient.

2. **Bootstrap off by default** — `num_eval_samples` defaults to 1, which bypasses `WebBootstrapEvaluator` entirely. Every LLM proposal gets accepted unconditionally. The experiment runner uses 50 samples with a 3-layer acceptance gate (mean improvement > 0, 95% CI above zero, CV ≤ 0.5).

3. **Degraded prompt inputs** — You're passing `cost_std=0` and `was_accepted=True` for every history entry. The LLM can't learn from failures because it never sees any, and it can't reason about variance because you're telling it there is none. The `SingleAgentIterationRecord` already has the right fields — they're just not getting real values.

## What to Fix (in priority order)

### Fix 1: Starting Fraction → 0.5 (30 min)

`game.py:26`, change `DEFAULT_POLICY`:
```python
"parameters": {"initial_liquidity_fraction": 0.5},  # was 1.0
```

This alone will likely unblock convergence. The LLM needs to start in a region where it can see both liquidity costs AND penalty costs.

### Fix 2: Default Bootstrap to ≥10 Samples (1-2 hours)

Your `WebBootstrapEvaluator` already works. Just make it the default:
```python
num_eval_samples = max(num_eval_samples, 10)  # experiment runner uses 50
```

When bootstrap is on, your code already does paired comparison, CI checks, and CV thresholds. You just need to wire the acceptance result through to the iteration history (see Fix 3).

### Fix 3: Pass Real Values to Iteration History (2-3 hours)

In `streaming_optimizer.py`, wherever you create `SingleAgentIterationRecord`:
- Pass the actual `was_accepted` from bootstrap evaluation (not hardcoded `True`)
- Compute real `cost_std` from per-seed costs when `num_eval_samples > 1`
- Track `is_best_so_far` against a running best that only updates on acceptance

The LLM prompt then shows ⭐/✅/❌ markers that teach it which directions work and which don't.

### Fix 4: Wire Experiment Config Fields (4-6 hours)

The paper configs have fields your platform ignores. Most impactful:

- **`prompt_customization.all`** — experiment-specific guidance text injected into the system prompt. The exp2 config has a whole paragraph about the liquidity/penalty tradeoff. The `SystemPromptBuilder` already supports this via the `customization` parameter.
- **`policy_constraints`** — exp2 restricts the LLM to just `initial_liquidity_fraction` with `[Release, Hold]` actions. Without this, the LLM wastes iterations generating complex trees instead of exploring the one parameter that matters.

### Fix 5: Convergence Detection (2 hours, optional)

Track the last N fractions per agent. If unchanged for 5 iterations, stop early. Saves LLM calls after convergence. Not critical for correctness.

## Reproduction Test

After fixes 1-3, run exp2 config:
- `num_eval_samples=50`, `max_days=25`, starting fraction=0.5
- Any GPT-4 class model or better

Expected: Both agents converge to fraction ~0.06-0.08 within 15-20 iterations. If they don't, add the `prompt_customization` text from `docs/papers/simcash-paper/paper_generator/configs/exp2.yaml` (Fix 4).

## Full Reference Docs

All pushed to main:
- `docs/reports/experiment-runner-audit.md` — Complete trace of the experiment runner (optimization loop, acceptance mechanism, prompt construction, seed management)
- `docs/reports/web-platform-audit.md` — Complete trace of your web implementation with every gap identified
- `docs/reports/experiment-runner-vs-web-comparison.md` — Side-by-side comparison with prioritized fix list

The bottom line: you have all the right pieces, they're just not wired up correctly. Fixes 1-3 are mostly changing defaults and passing real values where constants are hardcoded. The infrastructure already supports it.

Good luck 🏦
