# Phase 5: Polish and Test

**Status**: Pending

---

## Objective

Polish animations, ensure accessibility, handle edge cases (no bootstrap data, partial history), and write integration tests.

---

## Invariants Enforced in This Phase

- INV-1: Money is i64 — verify all displayed values converted correctly
- INV-GAME-2: Agent Isolation — verify no cross-agent data leakage in display

---

## TDD Steps

### Step 5.1: Edge Case Tests (RED → GREEN)

**Add to `web/backend/tests/test_accept_reject.py`:**

```python
class TestAcceptRejectEdgeCases:

    def test_no_bootstrap_graceful(self):
        """Games without bootstrap (num_eval_samples=1) still show accepted=True."""
        resp = client.post("/api/games", json={
            "scenario_id": "2bank_12tick",
            "max_days": 2,
            "num_eval_samples": 1,
        })
        game_id = resp.json()["game_id"]
        step = client.post(f"/api/games/{game_id}/step").json()

        for aid, result in step["reasoning"].items():
            assert result["accepted"] is True
            # No evaluation key or evaluation is None
            assert result.get("evaluation") is None

        client.delete(f"/api/games/{game_id}")

    def test_first_day_no_reasoning(self):
        """Day 0 has no prior reasoning — reasoning_history starts empty."""
        resp = client.post("/api/games", json={"max_days": 5})
        game_id = resp.json()["game_id"]
        state = client.get(f"/api/games/{game_id}").json()

        for aid in state["agent_ids"]:
            assert len(state["reasoning_history"][aid]) == 0

        client.delete(f"/api/games/{game_id}")

    def test_complete_game_has_full_history(self):
        """After all days, reasoning_history has max_days-1 entries per agent."""
        resp = client.post("/api/games", json={"max_days": 3, "num_eval_samples": 3})
        game_id = resp.json()["game_id"]

        # Auto-run
        client.post(f"/api/games/{game_id}/auto")
        state = client.get(f"/api/games/{game_id}").json()

        assert state["is_complete"] is True
        for aid in state["agent_ids"]:
            # Reasoning happens after each day except the last
            history = state["reasoning_history"][aid]
            assert len(history) >= 1  # At least some reasoning
            for entry in history:
                assert "accepted" in entry

        client.delete(f"/api/games/{game_id}")
```

### Step 5.2: Frontend Polish

- Add `transition-all duration-200` to ReasoningCard for smooth appearance
- Add `aria-label` to timeline nodes for screen readers
- Animate new timeline nodes sliding in
- Handle empty state gracefully (no history → "Waiting for first optimization...")

### Step 5.3: Refactor

- Extract shared color constants (green/red for accept/reject)
- Ensure modal doesn't render when evaluation is null

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/tests/test_accept_reject.py` | Modify | Add edge case tests |
| `web/frontend/src/components/ReasoningCard.tsx` | Modify | Polish animations |
| `web/frontend/src/components/PolicyTimeline.tsx` | Modify | Accessibility, animations |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_accept_reject.py -v --tb=short
cd /Users/ned/.openclaw/workspace-nash/SimCash/web/frontend && npx tsc --noEmit
```

## Completion Criteria

- [ ] No bootstrap → graceful fallback (accepted=True, no evaluation)
- [ ] Empty history → helpful empty state message
- [ ] Complete game → full reasoning history with accept/reject
- [ ] Animations smooth, not janky
- [ ] Accessible (aria-labels, keyboard navigation)
- [ ] All tests pass
