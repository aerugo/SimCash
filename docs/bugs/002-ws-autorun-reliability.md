# Bug Report 002: WebSocket & Auto-Run Reliability for Production

**Date:** 2025-02-20  
**Status:** Investigation Complete  
**Severity:** Critical (blocks production onboarding)

---

## 1. Root Cause Analysis

### Bug 1: WS Reconnection Storm

**Symptom:** Frontend reconnects dozens of times per second when WS drops, flooding the backend.

**Root Cause:** The `connect` callback in `useGameWebSocket.ts` depends on `gameId` and `handleMessage` (line ~117). The `useEffect` at line ~120 calls `connect()` whenever `connect` changes. A secondary `useEffect` at line ~128 triggers `connect()` when `initialState` changes:

```typescript
// Line 128-132
useEffect(() => {
  if (initialState && !wsRef.current) {
    connect();
  }
}, [initialState, connect]);
```

**The storm mechanism:**
1. WS connects → receives `game_state` message → `setGameState()` updates state
2. `gameState` update propagates to parent via `onUpdateRef` (GameView line ~100)
3. Parent re-renders → `initialState` prop changes (new object reference)
4. `initialState` change triggers the second `useEffect` → calls `connect()` again
5. Meanwhile, `ws.onclose` also schedules reconnect via `setTimeout`
6. Result: multiple parallel connection attempts

The fix at line ~128 (`if (initialState && !wsRef.current)`) mitigates this partially — it checks `wsRef.current` is null. But during the brief window between `ws.onclose` (which doesn't null `wsRef`) and the reconnect timer firing, the ref may be in a stale state. Also, `wsRef.current?.readyState` check in `connect()` (line ~81) prevents duplicate OPEN connections, but during CLOSING state, a new connection can start before the old one fully closes.

**Code path:**
- `useGameWebSocket.ts:128-132` — initialState effect
- `useGameWebSocket.ts:108-118` — onclose handler schedules reconnect
- `useGameWebSocket.ts:79-82` — guard is insufficient (doesn't cover CLOSING state)

### Bug 2: Games Advance Without LLM Optimization

**Symptom:** `run_day()` commits game state before WS send confirmation — if WS dies, days advance without optimization.

**Root Cause:** In `main.py:run_one_step()` (line ~410), the flow is:

```python
day = game.run_day()                    # 1. Mutates game state (appends to game.days)
await websocket.send_json(...)          # 2. Send day_complete (can fail if WS dead)
_save_game_checkpoint(game)             # 3. Checkpoint saved WITH the new day
# ... then optimization happens
```

**The critical issue:** `game.run_day()` (game.py line ~145) calls `self.days.append(day)` and increments `current_day` immediately. This is an **irreversible state mutation**. If the WS dies between step 1 and the optimization phase:

1. The day is committed to game state
2. `_save_game_checkpoint` persists this
3. On reconnect, auto-run resumes → but the day that needed optimization was already counted
4. `should_optimize(day.day_num)` for that day is never re-evaluated
5. The game proceeds with stale (unoptimized) policies

**Compounding factor:** In `auto_run()` (main.py line ~432), if the WS send in `run_one_step()` throws (because the socket died), the exception propagates to `auto_run()`'s try/except, which sets `running = False`. But the game state already advanced. On reconnect, the frontend re-sends the `auto` command (line ~140 of useGameWebSocket.ts), which creates a NEW `auto_run()` task — but the day that needed optimization was skipped.

**Code path:**
- `game.py:145` — `self.days.append(day)` (irreversible)
- `main.py:410-420` — `run_one_step()` mutates then sends
- `main.py:432-445` — `auto_run()` exception handling
- `useGameWebSocket.ts:137-140` — re-sends auto on reconnect

### Bug 3: WS Connect Fails on Direct Navigation

**Symptom:** Removing `initialState` from connect deps fixed the storm but broke initial connection for `/experiment/:id` direct navigation.

**Root Cause:** On direct navigation to `/experiment/:id`:

1. `GameView` mounts with `contextGameState = null` and `fetchedState = null`
2. `initialState = contextGameState ?? fetchedState = null`
3. `useGameWebSocket` is called with `initialState = null`
4. `connect()` checks `if (!initialState) return` (line ~80 via `initialStateRef.current`)
5. The `useEffect` at line ~120 fires immediately, but `connect()` bails because no state
6. Meanwhile, `GameView` fetches game state from API (line ~56-60)
7. `fetchedState` is set → `initialState` becomes non-null
8. The second `useEffect` (line ~128) should fire, triggering `connect()`

**The timing issue:** The `connect` callback is memoized with `useCallback([gameId, handleMessage])`. When `initialState` changes, `connect` itself doesn't change (it reads `initialStateRef.current`). So the second `useEffect` fires because `initialState` changed, and `connect` correctly reads the new value via the ref. **This should work.**

**However**, if `initialState` was removed from the second `useEffect`'s deps (as the "fix" for Bug 1), then after the API fetch completes, nothing triggers `connect()` again. The first `useEffect` already ran (with stale ref), and won't re-run because `connect` hasn't changed.

**The fundamental tension:** `initialState` must be in deps to trigger connection after async fetch, but including it causes reconnection storms because it changes on every WS message.

**Code path:**
- `GameView.tsx:56-60` — async fetch on direct nav
- `useGameWebSocket.ts:78-80` — guard on `initialStateRef.current`
- `useGameWebSocket.ts:128-132` — the contentious effect

### Bug 4: Multi-Instance State Divergence

**Symptom:** Cloud Run scales to multiple instances, each with in-memory game state — WS may connect to different instance than game creator.

**Root Cause:** Game state lives in `game_manager: dict[str, Game]` (main.py line ~39), which is a **per-process global**. The architecture:

1. User creates game via `POST /api/games` → game stored in instance A's `game_manager`
2. Checkpoint saved to GCS/local storage
3. User opens WS → `/ws/games/{game_id}` → may route to instance B
4. Instance B checks `game_manager` (empty) → falls back to `_try_load_game()` → loads from checkpoint
5. Now **both** instance A and B have the game in memory
6. Subsequent HTTP requests (step, export) may hit either instance
7. Each runs `run_day()` independently → game state diverges

**Session affinity** (`--session-affinity` on Cloud Run) helps but doesn't guarantee:
- New connections after timeout may route differently
- WS reconnects may hit different instances
- HTTP requests aren't covered by WS affinity

**Code path:**
- `main.py:39` — `game_manager: dict[str, Game] = {}`
- `main.py:95-110` — `_try_load_game()` loads from checkpoint into memory
- `main.py:390-395` — WS handler loads game into potentially different instance

---

## 2. Architecture Diagram

```
┌─────────────── Frontend ───────────────┐
│                                         │
│  GameView                               │
│    ├── useEffect: fetch game state ────────────── GET /api/games/:id
│    │   └── sets fetchedState            │              │
│    │                                    │              ▼
│    ├── initialState = context ?? fetched │       ┌──────────┐
│    │                                    │       │ Instance │
│    └── useGameWebSocket(gameId, initial)│       │    A     │
│         │                               │       └──────────┘
│         ├── connect() ─────────────────────── WS /ws/games/:id
│         │   ├── guard: !gameId || !init │              │
│         │   ├── guard: ws already open  │              ▼
│         │   └── creates WebSocket       │       ┌──────────┐
│         │                               │       │ Instance │
│         ├── onopen:                     │       │  B (!)   │  ← May be different!
│         │   ├── flush pending queue     │       └──────────┘
│         │   └── re-send auto if active  │
│         │                               │
│         ├── onclose:                    │
│         │   ├── exponential backoff     │
│         │   └── setTimeout → connect()  │
│         │                               │
│         └── onmessage → handleMessage:  │
│             ├── game_state → setGameState│
│             ├── day_complete → setLastDay│
│             ├── optimization_* → stream │
│             └── game_complete → stop    │
└─────────────────────────────────────────┘

┌─────────────── Backend (per instance) ──────────────┐
│                                                       │
│  game_manager: dict[str, Game]  ← IN-MEMORY, LOCAL   │
│                                                       │
│  WS /ws/games/:id                                     │
│    ├── game = game_manager.get(id)                    │
│    │   └── fallback: _try_load_game(id) from GCS      │
│    │                                                   │
│    ├── run_one_step():                                │
│    │   ├── game.run_day()     ← MUTATES STATE         │
│    │   ├── ws.send(day_complete)  ← CAN FAIL          │
│    │   ├── _save_checkpoint()                          │
│    │   ├── game.optimize_policies_streaming()          │
│    │   │   ├── send optimization_start per agent       │
│    │   │   ├── LLM calls (parallel, 10 max)           │
│    │   │   ├── send optimization_chunk (streaming)     │
│    │   │   └── send optimization_complete              │
│    │   ├── _save_checkpoint()                          │
│    │   └── ws.send(game_state)                         │
│    │                                                   │
│    └── auto_run():                                    │
│        └── while running && !complete:                │
│            ├── run_one_step()                          │
│            └── sleep(speed_ms)                         │
│                                                       │
│  GameStorage (GCS/local):                             │
│    ├── checkpoints/{uid}/{game_id}.json               │
│    ├── duckdb/{uid}/{game_id}.duckdb                  │
│    └── index/{uid}/games.json                         │
└───────────────────────────────────────────────────────┘
```

### Auto-Run Flow

```
User clicks "Auto"
  │
  ▼
Frontend: autoRun(speedMs)
  ├── autoRunState.current = { active: true, speedMs }
  └── send({ action: 'auto', speed_ms: speedMs })
        │
        ▼
Backend: receives 'auto' action
  ├── running = True
  └── asyncio.create_task(auto_run())
        │
        ▼
auto_run() loop:
  while running && !game.is_complete:
    │
    ├── run_one_step()
    │   ├── game.run_day()          ◄── STATE COMMITTED HERE
    │   │   ├── _run_single_sim()
    │   │   ├── days.append(day)    ◄── IRREVERSIBLE
    │   │   └── return day
    │   │
    │   ├── ws.send(day_complete)   ◄── CAN THROW if WS dead
    │   ├── _save_checkpoint()
    │   │
    │   ├── if should_optimize():
    │   │   └── optimize_policies_streaming()
    │   │       ├── For each agent (parallel):
    │   │       │   ├── send optimization_start
    │   │       │   ├── LLM call (stream chunks)
    │   │       │   ├── bootstrap eval (if samples>1)
    │   │       │   ├── _apply_result() ◄── POLICY UPDATE
    │   │       │   └── send optimization_complete
    │   │       └── _save_checkpoint()
    │   │
    │   └── ws.send(game_state)     ◄── CAN THROW
    │
    └── asyncio.sleep(speed_ms)

  if game.is_complete:
    ws.send(game_complete)
```

---

## 3. Proposed Fixes

### Fix 1: Eliminate WS Reconnection Storm (CRITICAL)

**Problem:** `initialState` changes trigger reconnects.

**Solution:** Use a `connectedOnce` ref to separate "first connection" from "reconnection". The second useEffect should only trigger the *first* connection, never subsequent ones. Reconnection is handled exclusively by `onclose`.

**File:** `web/frontend/src/hooks/useGameWebSocket.ts`

```typescript
// Add ref after line 67
const connectedOnceRef = useRef(false);

// Replace the second useEffect (lines 128-132) with:
useEffect(() => {
  // Only trigger initial connection when state becomes available
  // After first connection, reconnection is handled by onclose handler
  if (initialState && !connectedOnceRef.current && !wsRef.current) {
    connect();
  }
}, [initialState, connect]);

// In ws.onopen handler (after line 125), add:
connectedOnceRef.current = true;

// In cleanup (line 134), add:
connectedOnceRef.current = false;
```

**Also:** Null out `wsRef.current` in `onclose` before scheduling reconnect to prevent stale ref checks:

```typescript
// In ws.onclose (line 108), before the reconnect logic:
wsRef.current = null;
```

### Fix 2: Transactional Day Execution (CRITICAL)

**Problem:** `run_day()` mutates state before WS confirmation. If WS dies mid-step, the day is committed without optimization.

**Solution:** Split `run_day()` into simulate + commit phases. Only commit after successful WS delivery and optimization.

**File:** `web/backend/app/game.py`

Add a `simulate_day()` method that returns a `GameDay` without appending to `self.days`:

```python
# After run_day() method (~line 145)
def simulate_day(self) -> GameDay:
    """Run simulation without committing to game state.
    Returns a GameDay that can be committed via commit_day()."""
    day_num = self.current_day
    seed = self._base_seed + day_num
    all_events, balance_history, costs, per_agent_costs, total_cost, tick_events = self._run_single_sim(seed)
    # ... same multi-sample logic as run_day() ...
    return GameDay(
        day_num=day_num, seed=seed,
        policies=copy.deepcopy(self.policies),
        costs=costs, events=all_events,
        balance_history=balance_history,
        total_cost=total_cost,
        per_agent_costs=per_agent_costs,
        tick_events=tick_events,
    )

def commit_day(self, day: GameDay):
    """Commit a previously simulated day to game state."""
    self.days.append(day)
```

**File:** `web/backend/app/main.py`

Update `run_one_step()` (~line 410):

```python
async def run_one_step():
    if game.is_complete:
        await websocket.send_json({"type": "game_complete", "data": game.get_state()})
        return

    await websocket.send_json({"type": "simulation_running", ...})

    day = game.simulate_day()  # Don't commit yet

    try:
        await websocket.send_json({"type": "day_complete", "data": day.to_dict()})
    except Exception:
        # WS dead — don't commit the day, let reconnect retry
        logger.warning("WS dead during day delivery, not committing day %d", day.day_num)
        raise

    game.commit_day(day)  # Only commit after successful send
    _save_game_checkpoint(game)

    if not game.is_complete and game.should_optimize(day.day_num):
        await game.optimize_policies_streaming(websocket.send_json)
        day.optimized = True
        _save_game_checkpoint(game)

    await websocket.send_json({"type": "game_state", "data": game.get_state()})
```

### Fix 3: Proper Initial Connection Timing (CRITICAL)

**Problem:** Hook needs to connect when game state is available but not reconnect on every state update.

**Solution:** Already addressed by Fix 1. The `connectedOnceRef` pattern cleanly separates:
- **First connection:** Triggered by `initialState` becoming non-null
- **Reconnection:** Handled exclusively by `onclose` with exponential backoff

Additionally, move the `initialStateRef` guard to only block the *very first* connect, not reconnects:

```typescript
// In connect() (line 80), change the guard:
if (!gameId) return;
// Only require initialState for first connection
if (!connectedOnceRef.current && !initialStateRef.current) return;
```

This way, reconnections (triggered by `onclose`) don't need `initialState` — they already have a `gameId` and the backend will send fresh `game_state` on connect.

### Fix 4: Prevent Concurrent Game Execution (HIGH)

**Problem:** Two WS connections (or WS + HTTP) can run `run_day()` simultaneously on the same game.

**Solution:** Add a per-game asyncio lock.

**File:** `web/backend/app/main.py`

```python
# After game_manager declaration (line 39)
game_locks: dict[str, asyncio.Lock] = {}

def get_game_lock(game_id: str) -> asyncio.Lock:
    if game_id not in game_locks:
        game_locks[game_id] = asyncio.Lock()
    return game_locks[game_id]
```

In `run_one_step()`:
```python
async def run_one_step():
    async with get_game_lock(game_id):
        # ... existing logic ...
```

### Fix 5: Multi-Instance State Convergence (MEDIUM — for scale)

**Problem:** Cloud Run instances have independent in-memory state.

**Short-term:** This is acceptable with session affinity + single instance for early users. The checkpoint system provides eventual consistency.

**Medium-term solutions:**
1. **Redis for game state:** Move `game_manager` to Redis. Each `run_day()` reads from Redis, mutates, writes back with optimistic locking (WATCH/MULTI).
2. **Cloud Run min-instances=1, max-instances=1:** For early production, cap at 1 instance. Simplest fix.
3. **Sticky routing by game_id:** Use Cloud Run's session affinity with a custom header/cookie tied to game_id.

**Recommended for launch:** Set `max-instances=1` in Cloud Run config. This eliminates the problem entirely for the first ~50 concurrent users.

### Fix 6: WS Keepalive Robustness (LOW)

The backend already sends pings every 20s (line ~455). The frontend should respond or at least handle ping messages:

**File:** `web/frontend/src/hooks/useGameWebSocket.ts`

```typescript
// In handleMessage, add case:
case 'ping':
  // Ignored — keepalive from server
  break;
```

---

## 4. Production Readiness Checklist

### Critical (Must fix before any users)
- [ ] **Fix 1:** WS reconnection storm — `connectedOnceRef` pattern
- [ ] **Fix 2:** Transactional day execution — `simulate_day()` + `commit_day()`
- [ ] **Fix 3:** Initial connection timing — already covered by Fix 1
- [ ] **Fix 4:** Per-game execution lock

### High Priority (Before scaling beyond ~5 users)
- [ ] **Fix 5 (short-term):** Set `max-instances=1` on Cloud Run
- [ ] **Error recovery:** If WS dies during auto-run, frontend should show "connection lost, auto-run paused" and offer retry
- [ ] **Idempotent reconnect:** On WS reconnect, backend sends full `game_state` — frontend should reconcile (it already does via `game_state` handler)
- [ ] **Auto-run state sync:** Currently, reconnect re-sends `auto` command. If the backend's auto_run task is still running from the old connection, this creates a second concurrent task. Need to cancel old task on new WS connection.

### Medium Priority (Before ~50 users)
- [ ] **Fix 5 (medium-term):** Redis-backed game state or sticky routing
- [ ] **Rate limiting:** Limit WS connections per user (prevent tab-spam)
- [ ] **Graceful shutdown:** On Cloud Run instance shutdown, save all in-memory games to checkpoint
- [ ] **Health check for WS:** Backend should track active WS connections and expose via `/api/health`

### Nice to Have
- [ ] **Fix 6:** Handle ping messages in frontend
- [ ] **Connection quality indicator:** Show latency/jitter to user
- [ ] **Offline queue:** Queue user actions when disconnected, replay on reconnect

---

## 5. Priority Order

| Priority | Fix | Effort | Impact |
|----------|-----|--------|--------|
| 🔴 P0 | Fix 1: Reconnection storm | 1h | Eliminates backend flooding |
| 🔴 P0 | Fix 2: Transactional days | 2h | Prevents data loss/skipped optimization |
| 🔴 P0 | Fix 3: Initial connection | 0h (part of Fix 1) | Direct nav works |
| 🟠 P1 | Fix 4: Game execution lock | 30min | Prevents race conditions |
| 🟠 P1 | Auto-run task dedup on reconnect | 1h | Prevents double execution |
| 🟡 P2 | Fix 5: max-instances=1 | 5min | Eliminates multi-instance issue |
| 🟡 P2 | Reconnect UX (pause indicator) | 1h | User knows what's happening |
| 🟢 P3 | Fix 6: Ping handling | 5min | Cleaner logs |
| 🟢 P3 | Redis state (if scaling needed) | 1-2 days | True multi-instance support |

**Recommended implementation order:** Fix 1 → Fix 2 → Fix 4 → Cloud Run max-instances=1 → auto-run dedup → UX improvements.

Total estimated effort for P0+P1: **~4.5 hours**.
