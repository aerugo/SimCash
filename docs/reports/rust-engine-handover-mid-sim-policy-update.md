# Rust Engine Feature Request: Mid-Simulation Policy Update

**Date:** 2026-02-21  
**From:** Nash (AI research engineer on the web sandbox)  
**For:** Rust engine developer  
**Priority:** Medium — not blocking current work, enables next major feature  

---

## Context

The SimCash web sandbox runs a **multi-round policy optimization game** where LLM agents learn payment strategies. Currently, each "round" creates a fresh `Orchestrator`, runs the entire scenario (all days × all ticks), tears it down, then the LLM proposes new policies for the next round.

This works fine for single-day scenarios (e.g., the paper's 2-bank 12-tick experiment). But for multi-day scenarios like the 10-day crisis resolution (1000 ticks across 10 days with day-specific events like a central bank intervention on Day 4), we need the ability to **optimize between scenario days without restarting the simulation**.

See `docs/reports/time-model-clarification.md` for the full design document.

## What's Needed

A new method on `Orchestrator` (both the Rust `RustOrchestrator` and the PyO3 `PyOrchestrator`):

```rust
/// Update an agent's policy mid-simulation.
/// The new policy takes effect starting from the next tick.
/// 
/// # Arguments
/// * `agent_id` - The agent whose policy to update
/// * `policy_json` - A v2.0 policy JSON string (same format as FromJson)
///
/// # Errors
/// Returns an error if the agent_id is unknown or the policy JSON is invalid.
pub fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> Result<(), String>
```

## Where It Fits in the Engine

Looking at the current code:

1. **Policies live in** `Orchestrator.policies: HashMap<String, Box<dyn CashManagerPolicy>>` (engine.rs:754)

2. **Policies are created at init** from `PolicyConfig::FromJson { json }` via `crate::policy::tree::create_policy()` (engine.rs:1022-1028)

3. **The `tick()` method** reads from `self.policies` each tick to make payment decisions

So the implementation should be roughly:

```rust
pub fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> Result<(), String> {
    // 1. Verify agent exists
    if !self.policies.contains_key(agent_id) {
        return Err(format!("Unknown agent: {}", agent_id));
    }
    
    // 2. Parse the JSON into a PolicyConfig::FromJson
    let policy_config = PolicyConfig::FromJson { json: policy_json.to_string() };
    
    // 3. Create a new policy executor (same as init path)
    let new_policy = crate::policy::tree::create_policy(&policy_config)
        .map_err(|e| format!("Invalid policy JSON: {}", e))?;
    
    // 4. Replace the old policy
    self.policies.insert(agent_id.to_string(), Box::new(new_policy));
    
    Ok(())
}
```

And the PyO3 wrapper in `ffi/orchestrator.rs`:

```rust
/// Update an agent's policy mid-simulation.
/// 
/// >>> orch.update_agent_policy("BANK_A", '{"version": "2.0", ...}')
fn update_agent_policy(&mut self, agent_id: &str, policy_json: &str) -> PyResult<()> {
    self.inner.update_agent_policy(agent_id, policy_json).map_err(|e| {
        PyErr::new::<pyo3::exceptions::PyValueError, _>(e)
    })
}
```

## What About `liquidity_allocation_fraction`?

The LLM's policy JSON includes `parameters.initial_liquidity_fraction`, which controls how much of the pool the agent commits at the start of each day. This is currently set on the `AgentConfig` at init time and applied during the opening balance allocation phase.

For mid-simulation updates, there are two options:

**Option A (simpler):** Only update the decision tree policy, not the liquidity fraction. The fraction only matters at day-start, and by the time we're updating mid-sim, the current day's allocation has already happened. The new fraction would take effect if we support `save_state`/`load_state` round-trips.

**Option B (complete):** Also accept and store a new `liquidity_allocation_fraction` on the agent, to be applied at the next `EndOfDay` → day-start transition. This requires the engine to read the fraction from a mutable agent field rather than the immutable config.

**Recommendation:** Start with Option A. It's simpler and covers the immediate use case. We can add Option B later if needed.

## How the Web Backend Will Use It

```python
# In game.py — run a multi-day scenario with per-day optimization

orch = Orchestrator.new(ffi_config)

for scenario_day in range(num_days):
    # Run one day's worth of ticks
    for tick in range(ticks_per_day):
        orch.tick()
    
    # Collect costs, events for this day
    day_costs = orch.get_agent_accumulated_costs(...)
    
    # LLM optimization (async, ~15s per agent)
    new_policies = await optimize_all_agents(day_costs, ...)
    
    # Apply new policies for the next day
    for agent_id, policy_json in new_policies.items():
        orch.update_agent_policy(agent_id, policy_json)  # <-- THE NEW METHOD
    
    # Next day continues with new policies, same simulation state
```

The key point: **no Orchestrator teardown between days**. Balances, queues, collateral, and all state carry forward naturally. Only the decision-making policy changes.

## What Doesn't Need to Change

- **RNG**: No change. The simulation continues deterministically.
- **Balances/queues**: No reset. Everything carries forward.
- **Events**: `EndOfDay` events continue to fire at day boundaries as normal.
- **Scenario events**: Day-specific triggers (crisis, intervention) still fire on schedule.
- **`save_state`/`load_state`**: Should work as-is since policies are serialized from the current state.

## Testing

Suggested test cases:

1. **Basic**: Create orchestrator, run 50 ticks, update policy, run 50 more ticks. Verify the new policy affects decisions after tick 50.
2. **Unknown agent**: `update_agent_policy("NONEXISTENT", ...)` → error.
3. **Invalid JSON**: `update_agent_policy("BANK_A", "not json")` → error.
4. **No-op update**: Update with the same policy → no change in behavior.
5. **Determinism**: Same sequence of ticks + policy updates = same output (same seed).
6. **Multi-day**: Run across day boundary, update after EndOfDay, verify next day uses new policy.

## Timeline

This is not blocking current work — the web sandbox is functional with the round-based approach. But it's the key enabler for the most interesting feature: watching AI agents adapt their strategies **within** a multi-day crisis scenario, optimizing after each day based on that day's results.

If you have questions about the policy JSON format or how `create_policy` works with the tree types, the relevant code is:
- `simulator/src/policy/tree/types.rs` — the `PolicyTree` data structures
- `simulator/src/policy/tree/mod.rs` — `create_policy()` function
- `simulator/src/ffi/types.rs:420` — `parse_policy_config()` for how `FromJson` is handled at init

## Prompt Context Strategy for Intra-Scenario Optimization

This is arguably the hardest design problem in the whole feature. When optimizing between scenario days (rather than between full rounds), the LLM needs enough historical context to make informed decisions but the prompt can't grow unboundedly.

### Current Approach (Round-Based)

The current `build_prompt_for_agent()` in `streaming_optimizer.py` builds context as:

1. **System prompt** (~19k chars): Scenario rules, cost rate docs, policy schema, constraint rules. Fixed size.
2. **Iteration history**: One `SingleAgentIterationRecord` per previous round — includes cost, policy, and whether it was accepted. Grows linearly with rounds.
3. **Simulation trace**: Filtered tick-by-tick events from the **last round only** (the agent's own Arrivals, Settlements, Queued events). This is the big one — can be 50-150k chars for a 1000-tick scenario.
4. **Current policy**: Full JSON tree (~500-1500 chars).
5. **Cost breakdown**: Delay, penalty, overdraft for this agent.

Total: ~170-190k chars by Round 2 of the crisis scenario. GLM-4.7 handles this but takes 12-75s.

### The Problem with Intra-Scenario Optimization

If we optimize after **every scenario day** in a 10-day crisis scenario, by Day 10 the prompt would include:
- 9 iteration history records (one per completed day) — small, ~2k total
- Simulation trace from Day 10 only — ~15k (100 ticks vs 1000)
- **But**: the LLM has no visibility into Days 1-9's events, only their cost summaries

This is actually **better** than the current approach for prompt size. The trace is 1/10th the size (one day vs full scenario). The risk is losing context about *why* costs changed — the LLM sees "Day 3 cost was $72M, Day 4 cost was $500K" but doesn't see the intervention events that caused the drop.

### Proposed Context Strategy: Full Traces with Graceful Compaction

The target model context is **~170k tokens**. At ~4 chars/token, that's ~680k chars. The system prompt is ~19k chars, leaving ~660k for user prompt content. Each day's filtered trace is ~15k chars (100 ticks), so we can fit **~40 days of full traces** before hitting the limit. For most scenarios (≤10 days), we never need to compact at all.

The strategy: **include full traces for as many days as will fit, then compact the oldest days first.**

#### Always Include (Non-Negotiable)
- System prompt (scenario rules, cost rates, schema) — ~19k chars
- Current policy (full JSON) — ~1.5k chars
- Current day's cost breakdown and full simulation trace
- Scenario events timeline (crisis triggers, interventions across all days) — ~1-2k chars
- Policy change log (all days) — ~1-2k chars

#### Full Traces (Default for All Days)
Include the **complete filtered simulation trace** for every day in the round. For a 10-day crisis scenario at 100 ticks/day, this is ~150k chars total — well within budget.

#### Compaction (Only When Exceeding ~170k Token Budget)
When total prompt size exceeds the budget, compact the **oldest** days first while keeping recent days intact:

**Level 1 — Summarized traces for oldest days:**
Replace the oldest day's full trace with a structured summary:
```
Day 1 Summary (100 ticks):
  Arrivals: 187 payments, total $2.3M
  Settled: 156 (83.4%) — 142 RTGS immediate, 14 LSM bilateral
  Queued: 31 payments ($450K stuck at EOD)
  Key events: tick 23 — bilateral limit hit with MOMENTUM_CAPITAL
  Cost: $21.5M (delay=$53, penalty=$21.4M)
```
This compresses ~15k chars → ~500 chars per day (30× reduction).

**Level 2 — One-line summaries for very old days:**
If Level 1 isn't enough (very long scenarios, 30+ days):
```
Day 1: cost=$21.5M, settled=83.4%, policy=fraction:1.000 | Day 2: cost=$28.4M, settled=67.9% ...
```
~100 chars per day (150× reduction).

**Compaction algorithm:**
```python
def build_context_with_budget(
    day_results: list[DayResult],
    agent_id: str,
    token_budget: int = 170_000,
    chars_per_token: float = 4.0,
) -> list[DayContext]:
    char_budget = int(token_budget * chars_per_token)
    fixed_overhead = 25_000  # system prompt + policy + metadata
    available = char_budget - fixed_overhead
    
    # Start with full traces for all days
    contexts = []
    for i, day in enumerate(day_results):
        trace = get_full_trace(agent_id, day)
        contexts.append(DayContext(
            day_num=i,
            level="full",
            trace=trace,
            size=len(trace),
            summary=build_day_summary(agent_id, day),  # always precompute
        ))
    
    total = sum(c.size for c in contexts)
    
    # If within budget, we're done — full traces everywhere
    if total <= available:
        return contexts
    
    # Compact oldest days first (preserve recent context)
    for c in contexts:  # oldest first
        if total <= available:
            break
        old_size = c.size
        c.level = "summary"
        c.size = len(c.summary)
        total -= (old_size - c.size)
    
    # If still over, compress summaries to one-liners
    if total > available:
        for c in contexts:
            if total <= available:
                break
            if c.level == "summary":
                old_size = c.size
                c.level = "oneliner"
                c.size = len(c.oneliner)
                total -= (old_size - c.size)
    
    return contexts
```

### Implementation

```python
def build_intra_scenario_context(
    agent_id: str,
    current_day: int,
    total_days: int,
    day_results: list[DayResult],  # All days so far in this round
    current_policy: dict,
    cost_rates: dict,
    token_budget: int = 170_000,
) -> str:
    sections = []
    
    # Section 1: Where we are
    sections.append(f"## SCENARIO PROGRESS: Day {current_day + 1} of {total_days}")
    sections.append(f"This is an intra-scenario optimization. The simulation is paused "
                    f"at the end of Day {current_day + 1}. Your policy update will take "
                    f"effect starting Day {current_day + 2}.")
    
    # Section 2: Scenario events timeline (crisis triggers, interventions)
    sections.append("## SCENARIO EVENTS")
    for i, day in enumerate(day_results):
        scenario_events = [e for e in day.events 
                          if e.get("event_type") == "ScenarioEventExecuted"]
        if scenario_events:
            for se in scenario_events:
                sections.append(f"  Day {i+1}: {se.get('description', 'scenario event')}")
    
    # Section 3: Cost timeline (compact, all days)
    sections.append("## COST HISTORY")
    for i, day in enumerate(day_results):
        cost = day.per_agent_costs.get(agent_id, 0)
        marker = " ← CURRENT" if i == current_day else ""
        sections.append(f"  Day {i+1}: ${cost:,}{marker}")
    
    # Section 4: Policy change log
    sections.append("## POLICY CHANGES")
    for i in range(1, len(day_results)):
        old_f = day_results[i-1].policies.get(agent_id, {}).get(
            "parameters", {}).get("initial_liquidity_fraction", 1.0)
        new_f = day_results[i].policies.get(agent_id, {}).get(
            "parameters", {}).get("initial_liquidity_fraction", 1.0)
        if old_f != new_f:
            sections.append(f"  Day {i}→{i+1}: fraction {old_f:.3f} → {new_f:.3f}")
    
    # Section 5: Simulation traces — full for all days, compact oldest if over budget
    day_contexts = build_context_with_budget(day_results, agent_id, token_budget)
    
    sections.append("## SIMULATION TRACES")
    for dc in day_contexts:
        if dc.level == "full":
            sections.append(f"### Day {dc.day_num + 1} (full trace)")
            sections.append(dc.trace)
        elif dc.level == "summary":
            sections.append(f"### Day {dc.day_num + 1} (summary)")
            sections.append(dc.summary)
        else:  # oneliner
            sections.append(f"  Day {dc.day_num + 1}: {dc.oneliner}")
    
    return "\n\n".join(sections)
```

### Estimated Prompt Sizes (10-Day Crisis Scenario, 100 ticks/day)

| Day | Full Traces Included | Total User Prompt | Budget Status |
|-----|---------------------|-------------------|---------------|
| 1   | Day 1 (full)        | ~35k chars (~9k tokens) | ✅ Way under |
| 5   | Days 1-5 (all full) | ~95k chars (~24k tokens) | ✅ Under |
| 10  | Days 1-10 (all full)| ~170k chars (~43k tokens) | ✅ Under |
| 20  | Days 1-20 (all full)| ~320k chars (~80k tokens) | ✅ Under |
| 40  | Days 1-40 (all full)| ~620k chars (~155k tokens) | ✅ At limit |
| 50  | Days 1-10 summary + 11-50 full | ~630k chars (~158k tokens) | ⚠️ Compacting oldest 10 |

**For 10-day scenarios: full traces for every day, no compaction needed.** The budget only becomes relevant for scenarios with 40+ days, at which point the oldest days get gracefully compacted while recent days keep full detail.

### Key Design Decision: What Does the LLM "Remember"?

In the real world, a bank cash manager reviewing end-of-day results would have:
- **Full memory** of recent days — what happened, why, what they tried
- **Diminishing detail** for older days — they remember the outcomes and big events, not every transaction
- **Perfect recall** of scenario-wide events (crisis triggers, interventions)
- **Awareness of trends** (costs rising/falling, settlement rates improving)

The context strategy mirrors this naturally. For realistic scenario lengths (≤10 days), the LLM gets **complete information** — every tick of every day. For unusually long scenarios, the compaction preserves the narrative arc while freeing space for recent detail. This is actually more context than a human cash manager would have, since they'd be working from memory and summary reports for anything older than a few days.

### Note on the `iteration_history` Parameter

The existing `build_single_agent_context()` accepts `iteration_history: list[SingleAgentIterationRecord]`. For intra-scenario optimization, each "iteration" maps to a scenario day rather than a full round. The `SingleAgentIterationRecord` already captures cost + policy + accepted status, which is exactly the Tier 2 summary. So the existing infrastructure largely works — we just need to add the trace windowing and scenario event extraction on top.

Thanks! 🏦
