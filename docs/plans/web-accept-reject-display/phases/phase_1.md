# Phase 1: Backend — Ensure Acceptance Criteria in Game State

**Status**: Pending

---

## Objective

Verify and extend the game state API to include all acceptance criteria fields needed by the frontend. Ensure `get_state()` includes evaluation metadata in `reasoning_history` entries.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — delta_sum, ci bounds are integers
- INV-GAME-3: Bootstrap Identity — criteria labels match experiment runner

---

## TDD Steps

### Step 1.1: Write Failing Tests (RED)

**Create `web/backend/tests/test_accept_reject.py`:**

```python
"""Tests for accept/reject display support in API."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestAcceptRejectInState:
    """Verify acceptance metadata in game state."""

    def test_reasoning_history_has_accepted_field(self):
        """Every reasoning entry has 'accepted' boolean."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 3,
            "num_eval_samples": 3,
        })
        game_id = resp.json()["game_id"]

        # Run 2 steps to get reasoning history
        client.post(f"/api/games/{game_id}/step")
        client.post(f"/api/games/{game_id}/step")

        state = client.get(f"/api/games/{game_id}").json()
        for aid, history in state["reasoning_history"].items():
            for entry in history:
                assert "accepted" in entry
                assert isinstance(entry["accepted"], bool)

        client.delete(f"/api/games/{game_id}")

    def test_rejection_includes_reason(self):
        """Rejected entries include rejection_reason string."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 5,
            "num_eval_samples": 5,
        })
        game_id = resp.json()["game_id"]

        # Run several steps — some may be rejected
        for _ in range(4):
            client.post(f"/api/games/{game_id}/step")

        state = client.get(f"/api/games/{game_id}").json()
        for aid, history in state["reasoning_history"].items():
            for entry in history:
                if not entry["accepted"] and "evaluation" in entry:
                    assert "rejection_reason" in entry["evaluation"]
                    assert len(entry["evaluation"]["rejection_reason"]) > 0

        client.delete(f"/api/games/{game_id}")

    def test_accepted_count_in_summary(self):
        """Game state includes summary of accepted/rejected counts."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 5,
            "num_eval_samples": 3,
        })
        game_id = resp.json()["game_id"]

        for _ in range(4):
            client.post(f"/api/games/{game_id}/step")

        state = client.get(f"/api/games/{game_id}").json()

        # Count accepted/rejected per agent
        for aid, history in state["reasoning_history"].items():
            accepted = sum(1 for e in history if e.get("accepted"))
            rejected = sum(1 for e in history if not e.get("accepted"))
            assert accepted + rejected == len(history)

        client.delete(f"/api/games/{game_id}")
```

### Step 1.2: Implementation (GREEN)

The `accepted` field already exists in mock/real optimize results. Ensure:

1. `_mock_optimize()` always sets `"accepted": True` (mock always accepts)
2. With bootstrap (Plan 3), `accepted` reflects evaluation result
3. `evaluation` dict present in reasoning_history entries when bootstrap enabled

**Update `web/backend/app/game.py` `get_state()`:**

```python
def get_state(self) -> dict[str, Any]:
    return {
        ...existing fields...,
        "num_eval_samples": self.num_eval_samples,
        "reasoning_history": self.reasoning_history,
        # Summary stats
        "acceptance_summary": {
            aid: {
                "total": len(history),
                "accepted": sum(1 for e in history if e.get("accepted", True)),
                "rejected": sum(1 for e in history if not e.get("accepted", True)),
            }
            for aid, history in self.reasoning_history.items()
        },
    }
```

### Step 1.3: Refactor

- Ensure `acceptance_summary` is cheap to compute (small history)
- Add `last_evaluation` convenience field for latest result

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/game.py` | Modify | Add `acceptance_summary` to `get_state()` |
| `web/backend/tests/test_accept_reject.py` | Create | Acceptance metadata tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_accept_reject.py -v --tb=short
```

## Completion Criteria

- [ ] Every reasoning entry has `accepted: bool`
- [ ] Rejected entries have non-empty `rejection_reason` (when bootstrap enabled)
- [ ] `acceptance_summary` in game state with counts
- [ ] Tests pass
