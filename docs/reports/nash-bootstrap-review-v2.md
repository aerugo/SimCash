# Review v2: Bootstrap Pipeline on `feature/interactive-web-sandbox` (4c56f56a)

**Date:** 2025-07-22  
**Previous review was against stale commit.** This review covers Nash's actual latest code.

---

## Correction

My previous review was wrong about the bootstrap evaluator. Nash **has** wired the paper's pipeline:

- Lines 20-22: `TransactionHistoryCollector`, `BootstrapSampler`, `BootstrapPolicyEvaluator` all imported ✅
- `_run_real_bootstrap()` (line 806): full pipeline — collector → sampler → evaluator ✅
- `WebBootstrapEvaluator` removed (dead code cleaned up in `4c56f56a`) ✅
- History collected in both `simulate_day()` and the post-`run_day()` path ✅
- `cost_rates` passed from `self.raw_yaml.get("cost_rates")` directly ✅

My apologies — I reviewed against a stale fetch. The pipeline is structurally correct.

---

## Remaining Issues (Why `delta_sum=0`)

Nash reports "50 samples, delta_sum=0, accepted=False" in production. The pipeline is wired, but there are three bugs that could each independently cause zero costs:

### Bug 1: `liquidity_pool` Fallback Creates Phantom Pools

```python
liquidity_pool=agent_cfg.get("liquidity_pool") or agent_cfg.get("opening_balance", 0),
```

**Problem:** The `or` fallback triggers when `liquidity_pool` is `None` (non-pool agents) AND when it's `0`. This creates two failure modes:

- **Non-pool agents** (`opening_balance: 500000`, no `liquidity_pool`): Gets `liquidity_pool=500000` in the sandbox, creating a pool that doesn't exist in the real scenario. The sandbox TARGET now has both `opening_balance` AND `liquidity_pool`, doubling effective liquidity.

- **Pool agents with `opening_balance: 0`**: `liquidity_pool` is correctly set, but `opening_balance=0` is correct too. This case works.

- **Pool agents with `liquidity_pool: 0`** (edge case): Falls back to `opening_balance`, wrong.

**Fix:**
```python
liquidity_pool=agent_cfg.get("liquidity_pool"),  # None if not pool-mode, int if pool-mode
```

Don't fall back. `None` means "no pool" — the evaluator and sandbox handle `None` correctly.

### Bug 2: `cost_rates` Dict May Silently Produce Default Rates

`scenario_cost_rates = self.raw_yaml.get("cost_rates") or None`

The `or None` is fine for empty dicts. But the real question: **what does Nash's scenario YAML actually contain for `cost_rates`?**

If the scenario was created via the scenario editor UI and `cost_rates` is missing or empty, the sandbox gets `CostRates()` defaults:
- `delay_cost_per_tick_per_cent: 0.0001` (vs Castro's `0.2` — 2000× lower)
- `overdraft_bps_per_tick: 0.001`

With these defaults and small transaction amounts, `amount × rate × ticks` can be < 1 cent → integer truncation (INV-1) → zero.

**Diagnostic:** Add a log line before creating the evaluator:
```python
logger.warning("Bootstrap config for %s: opening_balance=%s, liquidity_pool=%s, cost_rates=%s",
    aid, agent_cfg.get("opening_balance"), agent_cfg.get("liquidity_pool"), scenario_cost_rates)
```

### Bug 3: Both Policies Produce Identical Costs → `delta=0` for Every Sample

If the old and new policies have very similar fractions (e.g., 0.50 vs 0.48), AND the sandbox has enough liquidity at both fractions to settle everything, then both policies produce identical zero costs → `delta=0` for every sample → `delta_sum=0`.

This isn't a bug per se — it's the sandbox correctly telling you the policy change doesn't matter at this liquidity level. But it can be masked by Bug 1 (phantom pool giving too much liquidity).

**Diagnostic:** Log per-sample costs:
```python
for d in deltas:
    logger.warning("  sample %d: old_cost=%d, new_cost=%d, delta=%d", d.sample_idx, d.cost_a, d.cost_b, d.delta)
```

If ALL `cost_a` and `cost_b` are 0, the sandbox has too much liquidity or too-low cost rates. If they're nonzero but identical, the fraction change is too small to matter.

### Bug 4 (Confirmed): `_inject_policies_into_orch()` Missing from HTTP Path

Nash acknowledged this. The HTTP API path (`POST /api/simulations/{sim_id}/optimize` and the `run_day` + `optimize_policies` flow) doesn't call `_inject_policies_into_orch()` after optimization. So REST-based intra-scenario runs silently don't apply policy swaps.

---

## Suggested Diagnostic Steps

1. **Add logging to `_run_real_bootstrap`** — print the evaluator config (opening_balance, liquidity_pool, cost_rates) and per-sample costs before computing deltas.

2. **Run one bootstrap eval with a deliberately extreme fraction** (e.g., 0.01 vs 0.99) to confirm the sandbox produces different costs. If even 0.01 vs 0.99 gives `delta=0`, the problem is definitely cost rates or pool config.

3. **Print `CostRates(**scenario_cost_rates).model_dump()`** to verify the rates the sandbox actually uses. Compare against what the full-sim scenario uses.

4. **Remove the `liquidity_pool` fallback** — use `agent_cfg.get("liquidity_pool")` without `or`. If it's `None`, the sandbox won't create a pool, which is correct for non-pool agents.

---

## What's Working Well

Credit to Nash — the overall architecture is now sound:

- Paper's pipeline correctly imported and used
- TransactionHistoryCollector fed from day events (both paths)
- Per-agent bootstrap profiles with configurable thresholds
- Proper paired delta computation (cost_a - cost_b)
- 95% CI, CV checks, significance testing
- History collected for both `simulate_day` and `run_day` paths
- Dead code (`WebBootstrapEvaluator`) cleaned up

The zero-cost issue is almost certainly a configuration/plumbing bug in how the evaluator receives its inputs, not a structural problem.
