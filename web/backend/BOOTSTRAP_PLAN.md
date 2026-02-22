# Plan: Wire Real Bootstrap Evaluation into Web Module

## Current State
- `WebBootstrapEvaluator` in `bootstrap_eval.py` does seed-variation on full multi-agent scenario
- Only created when `num_eval_samples > 1`
- `every_scenario_day` forces `num_eval_samples = 1` → evaluator = None → all proposals auto-accepted
- This means the most common mode has ZERO quality control on LLM proposals

## Target State
- Use the paper's `TransactionHistoryCollector` → `BootstrapSampler` → `BootstrapPolicyEvaluator` pipeline
- ALWAYS evaluate proposals (even in `every_scenario_day` mode)
- Single-agent sandbox isolation (SOURCE → TARGET → SINK), 50 samples
- Proper paired comparison with delta convention: positive = improvement

## Changes

### 1. game.py — Collect transaction histories after simulation

**Where:** After `_run_scenario_day()` or `_run_single_sim()` returns events, before `GameDay` is created.

**What:** 
```python
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import TransactionHistoryCollector

# In simulate_day() or run_day(), after getting tick_events:
collector = TransactionHistoryCollector()
all_flat_events = [e for tick_list in tick_events for e in tick_list]
collector.process_events(all_flat_events)
# Store on the GameDay object:
day._agent_histories = {aid: collector.get_agent_history(aid) for aid in self.agent_ids}
```

**Note:** For `every_scenario_day`, tick_events come from `_run_scenario_day()` which already returns them. The history needs to be from the CURRENT DAY only (not cumulative), because the bootstrap evaluator creates sandboxes of that day's length.

### 2. game.py — New `_run_real_bootstrap()` method

**What:** Replace `_run_bootstrap()` (which calls `WebBootstrapEvaluator`) with a new method using the real pipeline.

```python
def _run_real_bootstrap(self, aid: str, day: GameDay, result: dict) -> dict:
    """Run paper's bootstrap evaluation: resample → sandbox → paired comparison."""
    history = day._agent_histories.get(aid)
    if not history or (not history.outgoing and not history.incoming):
        # No transaction history → can't bootstrap → accept by default
        logger.warning("No transaction history for %s, skipping bootstrap", aid)
        return result
    
    # Get agent config from YAML
    agent_cfg = next((a for a in self.raw_yaml["agents"] if a["id"] == aid), None)
    if not agent_cfg:
        return result
    
    # Generate bootstrap samples
    sampler = BootstrapSampler(seed=self._base_seed + day.day_num * 100)
    samples = sampler.generate_samples(
        agent_id=aid,
        n_samples=50,
        outgoing_records=history.outgoing,
        incoming_records=history.incoming,
        total_ticks=self._ticks_per_day,
    )
    
    # Run paired evaluation
    evaluator = BootstrapPolicyEvaluator(
        opening_balance=agent_cfg.get("opening_balance", 0),
        credit_limit=agent_cfg.get("unsecured_cap", 0),
        liquidity_pool=agent_cfg.get("liquidity_pool", 0),
    )
    deltas = evaluator.compute_paired_deltas(
        samples=samples,
        policy_a=self.policies[aid],  # current/old
        policy_b=result["new_policy"],  # proposed/new
    )
    
    # Acceptance criteria (paper convention: delta = old - new, positive = improvement)
    delta_values = [d.delta for d in deltas]
    delta_sum = sum(delta_values)
    n = len(delta_values)
    mean_delta = delta_sum // n if n else 0
    
    # CI and CV
    import statistics, math
    if n >= 2 and mean_delta != 0:
        std = statistics.stdev(delta_values)
        se = std / math.sqrt(n)
        ci_lower = int(mean_delta - 1.96 * se)
        ci_upper = int(mean_delta + 1.96 * se)
        cv = abs(std / mean_delta)
    else:
        ci_lower = ci_upper = mean_delta
        cv = 0.0
        std = 0.0
    
    mean_old = sum(d.cost_a for d in deltas) // n if n else 0
    mean_new = sum(d.cost_b for d in deltas) // n if n else 0
    
    accepted = True
    rejection_reason = ""
    if delta_sum <= 0:
        accepted = False
        rejection_reason = f"No improvement: delta_sum={delta_sum}"
    elif ci_lower <= 0 and n >= 2:
        accepted = False
        rejection_reason = f"Not significant: 95% CI lower={ci_lower} ≤ 0"
    elif cv > 0.5:
        accepted = False
        rejection_reason = f"CV too high: {cv:.3f} > 0.5"
    
    # Annotate result
    result["bootstrap"] = {
        "delta_sum": delta_sum,
        "mean_delta": mean_delta,
        "cv": round(cv, 4),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "num_samples": n,
        "old_mean_cost": mean_old,
        "new_mean_cost": mean_new,
        "rejection_reason": rejection_reason,
    }
    
    if not accepted:
        result["accepted"] = False
        result["rejection_reason"] = rejection_reason
        result["reasoning"] += f" [REJECTED: {rejection_reason}]"
        result["new_policy"] = None
        result["new_fraction"] = None
    
    logger.warning(
        "Bootstrap eval for %s: %d samples, delta_sum=%d, accepted=%s%s",
        aid, n, delta_sum, accepted,
        f" ({rejection_reason})" if rejection_reason else "",
    )
    
    return result
```

### 3. game.py — Always run bootstrap (remove the num_eval_samples gate)

**Where:** `optimize_policies_streaming()` and `_optimize_intra_scenario()`

**Before:**
```python
evaluator = None
if self.num_eval_samples > 1:
    evaluator = WebBootstrapEvaluator(...)
...
if evaluator and result.get("new_policy"):
    result = self._run_bootstrap(evaluator, aid, result)
```

**After:**
```python
# No evaluator object needed — _run_real_bootstrap uses the paper's pipeline
...
if result.get("new_policy"):
    result = self._run_real_bootstrap(aid, last_day, result)
```

### 4. GameDay — Store agent histories

Add `_agent_histories` field to `GameDay.__init__()`.

### 5. Remove WebBootstrapEvaluator import

The old `bootstrap_eval.py` becomes dead code. Don't delete yet (keep as fallback), just remove the imports.

## Edge Cases

1. **No transaction history** — If a day produces no arrivals for an agent (e.g., the agent is idle), we can't bootstrap. Accept by default with a warning log.

2. **every_scenario_day mode** — The `_run_scenario_day()` method already returns `tick_events`. We collect history from THIS day's events only. The sandbox runs for `ticks_per_day` ticks (one day), not the full multi-day scenario.

3. **every_round mode** — `_run_single_sim()` returns `tick_events` via the 6th return value. Same collection logic applies.

4. **Simulated AI (mock mode)** — Mock optimizer also needs bootstrap evaluation. Apply the same gate.

5. **Performance** — 50 samples × 2 policies × ~100 ticks × 3-agent sandbox = ~10K ticks per agent. With 6 agents in parallel = ~60K ticks total. The Rust engine does >1M ticks/sec. Should complete in <100ms.

6. **num_eval_samples** — This parameter now only controls the multi-seed averaging for DAY COST DISPLAY (lines 394-440). It no longer gates bootstrap evaluation. Keep it for display robustness but decouple from acceptance.

## Testing

1. Run locally with a 2-bank exp2 scenario, verify bootstrap produces non-trivial deltas
2. Check that the `_agent_histories` field is populated on GameDay
3. Verify rejection/acceptance shows in the frontend activity log
4. Deploy and have Stefan re-test
