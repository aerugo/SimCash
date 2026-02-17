# WebSocket Streaming - Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`

## Summary

Stream day-by-day updates during auto-run via WebSocket. Essential for LLM mode where each day takes 30–120s. Currently `POST /api/games/{id}/auto` blocks until all days complete, making the UI unresponsive. The existing WebSocket at `/ws/games/{id}` has basic step/auto/stop but lacks structured message types for progressive UI updates.

## Critical Invariants to Respect

- **INV-1**: Money is i64 — all streamed costs in integer cents
- **INV-2**: Determinism — streaming doesn't affect simulation results
- **INV-3**: FFI Minimal — no new FFI surface
- **INV-GAME-1**: Policy Reality — streamed fraction changes must reflect actual policy updates
- **INV-GAME-2**: Agent Isolation — each agent's reasoning streamed separately

## Current State Analysis

### What Exists

1. **WebSocket `/ws/games/{game_id}`** in `main.py`: Accepts `step`, `auto`, `stop`, `state` actions. Auto-run sends `day`, `optimizing`, `reasoning`, `game_state` messages sequentially. No granular progress events.
2. **`Game.run_day()`**: Synchronous simulation. Returns `GameDay` when complete.
3. **`Game.optimize_policies()`**: Async (for LLM calls). Returns reasoning dict when complete.
4. **Frontend `GameView.tsx`**: Uses REST API (`/step`, `/auto`). No WebSocket integration.

### What's Missing

- Structured message types with discriminated unions (type field)
- Progress events during simulation and optimization phases
- Frontend WebSocket hook for game streaming
- Progressive chart/reasoning updates as data arrives
- Error recovery (reconnection, missed messages)

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/backend/app/main.py` | Basic WS with ad-hoc message types | Structured message protocol |
| `web/backend/app/game.py` | Returns full results synchronously | Add callback hooks for progress |
| `web/frontend/src/hooks/useGameWebSocket.ts` | Does not exist | WebSocket hook with message dispatch |
| `web/frontend/src/components/GameView.tsx` | REST-only | Wire to WebSocket for streaming |
| `web/frontend/src/types.ts` | Basic game types | Add WS message types |

## Message Protocol

```typescript
// Server → Client messages
type WSMessage =
  | { type: 'game_state'; data: GameState }
  | { type: 'day_complete'; data: DayResult }
  | { type: 'optimization_start'; day: number; agent_id: string }
  | { type: 'optimization_complete'; day: number; agent_id: string; reasoning: GameOptimizationResult }
  | { type: 'game_complete'; data: GameState }
  | { type: 'error'; message: string }

// Client → Server messages
type WSCommand =
  | { action: 'step' }
  | { action: 'auto'; speed_ms?: number }
  | { action: 'stop' }
  | { action: 'state' }
```

## Phase Overview

| Phase | Description | Key Deliverables |
|-------|-------------|-----------------|
| 1 | Backend: Refactor auto-run to yield structured WS messages | Typed message protocol, per-agent optimization events |
| 2 | Backend: Add granular message types for simulation phases | `day_complete`, `optimization_start/complete`, `error` messages |
| 3 | Frontend: WebSocket hook with message dispatch | `useGameWebSocket` hook, reconnection logic |
| 4 | Frontend: Progressive UI updates from WS stream | Chart animation, real-time reasoning panel |
| 5 | Test with mock (fast) and verify protocol | WS integration tests, protocol verification |
