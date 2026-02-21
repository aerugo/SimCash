# Intra-Scenario Optimization: Implementation Plan

**Date:** 2026-02-21  
**Prerequisite:** `update_agent_policy()` on Rust Orchestrator ✅ (Dennis, merged)

## Goal

For multi-day scenarios (e.g., crisis_resolution_10day with 10 days × 100 ticks), allow LLM optimization **between scenario days** within a single engine run. Currently, each "round" creates a fresh Orchestrator and runs all 1000 ticks. With this feature, a single round pauses at each EndOfDay, optimizes, injects new policies via `update_agent_policy()`, and continues — with all state (balances, queues, collateral) carrying forward.

## Architecture Change

### Current Flow (Round-Based)
```
Round 1: Orchestrator.new() → tick×1000 → costs → LLM optimize → destroy
Round 2: Orchestrator.new() → tick×1000 → costs → LLM optimize → destroy
...
```

### New Flow (Intra-Scenario)
```
Round 1:
  Orchestrator.new()
  → tick×100 (Day 1) → costs → LLM optimize → update_agent_policy()
  → tick×100 (Day 2) → costs → LLM optimize → update_agent_policy()
  → ...
  → tick×100 (Day 10) → costs → LLM optimize → destroy
```

## Changes Required

### 1. Game Model (`game.py`)

**New config field:**
```python
optimization_schedule: Literal["every_round", "every_scenario_day"] = "every_round"
```

**New method: `_run_single_day_from_orch()`**
Run `ticks_per_day` ticks on an existing Orchestrator (don't create/destroy it).

**Modified `simulate_day()` / `run_day()`:**
- If `optimization_schedule == "every_round"`: current behavior (create fresh Orchestrator per round)
- If `optimization_schedule == "every_scenario_day"`: keep Orchestrator alive, run one scenario-day at a time

**Persistent Orchestrator:**
- `self._live_orch: Orchestrator | None` — held between scenario days
- Created at start of round, destroyed at end of round
- `self._scenario_day_index: int` — which scenario day we're on within the current round

**GameDay semantics:**
- Each `GameDay` now represents one **scenario day** (not one round)
- `max_days` = `num_scenario_days * num_rounds` for intra-scenario mode
- Or better: `max_days` stays as "max rounds" and we add a sub-index for scenario days

**Revised approach — keep it simple:**
- `max_days` remains "max optimization steps" 
- For a 10-day scenario with `every_scenario_day`: `max_days = 10` means 10 optimization steps = 1 full round
- For `max_days = 20`: 2 full rounds of the 10-day scenario
- Each "day" in the UI = one scenario day with its own optimization step
- The frontend already calls them "rounds" — this is fine

### 2. Simulation Runner

New method on `Game`:

```python
def _run_scenario_day(self) -> tuple[list[dict], dict[str, list], dict[str, dict], dict[str, int], int, list[list[dict]]]:
    """Run one scenario day (ticks_per_day ticks) on the persistent Orchestrator."""
    if self._live_orch is None:
        # Start of a new round — create Orchestrator
        seed = self._base_seed + (self.current_day // self._scenario_num_days)
        ffi_config = self._build_ffi_config(seed)
        self._live_orch = Orchestrator.new(ffi_config)
        self._day_tick_offset = 0
    
    ticks_per_day = self.raw_yaml.get("simulation", {}).get("ticks_per_day", 12)
    
    day_events = []
    day_tick_events = []
    for t in range(ticks_per_day):
        tick = self._day_tick_offset + t
        self._live_orch.tick()
        events = self._live_orch.get_tick_events(tick)
        tick_event_list = [dict(e) for e in events]
        day_events.extend(tick_event_list)
        day_tick_events.append(tick_event_list)
    
    self._day_tick_offset += ticks_per_day
    
    # Collect costs (accumulated across all days so far)
    costs, per_agent_costs, total_cost = self._collect_costs()
    balance_history = self._collect_balances()
    
    # Check if this is the last scenario day
    scenario_day = self.current_day % self._scenario_num_days
    if scenario_day == self._scenario_num_days - 1:
        # End of round — destroy Orchestrator
        self._live_orch = None
        self._day_tick_offset = 0
    
    return day_events, balance_history, costs, per_agent_costs, total_cost, day_tick_events
```

### 3. Policy Injection

After LLM optimization, inject policies into the live Orchestrator:

```python
def _inject_policies_into_orch(self):
    """Update all agent policies in the live Orchestrator."""
    if self._live_orch is None:
        return
    for aid in self.agent_ids:
        policy_json = json.dumps(self.policies[aid])
        self._live_orch.update_agent_policy(aid, policy_json)
```

Call this in `commit_day()` after policies are updated.

### 4. Cost Tracking (Delta Costs)

**Problem:** `get_agent_accumulated_costs()` returns cumulative costs since tick 0. For intra-scenario optimization, we need **per-day** costs (delta from previous day).

**Solution:** Track cumulative costs at each day boundary, compute delta:

```python
self._prev_cumulative_costs: dict[str, int] = {}

def _collect_day_costs(self) -> tuple[dict, dict, int]:
    """Get costs for just this scenario day (delta from previous day)."""
    current_cumulative = {}
    for aid in self.agent_ids:
        ac = self._live_orch.get_agent_accumulated_costs(aid)
        current_cumulative[aid] = int(ac.get("total_cost", 0))
    
    # Compute delta
    day_costs = {}
    for aid in self.agent_ids:
        prev = self._prev_cumulative_costs.get(aid, 0)
        delta = current_cumulative[aid] - prev
        day_costs[aid] = delta
    
    self._prev_cumulative_costs = current_cumulative
    return day_costs
```

### 5. Frontend Changes

Minimal — the frontend already shows "rounds" and handles streaming optimization. The main changes:
- Show "Day 3/10 of Round 1" instead of just "Round 3/10"
- The Cost Evolution chart now shows per-scenario-day costs
- Activity feed: "Simulating day 3..." instead of "Simulating round 3..."

### 6. Launch Config

Add option to scenario detail page:
```
Optimization Schedule: [Every round ▼]
  - Every round (replay full scenario each time)
  - Every scenario day (optimize between days, continuous simulation)
```

For single-day scenarios, "every scenario day" = "every round" (no difference).

### 7. Eval Samples

For intra-scenario mode, eval samples are **disabled** (doesn't make sense — we can't re-run a scenario day with a different seed while keeping state). The representative run IS the run. Set `num_eval_samples = 1` implicitly.

### 8. Checkpoint Persistence

The live Orchestrator state needs to survive checkpoints. Two approaches:
- **A:** Use `orch.save_state()` / `Orchestrator.load_state()` to serialize/restore
- **B:** Don't checkpoint the Orchestrator — if the server restarts, the round restarts

**Recommendation:** Option B for now. Intra-scenario rounds are fast enough (~10 min for 10 days). Restarting from the beginning of a round on server restart is acceptable.

## Implementation Order

1. Add `optimization_schedule` to Game config + checkpoint
2. Implement `_run_scenario_day()` with persistent Orchestrator  
3. Delta cost tracking
4. Policy injection via `update_agent_policy()`
5. Wire into `simulate_day()` / WS handler
6. Frontend: day label + launch config option
7. Test end-to-end with crisis_resolution_10day
