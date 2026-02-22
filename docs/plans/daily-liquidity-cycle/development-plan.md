# Daily Liquidity Cycle — Development Plan

**Status**: Pending
**Created**: 2025-07-11
**Branch**: TBD (`feature/daily-liquidity-cycle`)

## Summary

Implement daily liquidity reallocation at day boundaries so that `initial_liquidity_fraction` becomes a live, daily strategic decision instead of a one-shot Day 1 parameter. At EOD, return allocated liquidity to the pool. At start of next day, reallocate according to the current policy's fraction.

This is necessary for multi-day scenarios to produce economically meaningful results. Without it, the LLM optimizer cannot learn "I should commit less/more liquidity tomorrow based on today."

## Motivation (from RTGS domain expert)

In real RTGS systems, liquidity is a daily cycle:
1. **Start of day**: Banks pledge collateral / deposit funds for intraday liquidity
2. **During day**: Banks manage that liquidity (what SimCash models well)
3. **End of day**: Intraday credit repaid, collateral released, positions square
4. **Next morning**: Fresh liquidity decision based on yesterday's experience

The daily liquidity decision is the core strategic variable in RTGS cash management — it's what BIS WP 1310 is fundamentally about.

## Critical Invariants

- **INV-1**: Money is i64 — all pool/balance arithmetic in integer cents
- **INV-2**: Determinism — same config + seed = identical reallocation sequence
- **INV-4**: Balance conservation — money moves between pool and RTGS, never created/destroyed
- **INV-5**: Replay identity — save_state must capture pool state for correct restore
- **INV-6**: Event completeness — reallocation must emit events (for observability)

## Current State

- `liquidity_pool` and `liquidity_allocation_fraction` are on `AgentConfig` (immutable after init)
- `Agent.allocated_liquidity` tracks what was allocated (for opportunity cost calculation)
- Allocation happens once in `Orchestrator::new()` at `engine.rs:970-979`
- `initial_liquidity_fraction` lives in the policy JSON's `parameters` dict
- After `update_agent_policy()`, the new fraction is in `self.config.agent_configs[].policy`
- EOD resets: cost accumulators, state registers, daily outflows. **Not** balances.
- Unsettled transactions persist across day boundaries

## Design

### Option A: Opt-in via config flag (recommended)

Add `daily_liquidity_reallocation: bool` to `OrchestratorConfig` (default `false`). When enabled:

**At EOD (after penalties, before metrics finalization):**
1. For each agent with `liquidity_pool`:
   - Return allocated liquidity: `agent.balance -= agent.allocated_liquidity`
   - Set `agent.allocated_liquidity = 0`
   - Emit `LiquidityReturn` event
2. Force-settle or cancel remaining queued transactions (design decision — see below)

**At start of next day (tick_within_day == 0, after cost reset):**
1. For each agent with `liquidity_pool`:
   - Read current fraction from the agent's policy (parse from `PolicyConfig::FromJson`)
   - Compute: `new_allocation = floor(pool × fraction)`
   - Apply: `agent.balance += new_allocation`
   - Set `agent.allocated_liquidity = new_allocation`
   - Emit `LiquidityAllocation` event with day, fraction, amount

**Fraction extraction from policy JSON:**
```rust
fn extract_fraction_from_policy(policy: &PolicyConfig) -> f64 {
    match policy {
        PolicyConfig::FromJson { json } => {
            // Parse JSON, read parameters.initial_liquidity_fraction
            serde_json::from_str::<serde_json::Value>(json)
                .ok()
                .and_then(|v| v["parameters"]["initial_liquidity_fraction"].as_f64())
                .unwrap_or(1.0)
        }
        _ => 1.0, // Non-JSON policies default to full allocation
    }
}
```

### Option B: Always reallocate (breaking change)

Always reallocate when `liquidity_pool` is set. Simpler but changes existing multi-day scenario behavior. **Not recommended** — would break paper reproduction.

### Design Decision: Unsettled Transactions at EOD

Three options for handling queued transactions when balance is withdrawn:

**Option 1: Leave them queued (recommended).** Transactions stay in queue. If the new day's allocation provides enough balance, they can settle. If not, they accrue delay costs and eventually hit deadline penalties. This matches real RTGS behavior — unsettled transactions carry forward.

**Option 2: Force-settle at EOD.** Settle everything possible before withdrawing liquidity. More aggressive, less realistic.

**Option 3: Cancel unsettled.** Drop all queued transactions at EOD. Unrealistic.

**Recommendation: Option 1.** Leave transactions queued. The balance withdrawal may cause the agent to go into overdraft (using `unsecured_cap`), which accrues liquidity cost — a natural penalty for under-allocating. This creates the right incentive for the LLM: allocate too little → overdraft costs, allocate too much → opportunity costs.

### Balance Conservation (INV-4)

```
Invariant: opening_balance + allocated_liquidity = agent.balance + sum(settled_outgoing) - sum(settled_incoming)
```

At EOD return:
- `agent.balance -= allocated_liquidity` (may go negative — that's fine, uses overdraft)
- `allocated_liquidity = 0`

At SOD allocation:
- `new_alloc = floor(pool × fraction)`
- `agent.balance += new_alloc`
- `allocated_liquidity = new_alloc`

Pool itself is never modified — it represents total available reserves. Only the allocation changes.

### Files to Modify

| File | Change |
|------|--------|
| `simulator/src/orchestrator/engine.rs` | Add `daily_liquidity_reallocation` to config. Add reallocation logic at EOD and SOD. Add `extract_fraction_from_policy()`. |
| `simulator/src/models/agent.rs` | May need `set_allocated_liquidity()` and `return_allocated_liquidity()` methods |
| `simulator/src/ffi/types.rs` | Parse new config field from FFI dict |
| `simulator/src/events/types.rs` | Add `LiquidityReturn` and `LiquidityAllocation` event variants |
| `simulator/src/ffi/orchestrator.rs` | Expose events via FFI (already generic) |
| `api/payment_simulator/config/schemas.py` | Add `daily_liquidity_reallocation` field to `SimulationSettings` |
| `simulator/tests/test_daily_liquidity_cycle.rs` | New test file |

## Phase Overview

| Phase | Description | TDD Focus | Estimated Tests |
|-------|-------------|-----------|-----------------|
| 1 | Fraction extraction from PolicyConfig | Parse JSON, handle all policy types, edge cases | 5 tests |
| 2 | EOD liquidity return | Balance withdrawal, event emission, balance conservation | 6 tests |
| 3 | SOD liquidity allocation | Reallocation with current fraction, event emission | 6 tests |
| 4 | Integration: full day cycle | Multi-day scenarios, interaction with `update_agent_policy`, determinism | 6 tests |
| 5 | FFI + Python config | Wire through FFI, add Python schema field | 3 tests |

~26 tests total across 5 phases.

## Phase 1: Fraction Extraction

**Goal**: Extract `initial_liquidity_fraction` from any `PolicyConfig` variant.

### Test Cases
1. `FromJson` with fraction in `parameters` → returns fraction
2. `FromJson` without fraction → returns 1.0
3. `FromJson` with invalid JSON → returns 1.0
4. `Fifo` / `Deadline` / other non-JSON variants → returns 1.0
5. Fraction at boundary values (0.0, 1.0, 0.5)

### Implementation
Add to `engine.rs`:
```rust
fn extract_fraction_from_policy(policy: &PolicyConfig) -> f64 { ... }
```

## Phase 2: EOD Liquidity Return

**Goal**: At end of day, return allocated liquidity to pool.

### Test Cases
1. Agent with pool: balance decreases by `allocated_liquidity` at EOD
2. Agent without pool: no change
3. `LiquidityReturn` event emitted with correct amounts
4. Balance conservation: pool unchanged, balance reduced, allocated_liquidity zeroed
5. Agent in overdraft after return: valid (uses unsecured_cap)
6. Feature disabled (`daily_liquidity_reallocation: false`): no change (backward compat)

### Implementation
In `handle_end_of_day()`, after penalties but before metrics finalization:
```rust
if self.config.daily_liquidity_reallocation {
    self.return_daily_liquidity(current_tick, current_day)?;
}
```

## Phase 3: SOD Liquidity Allocation

**Goal**: At start of new day, allocate from pool using current policy's fraction.

### Test Cases
1. Agent with pool: balance increases by `floor(pool × fraction)` at SOD
2. Fraction read from current policy (after `update_agent_policy`)
3. `LiquidityAllocation` event emitted with day, fraction, amount
4. Different fraction → different allocation
5. Zero fraction → zero allocation (balance = opening_balance only)
6. Feature disabled: no change

### Implementation
In `tick()`, after cost accumulator reset at `tick_within_day == 0`:
```rust
if self.config.daily_liquidity_reallocation
    && self.time_manager.tick_within_day() == 0
    && current_tick > 0
{
    self.allocate_daily_liquidity(current_tick)?;
}
```

## Phase 4: Integration

**Goal**: Full cycle works correctly across multiple days with policy updates.

### Test Cases
1. 3-day scenario: allocate → trade → return → reallocate with new fraction → trade → return
2. `update_agent_policy` changes fraction → next day uses new fraction
3. Determinism: two identical runs produce identical results (INV-2)
4. Balance conservation across full scenario (INV-4)
5. Save/load state preserves pool state correctly (INV-5)
6. Unsettled transactions carry forward, settle (or not) with new allocation

## Phase 5: FFI + Python

**Goal**: Wire through FFI and Python config.

### Test Cases
1. FFI dict accepts `daily_liquidity_reallocation` field
2. Python `SimulationSettings` has the field, defaults to `False`
3. Round-trip: Python config → FFI → Rust → events → Python

## Documentation Updates

- [ ] `docs/reference/architecture/` — document daily liquidity cycle
- [ ] `docs/reference/scenario/` — document new config field
- [ ] Update `patterns-and-conventions.md` if new invariant needed
- [ ] Handover to Nash: how to enable in web platform

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | Pending | |
| Phase 2 | Pending | |
| Phase 3 | Pending | |
| Phase 4 | Pending | |
| Phase 5 | Pending | |
