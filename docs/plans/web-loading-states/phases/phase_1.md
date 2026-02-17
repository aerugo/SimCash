# Phase 1: Backend — Add Progress Events to WebSocket

**Status**: Pending

---

## Objective

Emit granular progress events during game operations so the frontend can show exactly what's happening: simulation running, LLM calling for which agent, LLM complete.

---

## Invariants Enforced in This Phase

- INV-2: Determinism — progress events are observational only
- INV-GAME-2: Agent Isolation — LLM progress events are per-agent

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

**Create `web/backend/tests/test_loading_progress.py`:**

```python
"""Tests for loading progress WebSocket events."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestProgressEvents:
    """Verify progress events during game operations."""

    def test_step_emits_simulation_running(self):
        """Step action sends simulation_running before day_complete."""
        resp = client.post("/api/games", json={"max_days": 3})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})

            types = []
            for _ in range(15):
                msg = ws.receive_json()
                types.append(msg["type"])
                if msg["type"] == "game_state":
                    break

            assert "simulation_start" in types or "simulation_running" in types

        client.delete(f"/api/games/{game_id}")

    def test_optimization_emits_per_agent_llm_events(self):
        """Optimization emits llm_calling + llm_complete per agent."""
        resp = client.post("/api/games", json={
            "max_days": 3,
            "use_llm": False,  # mock is fine — still emits events
            "mock_reasoning": True,
        })
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})

            messages = []
            for _ in range(20):
                msg = ws.receive_json()
                messages.append(msg)
                if msg["type"] == "game_state":
                    break

            opt_starts = [m for m in messages if m["type"] == "optimization_start"]
            opt_completes = [m for m in messages if m["type"] == "optimization_complete"]

            # Should have events for each agent
            assert len(opt_starts) >= 1
            for m in opt_starts:
                assert "agent_id" in m

        client.delete(f"/api/games/{game_id}")

    def test_progress_events_include_timestamps(self):
        """Progress events include timestamp for elapsed time calculation."""
        resp = client.post("/api/games", json={"max_days": 2})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})

            for _ in range(15):
                msg = ws.receive_json()
                if msg["type"] in ("simulation_start", "optimization_start", "day_complete"):
                    assert "timestamp" in msg
                    break

        client.delete(f"/api/games/{game_id}")
```

### Step 1.2: Implement Progress Events (GREEN)

**Update `web/backend/app/main.py` — game WS handler `run_one_step`:**

```python
import time

async def run_one_step():
    if game.is_complete:
        await websocket.send_json({"type": "game_complete", "data": game.get_state()})
        return

    # Simulation phase
    await websocket.send_json({
        "type": "simulation_start",
        "day": game.current_day,
        "timestamp": time.time(),
    })

    day = game.run_day()

    await websocket.send_json({
        "type": "day_complete",
        "data": day.to_dict(),
        "timestamp": time.time(),
    })

    # Optimization phase
    if not game.is_complete:
        for aid in game.agent_ids:
            await websocket.send_json({
                "type": "optimization_start",
                "day": day.day_num,
                "agent_id": aid,
                "timestamp": time.time(),
            })

        reasoning = await game.optimize_policies()

        for aid, result in reasoning.items():
            await websocket.send_json({
                "type": "optimization_complete",
                "day": day.day_num,
                "agent_id": aid,
                "reasoning": result,
                "timestamp": time.time(),
            })

    await websocket.send_json({"type": "game_state", "data": game.get_state()})
```

### Step 1.3: Refactor

- For real LLM mode, emit `llm_calling` before each agent's LLM call and `llm_complete` after
- Add `phase` field: `"simulation"` or `"optimization"`

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/main.py` | Modify | Add timestamp + phase to WS messages |
| `web/backend/tests/test_loading_progress.py` | Create | Progress event tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_loading_progress.py -v --tb=short
```

## Completion Criteria

- [ ] `simulation_start` emitted before simulation runs
- [ ] `optimization_start` emitted per agent with `agent_id`
- [ ] `optimization_complete` emitted per agent with reasoning
- [ ] All progress events include `timestamp`
- [ ] Tests pass
