# Daily Liquidity Cycle — Work Notes

**Project**: Daily liquidity reallocation at day boundaries
**Started**: 2025-07-11
**Branch**: TBD

---

## Session Log

### 2025-07-11 — Planning

**Context**:
- Hugi asked whether balances return to pool at EOD. They don't — one-shot allocation at init.
- RTGS domain expert confirmed this is a significant modeling gap for multi-day scenarios.
- `initial_liquidity_fraction` is meaningless after Day 1 in current implementation.
- The LLM cannot learn the most important real-world lesson: how much liquidity to commit daily.

**Key Design Decisions**:

1. **Opt-in via `daily_liquidity_reallocation` config flag** — preserves backward compatibility. Existing single-day experiments and paper reproduction unaffected.

2. **Leave unsettled transactions queued at EOD** — don't force-settle or cancel. Matches real RTGS behavior. Under-allocation causes overdraft costs; over-allocation causes opportunity costs. Creates correct optimization gradient.

3. **Fraction extracted from policy JSON at SOD** — after `update_agent_policy()`, the new fraction is in the policy config. Engine parses it each morning. No new FFI method needed.

4. **Balance may go negative after EOD return** — this is fine. `unsecured_cap` provides overdraft capacity. Negative balance → liquidity cost accrual → natural penalty for previous under-allocation.

**Applicable Invariants**:
- INV-1: All arithmetic in i64 cents
- INV-2: Determinism — reallocation is deterministic (floor arithmetic, no RNG)
- INV-4: Balance conservation — pool unchanged, money moves between pool and RTGS balance
- INV-5: Replay identity — save_state must capture allocated_liquidity for correct restore
- INV-6: Events for all reallocation actions

**Files Read**:
- `engine.rs:103-193` — OrchestratorConfig fields
- `engine.rs:968-993` — Init allocation logic
- `engine.rs:2955-2975` — Day boundary cost reset
- `engine.rs:5117-5250` — handle_end_of_day
- `agent.rs:145-290` — Agent struct fields, allocated_liquidity

**Completed**:
- [x] Development plan

**Next Steps**:
1. Create branch
2. Phase 1: fraction extraction tests + implementation
