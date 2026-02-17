# Loading States & Progress - Development Plan

**Status**: Pending
**Created**: 2026-02-17
**Branch**: `feature/interactive-web-sandbox`
**Depends on**: `web-websocket-streaming` (Plan 2)

## Summary

Show meaningful progress during long LLM operations. Currently the UI shows "⏳ Running..." with no detail. Need: per-agent thinking indicator, elapsed timer, which phase (simulation vs optimization), and estimated time remaining. This is critical for LLM mode where each day takes 30–120 seconds.

## Critical Invariants to Respect

- **INV-1**: Money is i64 — not directly affected (display-only feature)
- **INV-2**: Determinism — progress tracking is observational, doesn't affect results
- **INV-3**: FFI Minimal — no new FFI surface
- **INV-GAME-2**: Agent Isolation — per-agent progress shown separately

## Current State Analysis

### What Exists

1. **WebSocket `/ws/games/{id}`**: Sends `day`, `optimizing`, `reasoning`, `game_state` messages. The `optimizing` message includes day number but not agent details.
2. **Frontend GameView**: Shows "⏳ Running..." text during operations. No phase distinction, no timer, no per-agent status.
3. **Plan 2 (WebSocket Streaming)**: Will add structured message types including `simulation_start`, `optimization_start`, `optimization_complete`, `llm_calling`, `llm_complete`.

### What's Missing

- Backend: `llm_calling` and `llm_complete` events per agent during optimization
- Frontend: Loading overlay with phase indicator
- Frontend: Elapsed timer / ETA
- Frontend: Per-agent status badges
- Frontend: Skeleton states for charts during updates

### Files to Modify

| File | Current State | Planned Changes |
|------|---------------|-----------------|
| `web/backend/app/game.py` | No per-agent progress events | Add progress callback for LLM phases |
| `web/backend/app/main.py` | Basic WS messages | Wire per-agent progress events |
| `web/frontend/src/components/LoadingOverlay.tsx` | Does not exist | Phase indicator + timer |
| `web/frontend/src/components/AgentStatusBadge.tsx` | Does not exist | Per-agent thinking indicator |
| `web/frontend/src/components/ChartSkeleton.tsx` | Does not exist | Shimmer placeholder for charts |
| `web/frontend/src/hooks/useGameWebSocket.ts` | From Plan 2 | Extend with progress state tracking |

## Phase Overview

| Phase | Description | Key Deliverables |
|-------|-------------|-----------------|
| 1 | Backend: Add progress events to WebSocket | `simulation_running`, `llm_calling`, `llm_complete` per agent |
| 2 | Frontend: Loading overlay with phase indicator + timer | `LoadingOverlay` component, elapsed timer |
| 3 | Frontend: Per-agent status badges | `AgentStatusBadge` with simulating/thinking/done states |
| 4 | Frontend: Skeleton/shimmer states for charts | `ChartSkeleton`, smooth transitions |
| 5 | Test and polish animations | Visual tests, timing accuracy, edge cases |
