# Multi-Day Game: Wiring & Frontend — Development Plan v2

**Status**: In Progress
**Created**: 2025-07-18
**Branch**: `feature/interactive-web-sandbox`

## Summary

Wire the multi-day game backend end-to-end (test-driven), build the frontend GameView, and verify that LLM policy optimization actually changes simulation outcomes. This is the "make it real" phase — no more mock-only, no more untested code.

## Critical Invariants

- **INV-1**: Money is i64 — all costs in integer cents
- **INV-2**: Determinism — same seed + config = same output
- **INV-3**: FFI Minimal — use `SimulationConfig.to_ffi_dict()` exclusively
- **INV-GAME-1** (NEW): Policy Reality — `initial_liquidity_fraction` MUST produce different costs. If fraction 0.1 and 1.0 produce identical results, something is broken.
- **INV-GAME-2** (NEW): Agent Isolation — each agent's optimization sees ONLY their own costs/events.

## Current State

Backend exists but is **completely untested**:
- `game.py` — Game/GameDay classes, mock + real optimize, policy injection
- `scenario_pack.py` — parameterized scenario generator
- `main.py` — game CRUD + step/auto + WebSocket endpoints
- `simulation.py` — single-run simulation (cost key fix applied but uncommitted)
- **No `web/backend/tests/` directory exists at all**

Frontend has 7 tabs but **no GameView** — the multi-day game has no UI.

## Phase Overview

| Phase | Description | TDD Focus | Est. Tests |
|-------|-------------|-----------|------------|
| 1 | Backend unit tests for Game engine | Policy injection, cost extraction, day progression | ~12 |
| 2 | Backend integration tests via API | Game CRUD, step, auto-run, scenario pack | ~10 |
| 3 | Verify policy causality (INV-GAME-1) | Different fractions → different costs | ~4 |
| 4 | Frontend GameView | Multi-day visualization, controls, reasoning display | manual |
| 5 | Wire real LLM (opt-in) | E2E with GPT-5.2 policy optimization | ~2 |
| 6 | Commit, push, playtest | Ruthless researcher mode | - |

## Phase 1: Game Engine Unit Tests

**Goal**: Prove `Game.run_day()` works correctly — policies inject, costs extract, days progress.

### TDD Steps
1. RED: Write tests for Game creation, run_day, policy injection, cost extraction
2. GREEN: Fix any bugs found (cost key mapping already fixed, may find more)
3. REFACTOR: Clean up game.py

### Tests
- `test_game_creation` — agent IDs extracted, policies initialized at fraction=1.0
- `test_run_day_returns_game_day` — day_num, seed, events, costs all populated
- `test_run_day_increments_day` — current_day advances
- `test_policy_injection_changes_fraction` — set fraction=0.2, verify agent config gets it
- `test_different_fractions_different_costs` — INV-GAME-1: fraction 0.1 vs 1.0 → different total_cost
- `test_costs_nonzero` — total_cost > 0 for standard scenarios
- `test_seed_varies_by_day` — day 0 seed != day 1 seed
- `test_mock_optimize_changes_fraction` — mock optimizer produces new fraction
- `test_game_completes_after_max_days` — is_complete after N days
- `test_get_state_shape` — state dict has expected keys
- `test_balance_history_populated` — per-agent balance list matches tick count
- `test_cost_key_mapping` — verify we read `total_cost` not `total` from FFI

## Phase 2: API Integration Tests

**Goal**: Prove the HTTP endpoints work end-to-end.

### Tests
- `test_create_game_default` — POST /api/games returns game_id + state
- `test_create_game_with_scenario` — specify scenario_id
- `test_step_game` — POST step returns day + reasoning
- `test_auto_run_game` — runs all days to completion
- `test_step_after_complete` — returns 400
- `test_get_game` — GET returns state
- `test_delete_game` — DELETE removes game
- `test_scenario_pack_all_presets` — every scenario_id creates successfully
- `test_game_with_mock_reasoning` — reasoning dict populated
- `test_game_cost_progression` — costs change across days (policies change)

## Phase 3: Policy Causality Verification

**Goal**: Prove INV-GAME-1 — that `initial_liquidity_fraction` actually matters.

### Tests
- `test_fraction_1_vs_01_different_costs` — same scenario, fraction 1.0 vs 0.1
- `test_fraction_0_causes_high_penalties` — zero liquidity → deadline penalties
- `test_determinism_same_seed_same_output` — INV-2: identical config → identical costs
- `test_different_seed_different_events` — different seed → different stochastic arrivals

## Phase 4: Frontend GameView

**Goal**: Build React component for multi-day game with day-by-day progression.

### Components
- `GameSetup.tsx` — scenario picker + config (max_days, use_llm)
- `GameView.tsx` — main game UI with day progression
- `GameDayCard.tsx` — single day results (costs, events summary)
- `PolicyChart.tsx` — fraction convergence over days (recharts line)
- `CostConvergence.tsx` — total cost per agent over days
- `ReasoningPanel.tsx` — refactored from existing mock panel, now fed by real game data

## Phase 5: Wire Real LLM

**Goal**: Toggle `mock_reasoning=false` and use GPT-5.2 via existing infrastructure.

### Tests
- `test_real_optimize_returns_policy` — integration test with real API (skip in CI)
- `test_real_optimize_fallback_on_error` — graceful fallback to mock

## Phase 6: Ship It

- Commit all with tests passing
- Push to GitHub
- Playtest per HEARTBEAT.md protocol
- Document bugs in memory/playtest-bugs.md

## Progress

| Phase | Status | Notes |
|-------|--------|-------|
| 1 | Pending | |
| 2 | Pending | |
| 3 | Pending | |
| 4 | Pending | |
| 5 | Pending | |
| 6 | Pending | |
