# Phase 3: Backend — Add Evaluation Metadata to Reasoning Results

**Status**: Pending

---

## Objective

Ensure evaluation metadata (delta_sum, cv, ci, accepted, rejection_reason) flows through the API responses and game state so the frontend can display it.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — delta_sum, ci_lower, ci_upper are integer cents
- INV-GAME-3: Bootstrap Identity — metadata matches experiment runner's format

---

## TDD Steps

### Step 3.1: Tests for API Response Shape (RED)

**Add to `web/backend/tests/test_bootstrap_eval.py`:**

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestBootstrapAPIResponse:
    """Test that bootstrap metadata appears in API responses."""

    def test_step_response_includes_evaluation(self):
        """POST /games/{id}/step includes evaluation metadata when bootstrap enabled."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 3,
            "num_eval_samples": 5,
        })
        game_id = resp.json()["game_id"]

        step = client.post(f"/api/games/{game_id}/step")
        data = step.json()
        reasoning = data["reasoning"]

        for aid, result in reasoning.items():
            assert "evaluation" in result
            eval_meta = result["evaluation"]
            assert "delta_sum" in eval_meta
            assert "cv" in eval_meta
            assert "ci_lower" in eval_meta
            assert "ci_upper" in eval_meta
            assert "accepted" in eval_meta
            assert isinstance(eval_meta["delta_sum"], int)
            assert isinstance(eval_meta["ci_lower"], int)

        client.delete(f"/api/games/{game_id}")

    def test_game_state_includes_evaluation_history(self):
        """GET /games/{id} includes evaluation in reasoning_history."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 2,
            "num_eval_samples": 3,
        })
        game_id = resp.json()["game_id"]
        client.post(f"/api/games/{game_id}/step")

        state = client.get(f"/api/games/{game_id}").json()
        for aid, history in state["reasoning_history"].items():
            if history:
                assert "evaluation" in history[-1]

        client.delete(f"/api/games/{game_id}")

    def test_no_evaluation_when_samples_1(self):
        """No evaluation metadata when num_eval_samples=1."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 2,
            "num_eval_samples": 1,
        })
        game_id = resp.json()["game_id"]
        step = client.post(f"/api/games/{game_id}/step").json()

        for aid, result in step["reasoning"].items():
            assert "evaluation" not in result or result.get("evaluation") is None

        client.delete(f"/api/games/{game_id}")
```

### Step 3.2: Ensure Metadata Flows Through (GREEN)

The Phase 2 implementation already adds `result["evaluation"]`. Verify:

1. `Game.get_state()` → `reasoning_history` includes evaluation dicts
2. `POST /api/games/{id}/step` → reasoning dict includes evaluation
3. `POST /api/games/{id}/auto` → all reasoning entries include evaluation

### Step 3.3: Refactor

- Add `EvaluationSummary` Pydantic model for type safety in API
- Ensure evaluation metadata serializes cleanly to JSON (no numpy types, no float('inf'))

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/models.py` | Modify | Add `EvaluationSummary` model (optional) |
| `web/backend/tests/test_bootstrap_eval.py` | Modify | Add API response shape tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_bootstrap_eval.py -v --tb=short
```

## Completion Criteria

- [ ] Step response includes `evaluation` dict when bootstrap enabled
- [ ] Game state `reasoning_history` includes evaluation
- [ ] No evaluation metadata when `num_eval_samples=1`
- [ ] All integer fields (delta_sum, ci) are actually ints in JSON
- [ ] CV is a float, serializes cleanly
