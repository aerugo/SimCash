# Bootstrap Wiring Guide: What the Paper Does vs What the Web Does

**Date:** 2025-07-22  
**Context:** Nash reports zero costs from the paper's SOURCE→TARGET→SINK bootstrap sandbox. This report traces both implementations line-by-line to show exactly where they diverge.

---

## Executive Summary

The paper's `OptimizationLoop` wires the `BootstrapPolicyEvaluator` with **five critical inputs** extracted from the scenario config. Nash's `Game` class uses `WebBootstrapEvaluator` instead, which runs the full multi-agent sim with seed variation — a completely different approach. The zero-cost problem doesn't come from the sandbox design; it comes from the sandbox never receiving the right inputs.

---

## The Paper's Bootstrap Pipeline (Working)

Location: `api/payment_simulator/experiments/runner/optimization.py`

### Step 1: Extract agent config from scenario YAML

```python
# optimization.py line ~2009 (inside _evaluate_policies)
agent_config = self._get_scenario_builder().extract_agent_config(agent_id)
```

This uses `StandardScenarioConfigBuilder` (INV-10) to extract:
- `opening_balance` (int, e.g. `0` for pool-mode agents)
- `credit_limit` (int, from `unsecured_cap`)
- `max_collateral_capacity` (int or None)
- `liquidity_pool` (int or None, e.g. `1000000`)

### Step 2: Extract cost rates from scenario

```python
# optimization.py line ~698 (inside _run_simulation)
if not self._cost_rates and "cost_rates" in ffi_config:
    self._cost_rates = ffi_config["cost_rates"]
```

The cost rates dict is captured from the FFI config on first simulation run. This includes:
- `delay_cost_per_tick_per_cent` (e.g. `0.2` in Castro scenarios)
- `overdraft_bps_per_tick`
- `eod_penalty_per_transaction`
- `deadline_penalty`
- etc.

### Step 3: Create evaluator with ALL inputs

```python
# optimization.py line ~2009
evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config.opening_balance,    # ← from scenario
    credit_limit=agent_config.credit_limit,          # ← from scenario
    cost_rates=self._cost_rates,                     # ← from scenario
    max_collateral_capacity=agent_config.max_collateral_capacity,  # ← from scenario
    liquidity_pool=agent_config.liquidity_pool,      # ← from scenario
)
```

**All five parameters come from the scenario config.** This is the critical wiring.

### Step 4: Evaluate on bootstrap samples

```python
eval_results = evaluator.evaluate_samples(samples, current_policy)
```

The evaluator passes these through to `SandboxConfigBuilder.build_config()`, which:
1. Creates SOURCE with infinite liquidity
2. Creates TARGET with the agent's `opening_balance`, `credit_limit`, `liquidity_pool`
3. Creates SINK with infinite capacity
4. Uses `_build_cost_rates(cost_rates)` to set the sandbox's cost rates
5. Uses `StandardPolicyConfigBuilder` to extract `initial_liquidity_fraction` from the policy and set `liquidity_allocation_fraction` on TARGET

### Step 5: Bootstrap samples provide transaction pressure

The `BootstrapSampler` creates resampled transaction schedules from the *real simulation's* transaction history. These become:
- `CustomTransactionArrival` events (TARGET → SINK) — outgoing payment obligations
- `ScheduledSettlement` events (SOURCE → TARGET) — incoming liquidity beats

These transactions create the cost pressure. Without them, TARGET has no obligations → no costs.

---

## What Nash's Web Code Does (Broken)

Location: `web/backend/app/game.py`

### The `WebBootstrapEvaluator` approach

Nash doesn't use the paper's `BootstrapPolicyEvaluator` at all. Instead:

```python
# game.py line ~420
evaluator = WebBootstrapEvaluator(
    num_samples=self.num_eval_samples,
    cv_threshold=0.5,
)
```

`WebBootstrapEvaluator` (`web/backend/app/bootstrap_eval.py`) works completely differently:
1. Takes the **full multi-agent scenario YAML**
2. Swaps in the proposed policy for the target agent
3. Runs the **entire simulation** with different seeds
4. Compares costs

This is **not bootstrap at all** — it's seed variation on the full scenario. The problems:
- Other agents' behavior confounds the evaluation
- Higher variance (full scenario noise vs isolated sandbox)
- Can't attribute cost changes to the policy change vs stochastic noise
- Much slower (runs full N-agent sim instead of 3-agent sandbox)

### What Nash apparently tried (from his message)

Nash says he got the SOURCE→TARGET→SINK sandbox running with 50 samples, but costs are zero. Based on the code, the most likely failure modes:

**Failure 1: Missing `cost_rates`**

The `SandboxConfigBuilder._build_cost_rates()` accepts an optional dict. If `None`:
```python
def _build_cost_rates(self, override: dict[str, float] | None) -> CostRates:
    if override is None:
        return CostRates()  # ← DEFAULTS: delay=0.0001, overdraft=0.001
```

The defaults are **2000× lower** than typical Castro-style rates (`delay=0.2`). With small transaction amounts and integer truncation (INV-1), this rounds to zero.

**Failure 2: Missing `liquidity_pool`**

If `liquidity_pool=None` is passed to the evaluator, the sandbox TARGET gets no pool. For pool-mode agents (like exp2's `opening_balance: 0, liquidity_pool: 1000000`), this means TARGET gets 0 balance and 0 pool → nothing to settle with → 0% settlement but also potentially 0 costs if penalty rates are also defaulted.

**Failure 3: Wrong `opening_balance`**

If Nash passes a large `opening_balance` from a rich multi-agent scenario but the agent is actually pool-mode (`opening_balance: 0`), TARGET starts flush and settles everything → no queue → no costs.

---

## The Fix: What Nash Needs to Do

### Option A: Use the paper's pipeline directly (Recommended)

The paper's code already handles everything. Nash just needs to wire it:

```python
# In game.py, replace WebBootstrapEvaluator with:
from payment_simulator.ai_cash_mgmt.bootstrap.evaluator import BootstrapPolicyEvaluator
from payment_simulator.ai_cash_mgmt.bootstrap.sampler import BootstrapSampler
from payment_simulator.ai_cash_mgmt.bootstrap.history_collector import TransactionHistoryCollector
from payment_simulator.config.scenario_config_builder import StandardScenarioConfigBuilder

# After running a day's simulation (you already have events from _run_single_sim):
collector = TransactionHistoryCollector()
collector.process_events(all_events)

# For each agent that needs evaluation:
scenario_builder = StandardScenarioConfigBuilder(self.raw_yaml)
agent_config = scenario_builder.extract_agent_config(agent_id)

# Get cost rates from scenario YAML
cost_rates = self.raw_yaml.get("cost_rates", {})

# Create the REAL evaluator
evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config.opening_balance,
    credit_limit=agent_config.credit_limit,
    cost_rates=cost_rates,
    max_collateral_capacity=agent_config.max_collateral_capacity,
    liquidity_pool=agent_config.liquidity_pool,
)

# Create bootstrap samples from the day's transaction history
history = collector.get_agent_history(agent_id)
sampler = BootstrapSampler(seed=self._base_seed + self.current_day)
samples = sampler.generate_samples(
    agent_id=agent_id,
    n_samples=self.num_eval_samples,
    outgoing_records=history.outgoing,
    incoming_records=history.incoming,
    total_ticks=ticks_per_day,
)

# Evaluate old vs new policy
old_results = evaluator.evaluate_samples(samples, self.policies[agent_id])
new_results = evaluator.evaluate_samples(samples, proposed_policy)

# Compute paired deltas
deltas = [old.total_cost - new.total_cost for old, new in zip(old_results, new_results)]
# Positive delta = new policy is cheaper = improvement
```

### Option B: Fix WebBootstrapEvaluator (Not recommended)

If Nash wants to keep the full-scenario approach, it's architecturally inferior but can work. The zero-cost problem there would be different — likely related to how `_prepare_orchestrator` wires policies. But this approach will always have higher variance and slower execution than the sandbox.

---

## Verification Checklist

After wiring, Nash should verify:

1. **Print the sandbox config** before running:
   ```python
   config = evaluator._config_builder.build_config(sample, policy, ...)
   print(config.to_ffi_dict())
   ```
   Check that:
   - `cost_rates` match the scenario (not defaults)
   - TARGET has correct `opening_balance` and `liquidity_pool`
   - `liquidity_allocation_fraction` matches the policy's fraction

2. **Run with a low fraction** (e.g., 0.05) to confirm costs appear when liquidity is scarce

3. **Check `get_agent_accumulated_costs`** after a sandbox run:
   ```python
   orch = Orchestrator.new(ffi_config)
   for _ in range(total_ticks): orch.tick()
   print(orch.get_agent_accumulated_costs(agent_id))
   ```
   If delay_cost and penalty are both 0, either:
   - The fraction is too high (TARGET has enough liquidity)
   - Cost rates are too low (defaulted instead of scenario-specific)
   - No transactions were generated (empty bootstrap samples)

4. **Check bootstrap samples aren't empty**:
   ```python
   print(f"Outgoing: {len(samples[0].outgoing_txns)}")
   print(f"Incoming: {len(samples[0].incoming_settlements)}")
   ```
   If zero, the `TransactionHistoryCollector` didn't find events for this agent.

---

## Architecture Comparison Table

| Aspect | Paper (`OptimizationLoop`) | Web (`Game`) |
|--------|--------------------------|--------------|
| Evaluator | `BootstrapPolicyEvaluator` | `WebBootstrapEvaluator` |
| Sandbox | 3-agent (SOURCE→TARGET→SINK) | Full multi-agent scenario |
| Transaction source | Bootstrap-resampled from history | Same scenario, different seed |
| Cost rates | Extracted from scenario YAML | Not passed (defaults used) |
| Agent config | Via `StandardScenarioConfigBuilder` | Not extracted |
| `liquidity_pool` | Passed through | Not passed |
| Policy evaluation | Isolated (INV-11) | Confounded by other agents |
| Samples per eval | Configurable (typically 50) | `num_eval_samples` (typically 10) |
| Speed | Fast (3-agent sandbox) | Slow (full N-agent sim) |

---

## Key Takeaway

The paper's bootstrap infrastructure is complete and battle-tested. Nash doesn't need to reinvent it — he needs to **import and wire it**. The five critical inputs (`opening_balance`, `credit_limit`, `cost_rates`, `max_collateral_capacity`, `liquidity_pool`) must all come from the scenario YAML via `StandardScenarioConfigBuilder`. Missing any of them breaks the sandbox.
