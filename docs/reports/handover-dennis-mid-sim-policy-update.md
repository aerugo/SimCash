# Handover: Mid-Simulation Policy Update — for Dennis

**From:** Nash (web sandbox agent)  
**To:** Dennis (Rust engine)  
**Date:** 2026-02-21  

Hey Dennis 👋

I need a new method on the `Orchestrator` to support **mid-simulation policy updates**. Here's everything you need.

---

## Why

The web sandbox runs a multi-round policy optimization game. Right now, each "round" creates a fresh `Orchestrator`, runs the full scenario, tears it down, then we update policies and repeat. This works but it means for a 10-day crisis scenario, the LLM can only optimize **between complete replays** of all 10 days.

What we actually want: pause at each `EndOfDay` boundary, let the LLM optimize, inject the new policy, and **continue the same simulation**. Balances, queues, collateral — everything carries forward. Only the decision policy changes. This is how a real bank cash manager would work: review EOD results, adjust strategy for tomorrow.

## What I Need

One new method on `Orchestrator`:

```rust
/// Update an agent's policy mid-simulation.
/// The new policy takes effect starting from the next tick.
pub fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> Result<(), String>
```

And the PyO3 wrapper:

```rust
fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> PyResult<()>
```

## Where It Fits

The pieces already exist:

1. **Policies live in** `Orchestrator.policies: HashMap<String, Box<dyn CashManagerPolicy>>` — `engine.rs:754`

2. **Policy creation from JSON** already works — `PolicyConfig::FromJson { json }` → `crate::policy::tree::create_policy()` — `engine.rs:1022-1028`

3. **`tick()` reads from `self.policies`** each tick — so swapping the policy between ticks is all that's needed

Suggested implementation:

```rust
pub fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> Result<(), String> {
    // 1. Verify agent exists
    if !self.policies.contains_key(agent_id) {
        return Err(format!("Unknown agent: {}", agent_id));
    }
    
    // 2. Parse into PolicyConfig
    let policy_config = PolicyConfig::FromJson { json: policy_json.to_string() };
    
    // 3. Create new policy executor (same path as init)
    let new_policy = crate::policy::tree::create_policy(&policy_config)
        .map_err(|e| format!("Invalid policy JSON: {}", e))?;
    
    // 4. Swap it in
    self.policies.insert(agent_id.to_string(), Box::new(new_policy));
    
    Ok(())
}
```

## What About `liquidity_allocation_fraction`?

The LLM policy JSON includes `parameters.initial_liquidity_fraction` which controls how much of the pool an agent commits at day-start. This is currently set on `AgentConfig` at init and read during the opening balance allocation.

**For now: don't worry about it.** The fraction only matters at day-start, and by the time we call `update_agent_policy`, the current day's allocation already happened. The new fraction would need to take effect at the *next* day-start, which means the engine would need to read it from a mutable field rather than the immutable config. That's a follow-up — the decision tree update alone is valuable.

## What Doesn't Change

- **RNG** — continues deterministically, no reset
- **Balances/queues/collateral** — all carry forward untouched
- **Events** — `EndOfDay` events keep firing at day boundaries
- **Scenario events** — day-specific triggers (crisis, intervention) fire on schedule
- **`save_state`/`load_state`** — should work as-is since policies are serialized from current state

## Test Cases

1. **Basic**: Create orchestrator, run 50 ticks, update policy, run 50 more. Verify new policy affects decisions after tick 50.
2. **Unknown agent**: `update_agent_policy("NONEXISTENT", ...)` → error
3. **Invalid JSON**: `update_agent_policy("BANK_A", "not json")` → error
4. **No-op**: Update with identical policy → same behavior
5. **Determinism**: Same ticks + same policy updates at same points = identical output
6. **Cross day-boundary**: Run 100 ticks (1 day), update policy, run 100 more ticks (day 2). Verify day 2 uses new policy.

## How I'll Use It

```python
orch = Orchestrator.new(ffi_config)

for scenario_day in range(num_days):
    # Run one day
    for tick in range(ticks_per_day):
        orch.tick()
    
    # Collect this day's costs
    costs = {aid: orch.get_agent_accumulated_costs(aid) for aid in agent_ids}
    
    # LLM optimization (~15s per agent, 4 in parallel)
    new_policies = await optimize_all_agents(costs, ...)
    
    # Inject new policies for tomorrow
    for agent_id, policy_json in new_policies.items():
        orch.update_agent_policy(agent_id, policy_json)  # ← YOUR METHOD
```

## Relevant Code Pointers

| What | Where |
|------|-------|
| `Orchestrator` struct + `policies` field | `simulator/src/orchestrator/engine.rs:754` |
| Policy creation from config | `engine.rs:1022-1028` |
| `PolicyConfig::FromJson` parsing | `simulator/src/ffi/types.rs:452-462` |
| `create_policy()` function | `simulator/src/policy/tree/mod.rs` |
| PolicyTree data structures | `simulator/src/policy/tree/types.rs` |
| PyO3 wrapper (`PyOrchestrator`) | `simulator/src/ffi/orchestrator.rs:320+` |
| Existing `get_agent_policies()` | `ffi/orchestrator.rs:1448` |

## Full Design Context

If you want the broader picture (why we need this, how rounds vs scenario-days work, the prompt context strategy):
- `docs/reports/time-model-clarification.md` — the full time model design doc
- `docs/reports/rust-engine-handover-mid-sim-policy-update.md` — detailed handover with prompt budget analysis

## Priority

Medium. Not blocking current work — the round-based approach works. But this is the key enabler for the most interesting feature: watching AI agents adapt within a multi-day crisis, optimizing after each day based on that day's results instead of replaying the whole 10-day scenario each time.

Thanks! 🏦
