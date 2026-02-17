# Phase 5: Test with Mock (Fast) and Verify Protocol

**Status**: Pending

---

## Objective

Write comprehensive WebSocket protocol tests using mock optimization (fast), verify message ordering, test edge cases (disconnect, reconnect, step after complete).

---

## Invariants Enforced in This Phase

- INV-1: All cost values in WS messages are integers
- INV-2: Determinism — same game produces same message sequence

---

## TDD Steps

### Step 5.1: Protocol Ordering Tests (RED → GREEN)

**Add to `web/backend/tests/test_ws_streaming.py`:**

```python
class TestWSProtocolOrdering:
    """Verify message ordering in the WS protocol."""

    def test_step_message_order(self):
        """Step produces: day_complete → optimization_start(s) → optimization_complete(s) → game_state."""
        resp = client.post("/api/games", json={"max_days": 5})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial game_state

            ws.send_json({"action": "step"})

            messages = []
            for _ in range(20):
                msg = ws.receive_json()
                messages.append(msg["type"])
                if msg["type"] == "game_state":
                    break

            # day_complete must come before any optimization
            assert "day_complete" in messages
            dc_idx = messages.index("day_complete")

            # If optimization happened, it must be after day_complete
            if "optimization_start" in messages:
                os_idx = messages.index("optimization_start")
                assert os_idx > dc_idx

            # game_state must be last
            assert messages[-1] == "game_state"

        client.delete(f"/api/games/{game_id}")

    def test_auto_complete_message(self):
        """Auto-run ends with game_complete when all days done."""
        resp = client.post("/api/games", json={"max_days": 2})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "auto", "speed_ms": 0})

            types = []
            for _ in range(50):
                msg = ws.receive_json()
                types.append(msg["type"])
                if msg["type"] == "game_complete":
                    break

            assert types[-1] == "game_complete"
            assert types.count("day_complete") == 2

        client.delete(f"/api/games/{game_id}")

    def test_stop_during_auto(self):
        """Stop command halts auto-run."""
        resp = client.post("/api/games", json={"max_days": 20})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "auto", "speed_ms": 100})

            # Let a couple days run
            import time
            time.sleep(0.3)

            ws.send_json({"action": "stop"})

            # Drain messages
            msg = ws.receive_json()
            # Game should not be complete (stopped early)
            ws.send_json({"action": "state"})
            state_msg = ws.receive_json()
            while state_msg["type"] != "game_state":
                state_msg = ws.receive_json()
            assert state_msg["data"]["current_day"] < 20

        client.delete(f"/api/games/{game_id}")

    def test_costs_are_integers_in_ws(self):
        """All cost values in day_complete messages are integers (INV-1)."""
        resp = client.post("/api/games", json={"max_days": 1})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})

            for _ in range(10):
                msg = ws.receive_json()
                if msg["type"] == "day_complete":
                    for aid, costs in msg["data"]["costs"].items():
                        assert isinstance(costs["total"], int), f"Cost not int: {costs['total']}"
                        assert isinstance(costs["delay_cost"], int)
                        assert isinstance(costs["penalty_cost"], int)
                    break

        client.delete(f"/api/games/{game_id}")
```

### Step 5.2: Refactor

- Extract test fixtures for game creation/cleanup
- Add timeout to WS receive calls to prevent test hangs

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/tests/test_ws_streaming.py` | Modify | Add protocol ordering + edge case tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_ws_streaming.py -v --tb=short
```

## Completion Criteria

- [ ] Message ordering verified: day_complete → optimization → game_state
- [ ] Auto-run ends with game_complete
- [ ] Stop command halts auto-run before completion
- [ ] All cost values are integers in WS messages
- [ ] No test hangs (timeouts on all receives)
- [ ] All tests pass
