# Handover: `daily_liquidity_reallocation` Now Defaults to `true`

**Branch:** `feature/daily-liquidity-cycle`  
**Commit:** `f4b6e3ba`  
**Date:** 2025-07-22

## What Changed

`daily_liquidity_reallocation` now defaults to **`true`** instead of `false`.

This means multi-day scenarios automatically get daily liquidity cycling:
- **End of Day (EOD):** Each agent's remaining balance is returned to the liquidity pool.
- **Start of Day (SOD):** Fresh allocation from pool using the agent's current `initial_liquidity_fraction` policy parameter.

## Impact on the Web Platform

### If you don't set the flag explicitly
Your scenarios now get daily reallocation automatically. This is the intended behavior for multi-day games — agents start each day with a fresh allocation based on their current policy, making the fraction a meaningful daily strategic lever.

### If you want the old behavior
Set `daily_liquidity_reallocation: false` in the scenario config dict passed to the engine.

### What to watch for
- **Balance values will differ between days.** Previously, balances carried forward as-is. Now they reset to `pool × fraction` each morning. Dashboard charts showing agent balances will look different for multi-day runs.
- **Single-day scenarios are unaffected.** Reallocation only triggers at day boundaries.
- **Agents without `liquidity_pool`** are unaffected.

## Files Changed

| File | Change |
|------|--------|
| `simulator/src/orchestrator/engine.rs` | `#[serde(default = "default_true")]` on field |
| `simulator/src/ffi/types.rs` | `unwrap_or(true)` in Python FFI config parser |

## No Breaking Tests

All 1266 Rust tests pass. The ~20 tests that previously relied on the `false` default either run single-day scenarios (no-op) or don't configure liquidity pools.
