# Bug Fix: Validation Summary Shows Wrong Costs

## Problem

The validation summary panel showed default cost values (Liquidity 0 bps, Delay 0.0001, EOD $100, Deadline $500) instead of my custom values (150 bps, 0.3, $200K, $300K).

## Root Cause

This was caused by Bug #2 — I used `cost_config:` instead of `cost_rates:` in the YAML. The Pydantic model's `cost_rates` field defaulted to `CostRates()` since the YAML didn't contain `cost_rates`. The validation summary correctly displayed what the engine would actually use — the defaults.

**This is NOT a separate bug.** The summary was accurate — it showed the real parsed values. The real fix is Bug #2 (warn users about unrecognized keys).

## Status

**No fix needed.** Resolved by plan #02. The summary correctly reflects the parsed configuration.

## Verification

After fix #02, if a user writes `cost_config:` they'll see a warning. If they write `cost_rates:` (correct key), the summary will show their custom values.
