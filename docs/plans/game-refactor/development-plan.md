# Game Module Refactor - Development Plan

**Status**: In Progress
**Created**: 2026-02-22
**Branch**: `feature/interactive-web-sandbox`
**Based on**: Dennis's deep review (`docs/reports/web-module-deep-review.md`)

## Summary

Refactor the 1,447-line `game.py` god-class and 1,631-line `main.py` monolith into maintainable, testable components. Focus on P0 (critical duplication) and P1 (diverging paths, god-class decomposition).

## Critical Invariants to Respect

- **INV-1**: Money is i64 — all cost computations stay integer
- **INV-9**: Policy Evaluation Identity — `_build_ffi_config()` remains the single path for policy→engine
- **INV-11**: Agent Isolation — optimization contexts only see own-agent data
- **INV-13**: Bootstrap Seed Hierarchy — seed logic unchanged

## Current State

```
game.py  (1,447 lines) — Game class: simulation, optimization, bootstrap, persistence, state
main.py  (1,631 lines) — route handlers with inline business logic
streaming_optimizer.py (680 lines) — WS streaming optimization (more robust than HTTP path)
```

Two optimization paths (`_real_optimize` HTTP vs `stream_optimize` WS) diverge on retries, MaaS support, and error handling. `run_day()`/`simulate_day()` share ~80 lines of identical multi-sample averaging.

## Target Architecture

```
game.py           (~400 lines) — Game orchestration: day loop, state, policies
simulation.py     (~200 lines) — SimulationRunner: _run_single_sim, _run_cost_only, _run_scenario_day, multi-sample
bootstrap_gate.py (~200 lines) — BootstrapGate: _run_real_bootstrap, threshold resolution
optimizer.py      (~300 lines) — Unified optimization (streaming_optimizer consolidated)
serialization.py  (~200 lines) — GameSerializer: checkpoint, DuckDB, state export
main.py           (~800 lines) — Thin routes delegating to GameService
game_service.py   (~300 lines) — GameService: create, step, auto_run business logic
```

## Phase Overview

| Phase | Description | Effort | Priority |
|-------|-------------|--------|----------|
| 1 | Extract multi-sample averaging (P0) | 1h | P0 |
| 2 | Unify optimization paths (P1) | 3h | P1 |
| 3 | Extract SimulationRunner (P1) | 2h | P1 |
| 4 | Extract BootstrapGate (P1) | 2h | P1 |
| 5 | Extract GameSerializer (P1) | 1h | P1 |
| 6 | Extract GameService from main.py (P1) | 3h | P1 |
| 7 | Cleanup: duplicate route, top-level imports, dotenv (P2) | 30min | P2 |

## Phase 1: Extract Multi-Sample Averaging (P0)

**Goal**: Eliminate the critical `run_day()`/`simulate_day()` duplication.

**Design**: New method `_run_with_samples(seed, use_scenario_day=False)` returns `(events, balance_history, costs, per_agent_costs, total_cost, tick_events, cost_std, tx_histories, cum_summary, cum_arrivals, cum_settled)`. Both `run_day()` and `simulate_day()` become thin wrappers.

**Success Criteria**:
- [ ] `run_day()` and `simulate_day()` each < 20 lines
- [ ] `import math` appears once at top of file
- [ ] Multi-sample logic exists in exactly one place

## Phase 2: Unify Optimization Paths (P1)

**Goal**: Delete `_real_optimize()` and `optimize_policies()`. All optimization goes through the streaming path.

**Design**: 
- Rename `streaming_optimizer.stream_optimize()` → `optimize_agent()`
- Add `send_fn=None` parameter — if None, collects results silently (HTTP mode)
- `optimize_policies_streaming()` and `optimize_policies()` merge into one `optimize_all_agents(send_fn=None)`
- Delete `_real_optimize()` (160 lines) and `_mock_optimize()` (move to test fixtures if needed)

**Success Criteria**:
- [ ] Single optimization code path for HTTP and WS
- [ ] Same retry count, MaaS support, and validation for both
- [ ] `_real_optimize()` deleted

## Phase 3: Extract SimulationRunner (P1)

**Goal**: Move simulation execution out of Game.

**Design**: `SimulationRunner` class with:
- `__init__(raw_yaml, agent_ids, policies, ticks_per_day, scenario_num_days, base_seed)`
- `run_single(seed)` → sim results
- `run_cost_only(seed)` → costs dict
- `run_scenario_day(live_orch)` → sim results + cumulative stats
- `run_with_samples(seed, num_samples, ...)` → averaged results
- `build_ffi_config(seed)` → ffi dict

Game holds a `SimulationRunner` instance, updates it when policies change.

**Success Criteria**:
- [ ] Game has no direct `Orchestrator` calls
- [ ] SimulationRunner is independently testable

## Phase 4: Extract BootstrapGate (P1)

**Goal**: Move bootstrap evaluation out of Game.

**Design**: `BootstrapGate` class with:
- `__init__(raw_yaml, agent_ids, ticks_per_day, base_seed)`
- `evaluate(aid, day, current_policy, proposed_policy) → BootstrapResult`
- `_resolve_thresholds(agent_cfg)` (moved from module-level)
- `BootstrapResult` dataclass with accepted, reason, stats

**Success Criteria**:
- [ ] `_run_real_bootstrap` (160 lines) moves entirely to BootstrapGate
- [ ] Game calls `self.bootstrap_gate.evaluate(...)` — one line

## Phase 5: Extract GameSerializer (P1)

**Goal**: Move persistence out of Game.

**Design**: Module-level functions or class:
- `game_to_checkpoint(game, scenario_id, uid) → dict`
- `game_from_checkpoint(data) → Game`
- `save_day_to_duckdb(db_path, day)`
- `day_to_checkpoint(day) → dict`

**Success Criteria**:
- [ ] Game has no DuckDB imports
- [ ] Checkpoint logic testable independently

## Phase 6: Extract GameService from main.py (P1)

**Goal**: Move business logic out of route handlers.

**Design**: `GameService` class with:
- `create_game(config) → Game`
- `step_game(game_id) → StepResult`
- `auto_run_game(game_id) → list[StepResult]`
- Route handlers become thin dispatchers

**Success Criteria**:
- [ ] Route handlers < 20 lines each
- [ ] Business logic testable without FastAPI

## Phase 7: Cleanup (P2)

- Delete duplicate `/api/scenario-pack` route
- Move `import math` to top-level
- Move `load_dotenv()` to app startup
- Delete `_mock_optimize()` or move to test fixtures

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | ✅ Done | `29e70aaf` — extracted `_run_with_samples()` |
| Phase 2 | ✅ Done | `8e23d46c` — unified optimization, deleted `_real_optimize` |
| Phase 3 | ✅ Done | `1c77e3a4` — extracted `SimulationRunner` (252 lines) |
| Phase 4 | ✅ Done | `6ad2e6ed` — extracted `BootstrapGate` (217 lines) |
| Phase 5 | ✅ Done | `fb1d8cb1` — extracted `GameSerializer` (191 lines) |
| Phase 6 | Deferred | main.py WS handler is tightly coupled to globals; low ROI vs risk |
| Phase 7 | ✅ Done | `467902f3` — duplicate route, dotenv, WS test fix |
| Tests  | ✅ Done | `2643cddc` — 32→0 refactor failures, 314 passing |
