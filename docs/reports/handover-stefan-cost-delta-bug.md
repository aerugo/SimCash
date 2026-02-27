# Cost Delta Bug — Impact Assessment & Fix

**For:** Stefan  
**From:** Nash  
**Date:** 2026-02-27  
**Status:** Fixed, tests passing

## What Happened

A bug in `web/backend/app/game.py` produced **negative costs** in certain experiments. Dennis diagnosed the root cause (thanks Dennis).

### The Bug

I wrote a function `_compute_cost_deltas()` that assumed the Rust engine accumulates costs cumulatively across days within a persistent Orchestrator. It subtracted the previous day's costs from the current day's costs to get a "delta."

**The assumption was wrong.** The engine resets cost accumulators to zero at each day boundary (`engine.rs:2973`). The values are already per-day. So my code was subtracting two independent values — and when the optimizer successfully reduced costs (day N < day N-1), the result went negative.

### The Fix

Deleted `_compute_cost_deltas()` and `_get_previous_day_in_round()` entirely. The raw cost values from the engine are already what we want. Added assertions that costs are non-negative. 15 TDD tests cover this, including a reproduction of the exact bug.

**Commit:** On branch `feature/interactive-web-sandbox`, not yet pushed.

## Impact on Your Experiments

### Good news: your standard experiments are NOT affected.

The bug only triggers in **intra-scenario mode** — experiments where the scenario YAML has `num_days > 1` (multi-day crisis scenarios). This is because:

1. All built-in scenarios (`2bank_2tick`, `2bank_12tick`, `3bank_6tick`, etc.) have `num_days: 1` (the default).
2. When `num_days ≤ 1`, the code at `game.py:188` normalizes the schedule to `"every_round"`, and `_get_previous_day_in_round()` always returns `None`.
3. When `prev_day is None`, `_compute_cost_deltas` just copies the values as-is: `day_total_cost = total_cost`. No subtraction happens.

**The broken path only executes when `_scenario_num_days > 1`**, which requires a custom scenario with an explicit multi-day configuration (e.g., the 10-day crisis scenario from game `7e314cdd`).

### What this means

- **Standard experiments** (all built-in scenarios): ✅ Costs are correct. LLM optimization prompts received correct data. **No re-runs needed.**
- **Intra-scenario experiments** (custom `num_days > 1`): ❌ Costs were corrupted AND fed into optimization prompts. Those experiments need re-running.

### How to verify your specific experiments

If you want to double-check, any experiment where `day_total_cost` or any value in `day_per_agent_costs` is negative was affected. In a correct experiment, all cost values are ≥ 0.

## What I Changed

| File | Change |
|------|--------|
| `web/backend/app/game.py` | Removed `_compute_cost_deltas()` and `_get_previous_day_in_round()` (-40 lines). Added non-negative cost assertions (+6 lines). |
| `web/backend/tests/test_cost_delta.py` | Rewrote: 15 tests covering no-delta-transformation, dead code removal, serialization, checkpoint round-trip, cost history, bug reproduction, and integration. |

## Lesson Learned

I assumed how the engine worked at the FFI boundary instead of reading the Rust source. Going forward, any code that consumes engine output will have assertions validating invariants (non-negative costs, settlement rates in [0,1], etc.) so bugs like this crash loudly in dev instead of silently corrupting data.
