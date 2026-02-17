# Game Setup Flow - Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Summary

Build a proper game setup screen where users pick a scenario preset, configure max_days (default 10), toggle mock/real LLM optimization, and set the number of evaluation samples. Currently `GameView` assumes it already has a `gameId` — we need a setup flow that creates the game via API then transitions to GameView.

## Critical Invariants to Respect

- **INV-1**: Money is i64 — all costs in integer cents; frontend converts to dollars for display only
- **INV-2**: Determinism — same seed + config = same output; expose seed in setup
- **INV-3**: FFI Minimal — use `SimulationConfig.to_ffi_dict()` exclusively; no new FFI surface
- **INV-GAME-1**: Policy Reality — `initial_liquidity_fraction` MUST produce different costs
- **INV-GAME-2**: Agent Isolation — each agent sees ONLY their own costs/events

## Current State Analysis

### What Exists

1. **Backend**: `POST /api/games` accepts a dict config with `scenario_id`, `use_llm`, `mock_reasoning`, `max_days`. No `num_eval_samples` support. No scenario list endpoint for games (only `/api/scenario-pack` exists).
2. **Frontend**: `GameView.tsx` renders day progression, charts, reasoning panel. It expects a `gameId` prop. `HomeView.tsx` is the landing page but has no game creation UI.
3. **Scenario Pack**: `scenario_pack.py` has `get_scenario_pack()` returning scenario metadata and `get_scenario_by_id()` returning full YAML configs.

### What's Missing

- No dedicated game scenarios endpoint (need to reuse scenario-pack for game setup)
- No `num_eval_samples` parameter in game creation
- No setup UI — user must somehow obtain a gameId before GameView works
- No validation of game creation params on backend
- No scenario preview (cost parameters, agent count, complexity)

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/backend/app/main.py` | `POST /api/games` accepts raw dict | Add validation, `num_eval_samples`, scenario list for games |
| `web/backend/app/game.py` | `Game.__init__` ignores `num_eval_samples` from API | Wire `num_eval_samples` from creation params |
| `web/backend/app/models.py` | No game creation model | Add `CreateGameRequest` Pydantic model |
| `web/frontend/src/components/GameSetup.tsx` | Does not exist | New setup component with scenario cards + config |
| `web/frontend/src/api.ts` | Has `createGame()` | Add `getGameScenarios()`, update `createGame()` params |
| `web/frontend/src/types.ts` | Has `GameState`, `ScenarioPackEntry` | Add `GameConfig` type |
| `web/frontend/src/App.tsx` | Routes to GameView directly | Add setup → game flow |

## Phase Overview

| Phase | Description | Key Deliverables |
|-------|-------------|-----------------|
| 1 | Backend: Scenario list endpoint + validated game creation | `CreateGameRequest` model, `/api/games/scenarios` endpoint, param validation |
| 2 | Frontend: GameSetup component with scenario cards + config sliders | `GameSetup.tsx` with scenario selection, max_days slider, LLM toggle |
| 3 | Frontend: Wire setup → create game → transition to GameView | State management, API call, navigation flow |
| 4 | Polish: Scenario descriptions, cost preview, input validation | Rich scenario cards, parameter tooltips, error states |
| 5 | Test & verify end-to-end | Backend tests, manual E2E verification |
