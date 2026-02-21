# Bug Report 003: Crisis Scenario Stalls at "Simulating Round 1..."

**Date:** 2025-02-21
**Reporter:** Hugi (production), Nash (investigation)
**Severity:** High — crisis_resolution_10day scenario never completes Round 1

## Symptoms

- User launches Crisis Resolution 10-Day scenario (4 banks × 100 ticks × 10 days, 50 eval samples)
- UI shows "Simulating Round 1..." indefinitely
- Game never progresses past day 0
- Other scenarios (2 banks × 12 ticks) work fine

## Root Causes

### Root Cause 1: HTTP Step Endpoint Blocks the Event Loop (CRITICAL)

**File:** `web/backend/app/main.py`, line ~816

The HTTP `POST /api/games/{game_id}/step` endpoint calls `game.run_day()` **synchronously** inside an async handler:

```python
async with get_game_lock(game_id):
    day = game.run_day()  # ← SYNC CALL, blocks entire event loop
```

For the crisis scenario with 50 eval samples, `run_day()` takes **~60 seconds** (verified locally on M-series Mac). During this time:
- Health checks time out (verified: `GET /api/health` → timeout)
- WebSocket keepalive pings cannot be sent
- No other requests can be processed
- Cloud Run may consider the instance dead

The WS auto-run path (`run_one_step`) correctly uses `await loop.run_in_executor(None, game.simulate_day)`, but the HTTP endpoint does not.

**The HTTP `POST /api/games/{game_id}/run-all` endpoint has the same bug** — it calls `game.run_day()` in a sync loop.

### Root Cause 2: Reconnection Storm from Completed Games (HIGH)

**File:** `web/frontend/src/` (WebSocket connection logic)

Production logs show ~8 old completed games reconnecting simultaneously every few seconds:
```
WS game 0e77b1e1 received action: auto (running=False, complete=True)
WS game 29d4d080 received action: auto (running=False, complete=True)
WS game 065b4a05 received action: auto (running=False, complete=True)
... (repeating)
```

Each reconnect:
1. Opens a new WebSocket connection
2. Sends `auto` command
3. Gets back `complete=True`
4. Connection closes
5. Frontend reconnects (backoff, but still frequent)

This generates 429 rate limits from Cloud Run and competes with the active game's WS connection. When combined with Root Cause 1 (blocked event loop), the active game's WS gets killed → `CancelledError` → "Auto-run cancelled for game (dedup or stop)".

### Root Cause 3: Massive Response Payload (MEDIUM)

The `day_complete` response includes **full events array and balance history** for all 4 agents across 1000 ticks. For the crisis scenario, this is ~2MB+ of JSON. While `to_summary_dict()` exists and is used in the WS path, the HTTP step endpoint returns the full `day.to_dict()` with all events.

This compounds the problem — even if the simulation completes, serializing and transmitting 2MB over a potentially degraded connection can fail.

## Evidence

### Production Logs (game 08ec5a89)
```
04:30:23 Auto-run started for game 08ec5a89 (speed_ms=3000)
04:30:23 Auto-run: starting step for day 0/10
  ... no run_one_step completion logged ...
04:31:17 Auto-run cancelled for game 08ec5a89 (dedup or stop)
```
54 seconds between start and cancellation. No simulation completion logged.

### Local Reproduction
```
$ time curl -s -X POST http://127.0.0.1:8642/api/games/b72ffa91/step
real    1m0.57s
```
Server completely unresponsive during this time (health check times out).

### Successful Prior Runs
Previous successful crisis runs used:
- Fewer eval samples (game `1204cc0c`: 1 eval sample)
- Smaller scenarios (game `b2718492`: 2 banks × 12 ticks, 10 rounds)
- No concurrent reconnection storm

## Fix Plan

### Fix 1: Async HTTP Step + Run-All Endpoints (CRITICAL)

Wrap `game.run_day()` in `run_in_executor` for both HTTP endpoints, matching the WS path:

```python
# Before (blocks event loop):
day = game.run_day()

# After (non-blocking):
loop = asyncio.get_event_loop()
day = await loop.run_in_executor(None, game.run_day)
```

Also use `to_summary_dict()` for HTTP responses to avoid 2MB payloads.

### Fix 2: Don't Reconnect Completed Games (HIGH)

In the frontend WebSocket hook, when initial state comes back with `is_complete=true`:
- Close the WebSocket cleanly
- Do NOT trigger reconnection
- Display final state from the HTTP game fetch (already available)

### Fix 3: Guard Against Concurrent Auto-Run on Completed Games (MEDIUM)

Backend should reject `auto` commands for completed games without entering the auto-run loop:

```python
if game.is_complete:
    await websocket.send_json({"type": "game_complete", "data": game.get_state()})
    return  # Don't start auto_run
```

(This may already exist but needs verification — the logs show `complete=True` responses but the reconnection still happens.)

### Fix 4: Timeout Guard for simulate_day (LOW)

Add a configurable timeout for `simulate_day` in `run_in_executor`. If a simulation takes longer than, say, 120s, cancel it and report an error rather than hanging indefinitely.

## Implementation Order

1. **Fix 1** — Most critical, unblocks the entire server
2. **Fix 2** — Stops the reconnection storm
3. **Fix 3** — Defense in depth on the backend
4. **Fix 4** — Nice to have, prevents future hangs
