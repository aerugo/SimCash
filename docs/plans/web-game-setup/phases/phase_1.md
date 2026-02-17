# Phase 1: Backend — Scenario List Endpoint + Validated Game Creation

**Status**: Pending

---

## Objective

Add a Pydantic model for game creation requests with proper validation, wire `num_eval_samples` into the Game constructor, and add a `/api/games/scenarios` endpoint that returns scenario metadata suitable for the setup UI.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — `num_eval_samples` and `max_days` are positive integers
- INV-2: Determinism — seed is preserved from scenario config
- INV-GAME-1: Policy Reality — scenario list includes cost parameters so UI can preview

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

Create `web/backend/tests/test_game_setup.py`:

```python
"""Tests for game setup API endpoints."""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCreateGameValidation:
    """Validate game creation parameters."""

    def test_create_game_with_defaults(self):
        """Creating a game with no params uses sensible defaults."""
        resp = client.post("/api/games", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data
        state = data["game"]
        assert state["max_days"] == 10
        assert state["use_llm"] is False

    def test_create_game_with_num_eval_samples(self):
        """num_eval_samples is accepted and stored."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "num_eval_samples": 5,
            "max_days": 3,
        })
        assert resp.status_code == 200

    def test_create_game_invalid_scenario(self):
        """Unknown scenario returns 400."""
        resp = client.post("/api/games", json={"scenario_id": "nonexistent"})
        assert resp.status_code == 400

    def test_create_game_max_days_bounds(self):
        """max_days must be 1-100."""
        resp = client.post("/api/games", json={"max_days": 0})
        assert resp.status_code == 422
        resp = client.post("/api/games", json={"max_days": 101})
        assert resp.status_code == 422

    def test_create_game_num_eval_samples_bounds(self):
        """num_eval_samples must be 1-50."""
        resp = client.post("/api/games", json={"num_eval_samples": 0})
        assert resp.status_code == 422
        resp = client.post("/api/games", json={"num_eval_samples": 51})
        assert resp.status_code == 422


class TestGameScenariosEndpoint:
    """Test /api/games/scenarios endpoint."""

    def test_list_game_scenarios(self):
        """Returns available scenarios with game-relevant metadata."""
        resp = client.get("/api/games/scenarios")
        assert resp.status_code == 200
        data = resp.json()
        assert "scenarios" in data
        assert len(data["scenarios"]) > 0
        scenario = data["scenarios"][0]
        assert "id" in scenario
        assert "name" in scenario
        assert "description" in scenario
        assert "num_agents" in scenario
        assert "ticks_per_day" in scenario

    def test_scenario_has_cost_preview(self):
        """Each scenario includes cost rate info for preview."""
        resp = client.get("/api/games/scenarios")
        scenarios = resp.json()["scenarios"]
        for s in scenarios:
            assert "cost_rates" in s or "difficulty" in s
```

### Step 1.2: Implement to Pass Tests (GREEN)

**Add to `web/backend/app/models.py`:**

```python
from pydantic import BaseModel, Field

class CreateGameRequest(BaseModel):
    scenario_id: str = "2bank_12tick"
    use_llm: bool = False
    mock_reasoning: bool = True
    max_days: int = Field(default=10, ge=1, le=100)
    num_eval_samples: int = Field(default=1, ge=1, le=50)
```

**Update `web/backend/app/main.py`:**

```python
from .models import CreateGameRequest

@app.get("/api/games/scenarios")
def list_game_scenarios():
    """List scenarios available for game creation with preview metadata."""
    pack = get_scenario_pack()
    scenarios = []
    for entry in pack:
        full = get_scenario_by_id(entry["id"])
        cost_rates = full.get("cost_rates", {}) if full else {}
        scenarios.append({
            "id": entry["id"],
            "name": entry["name"],
            "description": entry["description"],
            "num_agents": entry.get("num_agents", 2),
            "ticks_per_day": entry.get("ticks_per_day", 12),
            "cost_rates": cost_rates,
            "difficulty": entry.get("difficulty", "medium"),
        })
    return {"scenarios": scenarios}

@app.post("/api/games")
async def create_game(config: CreateGameRequest = CreateGameRequest()):
    """Create a multi-day policy optimization game."""
    game_id = str(uuid.uuid4())[:8]
    raw_yaml = get_scenario_by_id(config.scenario_id)
    if not raw_yaml:
        raise HTTPException(status_code=400, detail=f"Unknown scenario: {config.scenario_id}")

    import copy
    raw_yaml = copy.deepcopy(raw_yaml)

    game = Game(
        game_id=game_id,
        raw_yaml=raw_yaml,
        use_llm=config.use_llm,
        mock_reasoning=config.mock_reasoning,
        max_days=config.max_days,
        num_eval_samples=config.num_eval_samples,
    )
    game_manager[game_id] = game
    return {"game_id": game_id, "game": game.get_state()}
```

### Step 1.3: Refactor

- Ensure `Game.get_state()` includes `num_eval_samples` in the response so frontend can display it
- Add `num_eval_samples` to `Game.get_state()` dict

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/models.py` | Modify | Add `CreateGameRequest` Pydantic model |
| `web/backend/app/main.py` | Modify | Add `/api/games/scenarios`, update `POST /api/games` to use model |
| `web/backend/app/game.py` | Modify | Add `num_eval_samples` to `get_state()` output |
| `web/backend/tests/test_game_setup.py` | Create | Tests for setup endpoints |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_game_setup.py -v --tb=short
```

## Completion Criteria

- [ ] `POST /api/games` accepts and validates `CreateGameRequest` with all fields
- [ ] `GET /api/games/scenarios` returns scenario metadata with cost_rates
- [ ] Invalid `max_days` (0, 101) returns 422
- [ ] Invalid `num_eval_samples` (0, 51) returns 422
- [ ] Unknown `scenario_id` returns 400
- [ ] All tests pass
