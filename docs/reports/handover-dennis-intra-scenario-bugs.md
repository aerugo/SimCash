# Handover: Intra-Scenario Settlement & Cost Accounting Bugs

**For:** Dennis  
**From:** Nash  
**Date:** 2026-02-21  
**Priority:** High — these bugs make intra-scenario mode output nonsensical  
**Branch:** `feature/interactive-web-sandbox` (commit `31c6f6aa`)

## Context

We just shipped "intra-scenario optimization" — a mode where a multi-day scenario (e.g. 10-day crisis) runs one scenario-day at a time on a **persistent Orchestrator**, with LLM optimization between days. This differs from the normal mode where each "round" creates a fresh Orchestrator and runs the entire multi-day scenario from scratch.

The feature works end-to-end: Orchestrator persists, policies inject via `update_agent_policy()`, crisis events fire on correct days, LLM optimizes between days. But the **settlement counting and cost accounting are wrong**.

## Observed Bugs (Game `7e314cdd`, deployed rev 94)

### Bug 1: Settlement Rate > 100%

**Observed:** Day 10 shows 159.3% settlement rate. METRO_CENTRAL shows 640.0%.  
**Expected:** Settlement rate should be 0–100% per day.

**Likely cause:** In `GameDay._compute_event_summary()`, events are counted to compute arrivals and settlements. But in intra-scenario mode, the events passed to `GameDay` may include cumulative events from the persistent Orchestrator rather than just the current day's events. Or alternatively, settlements from previous days' arrivals (finally settling on a later day) are counted as settlements without corresponding arrivals in that day.

**Key question for investigation:** When `_run_scenario_day()` calls `self._live_orch.get_tick_events(tick)` for ticks in range `[day_tick_offset, day_tick_offset + ticks_per_day)`, does it return:
- (a) Only events from that specific tick? ✓ expected
- (b) Events from all ticks up to and including that tick? ✗ would cause accumulation

Check `simulator/src/ffi/orchestrator.rs` → `get_tick_events()` to verify.

### Bug 2: Negative Total Costs

**Observed:** METRO_CENTRAL has total cost -$40,268,871. System total is -$23,038,972.  
**Expected:** Costs should be non-negative (all cost rates are positive).

**Likely cause:** The delta-cost computation in `_run_scenario_day()`:
```python
prev = self._prev_cumulative_costs.get(aid, 0)
delta_total = cum_total - prev
```
If `get_agent_accumulated_costs()` returns cumulative costs that somehow decrease (e.g. balance changes interpreted as negative costs, or an overflow), the delta goes negative.

**Also suspicious:** The cost breakdown approximation using ratios:
```python
ratio = delta_total / cum_total if cum_total != 0 else 0
```
If `delta_total` is negative but `cum_total` is positive, the ratio is negative, producing negative cost components.

**Key question:** Does `get_agent_accumulated_costs()` actually return monotonically increasing values across ticks? Or can certain cost components (like `liquidity_cost` which maps to `overdraft_bps` in the engine) reset or fluctuate?

Check `simulator/src/ffi/orchestrator.rs` → `get_agent_accumulated_costs()` and trace back to what the engine tracks.

### Bug 3: MOMENTUM_CAPITAL at 0.0% Despite fraction=1.000

**Observed:** MOMENTUM_CAPITAL shows 0% settlement on Day 10 with $17.2M in penalties.  
**Expected:** With fraction=1.000, a bank commits all its liquidity. Shouldn't result in 0% settlement unless the bank has no liquidity left (crisis wiped it out).

**This might actually be correct** — by Day 10, after the crisis, MOMENTUM_CAPITAL may genuinely have no funds. But verify by checking its balance history.

## Relevant Code Paths

### Settlement counting
- `web/backend/app/game.py` → `GameDay._compute_event_summary()` (line ~63)
- Counts `Arrival` events for arrivals, `{RtgsImmediateSettlement, LsmBilateralOffset, Queue2LiquidityRelease}` for settlements
- Uses `sender_id` for arrivals, `sender_id || sender` for settlements

### Intra-scenario simulation
- `web/backend/app/game.py` → `_run_scenario_day()` (line ~270)
- Creates Orchestrator on first day of round, persists via `self._live_orch`
- Runs `ticks_per_day` ticks, collects events per tick
- Computes delta costs from cumulative `get_agent_accumulated_costs()`
- Destroys Orchestrator at end of last scenario day

### Rust FFI methods used
- `orchestrator.tick()` — advance one tick
- `orchestrator.get_tick_events(tick)` — get events for a tick
- `orchestrator.get_agent_balance(agent_id)` — current balance
- `orchestrator.get_agent_accumulated_costs(agent_id)` — cumulative costs
- `orchestrator.update_agent_policy(agent_id, policy_json)` — inject new policy

### Key files
- `simulator/src/ffi/orchestrator.rs` — FFI implementation
- `simulator/src/orchestrator/engine.rs` — engine tick/event logic
- `simulator/src/costs/` — cost accumulation logic
- `web/backend/app/game.py` — Python game loop

## What I Need From You

1. **Verify `get_tick_events(tick)`** — Does it return only events from the specific tick index, or could it return accumulated/duplicate events when called on a persistent Orchestrator across many ticks?

2. **Verify `get_agent_accumulated_costs()`** — Are these truly monotonically increasing? Can they decrease? What exactly do the fields (`total_cost`, `delay_cost`, `deadline_penalty`, `liquidity_cost`, `collateral_cost`, `split_friction_cost`) represent in cumulative terms?

3. **Check if arrivals from Day N can settle on Day N+1** — In a persistent Orchestrator, a payment that arrives on Day 3 might not settle until Day 5 (queued, then LSM offset later). This would mean:
   - Day 3 `GameDay` has the Arrival event but no Settlement
   - Day 5 `GameDay` has the Settlement event but no Arrival
   - Result: Day 3 shows low settlement %, Day 5 shows > 100%
   - **This is the most likely root cause of Bug 1.**

4. **Write a short report** with findings and recommended fix approach. If the cross-day settlement theory is correct, we may need to:
   - Track arrivals cumulatively across the round, not per-day
   - Compute settlement rate as cumulative_settled / cumulative_arrivals
   - Or: attribute settlements to the day their Arrival occurred (requires tracing payment IDs)

## How to Reproduce

```bash
# On deployed instance (rev 94):
# https://simcash-487714.web.app/experiment/7e314cdd
# (game is complete, all 10 days visible)

# Or locally:
cd SimCash/web/backend
SIMCASH_DEV_TOKEN=KclRK81alajdWpJ0nvO60LzNZTmuRP5s2Mya0ohEyoI \
  uv run uvicorn app.main:app --host 127.0.0.1 --port 8642

# Frontend:
cd SimCash/web/frontend && npm run dev

# Navigate to Library → Crisis Resolution 10 Day
# Set: Max Days=10, Eval Samples=1, Optimization Schedule="Every scenario day"
# Launch and run all 10 days
# Observe settlement rates > 100% and negative costs on later days
```
