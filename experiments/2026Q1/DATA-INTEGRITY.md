# DATA INTEGRITY REPORT — Cost Delta Bug (2026-02-27)

## Summary

On 2026-02-27, a bug was discovered in SimCash's Python orchestration layer (`_compute_cost_deltas`). The function subtracted consecutive days' cost values assuming they were cumulative, but the Rust engine resets cost accumulators at each day boundary. This produced **negative cost deltas fed to the LLM optimizer from day 2 onward** in multi-day scenarios, meaning the LLM optimized against incorrect cost feedback.

**Bug introduced in:** the multi-day optimization path (unknown date)  
**Bug fixed in:** revision simcash-00168-v29, commit 1b596876  
**Discovered by:** Stefan (negative costs in API results) → Dennis (engine audit) → Nash (root cause in `_compute_cost_deltas`)

## Impact

- **Only affects experiments where `num_days > 1` in the scenario config AND `use_llm: true`**
- The Rust engine's raw cost calculations are correct — the corruption is in what the LLM *saw* during optimization
- Final stored costs in results ARE the true engine-computed costs for the policies chosen, BUT the policies themselves were optimized against garbage feedback
- Therefore: **results cannot be trusted** because the LLM may have converged on suboptimal policies due to wrong signals

## Affected Experiments (38 total)

### Lehman Month (num_days=25) — 9 experiments
- lehman_month_-_flash (r1, r2, r3)
- lehman_month_-_glm (r1, r2, r3)
- lehman_month_-_pro (r1, r2, r3)

### Periodic Shocks (num_days=30) — 9 experiments
- periodic_shocks_-_flash_(r2, r3) + periodic_shocks_-_flash_(c4-full_r1, c4-full_r2, c4-full_r3)
- periodic_shocks_-_glm_(r2, r3)
- periodic_shocks_-_pro_(r2, r3)

### Large Network (num_days=25) — 8 experiments
- large_network_-_flash (r1, r2, r3)
- large_network_-_glm_(r2, r3)
- large_network_-_pro (r1, r2, r3)

### Liquidity Squeeze (num_days=10) — 12 experiments
- liquidity_squeeze_-_flash_(r2, r3)
- liquidity_squeeze_-_glm_(r2, r3)
- liquidity_squeeze_-_pro_(r2, r3)
- liq_squeeze_-_flash_(c4-full_r1, c4-full_r2, c4-full_r3)
- liq_squeeze_-_pro_(c4-full_r1, c4-full_r2, c4-full_r3)

## CLEAN Experiments (143 total)

All single-day scenarios (`num_days=1`) are unaffected:
- **Castro Exp2** (2bank_12tick): all v0.1, v0.2 (C1-C4), and retry experiments — **CLEAN**
- **2B 3T, 3B 6T, 4B 8T, 2B Stress**: all runs — **CLEAN**
- **Lynx Day**: all runs — **CLEAN**
- **All baselines** (no LLM): **CLEAN**

## Conclusions at Risk

1. **Complexity threshold** ("LLM worse than FIFO on 5+ banks") — built on Lehman, Periodic Shocks, Large Network. ALL AFFECTED. May be real or may be artifact of garbage feedback.
2. **Model performance reversal** ("Pro beats Flash on Periodic Shocks") — AFFECTED.
3. **Wave 2 complexity barrier tests** — Periodic Shocks and Liq Squeeze C4-full runs AFFECTED.

## Conclusions CONFIRMED SAFE

1. Settlement optimization analysis (constraints > information) — all on Castro Exp2, CLEAN
2. Flash model dominance under settlement floor — all on Castro Exp2, CLEAN
3. Retry mechanism analysis — all on Castro Exp2, CLEAN
4. Strategy poverty finding (5/11 actions used) — observed across all scenarios including clean ones, LIKELY VALID
5. Simple scenario results (2-4 banks) — all CLEAN

## Decision: GLM Dropped from Wave 3 Re-runs

GLM-4.7 is excluded from the re-run wave. Rationale:
- 0% score on floor conditions, 2% overall in model rankings
- Never achieves best settlement rate when constraints are active
- Sufficient clean data from single-day scenarios to characterize its behavior
- Compute better spent on Flash/Pro re-runs that test the complexity threshold

GLM results from compromised multi-day runs will NOT be re-run or cited.
If needed for completeness later, GLM multi-day runs can be added as a follow-up.

## Rule

**DO NOT cite, present, or include any of the 38 affected experiments in paper results.**  
They are archived in `api-results/` with original filenames for reference only.  
Re-run results on fixed code (rev 00168+) will use the same filenames and overwrite the compromised data.

## Verification for New Runs

On any new multi-day experiment, verify:
1. All `day_costs` values are non-negative
2. Runtime assertions in rev 00168+ will crash immediately if negative costs appear
