# Phase 5: Test and Polish Animations

**Status**: Pending

---

## Objective

Write integration tests for progress events, verify timing accuracy, polish animations, handle edge cases (fast mock mode, disconnection during loading).

---

## Invariants Enforced in This Phase

- INV-2: Determinism — verify progress events don't affect simulation results

---

## TDD Steps

### Step 5.1: Backend Progress Event Tests (RED → GREEN)

**Add to `web/backend/tests/test_loading_progress.py`:**

```python
class TestProgressEventIntegrity:
    """Verify progress events don't affect simulation results."""

    def test_same_results_with_progress_events(self):
        """Game with WS (progress events) produces same costs as REST (no events)."""
        config = {"scenario_id": "2bank_12tick", "max_days": 2}

        # REST path
        resp = client.post("/api/games", json=config)
        g_rest = resp.json()["game_id"]
        client.post(f"/api/games/{g_rest}/step")
        rest_state = client.get(f"/api/games/{g_rest}").json()

        # WS path
        resp2 = client.post("/api/games", json=config)
        g_ws = resp2.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{g_ws}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})
            msgs = []
            for _ in range(20):
                msg = ws.receive_json()
                msgs.append(msg)
                if msg["type"] == "game_state":
                    break

        ws_state = client.get(f"/api/games/{g_ws}").json()

        # Costs must be identical (INV-2)
        assert rest_state["cost_history"] == ws_state["cost_history"]

        client.delete(f"/api/games/{g_rest}")
        client.delete(f"/api/games/{g_ws}")

    def test_timestamps_are_monotonic(self):
        """All timestamps in progress events are monotonically increasing."""
        resp = client.post("/api/games", json={"max_days": 2})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "step"})

            timestamps = []
            for _ in range(20):
                msg = ws.receive_json()
                if "timestamp" in msg:
                    timestamps.append(msg["timestamp"])
                if msg["type"] == "game_state":
                    break

            # Timestamps should be monotonically increasing
            for i in range(1, len(timestamps)):
                assert timestamps[i] >= timestamps[i - 1]

        client.delete(f"/api/games/{game_id}")

    def test_fast_mock_doesnt_spam_events(self):
        """In mock mode, events still fire but don't cause issues at speed."""
        resp = client.post("/api/games", json={"max_days": 5})
        game_id = resp.json()["game_id"]

        with client.websocket_connect(f"/ws/games/{game_id}") as ws:
            ws.receive_json()  # initial state
            ws.send_json({"action": "auto", "speed_ms": 0})

            all_types = []
            for _ in range(100):
                msg = ws.receive_json()
                all_types.append(msg["type"])
                if msg["type"] == "game_complete":
                    break

            assert "game_complete" in all_types
            # Should have reasonable number of events (not thousands)
            assert len(all_types) < 60  # 5 days * ~10 events/day max

        client.delete(f"/api/games/{game_id}")
```

### Step 5.2: Frontend Animation Polish

- Ensure `animate-pulse` doesn't fire on mount (use `useEffect` delay)
- Verify badge transitions are smooth (no flicker between states)
- Test with slow network simulation (WS messages delayed)
- Timer drift compensation: use server timestamps, not client clock

### Step 5.3: Edge Case Handling

```tsx
// In useGameWebSocket — handle disconnection during loading
ws.onclose = () => setState(s => ({
  ...s,
  connected: false,
  currentPhase: 'idle',  // Reset phase on disconnect
  optimizingAgent: null,
  agentStatuses: Object.fromEntries(
    Object.keys(s.agentStatuses).map(aid => [aid, { phase: 'idle', startTime: null }])
  ),
}));
```

### Step 5.4: Refactor

- Add `data-testid` attributes for automated UI testing
- Document animation performance characteristics
- Add reduced-motion media query support

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/tests/test_loading_progress.py` | Modify | Integrity + timing tests |
| `web/frontend/src/hooks/useGameWebSocket.ts` | Modify | Edge case handling |
| `web/frontend/src/components/LoadingOverlay.tsx` | Modify | Reduced-motion support |
| `web/frontend/src/components/AgentStatusBadge.tsx` | Modify | Polish animations |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_loading_progress.py -v --tb=short
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] Progress events don't affect simulation results (INV-2)
- [ ] Timestamps monotonically increasing
- [ ] Fast mock mode doesn't spam excessive events
- [ ] Disconnection during loading resets UI gracefully
- [ ] Reduced-motion media query respected
- [ ] All tests pass
