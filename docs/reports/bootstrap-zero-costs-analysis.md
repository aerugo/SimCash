# Analysis: Bootstrap Sandbox Producing Zero Costs

**Date:** 2025-07-22  
**Context:** Nash reports that the paper's SOURCE→TARGET→SINK bootstrap sandbox produces zero costs for complex multi-agent scenarios. He concludes the sandbox design is fundamentally flawed for anything beyond the simple exp2 scenario and proposes three alternatives (hybrid approach, skip bootstrap, fix the sandbox).

## TL;DR

**Nash's diagnosis is wrong.** The sandbox design is correct. The zero-cost problem is almost certainly a configuration issue — not a fundamental limitation of the 3-agent sandbox architecture. The sandbox *can* reproduce cost pressure for any scenario, but only if it receives the right inputs.

## Why Costs Are Zero

For costs to accrue in the sandbox, TARGET must face **liquidity pressure** — meaning it can't settle all outgoing payments immediately. There are exactly three ways this happens:

1. **Delay costs:** Transactions sit in queue because TARGET lacks liquidity → delay_cost_per_tick_per_cent accrues per tick per queued cent
2. **Overdraft costs:** TARGET's balance goes negative → overdraft_bps_per_tick accrues
3. **Penalty costs:** Transactions miss deadlines or remain unsettled at EOD → fixed/rate penalty

If TARGET can settle everything the moment it arrives, all three are zero. That's not a sandbox design flaw — it means TARGET has too much liquidity relative to its obligations.

### The Likely Root Causes

**1. `cost_rates` not passed through from the scenario**

The `SandboxConfigBuilder._build_cost_rates()` method accepts an optional `cost_rates` override. If `None` is passed, it uses `CostRates()` defaults:
- `overdraft_bps_per_tick: 0.001`
- `delay_cost_per_tick_per_cent: 0.0001`
- `liquidity_cost_per_tick_bps: 0.0`

These are generic defaults. The actual scenario (e.g., Lehman Month) likely has **much higher cost rates** — possibly Castro-style rates where `delay_cost_per_tick_per_cent: 0.2` (2000× higher). If Nash isn't extracting cost_rates from the scenario config and passing them to the evaluator, costs will be negligibly small or zero after integer truncation (INV-1: costs are i64 cents).

**2. `liquidity_pool` not passed to the evaluator**

The `BootstrapPolicyEvaluator.__init__()` accepts `liquidity_pool` as an optional parameter, defaulting to `None`. If the scenario uses `liquidity_pool` mode (like exp2 with `opening_balance: 0, liquidity_pool: 1000000`), but Nash doesn't pass `liquidity_pool` to the evaluator, the sandbox TARGET gets `opening_balance` as direct liquidity instead of pool-allocated liquidity. This could mean:
- TARGET gets its full `opening_balance` as free cash (no pool constraint)
- Or TARGET gets 0 balance with no pool → *everything* fails (but costs might still be 0 if settlement_rate is 0% with no penalty rates)

**3. `opening_balance` too high**

If Nash passes the agent's `opening_balance` from a rich multi-agent scenario (where agents have large pre-funded balances), TARGET starts flush and settles everything immediately. The sandbox is designed for pool-mode agents (`opening_balance: 0` with `liquidity_pool`), where the fraction parameter controls how much liquidity TARGET actually gets.

**4. Incoming settlements flooding TARGET with liquidity**

The sampler schedules incoming settlements at their *original settlement ticks*. In the full multi-agent sim, these settlements might arrive late (after delays). But the sandbox SOURCE has infinite liquidity and settles immediately at the scheduled tick — meaning TARGET gets incoming liquidity *earlier* than in the real sim. This gives TARGET a liquidity advantage the real agent doesn't have.

This is a real subtlety but it's a calibration issue, not a fundamental design flaw. The paper handles it because exp2 has symmetric 2-bank configs where both agents face similar timing.

## Why Nash's Three Options Are All Wrong

### Option 1: "Hybrid approach — paper's bootstrap for simple, WebBootstrapEvaluator for complex"

This defeats the purpose. The paper's bootstrap exists to evaluate a *single agent's policy in isolation* — removing confounding from other agents' behavior. `WebBootstrapEvaluator` runs the full multi-agent sim with seed variation, which means:
- Other agents' policies confound the evaluation
- The comparison has higher variance
- You can't attribute cost changes to the agent's policy vs other agents' behavior

### Option 2: "Skip bootstrap for every_scenario_day — temporal comparison"

This is what was already broken. The experiment runner uses bootstrap *because* temporal comparison is unreliable — Day N+1 has different transaction arrivals than Day N, so cost changes could be noise rather than policy improvement.

### Option 3: "Fix the sandbox — limit SOURCE liquidity to match real sim"

This is closest to correct but misidentifies the problem. SOURCE liquidity isn't the issue — SOURCE just sends scheduled payments to TARGET. The issue is getting the sandbox *inputs* right (cost rates, pool config, balance config).

## What Actually Needs to Happen

Nash needs to wire the evaluator correctly. Specifically:

### 1. Pass `cost_rates` from the scenario config

```python
# Extract from scenario YAML
cost_rates_dict = scenario_config.get("cost_rates", {})

evaluator = BootstrapPolicyEvaluator(
    opening_balance=agent_config["opening_balance"],
    credit_limit=agent_config.get("unsecured_cap", 0),
    cost_rates=cost_rates_dict,  # ← CRITICAL
    liquidity_pool=agent_config.get("liquidity_pool"),
)
```

### 2. Pass `liquidity_pool` from the agent config

If the agent uses pool-mode liquidity (`opening_balance: 0` with `liquidity_pool`), this must be passed to the evaluator so the sandbox TARGET gets pool-allocated liquidity controlled by the fraction parameter.

### 3. Verify the cost rates match

After building a sandbox config, dump it and verify the cost rates match the real scenario. If the real scenario has `delay_cost_per_tick_per_cent: 0.2` and the sandbox has `0.0001`, that's a 2000× difference — costs in the sandbox will round to zero.

### 4. Check for integer truncation

With low cost rates and small transaction amounts, the intermediate calculation `amount × rate × ticks` might be < 1 cent and truncate to 0 (INV-1). This is correct behavior — but it means the rates need to be scenario-appropriate.

## Verification Steps

Nash can verify this by:

1. Running the sandbox with the scenario's actual cost_rates
2. Checking `orchestrator.get_agent_accumulated_costs(agent_id)` after the run
3. Checking if TARGET has any pending transactions (if settlement_rate = 100% with zero queue time, the fraction is too high for this transaction volume)
4. Trying with a deliberately low fraction (e.g., 0.05) to confirm costs appear when liquidity is scarce

If costs appear with a low fraction but not with the proposed fraction, the sandbox is working correctly — the policy just doesn't create enough scarcity to generate costs.

## Bottom Line

The sandbox architecture is sound. It was designed for exactly this use case. The problem is plumbing — getting the right config values into the evaluator. This is a 10-line fix, not an architectural rethink.
