# Plan: Game Status Visibility

**Problem:** Users can't tell if a game is actively running, stalled (backend died mid-run), or waiting for input. The experiment list shows "Running" for everything that isn't complete, whether it's actually executing or abandoned.

## Current State

- **Checkpoint status** is one of: `created`, `running`, `complete`
- **No heartbeat/timestamp** — once a game is "running", there's no way to know if something is still actively processing it
- **GameView** shows `connectionStatus` (connecting/connected/reconnecting/disconnected) but only while you're on that page
- **ExperimentsView** shows a static badge from the last checkpoint

## Design

### Backend: Add `last_activity_at` timestamp

Track when the game last did something meaningful:

1. **`Game` class** — add `last_activity_at: str` (ISO timestamp), updated on:
   - Day simulation complete
   - Optimization complete
   - Game created
   - Any WS action received (step/auto/rerun)

2. **Checkpoint** — persist `last_activity_at` in `game_to_checkpoint()`, restore in `game_from_checkpoint()`

3. **`GET /api/games`** — include `last_activity_at` and `has_active_ws` (whether a WebSocket is currently connected) in each game entry

4. **Derive display status** from these fields:
   - `complete` — game is done
   - `running` — has active WS connection AND last_activity < 2 min ago
   - `stalled` — status is "running" but no active WS AND last_activity > 2 min ago
   - `paused` — not complete, no active WS, last_activity > 2 min (user walked away)
   - `created` — no days run yet

### Frontend: Experiment List (`ExperimentsView`)

1. **New status badges:**
   - 🟢 **Running** (green, pulsing dot) — actively executing
   - 🟡 **Stalled** (amber) — was running, lost connection, last activity > 2 min
   - ⏸️ **Paused** (grey) — waiting for user to continue
   - ✅ **Complete** (green) — done
   - 🆕 **Created** (blue) — not started

2. **Time-since-activity** — show "2m ago", "3h ago" next to status

3. **Auto-refresh** — poll `GET /api/games` every 15s while on the list page (or use a lightweight WS)

### Frontend: Game Runner (`GameView`)

1. **Connection indicator in header** — already shows "Reconnecting (1/10)..." but:
   - Add a colored dot next to the game title: 🟢 connected, 🟡 reconnecting, 🔴 disconnected
   - Show time since last server message: "Last update: 30s ago"

2. **Stall detection** — if no WS message received for 60s during an auto-run:
   - Show a yellow banner: "⚠️ No response from server for 60s — simulation may have stalled"
   - Offer a "Retry connection" button

3. **Activity feed improvements:**
   - On reconnect after stall, log: "🔄 Reconnected — resumed from day N"
   - On permanent disconnect: "🔴 Connection lost — game paused at day N"

### Implementation Order

1. **Backend: `last_activity_at` + `has_active_ws`** — add to Game, checkpoint, list endpoint
2. **Backend: track active WS connections per game** — simple set in game_manager
3. **Frontend: ExperimentsView** — new badges, time-since, auto-refresh
4. **Frontend: GameView** — connection dot, stall detection banner, activity feed messages

### Estimated Scope

- Backend: ~50 lines across `game.py`, `serialization.py`, `main.py`
- Frontend ExperimentsView: ~40 lines
- Frontend GameView: ~60 lines
- Total: ~150 lines, no architectural changes
