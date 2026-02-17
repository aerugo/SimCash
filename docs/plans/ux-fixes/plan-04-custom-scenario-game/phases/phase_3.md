# Phase 3: Integration Tests

**Status**: Pending

## Objective

End-to-end verification that a custom scenario can be played as a multi-day game.

## Invariants

- INV-GAME-1: Policy Reality — custom configs produce different costs at different fractions

## TDD Steps

### Step 3.1: RED — Write Failing Test

Add to `web/backend/tests/test_game_setup.py`:

```python
class TestCustomScenarioGame:
    """E2E: custom config → game → step → verify costs."""

    def test_custom_game_step_produces_results(self):
        """A game created with inline config can be stepped."""
        inline = {
            "ticks_per_day": 3,
            "num_days": 1,
            "rng_seed": 42,
            "agents": [
                {"id": "BANK_A", "liquidity_pool": 100000},
                {"id": "BANK_B", "liquidity_pool": 100000},
            ],
            "cost_config": {
                "liquidity_cost_per_tick_bps": 333,
                "delay_cost_per_tick_per_cent": 0.2,
                "deadline_penalty": 50000,
            },
            "payment_schedule": [
                {"sender": "BANK_A", "receiver": "BANK_B", "amount": 50000, "tick": 0, "deadline": 2},
            ],
        }
        resp = client.post("/api/games", json={
            "inline_config": inline,
            "max_days": 3,
            "use_llm": False,
        })
        assert resp.status_code == 200
        game_id = resp.json()["game_id"]

        # Step the game
        resp2 = client.post(f"/api/games/{game_id}/step")
        assert resp2.status_code == 200
        state = resp2.json()
        assert state["current_day"] == 1
        assert len(state["days"]) == 1
        assert "BANK_A" in state["days"][0]["costs"]
```

### Step 3.2: GREEN — Verify Existing Implementation

If Phase 1 and 2 are correctly implemented, this should pass without additional code changes. The `Game` class already handles arbitrary `raw_yaml` dicts.

### Step 3.3: REFACTOR

Add error handling for malformed inline configs that crash the simulator.

## Files Changed

| File | Action |
|------|--------|
| `web/backend/tests/test_game_setup.py` | Modify — add E2E test |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest web/backend/tests/test_game_setup.py::TestCustomScenarioGame -v --tb=short
```

## Completion Criteria

- [ ] Custom inline config game can be created and stepped
- [ ] Day results contain costs for all agents
- [ ] Tests pass
