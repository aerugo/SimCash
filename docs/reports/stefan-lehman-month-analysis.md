# Stefan's Lehman Month Run — Root Cause Analysis

**Game ID:** `64f0b9e6`  
**Date:** 2026-02-22 12:35–12:42 UTC  
**Config:** 6 banks, 25 days, every_scenario_day optimization, Full decision trees, Live AI (GLM-4.7)

## What the Logs Show

### LLM calls: 144 total (24 days × 6 agents), all succeeded on attempt 1
- No retries, no timeouts, no rate limit errors
- Response sizes varied wildly: **326 chars** to **3614 chars**
- CLEARING_HUB and LARGE_BANK_1/2 often got ~326 chars (basically unchanged default policy)
- MID_BANK_1/2 sometimes got 2400-3600 chars (complex decision trees)

### Validation: zero failures
- No "Policy validation failed" warnings in logs
- No `InvalidFieldReference` errors
- The `_apply_result()` Orchestrator validation test passed for all policies

### Bootstrap evaluation: NEVER RAN
- `every_scenario_day` forces `num_eval_samples = 1`
- Bootstrap evaluator is only created when `num_eval_samples > 1`
- Therefore: **every proposed policy was automatically accepted without evaluation**

## The Real Root Cause

Stefan observed "frac=1.000 throughout" and "No policy changes." Given that:
1. Bootstrap never ran (so it's 0% to blame)
2. Validation never failed (so hallucinated fields are 0% to blame)
3. Every LLM proposal was auto-accepted

The issue is almost certainly one of these:

### Hypothesis A: LLM returned policies without `initial_liquidity_fraction` (HIGH confidence — ~70%)

The `_parse_policy_response()` function doesn't ensure the fraction parameter exists. If GLM-4.7 returned:
```json
{
  "version": "2.0",
  "payment_tree": {"type": "action", "action": "Release"},
  "bank_tree": {"type": "action", "action": "NoAction"}
}
```

This would:
1. Pass parsing ✅ (has required structure)
2. Pass validation ✅ (trees reference valid actions)
3. Be "accepted" ✅ (no bootstrap to reject it)
4. Run with **fraction = 1.0** because `_build_ffi_config` defaults to 1.0 when `parameters.initial_liquidity_fraction` is missing

The 326-char responses are suspicious — that's barely enough for a minimal policy without parameters.

### Hypothesis B: LLM explicitly returned fraction=1.0 (~20%)

GLM-4.7 may have analyzed the 100% settlement + zero delays and concluded: "the current policy is already optimal, keep fraction at 1.0." Especially in "Full" mode where it sees the default Release-everything tree is already achieving perfect settlement.

### Hypothesis C: Display bug showing 1.0 instead of 0.5 (~10%)

The GameView frontend uses `?? 1` when `initial_liquidity_fraction` is undefined in the policy object. If the state serialization drops the fraction, the UI shows 1.0 even though the engine ran at 0.5.

## Blame Attribution

| Cause | Blame % |
|-------|---------|
| **Missing fraction in LLM response** (parsed policy lacks `parameters.initial_liquidity_fraction`, engine defaults to 1.0) | **70%** |
| **LLM proposing no meaningful changes** (GLM-4.7 not generating diverse strategies for 6-bank crisis) | **20%** |
| **Display bug** (fraction shown as 1.0 but engine used 0.5) | **10%** |
| Bootstrap conservatism | **0%** (never ran) |
| Validation failures / hallucinated fields | **0%** (no failures logged) |

## Recommended Fixes

1. **Ensure fraction in parsed policies** — After `_parse_policy_response()`, if `parameters.initial_liquidity_fraction` is missing, inject the current fraction:
   ```python
   if "initial_liquidity_fraction" not in policy.get("parameters", {}):
       policy.setdefault("parameters", {})["initial_liquidity_fraction"] = current_fraction
   ```

2. **Log policy changes clearly** — Add a warning log when a policy is applied showing old_fraction → new_fraction so we can trace exactly what happened.

3. **Re-run with Simple mode** — This bypasses tree generation and only optimizes the fraction parameter, which can't go missing.

4. **Test GLM-4.7 response format** — Save a few raw LLM responses to verify whether the fraction parameter is present.
