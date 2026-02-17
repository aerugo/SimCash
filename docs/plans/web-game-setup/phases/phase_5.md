# Phase 5: Test & Verify End-to-End

**Status**: Pending

---

## Objective

Write comprehensive backend tests for the full game setup flow and verify the complete setup → game creation → play cycle works end-to-end.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — verify cost values are integers in API responses
- INV-2: Determinism — same config creates reproducible game
- INV-GAME-1: Policy Reality — verify created game produces different costs for different fractions

---

## TDD Steps

### Step 5.1: Backend Integration Tests (RED → GREEN)

**Add to `web/backend/tests/test_game_setup.py`:**

```python
class TestGameSetupE2E:
    """End-to-end game setup tests."""

    def test_full_setup_flow(self):
        """Scenario list → pick scenario → create game → run step."""
        # 1. List scenarios
        resp = client.get("/api/games/scenarios")
        assert resp.status_code == 200
        scenarios = resp.json()["scenarios"]
        assert len(scenarios) > 0

        # 2. Create game with first scenario
        scenario_id = scenarios[0]["id"]
        resp = client.post("/api/games", json={
            "scenario_id": scenario_id,
            "max_days": 3,
            "num_eval_samples": 2,
        })
        assert resp.status_code == 200
        game_id = resp.json()["game_id"]
        state = resp.json()["game"]
        assert state["max_days"] == 3
        assert state["current_day"] == 0

        # 3. Run a step
        resp = client.post(f"/api/games/{game_id}/step")
        assert resp.status_code == 200
        day = resp.json()["day"]
        assert day["day"] == 0
        # Costs are integers (INV-1)
        for aid, costs in day["costs"].items():
            assert isinstance(costs["total"], int)

        # 4. Cleanup
        resp = client.delete(f"/api/games/{game_id}")
        assert resp.status_code == 200

    def test_determinism_with_same_config(self):
        """Same scenario + config produces same day-0 costs (INV-2)."""
        config = {"scenario_id": "2bank_12tick", "max_days": 2}

        resp1 = client.post("/api/games", json=config)
        game1 = resp1.json()["game_id"]
        step1 = client.post(f"/api/games/{game1}/step").json()

        resp2 = client.post("/api/games", json=config)
        game2 = resp2.json()["game_id"]
        step2 = client.post(f"/api/games/{game2}/step").json()

        # Same seed → same costs
        assert step1["day"]["per_agent_costs"] == step2["day"]["per_agent_costs"]

        client.delete(f"/api/games/{game1}")
        client.delete(f"/api/games/{game2}")

    def test_num_eval_samples_affects_stability(self):
        """More eval samples should produce the same result for seed-based runs."""
        config1 = {"scenario_id": "2bank_12tick", "max_days": 2, "num_eval_samples": 1}
        config5 = {"scenario_id": "2bank_12tick", "max_days": 2, "num_eval_samples": 5}

        resp1 = client.post("/api/games", json=config1)
        g1 = resp1.json()["game_id"]
        s1 = client.post(f"/api/games/{g1}/step").json()

        resp5 = client.post("/api/games", json=config5)
        g5 = resp5.json()["game_id"]
        s5 = client.post(f"/api/games/{g5}/step").json()

        # Both should produce valid integer costs
        for aid in s1["day"]["per_agent_costs"]:
            assert isinstance(s1["day"]["per_agent_costs"][aid], int)
            assert isinstance(s5["day"]["per_agent_costs"][aid], int)

        client.delete(f"/api/games/{g1}")
        client.delete(f"/api/games/{g5}")

    def test_all_scenarios_create_valid_games(self):
        """Every scenario in the pack creates a valid game."""
        resp = client.get("/api/games/scenarios")
        scenarios = resp.json()["scenarios"]

        for s in scenarios:
            resp = client.post("/api/games", json={
                "scenario_id": s["id"],
                "max_days": 1,
            })
            assert resp.status_code == 200, f"Failed for scenario {s['id']}: {resp.text}"
            game_id = resp.json()["game_id"]

            # Should be able to run at least one step
            step_resp = client.post(f"/api/games/{game_id}/step")
            assert step_resp.status_code == 200, f"Step failed for {s['id']}"

            client.delete(f"/api/games/{game_id}")
```

### Step 5.2: Refactor

- Clean up any flaky test ordering issues
- Ensure test isolation (each test creates/deletes its own game)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/tests/test_game_setup.py` | Modify | Add E2E integration tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_game_setup.py -v --tb=short
```

## Completion Criteria

- [ ] All scenarios from pack create valid games
- [ ] Determinism test passes (same config → same costs)
- [ ] num_eval_samples parameter flows through correctly
- [ ] Full setup → step → cleanup flow works
- [ ] All integer cost invariant verified in responses
- [ ] All tests pass
