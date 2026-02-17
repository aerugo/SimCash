# Custom Scenario Game — Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Priority**: P13 — High
**Effort**: Medium
**Branch**: `feature/interactive-web-sandbox`

## Summary

Allow Custom Builder scenarios to be used in multi-day game mode. Currently the Custom Builder only connects to single-run "Launch Simulation". Need: (1) Backend accepts inline YAML config in `POST /api/games` as alternative to `scenario_id`, (2) Frontend adds "Start Game" button to Custom Builder tab.

## Critical Invariants

- **INV-1**: Money is i64 — custom config must use integer cents
- **INV-2**: Determinism — seed from custom config preserved
- **INV-GAME-1**: Policy Reality — custom configs must produce different costs at different fractions
- **INV-3**: FFI Minimal — use `SimulationConfig.to_ffi_dict()` exclusively

## Current State

- `POST /api/games` accepts `CreateGameRequest` with `scenario_id` field that looks up YAML from scenario pack
- Custom Builder builds a `ScenarioConfig` object (frontend type) and passes it to `onLaunch`
- No path from Custom Builder → Game creation
- `Game.__init__` takes `raw_yaml` dict — already supports arbitrary configs if wired

## Files to Modify

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/models.py` | Modify | Add optional `inline_config` to `CreateGameRequest` |
| `web/backend/app/main.py` | Modify | Handle inline_config in `POST /api/games` |
| `web/frontend/src/views/HomeView.tsx` | Modify | Add "Start Game" button to Custom Builder |
| `web/frontend/src/api.ts` | Modify | Update `createGame` to accept inline config |
| `web/frontend/src/types.ts` | Modify | Extend `GameSetupConfig` type |

## Phase Overview

| Phase | Description |
|-------|-------------|
| 1 | Backend: accept inline_config in game creation |
| 2 | Frontend: add "Start Game" button to Custom Builder tab |
| 3 | Integration tests |
