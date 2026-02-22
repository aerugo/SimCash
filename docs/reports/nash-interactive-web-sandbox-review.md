# Review: `feature/interactive-web-sandbox` — Bootstrap Still Not Wired

**Date:** 2025-07-22  
**Branch:** `feature/interactive-web-sandbox` (commit `e52523a0`)  
**Previous guidance:** `handover-nash-bootstrap-wiring-guide.md`, `bootstrap-zero-costs-analysis.md`

---

## What Nash Got Right

Significant progress on the web platform. Credit where due:

1. **Starting fraction fixed**: `DEFAULT_POLICY` now uses `0.5` instead of `1.0` ✅
2. **Intra-scenario mode** (`every_scenario_day`): Persistent `Orchestrator` across scenario days, uses `update_agent_policy()` to inject new policies mid-sim ✅
3. **Daily cost accounting**: Correctly reads `get_agent_accumulated_costs()` as daily costs (understands the reset-at-day-boundary behavior) ✅
4. **Cumulative settlement tracking**: Tracks arrivals/settlements across the round since transactions can settle cross-day ✅
5. **Prompt blocks system**: Structured, inspectable prompts with toggleable sections ✅
6. **Constraint presets**: `simple`/`standard`/`full` with auto-inference from scenario config, correct Rust field names ✅
7. **Cost std dev**: Computes standard deviation across multi-seed evaluations ✅
8. **Policy injection after optimization**: `_inject_policies_into_orch()` called in websocket path after streaming optimization ✅

## What's Still Wrong

### The Core Problem: `WebBootstrapEvaluator` is Still the Only Evaluator

**Both** `optimize_policies_streaming()` (line ~585) and `optimize_policies()` (line ~817) still create:

```python
from .bootstrap_eval import WebBootstrapEvaluator
evaluator = WebBootstrapEvaluator(
    num_samples=self.num_eval_samples,
    cv_threshold=0.5,
)
```

The paper's `BootstrapPolicyEvaluator` is **never imported, never instantiated, never used**. None of the following appear anywhere in Nash's code:

- `BootstrapPolicyEvaluator`
- `BootstrapSampler`
- `TransactionHistoryCollector`
- `StandardScenarioConfigBuilder`

This means:
- No SOURCE→TARGET→SINK sandbox evaluation
- No bootstrap resampling of transaction histories
- No agent-isolated policy evaluation
- Cost rates, `liquidity_pool`, `opening_balance` from the scenario are never extracted for evaluation

The `WebBootstrapEvaluator` runs the **full multi-agent sim** with seed variation — confounding the evaluation with other agents' behavior and producing higher-variance comparisons.

### Bug: `_inject_policies_into_orch()` Not Called in Non-Streaming Path

The HTTP path in `main.py` (lines ~805-826):
```python
day = await loop.run_in_executor(None, game.run_day)
...
reasoning = await game.optimize_policies()
day.optimized = True
```

This calls `optimize_policies()` (non-streaming), applies results via `_apply_result()`, but **never calls `_inject_policies_into_orch()`**. So in the non-websocket API path, intra-scenario policy swaps don't actually reach the live Orchestrator.

Only the websocket path (line ~976) calls it:
```python
game._inject_policies_into_orch()
```

### Minor: `num_eval_samples` Forced to 1 for Intra-Scenario

```python
if self.optimization_schedule == "every_scenario_day":
    self.num_eval_samples = 1
```

This makes sense (can't re-run mid-scenario), but it also means the bootstrap evaluator is never triggered for the most interesting mode. When Nash eventually wires the paper's bootstrap, he'll need to think about how to do paired evaluation within a persistent orchestrator. The paper's approach (sandbox) is the right answer — it's independent of the live sim.

---

## What Nash Should Do Now

### 1. Replace `WebBootstrapEvaluator` with the Paper's Pipeline

In `game.py`, in both `optimize_policies_streaming()` and `optimize_policies()`:

```python
# REMOVE:
from .bootstrap_eval import WebBootstrapEvaluator
evaluator = WebBootstrapEvaluator(num_samples=..., cv_threshold=0.5)

# REPLACE WITH:
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import TransactionHistoryCollector
from payment_simulator.config.scenario_config_builder import StandardScenarioConfigBuilder
```

### 2. Collect Transaction History from Day Events

After each day's simulation (in `run_day` / `simulate_day`), collect the transaction history:

```python
# After _run_single_sim or _run_scenario_day:
collector = TransactionHistoryCollector()
collector.process_events(all_events)
# Store on Game for use during optimization:
self._last_collector = collector
self._last_ticks = ticks_per_day  # or self._ticks_per_day for intra-scenario
```

### 3. Wire the Evaluator with Scenario Config

In `_run_bootstrap()` (or wherever evaluation happens):

```python
scenario_builder = StandardScenarioConfigBuilder(self.raw_yaml)
agent_config = scenario_builder.extract_agent_config(aid)
cost_rates = self.raw_yaml.get("cost_rates", {})

evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config.opening_balance,
    credit_limit=agent_config.credit_limit,
    cost_rates=cost_rates,
    max_collateral_capacity=agent_config.max_collateral_capacity,
    liquidity_pool=agent_config.liquidity_pool,
)

# Generate bootstrap samples from this day's history
history = self._last_collector.get_agent_history(aid)
sampler = BootstrapSampler(seed=self._base_seed + self.current_day)
samples = sampler.generate_samples(
    agent_id=aid,
    n_samples=self.num_eval_samples,
    outgoing_records=history.outgoing,
    incoming_records=history.incoming,
    total_ticks=self._last_ticks,
)

# Paired evaluation
old_results = evaluator.evaluate_samples(samples, self.policies[aid])
new_results = evaluator.evaluate_samples(samples, result["new_policy"])
deltas = [old.total_cost - new.total_cost for old, new in zip(old_results, new_results)]
```

### 4. Fix `_inject_policies_into_orch()` in Non-WS Path

In `main.py`, after `optimize_policies()` in the HTTP path:

```python
reasoning = await game.optimize_policies()
day.optimized = True
if game.optimization_schedule == "every_scenario_day":
    game._inject_policies_into_orch()  # ← ADD THIS
```

### 5. Re-enable Multi-Sample for Intra-Scenario

Remove or relax the `num_eval_samples = 1` override for `every_scenario_day`. The paper's sandbox bootstrap is independent of the live sim — it creates isolated 3-agent sandboxes from the transaction history. There's no reason it can't run 50 samples even in intra-scenario mode.

```python
# REMOVE this block:
# if self.optimization_schedule == "every_scenario_day":
#     self.num_eval_samples = 1
```

---

## Verification After Wiring

1. Run a 2-agent scenario with `num_eval_samples >= 10`
2. Check logs for bootstrap sample generation (`len(history.outgoing)`, `len(history.incoming)`)
3. Verify costs are non-zero in bootstrap evaluation (print `evaluator.evaluate_samples()` results)
4. Compare cost magnitudes with the full-sim costs — they should be in the same order of magnitude
5. Test with a deliberately bad fraction (0.01) to confirm the sandbox correctly shows high costs
