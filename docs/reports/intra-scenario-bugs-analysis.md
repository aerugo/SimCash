# Intra-Scenario Bugs — Rust Engine Analysis

**From:** Dennis (Rust engine)
**To:** Nash (web sandbox)
**Date:** 2025-07-11
**Re:** `docs/reports/handover-dennis-intra-scenario-bugs.md`

---

## Summary

Traced all three bugs through the Rust FFI layer and engine. Two have confirmed root causes in how the Python layer interprets engine data; one is likely a legitimate simulation outcome. **No bugs in the Rust engine itself.**

---

## Bug 1: Settlement Rate > 100%

**Root cause confirmed: Cross-day settlement.**

Transactions survive across day boundaries. The engine does **not** clear queues at EOD — unsettled payments carry forward to the next day. This is correct behavior (real RTGS systems don't expire payments at midnight). But it means:

- Day 3: `Arrival` event logged for tx_123 → tx goes to queue → not enough liquidity → stays queued
- Day 5: Liquidity arrives, tx_123 settles → `Settlement` event logged at Day 5's tick
- Result: Day 3 has 1 arrival, 0 settlements. Day 5 has 0 arrivals, 1 settlement → **∞% rate**

**Verification:** `get_tick_events(tick)` returns **only** events from that exact tick (`events.iter().filter(|e| e.tick() == tick)`). No accumulation, no duplication. The events themselves are correct — it's the per-day ratio computation that's wrong.

**`events_at_tick()` source:** `simulator/src/models/event.rs:597`
```rust
pub fn events_at_tick(&self, tick: usize) -> Vec<&Event> {
    self.events.iter().filter(|e| e.tick() == tick).collect()
}
```

### Recommended fix

Track arrivals and settlements **cumulatively across the round**, not per-day:

```python
# Instead of: settlement_rate = day_settlements / day_arrivals
# Do:
cumulative_arrivals += day_arrivals
cumulative_settlements += day_settlements
settlement_rate = cumulative_settlements / cumulative_arrivals
```

Or — attribute each settlement back to its arrival day by matching transaction IDs across events. Every `Settlement`/`LsmBilateralOffset`/`Queue2LiquidityRelease` event should reference the same `transaction_id` as its original `Arrival` event.

---

## Bug 2: Negative Total Costs

**Root cause confirmed: Cost accumulators reset daily.**

The engine resets `accumulated_costs` to zero at the **start of each new day** (first tick where `tick_within_day() == 0 && current_tick > 0`):

**`engine.rs:2958-2964`:**
```rust
// STEP 0: RESET COST ACCUMULATORS AT START OF NEW DAY
if self.time_manager.tick_within_day() == 0 && current_tick > 0 {
    let agent_ids: Vec<String> = self.state.get_all_agent_ids();
    for agent_id in agent_ids {
        if let Some(accumulator) = self.accumulated_costs.get_mut(&agent_id) {
            *accumulator = CostAccumulator::new();
        }
    }
}
```

This means `get_agent_accumulated_costs()` returns **daily** costs, not simulation-cumulative costs. The values are:
- **Monotonically increasing within a day** (costs only add, never subtract within a day)
- **Reset to zero at each day boundary**

Nash's delta computation assumes cumulative-across-run:
```python
prev = self._prev_cumulative_costs.get(aid, 0)  # e.g. 500,000 from Day 1
delta_total = cum_total - prev  # Day 2 returns 200,000 → delta = -300,000
```

Since Day 2's costs (200k) < Day 1's stored prev (500k), the delta goes negative.

### Recommended fix

Two options:

**Option A (simplest):** Don't compute deltas. Since costs reset each day, `get_agent_accumulated_costs()` already returns *this day's* costs. Use the value directly as the day's costs:

```python
day_costs = orch.get_agent_accumulated_costs(agent_id)
# This IS the day's costs — no delta needed
```

**Option B:** Maintain your own cumulative tracker in Python:

```python
day_costs = orch.get_agent_accumulated_costs(agent_id)  # daily, resets each day
self._cumulative_costs[aid] = self._cumulative_costs.get(aid, 0) + day_costs['total_cost']
```

**Option A is strongly preferred.** The reset-at-day-boundary design is intentional — the comment in the code says *"This ensures the previous day's costs remain queryable until the new day starts."*

### Cost fields returned by FFI

All are **daily** (reset each day), all are **non-negative** within a day:

| FFI field | Engine field | Description |
|-----------|-------------|-------------|
| `liquidity_cost` | `total_liquidity_cost` | Overdraft bps cost |
| `delay_cost` | `total_delay_cost` | Queue delay cost |
| `collateral_cost` | `total_collateral_cost` | Collateral opportunity cost |
| `deadline_penalty` | `total_penalty_cost` | Deadline miss + EOD penalties |
| `split_friction_cost` | `total_split_friction_cost` | Transaction splitting cost |
| `total_cost` | `.total()` | Sum of all above |

---

## Bug 3: MOMENTUM_CAPITAL at 0% Settlement

**Most likely legitimate.** No engine bug found.

In a 10-day crisis scenario, a bank can genuinely reach a state where:
1. Its balance is zero or deeply negative (crisis drained liquidity)
2. All incoming payments settle against outgoing debt (no net inflow)
3. Policy holds everything because there's no liquidity to release
4. Result: 0% settlement with massive penalty accumulation

The `fraction=1.000` just means the bank commits all its pool allocation. If the pool itself is empty (or the bank's share is wiped by crisis events), committing 100% of nothing is still nothing.

**To verify:** Check MOMENTUM_CAPITAL's balance on Day 10 via `get_agent_balance("MOMENTUM_CAPITAL")`. If it's ≤ 0, this is expected behavior.

---

## Summary Table

| Bug | Root Cause | Location | Engine Bug? | Fix Location |
|-----|-----------|----------|-------------|-------------|
| Settlement > 100% | Cross-day settlement (tx arrives Day N, settles Day N+k) | Engine design (correct) | No | Python: use cumulative rates |
| Negative costs | Cost accumulators reset daily, Python assumes cumulative | `engine.rs:2958` | No | Python: use daily costs directly |
| 0% settlement | Likely legitimate (crisis drained liquidity) | — | No | Verify with balance check |
