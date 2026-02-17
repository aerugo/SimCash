# Phase 1: Backend — Accept Inline Config

**Status**: Pending

## Objective

Extend `POST /api/games` to accept an `inline_config` dict as an alternative to `scenario_id`. When provided, use it directly as the raw YAML config instead of looking up from the scenario pack.

## Invariants

- INV-1: Money is i64
- INV-3: FFI Minimal

## TDD Steps

### Step 1.1: RED — Write Failing Test

Add to `web/backend/tests/test_game_setup.py`:

```python
class TestCreateGameInlineConfig:
    """Test game creation with inline config."""

    def test_create_game_with_inline_config(self):
        """inline_config creates a game without scenario_id lookup."""
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
            "payment_schedule": [],
        }
        resp = client.post("/api/games", json={
            "inline_config": inline,
            "max_days": 5,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "game_id" in data

    def test_inline_config_takes_precedence_over_scenario_id(self):
        """When both provided, inline_config wins."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "inline_config": {
                "ticks_per_day": 2,
                "num_days": 1,
                "rng_seed": 1,
                "agents": [
                    {"id": "X", "liquidity_pool": 50000},
                    {"id": "Y", "liquidity_pool": 50000},
                ],
                "cost_config": {
                    "liquidity_cost_per_tick_bps": 100,
                    "delay_cost_per_tick_per_cent": 0.1,
                    "deadline_penalty": 10000,
                },
                "payment_schedule": [],
            },
            "max_days": 3,
        })
        assert resp.status_code == 200

    def test_must_provide_scenario_id_or_inline_config(self):
        """If no scenario_id and no inline_config, use default scenario."""
        resp = client.post("/api/games", json={"max_days": 3})
        assert resp.status_code == 200  # falls back to default scenario_id
```

### Step 1.2: GREEN — Implement

Update `web/backend/app/models.py`:

```python
from typing import Any, Optional

class CreateGameRequest(BaseModel):
    scenario_id: str = "2bank_12tick"
    inline_config: Optional[dict[str, Any]] = None
    use_llm: bool = False
    mock_reasoning: bool = True
    max_days: int = Field(default=10, ge=1, le=100)
    num_eval_samples: int = Field(default=1, ge=1, le=50)
```

Update `web/backend/app/main.py` in `create_game`:

```python
@app.post("/api/games")
async def create_game(config: CreateGameRequest = CreateGameRequest()):
    game_id = str(uuid.uuid4())[:8]

    if config.inline_config:
        raw_yaml = config.inline_config
    else:
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

### Step 1.3: REFACTOR

Add basic validation for inline_config (must have `agents` list with at least 2 entries).

## Files Changed

| File | Action |
|------|--------|
| `web/backend/app/models.py` | Modify — add `inline_config` field |
| `web/backend/app/main.py` | Modify — handle inline_config |
| `web/backend/tests/test_game_setup.py` | Modify — add inline config tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest web/backend/tests/test_game_setup.py -v --tb=short
```

## Completion Criteria

- [ ] `inline_config` accepted and used to create game
- [ ] `inline_config` takes precedence over `scenario_id`
- [ ] Missing both still works (default scenario)
- [ ] Tests pass
