# Experiment Persistence — Development Plan

**Status**: Draft  
**Date**: 2026-02-19  
**Branch**: `feature/interactive-web-sandbox`  
**Estimated effort**: 10-14 hours

## Goal

Persist experiment state so users can:
1. Close the browser and return to a running/completed experiment later
2. Resume partially completed experiments without losing progress
3. See a history of past experiments on their dashboard
4. Survive Cloud Run cold starts, deploys, and instance restarts

## Current State

**What exists:**
- `GameStorage` class with local filesystem + GCS backends
- DuckDB per-game files with a `days` table (day results: seed, costs, events, balances)
- JSON index per user listing game metadata
- `save_day_to_duckdb()` on `Game` class — called nowhere in production flow
- `game_manager: dict[str, Game]` — pure in-memory, lost on restart

**What's missing:**
- Game configuration (raw_yaml, max_days, use_llm, constraint_preset) not persisted
- Policy state between rounds not persisted
- Reasoning history not persisted  
- No "resume from checkpoint" capability
- Frontend has no "My Experiments" list
- WebSocket reconnection doesn't restore auto-run state

## Architecture

### Storage Model

Each experiment gets a **single JSON file** as its checkpoint, stored alongside the DuckDB file:

```
users/{uid}/games/{game_id}.json     ← full game state checkpoint
users/{uid}/games/{game_id}.duckdb   ← day results (existing)
users/{uid}/games/index.json         ← game list (existing)
```

The checkpoint JSON contains everything needed to reconstruct a `Game` object:

```json
{
  "version": 1,
  "game_id": "abc123",
  "created_at": "2026-02-19T22:00:00Z",
  "updated_at": "2026-02-19T22:05:00Z",
  "status": "running",           // "created" | "running" | "paused" | "complete"
  
  "config": {
    "scenario_id": "preset_3bank_6tick",
    "raw_yaml": { ... },          // full scenario YAML dict
    "use_llm": true,
    "simulated_ai": false,
    "max_days": 10,
    "num_eval_samples": 50,
    "optimization_interval": 1,
    "constraint_preset": "full",
    "base_seed": 42
  },
  
  "progress": {
    "current_day": 3,
    "agent_ids": ["BANK_A", "BANK_B", "BANK_C"],
    "policies": {
      "BANK_A": { ... },         // current policy JSON
      "BANK_B": { ... },
      "BANK_C": { ... }
    },
    "reasoning_history": {
      "BANK_A": [ ... ],         // list of GameOptimizationResult dicts
      "BANK_B": [ ... ],
      "BANK_C": [ ... ]
    },
    "days": [                    // GameDay.to_dict() for each completed day
      { "day": 0, "seed": 42, "total_cost": 149400, ... },
      { "day": 1, "seed": 43, "total_cost": 68000, ... },
      { "day": 2, "seed": 44, "total_cost": 48000, ... }
    ]
  }
}
```

### Save Strategy

**Save after every significant state change:**
1. After `run_day()` completes → save checkpoint
2. After `optimize_policies_streaming()` completes → save checkpoint
3. On game creation → save initial checkpoint
4. On game completion → save final checkpoint with `status: "complete"`

This means if the server dies mid-optimization, we lose at most the current round's LLM responses — but all completed days and their reasoning are safe.

### Load Strategy

**On startup:** Nothing loaded eagerly. Games are loaded on demand.

**On `GET /api/games/{id}` or WebSocket connect:**
1. Check `game_manager` (in-memory cache) → return if found
2. Load checkpoint JSON from local disk (or GCS if not local)
3. Reconstruct `Game` object from checkpoint
4. Put in `game_manager` cache
5. Return game state

**Reconstruction:** `Game.from_checkpoint(data: dict) → Game` class method that rebuilds the full object including `days`, `policies`, and `reasoning_history`.

### Resume Logic

When a user reconnects to a `status: "running"` or `"paused"` experiment:
1. Load from checkpoint → game has `current_day=3`, `max_days=10`
2. Frontend shows "Round 3/10 — PAUSED" with all previous results
3. User clicks ▶ Next or ⏩ Auto → resumes from day 4
4. Seeds are deterministic: `base_seed + day_num` so resuming produces the same sequence

**Key invariant:** The game's RNG seed sequence is `base_seed + day_num`, not random. This means resuming from checkpoint produces the exact same stochastic arrivals for each future day as if the run had never been interrupted.

## Web Invariants

- **WEB-INV-1 (Policy Reality)**: Policies stored in checkpoint are the exact policies the engine executed. On resume, these policies are loaded back.
- **WEB-INV-2 (Agent Isolation)**: Reasoning history scoped per-agent in checkpoint.
- **WEB-INV-4 (Cost Consistency)**: Day results stored verbatim from engine output.
- **WEB-INV-5 (Auth Gate)**: Checkpoints scoped to user's UID directory.

## Phases

| Phase | What | Est. Time | Risk |
|-------|------|-----------|------|
| 1 | Backend: checkpoint save/load | 3-4h | Low — pure serialization |
| 2 | Backend: auto-save in game flow | 2-3h | Medium — must not break WS streaming |
| 3 | Frontend: My Experiments page | 2-3h | Low — new page, no regressions |
| 4 | Frontend: reconnect + resume UX | 2-3h | Medium — WS state management |
| 5 | GCS sync + deploy | 1-2h | Low — GCS layer already exists |

## Phase 1: Checkpoint Save/Load

### Backend changes

**`web/backend/app/game.py`:**
- Add `Game.to_checkpoint() → dict` — serializes full state
- Add `Game.from_checkpoint(data: dict) → Game` — class method to reconstruct
- Add `GameDay.from_dict(data: dict) → GameDay` — deserialize day results
- Ensure `reasoning_history` entries are plain dicts (already are)

**`web/backend/app/storage.py`:**
- Add `save_checkpoint(uid, game_id, data: dict)` — writes JSON locally + GCS
- Add `load_checkpoint(uid, game_id) → dict | None` — reads JSON
- Add `list_checkpoints(uid) → list[dict]` — returns summary for My Experiments

### Tests
- Round-trip: create game → run 2 days → `to_checkpoint()` → `from_checkpoint()` → verify `current_day`, policies, reasoning match
- Resume: load checkpoint → run 1 more day → verify seed is correct, costs are non-zero
- Edge cases: empty game (0 days), complete game, game with rejected optimizations

## Phase 2: Auto-Save in Game Flow

### Backend changes

**`web/backend/app/main.py`:**
- After `game.run_day()` in both `run_one_step()` and the REST `/step` endpoint → call `save_checkpoint()`
- After `game.optimize_policies_streaming()` → call `save_checkpoint()`
- On game creation → save initial checkpoint with `status: "created"`
- On game completion → save with `status: "complete"`

**`web/backend/app/main.py` — game loading:**
- In `game_ws()` and `get_game()`: if game not in `game_manager`, try `load_checkpoint()`
- If checkpoint found, reconstruct and cache in `game_manager`
- Update index entry with loaded game info

### Key design: non-blocking saves
- Save checkpoint in background (`asyncio.create_task`) to avoid blocking the WS response
- Local filesystem save is fast (~1ms for JSON); GCS upload can be fire-and-forget

## Phase 3: My Experiments Page

### Frontend changes

**New: `web/frontend/src/views/ExperimentsView.tsx`:**
- Lists user's experiments from `GET /api/games`
- Shows: scenario name, status badge, round progress, cost reduction, created date
- Click → navigates to `/experiment/{id}` 
- Delete button with confirmation
- Filter: All / Running / Complete
- Sort: newest first

**`web/frontend/src/App.tsx`:**
- Add "📋 Experiments" nav link

**`web/frontend/src/views/HomeView.tsx`:**
- Add "Recent Experiments" section showing last 3 games

### Backend changes

**`web/backend/app/main.py`:**
- Enhance `GET /api/games` to return richer metadata from checkpoints (not just index)
- Add `status`, `scenario_name`, `current_day`, `max_days`, `cost_reduction` to listing

## Phase 4: Reconnect + Resume UX

### Frontend changes

**`web/frontend/src/views/GameView.tsx`:**
- On mount: if game loaded from checkpoint (not fresh), show "Resumed from Round X" banner
- "Paused" status display when game is mid-experiment but not actively running
- Auto-run state is NOT persisted — user must click Auto again after reconnecting
- Show all previous days' results, charts, reasoning immediately on load

**`web/frontend/src/hooks/useGameWebSocket.ts`:**
- On WS connect: backend sends full `game_state` including all history
- Already works this way — the initial `game_state` message includes everything
- No changes needed if `Game.get_state()` returns all days and reasoning

### Key UX decisions
- **Auto-run does NOT auto-resume.** When you come back, the experiment is paused. You click Auto to continue. This prevents surprise API costs.
- **Status badge on experiment page:** "Round 5/10 — PAUSED · Click ▶ to continue"
- **Complete experiments are read-only** — all data viewable, no action buttons except Export and New

## Phase 5: GCS Sync + Deploy

- Checkpoint JSON saved to GCS alongside DuckDB (already have the pattern)
- On Cloud Run cold start, `load_checkpoint()` pulls from GCS transparently
- Set `SIMCASH_STORAGE_MODE=gcs` and `SIMCASH_GCS_BUCKET=simcash-data` in Cloud Run env
- Create GCS bucket if it doesn't exist
- Test: create experiment → deploy new revision → reconnect → experiment loads from GCS

## Files

### New
| File | Purpose |
|------|---------|
| `web/frontend/src/views/ExperimentsView.tsx` | My Experiments listing page |

### Modified
| File | Changes |
|------|---------|
| `web/backend/app/game.py` | `to_checkpoint()`, `from_checkpoint()`, `GameDay.from_dict()` |
| `web/backend/app/storage.py` | `save_checkpoint()`, `load_checkpoint()`, `list_checkpoints()` |
| `web/backend/app/main.py` | Auto-save hooks, checkpoint loading in get/ws endpoints |
| `web/frontend/src/App.tsx` | Add Experiments nav link |
| `web/frontend/src/views/HomeView.tsx` | Recent experiments section |
| `web/frontend/src/views/GameView.tsx` | Resume banner, paused state UX |

### NOT Modified
| File | Why |
|------|-----|
| `simulator/` | Never touch the engine |
| `api/` | Import only |
| `web/backend/app/streaming_optimizer.py` | No changes needed — reasoning already returned as dicts |

## Success Criteria

- [ ] Create experiment → close browser → reopen → experiment loads with all progress
- [ ] Resume mid-experiment → next day uses correct seed, produces non-zero costs
- [ ] Deploy new Cloud Run revision → experiments survive via GCS
- [ ] My Experiments page shows all user's experiments with status/progress
- [ ] Complete experiments are fully viewable (all days, reasoning, charts)
- [ ] Auto-run does not auto-resume (prevents surprise costs)
- [ ] Save latency < 50ms (local) — does not noticeably delay WS responses
- [ ] All existing tests still pass
- [ ] TypeScript compiles clean

## Open Questions

1. **Checkpoint size**: With 10 rounds × 3 agents × full reasoning history, checkpoints could be 500KB-1MB. Is this OK for GCS? (Yes — GCS handles this easily, and we already upload DuckDB files.)

2. **Concurrent access**: What if two browser tabs connect to the same experiment? Current answer: last-writer-wins on checkpoint, both tabs see the same game state via WS. Fine for single-user.

3. **Experiment TTL**: Should old experiments auto-expire? Suggest: keep indefinitely for now, add cleanup later if storage costs matter (they won't at current scale).

4. **tick_events in checkpoint**: These are large (hundreds of events per day). Options:
   - (a) Store in checkpoint → larger files but full replay available
   - (b) Store only in DuckDB → checkpoint stays small, replay requires DB load
   - Recommend (b) for now — tick replay is a secondary feature, checkpoint should be fast to save/load
