# Phase 1: Backend — Refactor Auto-Run to Yield Structured WS Messages

**Status**: Pending

---

## Objective

Refactor the game WebSocket handler to emit structured, typed messages during auto-run. Each phase of the day cycle (simulation, per-agent optimization) gets its own message type, enabling progressive frontend updates.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — all cost values in messages are integers
- INV-2: Determinism — refactoring message format doesn't change simulation results
- INV-GAME-2: Agent Isolation — optimization messages are per-agent

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

**Create `web/backend/tests/test_ws_streaming.py`:**

```python
"""Tests for WebSocket game streaming protocol."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestWSMessageTypes:
    """Verify WebSocket message protocol."""

    def test_step_emits_day_complete(self):
        """Step action sends day_complete message."""
        # Create game
        resp = client.post("/api/games", json={"max_days": 3})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            # Initial state
            msg = ws.receive_json()
            assert msg["type"] == "game_state"

            # Step
            ws.send_json({"action": "step"})

            # Should get day_complete
            msg = ws.receive_json()
            assert msg["type"] == "day_complete"
            assert "data" in msg
            assert msg["data"]["day"] == 0
            assert isinstance(msg["data"]["total_cost"], int)

            # Then optimization messages (per agent)
            msg = ws.receive_json()
            assert msg["type"] in ("optimization_start", "reasoning", "game_state")

        client.delete(f"/api/games/{game_id}")

    def test_auto_streams_all_days(self):
        """Auto-run streams day_complete for each day."""
        resp = client.post("/api/games", json={"max_days": 3})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            msg = ws.receive_json()  # initial state
            assert msg["type"] == "game_state"

            ws.send_json({"action": "auto", "speed_ms": 0})

            day_completes = []
            game_complete = None
            for _ in range(50):  # safety limit
                msg = ws.receive_json()
                if msg["type"] == "day_complete":
                    day_completes.append(msg)
                elif msg["type"] == "game_complete":
                    game_complete = msg
                    break

            assert len(day_completes) == 3
            assert game_complete is not None
            assert game_complete["data"]["is_complete"] is True

        client.delete(f"/api/games/{game_id}")

    def test_error_message_on_complete_game(self):
        """Stepping a complete game sends error message."""
        resp = client.post("/api/games", json={"max_days": 1})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})

            # Collect messages until game_state
            msgs = []
            for _ in range(10):
                msg = ws.receive_json()
                msgs.append(msg)
                if msg["type"] in ("game_complete", "game_state"):
                    break

            # Step again on complete game
            ws.send_json({"action": "step"})
            msg = ws.receive_json()
            assert msg["type"] in ("complete", "error", "game_complete")

        client.delete(f"/api/games/{game_id}")
```

### Step 1.2: Implement Structured Messages (GREEN)

**Update `web/backend/app/main.py` — game WebSocket handler:**

```python
@app.websocket("/ws/games/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str):
    await websocket.accept()
    game = game_manager.get(game_id)
    if not game:
        await websocket.send_json({"type": "error", "message": "Game not found"})
        await websocket.close()
        return

    running = False
    speed_ms = 1000

    async def run_one_step():
        """Run one day + optimization with structured messages."""
        if game.is_complete:
            await websocket.send_json({"type": "game_complete", "data": game.get_state()})
            return

        day = game.run_day()
        await websocket.send_json({"type": "day_complete", "data": day.to_dict()})

        if not game.is_complete:
            for aid in game.agent_ids:
                await websocket.send_json({
                    "type": "optimization_start",
                    "day": day.day_num,
                    "agent_id": aid,
                })

            reasoning = await game.optimize_policies()

            for aid, result in reasoning.items():
                await websocket.send_json({
                    "type": "optimization_complete",
                    "day": day.day_num,
                    "agent_id": aid,
                    "reasoning": result,
                })

        await websocket.send_json({"type": "game_state", "data": game.get_state()})

    async def auto_run():
        nonlocal running
        while running and not game.is_complete:
            await run_one_step()
            await asyncio.sleep(speed_ms / 1000.0)
        if game.is_complete:
            await websocket.send_json({"type": "game_complete", "data": game.get_state()})
        running = False

    # ... rest of handler unchanged
```

### Step 1.3: Refactor

- Extract `run_one_step` as a method for reuse
- Ensure `stop` cleanly cancels auto-run mid-optimization

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/main.py` | Modify | Restructure WS handler with typed messages |
| `web/backend/tests/test_ws_streaming.py` | Create | WS protocol tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_ws_streaming.py -v --tb=short
```

## Completion Criteria

- [ ] Step sends `day_complete` then per-agent `optimization_start`/`optimization_complete`
- [ ] Auto-run streams all days with correct message types
- [ ] `game_complete` sent when game finishes
- [ ] All cost values in messages are integers
- [ ] Tests pass
