# Phase 2: Backend — Wire Bootstrap into Game.optimize_policies()

**Status**: Pending

---

## Objective

Integrate `WebBootstrapEvaluator` into `Game.optimize_policies()` so proposed policies are evaluated before acceptance. If bootstrap rejects, keep the old policy and record the rejection reason.

---

## Invariants Enforced in This Phase

- INV-GAME-3: Bootstrap Identity — acceptance uses same criteria as experiment runner
- INV-GAME-1: Policy Reality — rejected policies don't change agent's fraction

---

## TDD Steps

### Step 2.1: Write Failing Tests (RED)

**Add to `web/backend/tests/test_bootstrap_eval.py`:**

```python
class TestGameBootstrapIntegration:
    """Test bootstrap evaluation integrated into Game."""

    def test_game_with_bootstrap_rejects_bad_proposals(self):
        """Game with bootstrap should reject proposals that don't improve."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id
        import copy

        scenario = get_scenario_by_id("2bank_12tick")
        game = Game(
            game_id="test",
            raw_yaml=copy.deepcopy(scenario),
            use_llm=False,
            mock_reasoning=True,
            max_days=5,
            num_eval_samples=5,  # Triggers bootstrap evaluation
        )

        # Run first day
        game.run_day()

        # Force a known bad policy change and check rejection
        import asyncio
        reasoning = asyncio.get_event_loop().run_until_complete(game.optimize_policies())

        for aid, result in reasoning.items():
            # Result should have evaluation metadata
            assert "evaluation" in result or "accepted" in result

    def test_rejected_policy_keeps_old_fraction(self):
        """When bootstrap rejects, agent keeps previous fraction."""
        from app.game import Game
        from app.scenario_pack import get_scenario_by_id
        import copy

        scenario = get_scenario_by_id("2bank_12tick")
        game = Game(
            game_id="test",
            raw_yaml=copy.deepcopy(scenario),
            max_days=3,
            num_eval_samples=5,
        )

        game.run_day()
        old_fractions = {
            aid: p["parameters"]["initial_liquidity_fraction"]
            for aid, p in game.policies.items()
        }

        import asyncio
        reasoning = asyncio.get_event_loop().run_until_complete(game.optimize_policies())

        for aid, result in reasoning.items():
            if not result.get("accepted", True):
                # Fraction should be unchanged
                current = game.policies[aid]["parameters"]["initial_liquidity_fraction"]
                assert current == old_fractions[aid]
```

### Step 2.2: Implement Bootstrap Integration (GREEN)

**Update `web/backend/app/game.py`:**

```python
from .bootstrap_eval import WebBootstrapEvaluator

class Game:
    def __init__(self, ..., num_eval_samples: int = 1):
        ...
        self.num_eval_samples = num_eval_samples
        self._evaluator = WebBootstrapEvaluator(
            num_samples=num_eval_samples,
            cv_threshold=0.5,
        ) if num_eval_samples > 1 else None

    async def optimize_policies(self) -> dict[str, dict]:
        if not self.days:
            return {}

        last_day = self.days[-1]
        reasoning = {}

        for aid in self.agent_ids:
            if self.mock_reasoning:
                result = _mock_optimize(aid, self.policies[aid], last_day, self.days)
            else:
                result = await _real_optimize(...)

            # Bootstrap evaluation if enabled
            if self._evaluator and result.get("new_policy"):
                eval_result = self._evaluator.evaluate(
                    raw_yaml=self.raw_yaml,
                    agent_id=aid,
                    old_policy=self.policies[aid],
                    new_policy=result["new_policy"],
                    base_seed=self._base_seed + self.current_day,
                    other_policies={
                        oid: self.policies[oid]
                        for oid in self.agent_ids if oid != aid
                    },
                )

                result["evaluation"] = {
                    "delta_sum": eval_result.delta_sum,
                    "mean_delta": eval_result.mean_delta,
                    "cv": eval_result.cv,
                    "ci_lower": eval_result.ci_lower,
                    "ci_upper": eval_result.ci_upper,
                    "accepted": eval_result.accepted,
                    "rejection_reason": eval_result.rejection_reason,
                    "num_samples": eval_result.num_samples,
                    "old_mean_cost": eval_result.old_mean_cost,
                    "new_mean_cost": eval_result.new_mean_cost,
                }
                result["accepted"] = eval_result.accepted

                if not eval_result.accepted:
                    result["new_policy"] = None  # Don't apply rejected policy
                    result["new_fraction"] = None

            if result.get("new_policy"):
                self.policies[aid] = result["new_policy"]

            reasoning[aid] = result
            self.reasoning_history[aid].append(result)

        return reasoning
```

### Step 2.3: Refactor

- Keep `num_eval_samples=1` (default) path unchanged — no bootstrap overhead
- Ensure `_mock_optimize` still produces varied proposals for testing
- Add evaluation metadata to `get_state()` for frontend consumption

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `web/backend/app/game.py` | Modify | Wire `WebBootstrapEvaluator` into `optimize_policies()` |
| `web/backend/tests/test_bootstrap_eval.py` | Modify | Add integration tests |

## Verification

```bash
$HOME/Library/Python/3.9/bin/uv run --directory api python -m pytest /Users/ned/.openclaw/workspace-nash/SimCash/web/backend/tests/test_bootstrap_eval.py -v --tb=short
```

## Completion Criteria

- [ ] `num_eval_samples > 1` triggers bootstrap evaluation
- [ ] `num_eval_samples = 1` skips bootstrap (backward compatible)
- [ ] Rejected proposals don't change the agent's policy
- [ ] Evaluation metadata included in reasoning result
- [ ] Other agents' policies held fixed during evaluation
